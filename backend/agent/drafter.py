import json
import os
from datetime import date

PROMPT = """You are writing a weekly project status report for stakeholders.
Use ONLY the facts in the JSON below. Do not invent items, names, dates or numbers.
Format in Markdown with: a one-line headline with overall health, Highlights (completed),
In Progress, Risks & Blockers (include blocker notes), Overdue Items, Next Week (upcoming).
Be concise and neutral. Refer to people by name only when given.

DATA:
{data}
"""


def _slim(sections):
    keep = ("title", "assignees", "due", "list", "blocker_note", "url")
    return {k: [{f: i.get(f) for f in keep} for i in v] for k, v in sections.items()}


def template_draft(sections, kpis):
    def block(name, rows, extra=""):
        if not rows:
            return f"### {name}\n- None\n"
        lines = []
        for i in rows:
            who = f" ({', '.join(i['assignees'])})" if i["assignees"] else ""
            due = f" - due {i['due'][:10]}" if i["due"] else ""
            note = f" - {i['blocker_note']}" if extra == "note" and i["blocker_note"] else ""
            lines.append(f"- {i['title']}{who}{due}{note}")
        return f"### {name}\n" + "\n".join(lines) + "\n"

    return (
        f"# Weekly Status Report - {date.today():%d %b %Y}\n"
        f"**Overall health: {kpis['health']}** | Completed: {kpis['completed_this_week']} | "
        f"In progress: {kpis['in_progress']} | Blocked: {kpis['blocked']} | Overdue: {kpis['overdue']}\n\n"
        + block("Completed this week", sections["completed"])
        + block("In progress", sections["in_progress"])
        + block("Blockers", sections["blocked"], "note")
        + block("Overdue", sections["overdue"])
        + block("Next week", sections["upcoming"])
    )


def _get_llm():
    if os.getenv("GOOGLE_API_KEY"):
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(model=os.getenv("LLM_MODEL", "gemini-3.8-flash"), temperature=0.2, timeout=45, max_retries=1)
    return None


def llm_text(resp):
    """Message text as a string; Gemini may return a list of content blocks."""
    c = resp.content
    if isinstance(c, str):
        return c
    return "".join(b if isinstance(b, str) else b.get("text", "") for b in c)


def draft_report(sections, kpis, use_llm=True):
    llm = _get_llm() if use_llm else None
    if llm is None:
        return template_draft(sections, kpis)
    try:
        data = json.dumps({"kpis": kpis, "sections": _slim(sections)}, indent=2)
        return llm_text(llm.invoke(PROMPT.format(data=data)))
    except Exception as e:  # fall back so the manager always gets a draft
        return template_draft(sections, kpis) + f"\n\n_(LLM unavailable, template used: {e})_"
