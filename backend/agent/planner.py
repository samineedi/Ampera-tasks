"""Planning agent: project brief -> task breakdown -> assignment -> schedule.
The LLM only proposes tasks; assignment and dates are computed by code so they are predictable."""
import json
import os
import re
from datetime import date, timedelta

import requests

from . import config
from .drafter import _get_llm, llm_text
from .trello_client import BASE

PLAN_PROMPT = """You are a project planner. Break the project brief into 8-15 ordered tasks.
Return ONLY a JSON list (no prose, no code fences). Each item:
{{"title": str, "description": str, "skills": [str], "estimate_days": int, "priority": "High"|"Medium"|"Low"}}
Choose skills from this list when possible: {skills}

BRIEF:
{brief}
"""


def parse_team(text):
    """'Asha: design, frontend' per line -> [{'name','skills'}]"""
    team = []
    for line in text.splitlines():
        if not line.strip():
            continue
        name, _, skills = line.partition(":")
        team.append({"name": name.strip(), "skills": [s.strip().lower() for s in skills.split(",") if s.strip()]})
    return team


def _fallback_tasks(brief):
    sents = [s.strip(" -*\u2022\t") for s in re.split(r"[\n.]+", brief) if len(s.strip()) > 15][:6]
    feats = [{"title": f"Build: {s[:70]}", "description": s, "skills": ["development"],
              "estimate_days": 4, "priority": "Medium"} for s in sents]
    head = [
        {"title": "Requirements & scope", "description": "Confirm scope and acceptance criteria", "skills": ["analysis"], "estimate_days": 2, "priority": "High"},
        {"title": "Design & architecture", "description": "Solution design and approach", "skills": ["design"], "estimate_days": 3, "priority": "High"},
    ]
    tail = [
        {"title": "Testing & QA", "description": "Test and fix defects", "skills": ["testing"], "estimate_days": 3, "priority": "High"},
        {"title": "Deployment & handover", "description": "Release and hand over", "skills": ["devops"], "estimate_days": 2, "priority": "Medium"},
    ]
    return head + feats + tail


def propose_tasks(brief, team):
    llm = _get_llm()
    if llm is None:
        return _fallback_tasks(brief)
    skills = sorted({s for m in team for s in m["skills"]}) or ["development", "design", "testing"]
    try:
        out = llm_text(llm.invoke(PLAN_PROMPT.format(skills=", ".join(skills), brief=brief)))
        out = re.sub(r"^```(?:json)?|```$", "", out.strip(), flags=re.M).strip()
        tasks = json.loads(out)
        assert isinstance(tasks, list) and tasks
        return tasks
    except Exception:
        return _fallback_tasks(brief)


def assign_and_schedule(tasks, team, start=None):
    """Skill match first, then least-loaded person. Due dates stack per person."""
    start = start or date.today()
    load = {m["name"]: 0 for m in team}
    planned = []
    for t in tasks:
        need = {s.lower() for s in t.get("skills", [])}
        pool = [m for m in team if need & set(m["skills"])] or team
        if not pool:
            planned.append({**t, "assignee": "Unassigned", "due": None})
            continue
        person = min(pool, key=lambda m: load[m["name"]])["name"]
        load[person] += int(t.get("estimate_days", 2))
        planned.append({**t, "assignee": person, "due": (start + timedelta(days=load[person])).isoformat()})
    return planned


def plan_project(brief, team):
    return assign_and_schedule(propose_tasks(brief, team), team)


def create_trello_cards(plan, board_id=None, dry_run=True, project=None):
    """Write planned tasks to Trello. dry_run (default) only reports what would happen."""
    key, token = os.getenv("TRELLO_API_KEY"), os.getenv("TRELLO_TOKEN")
    board_id = board_id or os.getenv("TRELLO_BOARD_ID")
    if dry_run or not (key and token and board_id):
        return f"Dry run: {len(plan)} cards would be created (no Trello credentials/board, or dry-run on)."
    auth = {"key": key, "token": token}
    get = lambda p: requests.get(f"{BASE}{p}", params=auth, timeout=30).json()
    lists = get(f"/boards/{board_id}/lists")
    target = next((l for l in lists if l["name"].lower() in config.TODO_LISTS), lists[0])
    label_id = None
    if project:                                     # reuse the board's "Project: X" label or create it
        name = f"Project: {project}"
        labels = get(f"/boards/{board_id}/labels")
        label_id = next((l["id"] for l in labels if l.get("name") == name), None)
        if not label_id:
            r = requests.post(f"{BASE}/boards/{board_id}/labels", data={**auth, "name": name, "color": "sky"}, timeout=30)
            r.raise_for_status()
            label_id = r.json()["id"]
    members = {m["fullName"]: m["id"] for m in get(f"/boards/{board_id}/members")}
    n = 0
    for t in plan:
        desc = f"{t.get('description','')}\n\nPriority: {t.get('priority','')} | Est: {t.get('estimate_days','')}d"
        if t["assignee"] not in members:          # not a Trello member: keep the owner visible on the card
            desc += f"\nAssignee: {t['assignee']}"
        data = {**auth, "idList": target["id"], "name": t["title"], "desc": desc,
                "due": f"{t['due']}T17:00:00.000Z" if t.get("due") else ""}
        if t["assignee"] in members:
            data["idMembers"] = members[t["assignee"]]
        if label_id:
            data["idLabels"] = label_id
        requests.post(f"{BASE}/cards", data=data, timeout=30).raise_for_status()
        n += 1
    return f"Created {n} cards in list '{target['name']}'."
