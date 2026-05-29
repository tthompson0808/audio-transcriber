"""Microsoft Graph poller — fetches new Teams meeting transcripts.

Uses delegated auth via MSAL. Refresh token persisted in Windows Credential
Manager under 'audio_transcriber:graph_refresh_token'. Run by a Windows
scheduled task every 5 min.

Flow:
  1. Resolve access token (refresh if needed)
  2. List recent online meetings: GET /me/onlineMeetings (filtered by date)
  3. For each meeting, list transcripts: GET /me/onlineMeetings/{id}/transcripts
  4. For each new transcript, fetch the VTT content
  5. Apply exclusion rules; if allowed, ingest via vtt parser path
  6. Persist a "last seen transcript ID per meeting" cursor

This module is intentionally thin — wraps msal + httpx and delegates the
actual VTT parse + synthesis to the existing vtt_ingest pipeline.
"""
import json
import os
from datetime import datetime, timedelta, timezone

try:
    import msal
    import httpx
except ImportError:
    msal = None
    httpx = None

from audio_transcriber.auth import credentials
from audio_transcriber.capture.exclusion import should_record
from audio_transcriber.config import get_local_dir

GRAPH_BASE = "https://graph.microsoft.com/v1.0"
CURSOR_FILE = "graph_cursor.json"


def _cursor_path(cfg: dict) -> str:
    return os.path.join(get_local_dir(cfg), CURSOR_FILE)


def _load_cursor(cfg: dict) -> dict:
    path = _cursor_path(cfg)
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return {"seen_transcript_ids": []}


def _save_cursor(cursor: dict, cfg: dict) -> None:
    path = _cursor_path(cfg)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(cursor, f)


def _get_token(cfg: dict) -> str:
    if msal is None:
        raise RuntimeError("msal not installed. pip install msal httpx")
    client_id = credentials.get_secret("graph_client_id") or os.environ.get("GRAPH_CLIENT_ID")
    tenant_id = credentials.get_secret("graph_tenant_id") or os.environ.get("GRAPH_TENANT_ID")
    refresh_token = credentials.get_secret("graph_refresh_token")
    if not (client_id and tenant_id and refresh_token):
        raise RuntimeError("Graph credentials missing. Run first-run OAuth flow.")

    app = msal.PublicClientApplication(
        client_id, authority=f"https://login.microsoftonline.com/{tenant_id}"
    )
    scopes = cfg.get("graph", {}).get("scopes", [])
    result = app.acquire_token_by_refresh_token(refresh_token, scopes=scopes)
    if "access_token" not in result:
        raise RuntimeError(f"Token refresh failed: {result.get('error_description')}")
    if result.get("refresh_token"):
        credentials.set_secret("graph_refresh_token", result["refresh_token"])
    return result["access_token"]


def _list_recent_meetings(token: str, since: datetime) -> list[dict]:
    iso = since.isoformat().replace("+00:00", "Z")
    # Note: /me/onlineMeetings doesn't support a date filter directly — list and
    # filter client-side by startDateTime. For backfill we paginate.
    url = f"{GRAPH_BASE}/me/onlineMeetings"
    with httpx.Client(timeout=30) as client:
        resp = client.get(url, headers={"Authorization": f"Bearer {token}"})
        resp.raise_for_status()
        meetings = resp.json().get("value", [])
    return [m for m in meetings if m.get("startDateTime", "") >= iso]


def _list_transcripts(token: str, meeting_id: str) -> list[dict]:
    url = f"{GRAPH_BASE}/me/onlineMeetings/{meeting_id}/transcripts"
    with httpx.Client(timeout=30) as client:
        resp = client.get(url, headers={"Authorization": f"Bearer {token}"})
        if resp.status_code == 404:
            return []
        resp.raise_for_status()
        return resp.json().get("value", [])


def _fetch_vtt_content(token: str, meeting_id: str, transcript_id: str) -> str:
    url = f"{GRAPH_BASE}/me/onlineMeetings/{meeting_id}/transcripts/{transcript_id}/content?$format=text/vtt"
    with httpx.Client(timeout=60) as client:
        resp = client.get(url, headers={"Authorization": f"Bearer {token}"})
        resp.raise_for_status()
        return resp.text


def poll_once(cfg: dict, lookback_days: int = 7) -> int:
    """One Graph poll. Returns count of new meetings ingested."""
    from audio_transcriber.ingest.vtt_ingest import ingest_vtt

    token = _get_token(cfg)
    cursor = _load_cursor(cfg)
    seen = set(cursor.get("seen_transcript_ids", []))

    since = datetime.now(timezone.utc) - timedelta(days=lookback_days)
    meetings = _list_recent_meetings(token, since)

    ingested = 0
    for meeting in meetings:
        meeting_id = meeting.get("id")
        title = meeting.get("subject") or ""
        attendees = [
            (a.get("emailAddress") or {}).get("address", "")
            for a in (meeting.get("participants", {}).get("attendees") or [])
        ]

        allowed, msg = should_record(title, attendees, cfg)
        if not allowed:
            print(f"Teams meeting '{title}': {msg}")
            continue

        try:
            transcripts = _list_transcripts(token, meeting_id)
        except httpx.HTTPError as e:
            print(f"Failed to list transcripts for {title}: {e}")
            continue

        for t in transcripts:
            tid = t.get("id")
            if not tid or tid in seen:
                continue
            try:
                vtt_text = _fetch_vtt_content(token, meeting_id, tid)
            except httpx.HTTPError as e:
                print(f"Failed to fetch VTT for {title}/{tid}: {e}")
                continue

            tmp_path = os.path.join(get_local_dir(cfg), f"graph_{tid}.vtt")
            with open(tmp_path, "w", encoding="utf-8") as f:
                f.write(vtt_text)
            try:
                ingest_vtt(tmp_path, cfg)
                ingested += 1
                seen.add(tid)
            except Exception as e:
                print(f"Ingest failed for {title}: {e}")
            finally:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)

    cursor["seen_transcript_ids"] = sorted(seen)
    _save_cursor(cursor, cfg)
    return ingested
