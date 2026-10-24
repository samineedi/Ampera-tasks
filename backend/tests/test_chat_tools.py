import pytest

from agent.chat_agent import make_tools


@pytest.fixture
def tools(items):
    return {t.name: t for t in make_tools(items)}


def call(tools, name, **kw):
    return tools[name].invoke(kw)


def test_list_projects(tools):
    assert call(tools, "list_projects") == ["Project A", "Project B"]


def test_get_dashboard_totals_match_fixture(tools):
    t = call(tools, "get_dashboard", project="Project A")["totals"]
    assert (t["total"], t["done"], t["blocked"], t["overdue"]) == (4, 1, 1, 1)


def test_unknown_project_returns_error_with_valid_projects(tools):
    r = call(tools, "get_kpis", project="Nope")
    assert r["error"] == "Unknown project" and r["valid_projects"] == ["Project A", "Project B"]


def test_search_cards_blocked_filter(tools):
    r = call(tools, "search_cards", blocked=True)
    assert [c["title"] for c in r] == ["Stuck"] and r[0]["blocker_note"] == "waiting on vendor"


def test_search_cards_overdue_filter(tools):
    assert [c["title"] for c in call(tools, "search_cards", overdue=True)] == ["Late"]


def test_search_cards_assignee_filter(tools):
    assert {c["title"] for c in call(tools, "search_cards", assignee="asha")} == {"Working", "Late"}


def test_search_cards_limit_caps_at_25(make_card):
    ts = {t.name: t for t in make_tools([make_card(f"c{i}") for i in range(40)])}
    assert len(ts["search_cards"].invoke({"limit": 100})) == 25


def test_search_cards_handles_missing_due_and_assignees(tools):
    r = call(tools, "search_cards", overdue=True, assignee="zzz", label="x", status="todo")
    assert r == []


def test_tools_on_empty_board_return_empty_not_error():
    ts = {t.name: t for t in make_tools([])}
    assert ts["list_projects"].invoke({}) == []
    assert ts["search_cards"].invoke({}) == []
    assert "error" not in ts["get_dashboard"].invoke({})
