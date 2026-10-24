from datetime import datetime, timedelta, timezone

from . import config
from .normalize import _dt


def classify(items, days=config.LOOKBACK_DAYS, upcoming_days=config.UPCOMING_DAYS):
    """Plain rules, no LLM: sort items into report sections."""
    now = datetime.now(timezone.utc)
    since = now - timedelta(days=days)
    horizon = now + timedelta(days=upcoming_days)
    s = {"completed": [], "in_progress": [], "blocked": [], "overdue": [], "upcoming": []}
    for it in items:
        due = _dt(it["due"])
        if it["status"] == "done":
            done_at = _dt(it["completed_at"])
            if done_at and done_at >= since:
                s["completed"].append(it)
            continue
        if it["status"] == "blocked":
            s["blocked"].append(it)
        elif it["status"] == "in_progress":
            s["in_progress"].append(it)
        if due and due < now:
            s["overdue"].append(it)
        elif due and due <= horizon:
            s["upcoming"].append(it)
    return s
