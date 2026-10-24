# PMO Automation (Trello): dashboard, weekly report, planning, closure

A Flask JSON API with a React (Vite) frontend, plus LangGraph agents that read a Trello board and give a PMO team the visibility it normally
builds by hand for software projects: how complete the project is, weekly status and risks, and project planning/closure.

## Run it
```
pip install -r backend/requirements.txt
cp .env.example .env        # add your Trello keys (and optionally GOOGLE_API_KEY)
cd frontend && npm install && npm run build && cd ..   # build the React app once
python backend/app.py       # http://localhost:5000 (run from the project root)
```
Frontend development with hot reload: run `python backend/app.py` and, in another terminal, `cd frontend && npm run dev`
(http://localhost:5173, `/api` is proxied to Flask). Needs Node 18+.
Live Trello data only: the app will not start without the three Trello settings in `.env`.

## Pages
| Page | Purpose |
|---|---|
| Dashboard | Project selector, completion of each project, tasks done / in progress / blocked / overdue, pipeline Backlog > Development > Testing > Done, planned vs actual dates |
| Weekly Report | KPIs, risk radar, reminders, editable report draft (Gemini wording optional) |
| Planning | Brief + team -> tasks, assignments, due dates -> create Trello cards |
| Closure | Completion check, closure report, archive board |

A floating chat bubble (bottom-right, every page) answers questions about the board through a read-only Gemini tool-calling agent (`backend/agent/chat_agent.py`); it needs `GOOGLE_API_KEY`.

Pages read cached data, so opening them never calls Trello. The cache refreshes every 30 minutes
and with the Refresh button.

## Use your real Trello board
1. Get an API key and token (see below) and put them in `.env`.
2. Set `TRELLO_BOARD_ID=...` in `.env`, then start the app.

Get credentials: https://trello.com/power-ups/admin -> New -> generate an API key -> click the Token link (authorize, read+write).
Board ID: open the board, add `.json` to its URL, copy the top-level `id`.

## Tag your cards (the dashboards read these)
`Project: Project 1`, `Release: v1.4`, `Team: Backend`, `Phase: QA` as labels (phases such as Design, Dev, QA, UAT); a `Blocked` label plus a comment for the reason;
Lists are the status (To Do / Doing / In Review / Done).
Names are configurable in `agent/config.py`. Cards without a Release or Phase label appear under "Unassigned" / "No phase".

## Automatic runs (email/Slack)
```
python backend/run_scheduled.py reminders      # saves reminders to ./reports (nothing is sent)
python backend/run_scheduled.py weekly
python backend/scheduler.py                            # keeps running: weekly report + weekday reminders (see .env)
```
Safe by default: output is saved to `./reports`. Add `--send` (or `SCHEDULE_SEND=true`) to really email or post.
Jobs refuse to run without Trello credentials. A GitHub Actions option is in `.github/workflows/`.

## How it is built
`backend/agent/` holds the logic (plain Python rules for numbers; the LLM only writes wording), `backend/app.py` is the JSON API (and serves
`frontend/dist`), and `frontend/` is the React app (`src/pages/` has one component per page). See `docs/ARCHITECTURE.md` for the workflow diagram, models, tools and API keys.
Health checks: `/ping`, `/api/trello-health`.
