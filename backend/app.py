"""PMO Automation backend (Flask JSON API) serving the React frontend.

    python backend/app.py  ->  http://localhost:5000   (run from the project root; needs `npm run build` in frontend/ once)
    cd frontend && npm run dev  ->  http://localhost:5173 with /api proxied to Flask

Pages (React routes): /dashboard   /weekly-report   /planning   /closure
Health: /ping   /api/trello-health
Pattern per module: GET /api/<module> (JSON), POST /api/refresh/<module>.
Trello is the only data source. The board is fetched once into a JSON cache (refreshed every 30 min in the background) and every page
reads it from there, so opening a page never calls Trello.
"""
import logging
import os
import re
from datetime import datetime

import requests
from dotenv import load_dotenv

load_dotenv()
from flask import Flask, jsonify, request, send_from_directory

from agent import cache, config
from agent.chat_agent import ChatUnavailable, ask
from agent.closure import archive_board, assess
from agent.dashboard import dashboard_view, filter_project, project_names
from agent.drafter import _get_llm
from agent.notifier import build_notifications, send_notifications
from agent.planner import create_trello_cards, parse_team
from agent.sender import send_report
from agent.trello_client import BASE

log = logging.getLogger("pmo")
REQUIRED = ("TRELLO_API_KEY", "TRELLO_TOKEN", "TRELLO_BOARD_ID")
MODULES = {"dashboard", "digest", "planning", "closure"}
DIST = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend", "dist")

# Fail fast: never start half-configured.
_missing = [k for k in REQUIRED if not os.getenv(k)]
if _missing:
    raise SystemExit(f"Missing required settings in .env: {', '.join(_missing)}")

app = Flask(__name__, static_folder=None)
app.config["MAX_CONTENT_LENGTH"] = 2 * 1024 * 1024
_graph = None


def graph():
    global _graph
    if _graph is None:
        from agent.graph import build_graph
        _graph = build_graph()
    return _graph


def board(refresh=False):
    return cache.get_board(refresh=refresh)


def _fmt(iso):
    try:
        return datetime.fromisoformat(iso).strftime("%d %b %H:%M UTC")
    except (TypeError, ValueError):
        return "never"


def _body():
    return request.get_json(silent=True) or {}


@app.get("/api/meta")
def api_meta():
    b = cache.load("board")
    return jsonify(fetched_at=_fmt(b["fetched_at"]) if b else "not loaded")


@app.after_request
def security_headers(resp):
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["X-Frame-Options"] = "DENY"
    resp.headers["X-XSS-Protection"] = "1; mode=block"
    resp.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return resp


@app.errorhandler(Exception)
def on_error(e):
    code = getattr(e, "code", 500) if hasattr(e, "code") and isinstance(getattr(e, "code"), int) else 500
    if code >= 500:
        log.exception("Unhandled error")
    if request.path.startswith("/api/"):
        return jsonify(error=str(e)), code
    if code == 404 and request.method == "GET":                  # client-side routes fall through to the SPA
        return serve_spa(request.path.lstrip("/"))
    return jsonify(error=str(e)), code


# ---------------------------------------------------------------- React app
@app.get("/", defaults={"path": ""})
@app.get("/<path:path>")
def serve_spa(path):
    if path and os.path.isfile(os.path.join(DIST, path)):
        return send_from_directory(DIST, path)
    if path.startswith(("api/", "assets/")):
        return jsonify(error="Not found"), 404
    if not os.path.isfile(os.path.join(DIST, "index.html")):
        return ("Frontend not built. Run: cd frontend && npm install && npm run build", 503)
    return send_from_directory(DIST, "index.html")


# ---------------------------------------------------------------- JSON APIs
def _draft_key(project):
    return "digest_draft_" + (re.sub(r"[^a-z0-9]+", "_", project.lower()).strip("_") if project else "all")


@app.get("/api/projects")
def api_projects():
    return jsonify(projects=project_names(board()["items"]))


@app.get("/api/digest")
def api_digest():
    project = request.args.get("project")
    items = filter_project(board()["items"], project)
    res = graph().invoke({"mode": "weekly", "items": items, "days": config.LOOKBACK_DAYS, "use_llm": False})
    saved = cache.load(_draft_key(project))
    return jsonify(kpis=res["kpis"], risk=res["risk"], sections=res["sections"], notifications=res["notifications"],
                   days=config.LOOKBACK_DAYS, draft=saved["draft"] if saved else res["draft"],
                   draft_time=_fmt(saved["generated_at"]) if saved else None, llm_available=_get_llm() is not None)


@app.get("/api/dashboard")
def api_dashboard():
    return jsonify(dashboard_view(board()["items"], request.args.get("project")))


def _valid_history(h):
    return isinstance(h, list) and all(isinstance(m, dict) and m.get("role") in ("user", "assistant")
                                       and isinstance(m.get("content"), str) for m in h)


@app.post("/api/chat")
def api_chat():
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        return jsonify(error="Expected a JSON body"), 400
    message, history, project = body.get("message"), body.get("history", []), body.get("project", "")
    if not isinstance(message, str) or not message.strip() or len(message) > 1000:
        return jsonify(error="message must be 1-1000 characters"), 400
    if not _valid_history(history):
        return jsonify(error="history must be a list of {role: user|assistant, content: string}"), 400
    if not isinstance(project, str):
        return jsonify(error="project must be a string"), 400
    try:
        return jsonify(ask(board()["items"], message.strip(), history, project))
    except ChatUnavailable as e:
        return jsonify(error=str(e)), 503
    except Exception:
        log.exception("Chat failed")
        return jsonify(error="The assistant had a problem answering. Please try again."), 502


@app.post("/api/refresh/<module>")
def api_refresh(module):
    if module not in MODULES:
        return jsonify(error="Unknown module"), 404
    try:
        b = board(refresh=True)
    except Exception as e:
        log.exception("Refresh failed")
        return jsonify(error=f"Could not refresh from Trello: {e}"), 502
    return jsonify(status="ok", fetched_at=_fmt(b["fetched_at"]), items=len(b["items"]))


@app.post("/api/digest/draft")
def api_digest_draft():
    project = _body().get("project")
    items = filter_project(board()["items"], project)
    res = graph().invoke({"mode": "weekly", "items": items, "days": config.LOOKBACK_DAYS, "use_llm": True})
    cache.save(_draft_key(project), {"draft": res["draft"], "generated_at": datetime.utcnow().isoformat() + "+00:00"})
    return jsonify(draft=res["draft"], llm_used=_get_llm() is not None)


@app.post("/api/digest/send")
def api_digest_send():
    text = _body().get("text", "").strip()
    if not text:
        return jsonify(error="Draft is empty"), 400
    return jsonify(message=send_report(text, subject="Weekly Status Report"))


@app.post("/api/notifications/send")
def api_notifications_send():
    d = _body()
    dry = bool(d.get("dry_run", True))
    msgs = build_notifications(filter_project(board()["items"], d.get("project")))
    if not msgs:
        return jsonify(message="Nothing to send.")
    return jsonify(message=send_notifications(msgs, dry_run=dry))


@app.post("/api/plan")
def api_plan():
    d = _body()
    if not d.get("brief", "").strip():
        return jsonify(error="Please enter a project brief"), 400
    team = parse_team(d.get("team_text", ""))
    if not team:
        return jsonify(error="Please enter at least one team member"), 400
    res = graph().invoke({"mode": "plan", "brief": d["brief"], "team": team})
    return jsonify(plan=res["plan"], llm_used=_get_llm() is not None)


@app.post("/api/plan/create")
def api_plan_create():
    d = _body()
    plan = d.get("plan") or []
    if not plan:
        return jsonify(error="The plan is empty"), 400
    dry = bool(d.get("dry_run", True))
    msg = create_trello_cards(plan, None, dry_run=dry, project=(d.get("project") or "").strip() or None)
    if not dry:
        try:
            board(refresh=True)
        except Exception:
            log.exception("Refresh after card creation failed")
    return jsonify(message=msg)


@app.post("/api/closure/run")
def api_closure_run():
    d = _body()
    project = d.get("project")
    res = graph().invoke({"mode": "closure", "items": filter_project(board()["items"], project),
                          "project_name": d.get("project_name") or project or "Project"})
    a = res["closure"]
    return jsonify(kpis=a["kpis"], ready=a["ready_to_close"], draft=res["closure_draft"],
                   outstanding=[i["title"] for i in a["sections"]["outstanding"]])


@app.post("/api/closure/send")
def api_closure_send():
    d = _body()
    text = d.get("text", "").strip()
    if not text:
        return jsonify(error="Report is empty"), 400
    return jsonify(message=send_report(text, subject=f"Closure Report - {d.get('project_name') or 'Project'}"))


@app.post("/api/closure/archive")
def api_closure_archive():
    d = _body()
    if not assess(board()["items"])["ready_to_close"]:       # checked on the server, not just in the UI
        return jsonify(error="Open items remain - the board cannot be archived yet."), 400
    if d.get("dry_run", True):
        return jsonify(message="Dry run - nothing was archived.")
    return jsonify(message=archive_board(None, confirm=bool(d.get("confirm"))))


# ---------------------------------------------------------------- health
@app.get("/ping")
def ping():
    return jsonify(status="ok")


@app.get("/api/trello-health")
def trello_health():
    try:
        r = requests.get(f"{BASE}/members/me", params={"key": os.getenv("TRELLO_API_KEY"),
                         "token": os.getenv("TRELLO_TOKEN"), "fields": "username"}, timeout=15)
        return jsonify(status="ok" if r.ok else "error", http=r.status_code, ), (200 if r.ok else 502)
    except requests.RequestException as e:
        return jsonify(status="error", detail=str(e)), 502


def start_background_refresh():
    """Refresh the board cache every CACHE_REFRESH_MINUTES (set DISABLE_BG_REFRESH=true to turn off)."""
    if os.getenv("DISABLE_BG_REFRESH", "false").lower() == "true":
        return
    from apscheduler.schedulers.background import BackgroundScheduler

    def job():
        try:
            cache.refresh_board()
            log.info("Cache refreshed: board")
        except Exception:
            log.exception("Background refresh failed")

    sched = BackgroundScheduler(daemon=True)
    sched.add_job(job, "interval", minutes=config.CACHE_REFRESH_MINUTES, id="board-refresh",
                  max_instances=1, coalesce=True)
    sched.start()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    start_background_refresh()
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")), debug=False)
