"""Small JSON-file cache (one file per module), same idea as the reference platform.
The board is fetched once, then every page reads it from the cache."""
import json
import threading
from datetime import datetime, timezone
from pathlib import Path

from . import config
from .normalize import normalize
from .trello_client import fetch_board

_lock = threading.Lock()


def _path(name):
    return Path(config.CACHE_DIR) / f"cache_{name}.json"


def save(name, data):
    p = _path(name)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(data), encoding="utf-8")
    tmp.replace(p)


def load(name):
    p = _path(name)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def refresh_board(board_id=None):
    with _lock:
        items = normalize(fetch_board(board_id))
        if config.EPICS_ONLY:
            items = [i for i in items if (i["type"] or "").lower() == "epic"]
        payload = {"fetched_at": datetime.now(timezone.utc).isoformat(), "items": items}
        save("board", payload)
        return payload


def get_board(refresh=False, board_id=None):
    if not refresh:
        cached = load("board")
        if cached:
            return cached
    return refresh_board(board_id)
