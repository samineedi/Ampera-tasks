"""Closure agent: completion check, final report with lessons learned, optional board archive."""
import json
import os
from datetime import date

import requests

from .drafter import _get_llm, _slim, llm_text
from .normalize import _dt
from .trello_client import BASE

PROMPT = """Write a project closure report in Markdown for stakeholders, using ONLY the facts below.
Sections: Summary, Delivered, Outstanding / Handover items, Performance (completion & on-time rate),
Lessons Learned (3-5 evidence-based points, no invention), Recommendation (close / not ready and why).

DATA:
{data}
"""


def assess(items):
    done = [i for i in items if i["status"] == "done"]
    open_ = [i for i in items if i["status"] != "done"]
    with_due = [i for i in done if i["due"] and i["completed_at"]]
    late = [i for i in with_due if _dt(i["completed_at"]) > _dt(i["due"])]
    total = len(items) or 1
    return {
        "kpis": {"total": len(items), "done": len(done), "open": len(open_),
                 "completion_pct": round(100 * len(done) / total),
                 "on_time_pct": round(100 * (len(with_due) - len(late)) / len(with_due)) if with_due else None,
                 "late_deliveries": len(late),
                 "blocked_open": sum(1 for i in open_ if i["status"] == "blocked")},
        "sections": {"delivered": done, "outstanding": open_, "late": late},
        "ready_to_close": not open_,
    }


def _template(a, name):
    k = a["kpis"]
    def lines(rows):
        return "\n".join(f"- {i['title']}" + (f" ({', '.join(i['assignees'])})" if i["assignees"] else "") for i in rows) or "- None"
    lessons = []
    if k["late_deliveries"]:
        lessons.append(f"{k['late_deliveries']} deliverable(s) finished after their due date - review estimation.")
    if k["blocked_open"]:
        lessons.append(f"{k['blocked_open']} item(s) still blocked - identify dependencies earlier.")
    if k["open"]:
        lessons.append(f"{k['open']} item(s) unfinished at closure - re-check scope control.")
    if not lessons:
        lessons.append("All work delivered on schedule; capture what worked for reuse.")
    rec = "Ready to close." if a["ready_to_close"] else f"NOT ready to close: {k['open']} open item(s) need an owner or a decision."
    return (f"# Project Closure Report - {name} ({date.today():%d %b %Y})\n\n"
            f"**Completion:** {k['completion_pct']}% ({k['done']}/{k['total']}) | **On-time:** "
            f"{'n/a' if k['on_time_pct'] is None else str(k['on_time_pct']) + '%'}\n\n"
            f"## Delivered\n{lines(a['sections']['delivered'])}\n\n"
            f"## Outstanding / handover\n{lines(a['sections']['outstanding'])}\n\n"
            f"## Lessons learned\n" + "\n".join(f"- {l}" for l in lessons) + f"\n\n## Recommendation\n{rec}\n")


def draft_closure(a, name="Project"):
    llm = _get_llm()
    if llm is None:
        return _template(a, name)
    try:
        data = json.dumps({"project": name, "kpis": a["kpis"], "ready_to_close": a["ready_to_close"],
                           "sections": _slim(a["sections"])}, indent=2)
        return llm_text(llm.invoke(PROMPT.format(data=data)))
    except Exception as e:
        return _template(a, name) + f"\n\n_(LLM unavailable, template used: {e})_"


def archive_board(board_id=None, confirm=False):
    """Closes (archives) the Trello board. Requires confirm=True; reversible from Trello."""
    key, token = os.getenv("TRELLO_API_KEY"), os.getenv("TRELLO_TOKEN")
    board_id = board_id or os.getenv("TRELLO_BOARD_ID")
    if not confirm or not (key and token and board_id):
        return "Not archived (needs confirmation and real Trello credentials/board)."
    requests.put(f"{BASE}/boards/{board_id}", params={"key": key, "token": token, "closed": "true"}, timeout=30).raise_for_status()
    return "Board archived (you can re-open it from Trello's closed boards)."
