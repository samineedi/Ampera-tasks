"""Headless runner for scheduled jobs (run from the project root).

  python backend/run_scheduled.py weekly     # build weekly report draft
  python backend/run_scheduled.py reminders  # build reminders + escalations
  python backend/run_scheduled.py closure    # closure completion check + report

Safe by default: output is only SAVED to ./reports. Add --send to actually email the report
or post to Slack. Trello credentials in .env are required.
"""
import argparse
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()
log = logging.getLogger("scheduled")
REQUIRED = ("TRELLO_API_KEY", "TRELLO_TOKEN", "TRELLO_BOARD_ID")


def _save(prefix, text):
    path = Path("reports") / f"{prefix}_{datetime.now():%Y%m%d_%H%M}.md"
    path.parent.mkdir(exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def run_job(job, send=False):
    if not all(os.getenv(k) for k in REQUIRED):
        raise RuntimeError(f"Missing Trello settings ({', '.join(REQUIRED)}).")
    days = int(os.getenv("LOOKBACK_DAYS", "7"))
    state = {"days": days, "project_name": os.getenv("PROJECT_NAME", "Project")}

    if job == "weekly":
        from agent.graph import build_graph
        from agent.sender import send_report
        res = build_graph().invoke({**state, "mode": "weekly"})
        path = _save("weekly_draft", res["draft"])
        log.info("Weekly draft saved to %s (health=%s)", path, res["kpis"]["health"])
        if send:
            log.info(send_report(res["draft"], subject="Weekly Status Report"))

    elif job == "reminders":
        # No LLM or graph needed: just fetch, normalize and build messages.
        from agent.normalize import normalize
        from agent.notifier import build_notifications, send_notifications
        from agent.trello_client import fetch_board
        items = normalize(fetch_board(days=days), days)
        msgs = build_notifications(items)
        log.info("%d notification(s) built", len(msgs))
        if msgs:
            log.info(send_notifications(msgs, dry_run=not send))

    elif job == "closure":
        from agent.graph import build_graph
        from agent.sender import send_report
        res = build_graph().invoke({**state, "mode": "closure"})
        path = _save("closure_draft", res["closure_draft"])
        log.info("Closure draft saved to %s (ready_to_close=%s)", path, res["closure"]["ready_to_close"])
        if send and res["closure"]["ready_to_close"]:   # never auto-send a "ready" report for an unfinished project
            log.info(send_report(res["closure_draft"], subject="Project Closure Report"))
    else:
        raise ValueError(f"Unknown job: {job}")


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    p = argparse.ArgumentParser()
    p.add_argument("job", choices=["weekly", "reminders", "closure"])
    p.add_argument("--send", action="store_true", help="really send email/Slack (default: save only)")
    a = p.parse_args()
    try:
        run_job(a.job, a.send)
    except Exception as e:
        log.error("Job '%s' failed: %s", a.job, e)
        sys.exit(1)


if __name__ == "__main__":
    main()
