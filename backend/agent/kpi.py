from .normalize import _dt


def compute_kpis(items, sections):
    done = sections["completed"]
    with_due = [i for i in done if i["due"] and i["completed_at"]]
    on_time = [i for i in with_due if _dt(i["completed_at"]) <= _dt(i["due"])]
    open_items = [i for i in items if i["status"] != "done"]
    blocked, overdue = len(sections["blocked"]), len(sections["overdue"])
    health = "RED" if (blocked >= 3 or overdue >= 3) else "AMBER" if (blocked or overdue) else "GREEN"
    return {
        "completed_this_week": len(done),
        "in_progress": len(sections["in_progress"]),
        "blocked": blocked,
        "overdue": overdue,
        "open_total": len(open_items),
        "on_time_rate_pct": round(100 * len(on_time) / len(with_due)) if with_due else None,
        "health": health,
    }
