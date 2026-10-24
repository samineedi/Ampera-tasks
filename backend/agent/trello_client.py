import os
from datetime import datetime, timedelta, timezone

import requests

from .config import LOOKBACK_DAYS

BASE = "https://api.trello.com/1"


def fetch_board(board_id=None, days=LOOKBACK_DAYS):
    """Return raw board data: {lists, cards, members, actions}."""
    key, token = os.getenv("TRELLO_API_KEY"), os.getenv("TRELLO_TOKEN")
    board_id = board_id or os.getenv("TRELLO_BOARD_ID")
    if not (key and token and board_id):
        raise RuntimeError("Missing Trello settings: TRELLO_API_KEY, TRELLO_TOKEN and TRELLO_BOARD_ID are required.")

    auth = {"key": key, "token": token}
    since = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%S.000Z")

    def get(path, **params):
        r = requests.get(f"{BASE}{path}", params={**auth, **params}, timeout=30)
        r.raise_for_status()
        return r.json()

    actions, before = [], None
    for _ in range(10):                       # page through history (Trello returns max 1000 per call)
        params = dict(filter="updateCard:idList,commentCard", since=since, limit=1000)
        if before:
            params["before"] = before
        page = get(f"/boards/{board_id}/actions", **params)
        actions.extend(page)
        if len(page) < 1000:
            break
        before = page[-1]["id"]

    return {
        "lists": get(f"/boards/{board_id}/lists", fields="name"),
        "cards": get(f"/boards/{board_id}/cards", fields="name,idList,due,dueComplete,labels,idMembers,dateLastActivity,shortUrl"),
        "members": get(f"/boards/{board_id}/members", fields="fullName"),
        "actions": actions,
    }
