from datetime import datetime

from . import config


def _dt(s):
    if not s:
        return None
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def _label_value(labels, key):
    prefix = config.LABEL_PREFIXES[key]
    for l in labels:
        if l.lower().startswith(prefix):
            return l[len(prefix):].strip() or None
    return None


def normalize(raw, days=config.LOOKBACK_DAYS):
    """Turn raw Trello data into tool-agnostic work items (plain dicts)."""
    lists = {l["id"]: l["name"] for l in raw["lists"]}
    order = {l["id"]: i for i, l in enumerate(raw["lists"])}
    members = {m["id"]: m["fullName"] for m in raw["members"]}
    done_ids = {i for i, n in lists.items() if n.lower() in config.DONE_LISTS}
    blocked_list_ids = {i for i, n in lists.items() if n.lower() in config.BLOCKED_LISTS}
    moved_to_done, comments, last_move = {}, {}, {}

    # Oldest first, so "latest" really is the latest whatever order the API returned.
    for a in sorted(raw["actions"], key=lambda a: a["date"]):
        data = a["data"]
        cid = data.get("card", {}).get("id")
        if a["type"] == "updateCard":
            after = data.get("listAfter", {}).get("id")
            before = data.get("listBefore", {}).get("id")
            if after in done_ids:
                moved_to_done[cid] = a["date"]
            if after:
                last_move[cid] = (before, after)
        elif a["type"] == "commentCard":
            comments.setdefault(cid, []).append(data.get("text", ""))

    items = []
    for c in raw["cards"]:
        list_name = lists.get(c["idList"], "Unknown")
        labels = [l["name"] for l in c.get("labels", []) if l.get("name")]
        lname = list_name.lower()
        is_done = lname in config.DONE_LISTS or bool(c.get("dueComplete"))
        blocked = (lname in config.BLOCKED_LISTS
                   or any(l.lower() in config.BLOCKED_LABELS for l in labels))
        if is_done:
            status = "done"
        elif blocked:
            status = "blocked"
        elif lname in config.IN_PROGRESS_LISTS:
            status = "in_progress"
        else:
            status = "todo"
        completed_at = moved_to_done.get(c["id"]) or (c["dateLastActivity"] if is_done else None)

        regressed, note, from_list = False, "", None
        mv = last_move.get(c["id"])
        if mv:
            before, after = mv
            if (before in order and after in order and after == c["idList"]
                    and order[after] < order[before] and before not in blocked_list_ids):
                regressed, from_list = True, lists[before]
                note = f"Moved back: {lists[before]} \u2192 {lists[after]}"

        items.append({
            "id": c["id"], "title": c["name"], "list": list_name, "status": status,
            "stage": "Done" if is_done else config.STAGE_BY_LIST.get(lname, "Backlog"),
            "assignees": [members.get(mid, "?") for mid in c.get("idMembers", [])],
            "due": c.get("due"), "labels": labels, "url": c.get("shortUrl"),
            "last_activity": c.get("dateLastActivity"), "completed_at": completed_at,
            "blocker_note": (comments.get(c["id"]) or [""])[-1] if blocked else "",
            "project": _label_value(labels, "project") or "No project",
            "release": _label_value(labels, "release") or "Unassigned",
            "team": _label_value(labels, "team"), "phase": _label_value(labels, "phase"),
            "sprint": _label_value(labels, "sprint"), "type": _label_value(labels, "type"),
            "severity": _label_value(labels, "severity"),
            "regressed": regressed, "regressed_note": note, "regressed_from": from_list,
        })
    return items
