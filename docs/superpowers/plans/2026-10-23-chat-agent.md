# Chat Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A floating chat bubble on every page that answers questions about the Trello board through a read-only, tool-calling LangGraph agent.

**Architecture:** `backend/agent/chat_agent.py` holds plain tool functions over the cached normalized items plus a `create_react_agent` on the Gemini model from `drafter._get_llm()`. `POST /api/chat` in `app.py` validates input and calls it. `ChatWidget.jsx` is mounted once in `App.jsx`.

**Tech Stack:** Python 3.12, Flask, langgraph 1.2 (`langgraph.prebuilt.create_react_agent`), langchain-google-genai, React + Vite, pytest (dev only, not yet installed).

**Spec:** `docs/superpowers/specs/2026-10-23-chat-agent-design.md`

## Global Constraints

- Read-only: no Trello writes, no sending, no cache writes.
- No new runtime dependencies (pytest is dev-only; do not add it to `backend/requirements.txt`).
- Tools read the cached board only (`app.board()["items"]`), never call Trello.
- Max 6 tool calls per question; `search_cards` returns at most 25 cards; message max 1000 chars; history trimmed to last 10 messages.
- No `GOOGLE_API_KEY`: `/api/chat` returns 503 with message "Chat needs GOOGLE_API_KEY". No fake answers.
- LLM error/timeout: friendly message, no stack trace in the response.
- Backend code is run from `backend/` (modules import as `from agent import ...`); tests live in `backend/tests/` and run with `cd backend && python -m pytest`.

## Review Focus

- Empty board (no items): tools return empty results, agent says there is no data, no crash.
- Unknown or misspelled project name: tools return an error object listing valid projects instead of an empty success.
- Cards with `due: None`, no assignees, or empty labels: `search_cards` filters must not raise.
- `history` containing malformed entries (missing role, non-string content, roles other than user/assistant): endpoint returns 400, not 500.
- Empty/whitespace-only or over-1000-char message: 400.

## File Structure

- Create `backend/agent/chat_agent.py` — tools, system prompt, `ask()`.
- Create `backend/tests/conftest.py`, `backend/tests/test_chat_tools.py`, `backend/tests/test_chat_agent.py`, `backend/tests/test_chat_api.py`.
- Modify `backend/app.py` — add `/api/chat` route.
- Create `frontend/src/ChatWidget.jsx`.
- Modify `frontend/src/App.jsx` (mount widget), `frontend/src/style.css` (widget styles).

---

### Task 1: Chat tools

**Files:**
- Create: `backend/agent/chat_agent.py` (tools part)
- Create: `backend/tests/conftest.py`, `backend/tests/test_chat_tools.py`

**Interfaces:**
- Consumes: `dashboard.project_names`, `dashboard.dashboard_view(items, project)`, `dashboard.filter_project(items, project)`, `classify.classify(items)`, `kpi.compute_kpis(items, sections)`, `risk.build_risk_radar(items)`, `notifier.build_notifications(items)`.
- Produces: `make_tools(items: list[dict]) -> list` returning LangChain tools (`@tool`-decorated closures) named `list_projects`, `get_dashboard`, `get_kpis`, `get_risks`, `get_reminders`, `search_cards`. Every tool returns a JSON-serializable dict/list. A project argument that is not in `project_names(items)` (and not empty/"all") returns `{"error": "Unknown project", "valid_projects": [...]}`.

- [ ] **Step 1: Write `conftest.py`** — sets dummy `TRELLO_API_KEY`, `TRELLO_TOKEN`, `TRELLO_BOARD_ID` env vars before anything imports `app`, adds `backend/` to `sys.path`, and provides a `items` fixture: 5 normalized cards (same keys as `cache/cache_board.json` items) across `Project A` and `Project B`, covering done, in_progress, blocked, overdue (past `due`), a card with `due: None`, and a card with `assignees: []`.
- [ ] **Step 2: Write failing tests** in `test_chat_tools.py`: `test_list_projects`, `test_get_dashboard_totals_match_fixture`, `test_unknown_project_returns_error_with_valid_projects`, `test_search_cards_blocked_filter`, `test_search_cards_overdue_filter`, `test_search_cards_assignee_filter`, `test_search_cards_limit_caps_at_25` (build 40 matching cards, assert `len(result) == 25`), `test_search_cards_handles_missing_due_and_assignees`, `test_tools_on_empty_board_return_empty_not_error`.
- [ ] **Step 3: Run** `cd backend && python -m pip install pytest && python -m pytest tests/test_chat_tools.py -v` — expected: FAIL (module not found).
- [ ] **Step 4: Implement `make_tools`** in `chat_agent.py`. `search_cards(project: str = "", status: str = "", assignee: str = "", label: str = "", overdue: bool = False, blocked: bool = False, limit: int = 25)` filters `filter_project` output, uses `normalize._dt` for overdue (non-done and due < now), clamps `limit` to 1..25, returns `[{title, list, status, due, assignees, project, blocker_note, url}]`. Other tools wrap the Consumes functions; `get_kpis`/`get_risks`/`get_reminders` first filter by project.
- [ ] **Step 5: Run** `python -m pytest tests/test_chat_tools.py -v` — expected: all PASS.

### Task 2: Agent runner

**Files:**
- Modify: `backend/agent/chat_agent.py`
- Create: `backend/tests/test_chat_agent.py`

**Interfaces:**
- Consumes: `make_tools(items)` (Task 1), `drafter._get_llm()` (returns a chat model or `None`).
- Produces: `class ChatUnavailable(Exception)`; `ask(items: list[dict], message: str, history: list[dict], project: str = "", llm=None) -> dict` returning `{"answer": str, "tools_used": list[str]}`. `history` entries are `{"role": "user"|"assistant", "content": str}`; only the last 10 are used. If `llm` is None it calls `_get_llm()`; if that is also None it raises `ChatUnavailable`. Uses `create_react_agent(llm, tools, prompt=SYSTEM_PROMPT)` and `recursion_limit` sized for 6 tool calls (each call is an agent+tools step pair, so `2*6+1`). `tools_used` is the de-duplicated, ordered tool names from the returned messages. `drafter.llm_text` converts the final message to a string.

- [ ] **Step 1: Write failing tests** with a fake chat model (a `langchain_core.language_models.fake_chat_models.GenericFakeChatModel` subclass that implements `bind_tools` returning itself, fed `AIMessage` objects with `tool_calls`): `test_ask_returns_answer_and_tools_used` (fake calls `get_kpis`, then answers "3 blocked"), `test_ask_raises_when_no_llm` (monkeypatch `_get_llm` to return None), `test_history_trimmed_to_last_10` (assert the messages the fake model received contain at most 10 history messages plus the new one plus the system prompt), `test_system_prompt_mentions_selected_project`, `test_tool_call_limit_stops_runaway_loop` (fake always requests a tool; assert `ask` returns a message without raising and `tools_used` has at most 6 entries... catch `GraphRecursionError` and return the answer "I couldn't finish looking that up; try a narrower question.").
- [ ] **Step 2: Run** `python -m pytest tests/test_chat_agent.py -v` — expected: FAIL.
- [ ] **Step 3: Implement `SYSTEM_PROMPT`, `ChatUnavailable`, `ask`.** Prompt text: answer only from tool results; if the tools don't cover the question say so; be concise; never invent numbers; `Selected project: {project or "all projects"}`.
- [ ] **Step 4: Run** `python -m pytest tests/test_chat_agent.py -v` — expected: all PASS.

### Task 3: `/api/chat` endpoint

**Files:**
- Modify: `backend/app.py` (add route near the other `/api/*` routes, import `from agent.chat_agent import ask, ChatUnavailable`)
- Create: `backend/tests/test_chat_api.py`

**Interfaces:**
- Consumes: `ask`, `ChatUnavailable` (Task 2), `board()["items"]`.
- Produces: `POST /api/chat` body `{message: str, history?: list, project?: str}` → `200 {answer, tools_used}`; `400 {error}` for invalid input; `503 {error: "Chat needs GOOGLE_API_KEY"}` on `ChatUnavailable`; `502 {error: "The assistant had a problem answering. Please try again."}` on any other exception (log the exception server-side).

- [ ] **Step 1: Write failing tests** using Flask's test client with `app.ask` and `app.board` monkeypatched: `test_chat_ok_returns_answer`, `test_chat_empty_message_400`, `test_chat_whitespace_message_400`, `test_chat_message_over_1000_chars_400`, `test_chat_history_not_a_list_400`, `test_chat_history_bad_role_400`, `test_chat_history_non_string_content_400`, `test_chat_no_api_key_503` (ask raises `ChatUnavailable`), `test_chat_agent_error_502_no_traceback` (ask raises `RuntimeError("secret")`; assert "secret" not in response text), `test_chat_passes_project_to_ask`.
- [ ] **Step 2: Run** `python -m pytest tests/test_chat_api.py -v` — expected: FAIL (404).
- [ ] **Step 3: Implement the route** with a small `_valid_history(h)` helper in `app.py` that checks list of dicts with `role in {"user","assistant"}` and string `content`.
- [ ] **Step 4: Run** `python -m pytest tests -v` — expected: all PASS.

### Task 4: Chat widget

**Files:**
- Create: `frontend/src/ChatWidget.jsx`
- Modify: `frontend/src/App.jsx` (import and render `<ChatWidget />` inside `AppCtx.Provider`, after `</main>`), `frontend/src/style.css`

**Interfaces:**
- Consumes: `post(url, body)` from `lib.jsx` (throws on non-2xx; check how `request` surfaces the `error` field and show it), `useSearchParams` from `react-router-dom` to read `project` (the dashboard keeps the selected project in `?project=`).
- Produces: default-exported `ChatWidget` component, no props.

- [ ] **Step 1: Implement `ChatWidget`:** fixed bottom-right bubble button; click toggles a panel with scrolling message list, text input (Enter sends, Shift+Enter newline), Send button disabled while empty or busy, "Thinking…" row while waiting, 3 starter chips shown when there are no messages ("What's overdue?", "Which cards are blocked?", "Summarize project health"). Messages live in `useState`; each request sends `{message, history: last 10 messages as {role, content}, project}`. Assistant messages render `tools_used` as a muted "Looked at: a, b" line. Errors (including the 503 key message) render as an assistant-styled error bubble. No `dangerouslySetInnerHTML`: render text only.
- [ ] **Step 2: Add styles** to `style.css` using the existing CSS variables and class naming style of that file; panel must fit a 360px-wide phone (`max-width: calc(100vw - 24px)`).
- [ ] **Step 3: Mount in `App.jsx`.**
- [ ] **Step 4: Verify build:** `cd frontend && npm run build` — expected: build succeeds with no errors.

### Task 5: End-to-end check

**Files:** none (verification only); update `README.md` "Pages" section with one line about the chat bubble and that it needs `GOOGLE_API_KEY`.

- [ ] **Step 1:** Stop any running server, run `python backend/app.py` from the project root, open http://localhost:5000, confirm the bubble appears on all four pages.
- [ ] **Step 2:** With `GOOGLE_API_KEY` set, ask: "What's overdue in Project 1?", "Which cards are blocked?", "How many cards are done overall?" Compare each answer with the Dashboard numbers.
- [ ] **Step 3:** Ask something the tools can't answer ("What is the budget?") — expected: agent says it has no data on that.
- [ ] **Step 4:** Unset the key, restart, send a message — expected: the 503 message appears in the panel.
- [ ] **Step 5:** Run `cd backend && python -m pytest tests -v` — expected: all PASS.
