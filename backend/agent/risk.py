"""Risk radar: stuck, blocked, overdue and regressed items, merged into one row per card."""
from datetime import datetime, timezone

from . import config
from .normalize import _dt


def build_risk_radar(items, now=None):
    now = now or datetime.now(timezone.utc)
    rows = []
    for it in items:
        if it["status"] == "done":
            continue
        reasons, high = [], False
        due, last = _dt(it["due"]), _dt(it["last_activity"])
        idle = (now - last).days if last else 0

        if due and due < now:
            late = (now - due).days
            reasons.append(f"Overdue {late}d" if late else "Overdue")
            high = high or late >= config.ESCALATE_OVERDUE_DAYS
        if it["status"] == "blocked":
            note = it["blocker_note"]
            why = (note if note.lower().startswith("blocked") else f"Blocked: {note}") if note else "Blocked (no reason noted)"
            if idle >= config.STALE_DAYS:
                why += f" (no activity {idle}d)"
                high = True
            reasons.append(why)
        elif it["stage"] != "Backlog" and idle >= config.STALE_DAYS:
            reasons.append(f"No activity for {idle}d")
        if it.get("regressed"):
            reasons.append(it["regressed_note"])
            high = high or (it["regressed_from"] or "").lower() in config.DONE_LISTS

        if reasons:
            rows.append({"title": it["title"], "url": it["url"], "assignees": it["assignees"],
                         "stage": it["stage"], "reasons": reasons,
                         "severity": "High" if (high or len(reasons) >= 3) else "Medium"})
    rows.sort(key=lambda r: (r["severity"] != "High", r["title"]))
    return rows
