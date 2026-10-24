# Chat Agent (floating bubble) — Design

## Goal
PMO users ask plain-English questions about the Trello board from a floating chat bubble on every page and get answers grounded in the cached board data. Read-only: no Trello writes, no sending.

**Success:** "What's blocked in Project 1?" returns a correct answer in a few seconds; the agent never invents numbers and says so when its tools don't cover a question.

## Approach
Tool-calling agent. A LangGraph ReAct agent (`langgraph.prebuilt.create_react_agent`) on the Gemini model from `drafter._get_llm()`. No new dependencies. Tools are thin wrappers over existing functions and read the cached board only (no Trello calls).

## Backend
### `backend/agent/chat_agent.py`
- `build_agent(items, project)` builds the agent with tools bound to the given (already cached) items.
- System prompt: answer only from tool results; if tools do not cover the question, say so; be concise; the currently selected project is `{project}`.
- Tools (each returns compact JSON):
  | Tool | Backed by |
  |---|---|
  | `list_projects()` | `dashboard.project_names` |
  | `get_dashboard(project)` | `dashboard.dashboard_view` |
  | `get_kpis(project)` | `classify` + `kpi.compute_kpis` |
  | `get_risks(project)` | `risk.build_risk_radar` |
  | `get_reminders(project)` | `notifier.build_notifications` |
  | `search_cards(project, status, assignee, label, overdue, blocked, limit)` | filter over normalized items |
- Limits: recursion limit for at most 6 tool calls per question; `search_cards` returns at most 25 cards; message max 1000 chars; history trimmed to last 10 messages.
- `ask(message, history, project)` returns `{answer, tools_used}`.

### `POST /api/chat` (`backend/app.py`)
- Body: `{message, history, project}`. Validates types and lengths (400 on bad input).
- No `GOOGLE_API_KEY`: 503 with message "Chat needs GOOGLE_API_KEY".
- LLM error/timeout: friendly error message, no stack trace.
- Response: `{answer, tools_used}`.

## Frontend
- `frontend/src/ChatWidget.jsx`: bottom-right bubble opening a panel with message list, input, "thinking…" state, starter chips, and a "looked at: …" line from `tools_used` under each answer. History is kept in component state for the session. Sends the currently selected project.
- Mounted once in `App.jsx` so it shows on every route. Styles in `style.css`.

## Out of scope
Any write action (create cards, send reports, archive), persistence of chat history, streaming responses, auth.

## Testing
- Unit tests per tool against a small fixture board.
- Agent test with a mocked LLM verifying the tool-call loop and limits.
- Endpoint validation tests (400 / 503 paths).
- Manual run in the app with real questions on a real board.
