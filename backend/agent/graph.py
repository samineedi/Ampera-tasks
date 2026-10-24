"""Master LangGraph. mode = "weekly" | "plan" | "closure".

  plan:     START -> plan -> END
  weekly:   START -> fetch -> normalize -> classify -> kpi -> risk -> draft -> notify -> END
  closure:  START -> fetch -> normalize -> closure -> END

If the state already contains "items" (the web app passes its cached board), fetch/normalize are skipped.
Set use_llm=False to get the template draft without calling an LLM.

Anything with side effects (create cards, send report/notifications, archive board)
happens in the web app after the manager approves.
"""
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from .classify import classify
from .closure import assess, draft_closure
from .drafter import draft_report
from .kpi import compute_kpis
from .normalize import normalize
from .notifier import build_notifications
from .planner import plan_project
from .risk import build_risk_radar
from .trello_client import fetch_board


class State(TypedDict, total=False):
    mode: str
    board_id: str
    days: int
    use_llm: bool
    risk: list
    project_name: str
    brief: str
    team: list
    raw: dict
    items: list
    sections: dict
    kpis: dict
    draft: str
    plan: list
    notifications: list
    closure: dict
    closure_draft: str


def fetch_node(s: State) -> dict[str, Any]:
    return {"raw": fetch_board(s.get("board_id"), s.get("days", 7))}

def normalize_node(s: State):
    return {"items": normalize(s["raw"], s.get("days", 7))}

def classify_node(s: State):
    return {"sections": classify(s["items"], s.get("days", 7))}

def kpi_node(s: State):
    return {"kpis": compute_kpis(s["items"], s["sections"])}

def risk_node(s: State):
    return {"risk": build_risk_radar(s["items"])}

def draft_node(s: State):
    return {"draft": draft_report(s["sections"], s["kpis"], s.get("use_llm", True))}

def notify_node(s: State):
    return {"notifications": build_notifications(s["items"])}

def plan_node(s: State):
    return {"plan": plan_project(s["brief"], s["team"])}

def closure_node(s: State):
    a = assess(s["items"])
    return {"closure": a, "closure_draft": draft_closure(a, s.get("project_name", "Project"))}


def build_graph():
    g = StateGraph(State)
    for name, fn in [("fetch", fetch_node), ("normalize", normalize_node), ("classify", classify_node),
                     ("kpi", kpi_node), ("risk", risk_node), ("draft", draft_node), ("notify", notify_node),
                     ("plan", plan_node), ("closure", closure_node)]:
        g.add_node(name, fn)

    def route_start(s):
        if s.get("mode") == "plan":
            return "plan"
        if s.get("items"):                      # board already fetched (web app cache)
            return "closure" if s.get("mode") == "closure" else "classify"
        return "fetch"

    g.add_conditional_edges(START, route_start,
                            {"plan": "plan", "fetch": "fetch", "classify": "classify", "closure": "closure"})
    g.add_edge("fetch", "normalize")
    g.add_conditional_edges("normalize", lambda s: "closure" if s.get("mode") == "closure" else "classify",
                            {"closure": "closure", "classify": "classify"})
    g.add_edge("classify", "kpi")
    g.add_edge("kpi", "risk")
    g.add_edge("risk", "draft")
    g.add_edge("draft", "notify")
    g.add_edge("notify", END)
    g.add_edge("plan", END)
    g.add_edge("closure", END)
    return g.compile()
