"""Read-only chat agent: a tool-calling LangGraph agent over the cached board.
Tools only read the items passed in (the web app's cached board); nothing here writes to Trello."""
from datetime import datetime, timezone

from langchain_core.tools import tool
from langgraph.errors import GraphRecursionError
from langgraph.prebuilt import create_react_agent

from .classify import classify
from .drafter import _get_llm, llm_text
from .dashboard import dashboard_view, filter_project, project_names
from .kpi import compute_kpis
from .normalize import _dt
from .notifier import build_notifications
from .risk import build_risk_radar

MAX_CARDS = 25
MAX_TOOL_CALLS = 6
MAX_HISTORY = 10

SYSTEM_PROMPT = (
    "You are a PMO assistant for a Trello board. Answer only from the results of your tools. "
    "If the tools do not cover the question, say you have no data on it. Never invent numbers. "
    "Be concise. Selected project: {project}."
)


class ChatUnavailable(Exception):
    """No LLM is configured (GOOGLE_API_KEY missing)."""


def make_tools(items):
    valid = project_names(items)

    def scoped(project):
        """(items for the project, None) or (None, error object) when the project name is unknown."""
        if project and project != "all" and project not in valid:
            return None, {"error": "Unknown project", "valid_projects": valid}
        return filter_project(items, project), None

    @tool
    def list_projects() -> list:
        """List the project names on the board."""
        return valid

    @tool
    def get_dashboard(project: str = "") -> dict:
        """Completion %, status totals (done / in progress / blocked / overdue), pipeline stages and
        per-project rows. Empty project = all projects."""
        rows, err = scoped(project)
        return err or dashboard_view(items, project)

    @tool
    def get_kpis(project: str = "") -> dict:
        """Weekly KPIs (completed this week, blocked, overdue, health RED/AMBER/GREEN). Empty project = all."""
        rows, err = scoped(project)
        return err or compute_kpis(rows, classify(rows))

    @tool
    def get_risks(project: str = "") -> list:
        """Risk radar: stuck, blocked, overdue and regressed cards with reasons. Empty project = all."""
        rows, err = scoped(project)
        return err or build_risk_radar(rows)

    @tool
    def get_reminders(project: str = "") -> dict:
        """Pending reminders per person and manager escalations. Empty project = all."""
        rows, err = scoped(project)
        return err or build_notifications(rows)

    @tool
    def search_cards(project: str = "", status: str = "", assignee: str = "", label: str = "",
                     overdue: bool = False, blocked: bool = False, limit: int = MAX_CARDS) -> list:
        """Find cards. status is one of todo / in_progress / blocked / done; assignee and label are
        case-insensitive substring matches. Returns at most 25 cards."""
        rows, err = scoped(project)
        if err:
            return err
        now = datetime.now(timezone.utc)
        out = []
        for it in rows:
            due = _dt(it["due"])
            if status and it["status"] != status:
                continue
            if blocked and it["status"] != "blocked":
                continue
            if overdue and not (it["status"] != "done" and due and due < now):
                continue
            if assignee and not any(assignee.lower() in a.lower() for a in it["assignees"] or []):
                continue
            if label and not any(label.lower() in l.lower() for l in it["labels"] or []):
                continue
            out.append({"title": it["title"], "list": it["list"], "status": it["status"], "due": it["due"],
                        "assignees": it["assignees"], "project": it["project"],
                        "blocker_note": it["blocker_note"], "url": it["url"]})
        return out[:max(1, min(limit, MAX_CARDS))]

    return [list_projects, get_dashboard, get_kpis, get_risks, get_reminders, search_cards]


def ask(items, message, history, project="", llm=None):
    """Run the agent for one question. history = [{"role": "user"|"assistant", "content": str}, ...]."""
    llm = llm or _get_llm()
    if llm is None:
        raise ChatUnavailable("Chat needs GOOGLE_API_KEY")
    agent = create_react_agent(llm, make_tools(items), prompt=SYSTEM_PROMPT.format(project=project or "all projects"))
    msgs = [(h["role"], h["content"]) for h in history[-MAX_HISTORY:]] + [("user", message)]
    state, answer = {"messages": []}, None
    try:
        for state in agent.stream({"messages": msgs}, {"recursion_limit": 2 * MAX_TOOL_CALLS + 1}, stream_mode="values"):
            pass
        answer = llm_text(state["messages"][-1])
    except GraphRecursionError:
        answer = "I couldn't finish looking that up; try a narrower question."
    used = []
    for m in state["messages"]:
        for c in getattr(m, "tool_calls", None) or []:
            if c["name"] not in used:
                used.append(c["name"])
    return {"answer": answer, "tools_used": used}
