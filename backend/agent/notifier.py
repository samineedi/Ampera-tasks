"""Notification agent: per-person reminders + manager escalations. Sending is a separate, explicit step."""
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

from . import config
from .normalize import _dt


def build_notifications(items, now=None):
    now = now or datetime.now(timezone.utc)
    soon = now + timedelta(days=config.DUE_SOON_DAYS)
    per, escalate = {}, []
    for it in items:
        if it["status"] == "done":
            continue
        due, last = _dt(it["due"]), _dt(it["last_activity"])
        notes = []
        if due and due < now:
            days_late = (now - due).days
            notes.append(f"OVERDUE by {days_late}d: {it['title']}")
            if days_late >= config.ESCALATE_OVERDUE_DAYS:
                escalate.append(f"{it['title']} is {days_late}d overdue")
        elif due and due <= soon:
            notes.append(f"Due soon ({it['due'][:10]}): {it['title']}")
        if it["status"] == "blocked":
            notes.append(f"BLOCKED: {it['title']} - {it['blocker_note'] or 'no reason noted, please add a comment'}")
            if last and (now - last).days >= config.STALE_DAYS:
                escalate.append(f"{it['title']} blocked with no activity for {(now - last).days}d")
        for who in (it["assignees"] or ["Unassigned"]):
            per.setdefault(who, []).extend(notes)
    msgs = [{"to": who, "kind": "reminder", "body": "\n".join(f"- {n}" for n in notes)}
            for who, notes in per.items() if notes]
    if escalate:
        msgs.append({"to": "Manager", "kind": "escalation",
                     "body": "\n".join(f"- {e}" for e in sorted(set(escalate)))})
    return msgs


def send_notifications(msgs, dry_run=True):
    webhook = os.getenv("SLACK_WEBHOOK_URL")
    if webhook and not dry_run:
        for m in msgs:
            requests.post(webhook, json={"text": f"*{m['kind'].title()} for {m['to']}*\n{m['body']}"}, timeout=15).raise_for_status()
        return f"Posted {len(msgs)} messages to Slack."
    out = Path("reports") / f"notifications_{datetime.now():%Y%m%d_%H%M}.txt"
    out.parent.mkdir(exist_ok=True)
    out.write_text("\n\n".join(f"[{m['kind']}] {m['to']}\n{m['body']}" for m in msgs), encoding="utf-8")
    return f"Dry run / no SLACK_WEBHOOK_URL - saved to {out}"
