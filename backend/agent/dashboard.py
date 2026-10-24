"""Dashboard data for a software project: overall completion, pipeline stages, planned vs actual dates."""
from datetime import datetime, timezone

from . import config
from .normalize import _dt


def _pct(part, whole):
    return round(100 * part / whole) if whole else 0


def project_names(items):
    return sorted({i["project"] for i in items})


def filter_project(items, project=None):
    return [i for i in items if i["project"] == project] if project and project != "all" else items


def _project_row(name, rows):
    done = sum(1 for i in rows if i["status"] == "done")
    return {"name": name, "total": len(rows), "done": done, "completion_pct": _pct(done, len(rows)),
            "in_progress": sum(1 for i in rows if i["status"] == "in_progress"),
            "blocked": sum(1 for i in rows if i["status"] == "blocked")}


def dashboard_view(all_items, project=None):
    projects = [_project_row(n, [i for i in all_items if i["project"] == n]) for n in project_names(all_items)]
    items = filter_project(all_items, project)
    now = datetime.now(timezone.utc)
    done = [i for i in items if i["status"] == "done"]
    totals = {"total": len(items), "done": len(done),
              "in_progress": sum(1 for i in items if i["status"] == "in_progress"),
              "blocked": sum(1 for i in items if i["status"] == "blocked"),
              "overdue": sum(1 for i in items if i["status"] != "done" and _dt(i["due"]) and _dt(i["due"]) < now),
              "completion_pct": _pct(len(done), len(items)),
              "stages": {s: sum(1 for i in items if i["stage"] == s) for s in config.STAGES}}

    schedule, measured, late = [], 0, 0
    for it in items:
        due = _dt(it["due"])
        completed = _dt(it["completed_at"]) if it["status"] == "done" else None
        if it["status"] == "done":
            if due and completed:
                v = (completed.date() - due.date()).days
                measured += 1
                late += v > 0
                status, tone = ("On time", "ok") if v <= 0 else (f"Late +{v}d", "bad")
            else:
                status, tone = "Done (no due date)", "muted"
        elif due:
            if due < now:
                n = (now - due).days
                status, tone = (f"Overdue {n}d" if n else "Overdue"), "bad"
            else:
                n = (due.date() - now.date()).days
                status, tone = ("Due today" if n == 0 else f"Due in {n}d"), ("warn" if n <= config.DUE_SOON_DAYS else "ok")
        else:
            status, tone = "No date", "muted"
        schedule.append({"title": it["title"], "url": it["url"], "stage": it["stage"], "assignees": it["assignees"],
                         "planned": it["due"][:10] if it["due"] else None,
                         "actual": it["completed_at"][:10] if completed else None,
                         "status": status, "tone": tone})
    schedule.sort(key=lambda r: (r["planned"] is None, r["planned"] or ""))
    return {"totals": totals, "schedule": schedule, "projects": projects, "project": project or "",
            "on_time_pct": _pct(measured - late, measured) if measured else None}
