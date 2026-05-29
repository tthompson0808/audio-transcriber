"""MCP server for Claude Desktop.

Exposes the pending-synthesis queue and digest read tools as MCP tools, so the
CEO's Claude Desktop app (or his Claude Code) can drive synthesis using his
Pro/Max subscription quota instead of per-token API.

Configured in Claude Desktop via %APPDATA%\\Claude\\claude_desktop_config.json:

    {
      "mcpServers": {
        "audio_transcriber": {
          "command": "C:\\\\Users\\\\<user>\\\\AppData\\\\Local\\\\Audio_Transcriber\\\\venv\\\\Scripts\\\\python.exe",
          "args": ["-m", "audio_transcriber.mcp_server"]
        }
      }
    }

Typical Claude Desktop prompt:
    "Use the audio_transcriber tools to synthesize all pending meetings."
"""
from __future__ import annotations

import json
import os
import sys

try:
    from mcp.server.fastmcp import FastMCP
except ImportError:
    print(
        "mcp package not installed. pip install 'mcp[cli]>=1.0' to use the MCP server.",
        file=sys.stderr,
    )
    sys.exit(1)

from audio_transcriber.config import load_config
from audio_transcriber.digest import queries
from audio_transcriber.ingest.vtt_parser import utterances_to_plain_text
from audio_transcriber.storage.manager import search_transcripts
from audio_transcriber.synthesize.pending import apply_synthesis, list_pending, load_meeting


mcp = FastMCP("audio_transcriber")


# ---------- Synthesis queue ----------

@mcp.tool()
def list_pending_meetings() -> list[dict]:
    """List meetings that have been captured but not yet synthesized.

    Returns one entry per pending meeting with: id, date, title (current placeholder),
    source, participants, has_speakers. Synthesize them by calling get_meeting_for_synthesis
    then save_synthesis.
    """
    cfg = load_config()
    return list_pending(cfg)


@mcp.tool()
def get_meeting_for_synthesis(meeting_id: str) -> dict:
    """Fetch a single pending meeting's transcript + metadata for synthesis.

    Returns: {id, date, source, participants, has_speakers, transcript_plain,
              utterances, duration_seconds}. Pass the result to save_synthesis
              after you've produced the title/summary/action items/decisions/topics.
    """
    cfg = load_config()
    meeting = load_meeting(cfg, meeting_id)
    if not meeting:
        raise ValueError(f"Meeting {meeting_id} not found")
    return {
        "id": meeting["id"],
        "date": meeting["date"],
        "source": meeting.get("source"),
        "participants": meeting.get("participants", []),
        "has_speakers": meeting.get("has_speakers", True),
        "duration_seconds": meeting.get("duration_seconds", 0),
        "utterances": meeting.get("utterances", []),
        "transcript_plain": utterances_to_plain_text(meeting.get("utterances", [])),
        "existing_title": meeting.get("title", ""),
    }


@mcp.tool()
def save_synthesis(
    meeting_id: str,
    title: str,
    summary: str,
    action_items: list[dict],
    decisions: list[dict],
    topics: list[str],
) -> dict:
    """Persist a synthesis result.

    action_items shape: [{"owner": "Name or (unattributed)", "task": "...", "due": "YYYY-MM-DD or null"}]
    decisions shape:    [{"decision": "...", "context": "..."}]
    topics shape:       ["lowercase-hyphenated", ...] — 2-5 items typical

    Marks the meeting `synthesized: true`, writes rows into tasks/decisions/topics
    tables, updates the people table. Idempotent — re-calling for the same
    meeting_id replaces the prior rows.

    Returns {meeting_id, synthesized_by, tasks, decisions, topics} counts.
    """
    cfg = load_config()
    return apply_synthesis(
        cfg,
        meeting_id=meeting_id,
        title=title,
        summary=summary,
        action_items=action_items,
        decisions=decisions,
        topics=topics,
        synthesized_by="claude_desktop",
    )


# ---------- Read-only queries (so Claude can answer ad-hoc questions) ----------

@mcp.tool()
def query_open_tasks(owner: str | None = None, overdue_only: bool = False) -> list[dict]:
    """List open action items. Optionally filter by owner substring, or to overdue only."""
    cfg = load_config()
    if overdue_only:
        return queries.get_overdue_tasks(cfg)
    return queries.get_open_tasks(cfg, owner=owner)


@mcp.tool()
def query_decisions(since: str | None = None, keyword: str | None = None) -> list[dict]:
    """List decisions. `since` is YYYY-MM-DD. `keyword` matches in decision or context."""
    cfg = load_config()
    return queries.get_decisions(cfg, since=since, keyword=keyword)


@mcp.tool()
def query_person(name: str) -> dict | None:
    """Get a person's context — meeting count, last meeting, topics, open tasks, recent decisions."""
    cfg = load_config()
    return queries.get_person_context(cfg, name)


@mcp.tool()
def query_topics() -> list[str]:
    """List every distinct topic tag across all digested meetings."""
    cfg = load_config()
    return queries.get_topics(cfg)


@mcp.tool()
def search_meetings(query: str) -> list[dict]:
    """Full-text search across all meeting transcripts + summaries + titles."""
    cfg = load_config()
    return search_transcripts(query, cfg)


@mcp.tool()
def digest_status() -> dict:
    """Health snapshot: total meetings, digested, pending, open tasks, decisions, people, topics."""
    cfg = load_config()
    return queries.get_digest_status(cfg)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
