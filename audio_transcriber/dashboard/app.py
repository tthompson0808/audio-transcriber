"""FastAPI dashboard, served on 127.0.0.1 only (no network exposure)."""
import json
import os
from pathlib import Path

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from jinja2 import Environment, FileSystemLoader, select_autoescape

from audio_transcriber.auth import credentials
from audio_transcriber.config import DEFAULT_CONFIG_PATH, get_data_dir, load_config, save_config
from audio_transcriber.digest import queries
from audio_transcriber.storage.index import load_index
from audio_transcriber.storage.manager import search_transcripts


BASE = Path(__file__).parent

# Use jinja2 Environment directly to avoid starlette templating cache key issues
# on newer Python versions.
_env = Environment(
    loader=FileSystemLoader(str(BASE / "templates")),
    autoescape=select_autoescape(["html"]),
)


def _render(name: str, **ctx) -> HTMLResponse:
    template = _env.get_template(name)
    return HTMLResponse(template.render(**ctx))


app = FastAPI(title="Audio_Transcriber Dashboard")
app.mount("/static", StaticFiles(directory=str(BASE / "static")), name="static")


def _cfg():
    return load_config()


@app.get("/", response_class=HTMLResponse)
def index():
    cfg = _cfg()
    idx = load_index(cfg)
    meetings = list(reversed(idx["meetings"][-20:]))
    return _render("index.html", meetings=meetings)


@app.get("/meeting/{meeting_id}", response_class=HTMLResponse)
def meeting_detail(meeting_id: str):
    cfg = _cfg()
    idx = load_index(cfg)
    entry = next((m for m in idx["meetings"] if m["id"] == meeting_id), None)
    if not entry:
        return HTMLResponse(f"<p>Meeting {meeting_id} not found.</p>", status_code=404)
    path = os.path.join(get_data_dir(cfg), "meetings", entry["path"])
    with open(path) as f:
        meeting = json.load(f)
    tasks = [t for t in queries.get_open_tasks(cfg) if t["meeting_id"] == meeting_id]
    decisions = queries.get_decisions(cfg, meeting_id=meeting_id)
    topics = queries.get_topics(cfg, meeting_id=meeting_id)
    return _render("meeting.html", meeting=meeting, tasks=tasks, decisions=decisions, topics=topics)


@app.get("/tasks", response_class=HTMLResponse)
def tasks_page(owner: str | None = None):
    cfg = _cfg()
    tasks = queries.get_open_tasks(cfg, owner=owner)
    overdue = queries.get_overdue_tasks(cfg)
    return _render("tasks.html", tasks=tasks, overdue=overdue, owner=owner or "")


@app.post("/tasks/{task_id}/complete")
def complete_task(task_id: int):
    queries.complete_task(_cfg(), task_id)
    return RedirectResponse(url="/tasks", status_code=303)


@app.post("/tasks/{task_id}/cancel")
def cancel_task(task_id: int):
    queries.cancel_task(_cfg(), task_id)
    return RedirectResponse(url="/tasks", status_code=303)


@app.get("/decisions", response_class=HTMLResponse)
def decisions_page(since: str | None = None, keyword: str | None = None):
    cfg = _cfg()
    rows = queries.get_decisions(cfg, since=since, keyword=keyword)
    return _render("decisions.html", decisions=rows, since=since or "", keyword=keyword or "")


@app.get("/search", response_class=HTMLResponse)
def search_page(q: str | None = None):
    results = search_transcripts(q, _cfg()) if q else []
    return _render("search.html", results=results, q=q or "")


@app.get("/settings", response_class=HTMLResponse)
def settings_page(saved: str | None = None):
    cfg = _cfg()
    return _render(
        "settings.html",
        cfg=cfg,
        has_anthropic=bool(credentials.get_secret("anthropic_api_key")),
        has_openai=bool(credentials.get_secret("openai_api_key")),
        has_graph=bool(credentials.get_secret("graph_refresh_token")),
        saved=saved,
    )


@app.post("/settings/keys")
def save_keys(
    anthropic_key: str = Form(""),
    openai_key: str = Form(""),
):
    if anthropic_key.strip():
        credentials.set_secret("anthropic_api_key", anthropic_key.strip())
    if openai_key.strip():
        credentials.set_secret("openai_api_key", openai_key.strip())
    return RedirectResponse(url="/settings?saved=keys", status_code=303)


@app.post("/settings/exclusion")
def save_exclusion(
    title_patterns: str = Form(""),
    attendee_blocklist: str = Form(""),
    auto_record: str = Form("off"),
):
    cfg = _cfg()
    cfg.setdefault("exclusion", {})
    cfg["exclusion"]["title_patterns"] = [
        p.strip() for p in title_patterns.splitlines() if p.strip()
    ]
    cfg["exclusion"]["attendee_email_blocklist"] = [
        p.strip() for p in attendee_blocklist.splitlines() if p.strip()
    ]
    cfg.setdefault("auto_record", {})
    cfg["auto_record"]["enabled"] = auto_record == "on"
    save_config(cfg, DEFAULT_CONFIG_PATH)
    return RedirectResponse(url="/settings?saved=exclusion", status_code=303)


def run():
    """Entry point used by tray icon / scheduled task."""
    import uvicorn
    cfg = _cfg()
    dash = cfg.get("dashboard", {})
    uvicorn.run(app, host=dash.get("host", "127.0.0.1"), port=dash.get("port", 8765), log_level="warning")


if __name__ == "__main__":
    run()
