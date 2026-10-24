import os
import re
import smtplib
from datetime import datetime
from email.message import EmailMessage
from pathlib import Path

import requests

SLACK_CHUNK = 3000


def to_slack(markdown_text):
    """Slack has no Markdown headings: '# Title' -> '*Title*', '**bold**' -> '*bold*'."""
    text = re.sub(r"^#{1,6}\s+(.+?)\s*$", r"*\1*", markdown_text, flags=re.M)
    return re.sub(r"\*\*(.+?)\*\*", r"*\1*", text)


def split_slack(text, limit=SLACK_CHUNK):
    """Split at blank lines so each post stays under `limit`; a single oversized block is cut hard."""
    chunks, cur = [], ""
    for block in text.split("\n\n"):
        while len(block) > limit:
            if cur:
                chunks.append(cur)
                cur = ""
            chunks.append(block[:limit])
            block = block[limit:]
        if cur and len(cur) + 2 + len(block) > limit:
            chunks.append(cur)
            cur = block
        else:
            cur = f"{cur}\n\n{block}" if cur else block
    if cur:
        chunks.append(cur)
    return chunks


def send_report(markdown_text, subject="Weekly Status Report"):
    """Send by email (if SMTP is configured) and/or Slack (if SLACK_WEBHOOK_URL is set);
    if neither is configured, save to ./reports. Returns a message."""
    host, to, webhook = os.getenv("SMTP_HOST"), os.getenv("REPORT_TO"), os.getenv("SLACK_WEBHOOK_URL")
    sent, failed = [], []
    if host and to:
        try:
            msg = EmailMessage()
            msg["Subject"], msg["From"], msg["To"] = subject, os.getenv("REPORT_FROM", ""), to
            msg.set_content(markdown_text)
            with smtplib.SMTP(host, int(os.getenv("SMTP_PORT", "587"))) as smtp:
                smtp.starttls()
                if os.getenv("SMTP_USER"):
                    smtp.login(os.getenv("SMTP_USER"), os.getenv("SMTP_PASSWORD", ""))
                smtp.send_message(msg)
            sent.append(f"Sent to {to}")
        except Exception as e:                      # one channel failing must not block the other
            failed.append(f"Email failed: {e}")
    if webhook:
        try:
            chunks = split_slack(to_slack(markdown_text))
            for c in chunks:
                requests.post(webhook, json={"text": c}, timeout=15).raise_for_status()
            sent.append(f"Posted to Slack ({len(chunks)} message{'s' if len(chunks) != 1 else ''})")
        except Exception as e:
            failed.append(f"Slack failed: {e}")
    if failed and not sent:
        raise RuntimeError("; ".join(failed))
    if sent:
        return "; ".join(sent + failed)
    slug = re.sub(r"[^a-z0-9]+", "_", subject.lower()).strip("_") or "report"
    out = Path("reports") / f"{slug}_{datetime.now():%Y%m%d_%H%M}.md"
    out.parent.mkdir(exist_ok=True)
    out.write_text(markdown_text, encoding="utf-8")
    return f"SMTP and Slack not configured - saved to {out}"
