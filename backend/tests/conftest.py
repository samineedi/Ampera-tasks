import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

for k in ("TRELLO_API_KEY", "TRELLO_TOKEN", "TRELLO_BOARD_ID"):
    os.environ.setdefault(k, "test")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest


def card(title, project="Project A", status="todo", due=None, assignees=None, labels=None, **kw):
    base = {"id": title, "title": title, "list": "Backlog", "status": status, "stage": "Backlog",
            "assignees": assignees if assignees is not None else [], "due": due, "labels": labels or [],
            "url": "https://trello.com/c/" + title.replace(" ", ""), "last_activity": datetime.now(timezone.utc).isoformat(),
            "completed_at": None, "blocker_note": "", "project": project, "release": None, "team": None,
            "phase": None, "sprint": None, "type": None, "severity": None, "regressed": False,
            "regressed_note": "", "regressed_from": None}
    base.update(kw)
    return base


@pytest.fixture
def make_card():
    return card


@pytest.fixture
def items():
    past = (datetime.now(timezone.utc) - timedelta(days=5)).isoformat()
    now = datetime.now(timezone.utc).isoformat()
    return [
        card("Done one", status="done", completed_at=now, due=past),
        card("Working", status="in_progress", assignees=["Asha"]),
        card("Stuck", status="blocked", assignees=["Ben"], blocker_note="waiting on vendor"),
        card("Late", status="in_progress", due=past, assignees=["Asha"]),
        card("Other project", project="Project B"),
    ]
