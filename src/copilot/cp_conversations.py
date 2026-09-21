"""Save / load conversations as JSON files under ~/.config/hailper/conversations."""

import json
import os
import time
import uuid

DIR = os.path.join(os.path.expanduser("~"), ".config", "hailper", "conversations")


def _path(cid):
    return os.path.join(DIR, cid + ".json")


def list_conversations():
    items = []
    try:
        names = os.listdir(DIR)
    except OSError:
        return items
    for name in names:
        if not name.endswith(".json"):
            continue
        cid = name[:-5]
        data = load(cid)
        if not data:
            continue
        items.append({
            "id": cid,
            "name": data.get("name") or "Untitled",
            "updated": data.get("updated", 0),
            "count": len(data.get("messages", []) or []),
        })
    items.sort(key=lambda item: item.get("updated", 0), reverse=True)
    return items


def save(name, messages, meta=None):
    cid = uuid.uuid4().hex[:12]
    data = {
        "id": cid,
        "name": name or "Conversation",
        "created": time.time(),
        "updated": time.time(),
        "messages": list(messages or []),
    }
    if meta:
        data.update(meta)
    _write(cid, data)
    return cid


def update(cid, name, messages, meta=None):
    data = load(cid) or {"id": cid, "created": time.time()}
    data["name"] = name or data.get("name") or "Conversation"
    data["messages"] = list(messages or [])
    data["updated"] = time.time()
    if meta:
        data.update(meta)
    _write(cid, data)
    return cid


def load(cid):
    try:
        with open(_path(cid), "r", encoding="utf-8") as handle:
            return json.load(handle)
    except (ValueError, OSError):
        return None


def delete(cid):
    try:
        os.remove(_path(cid))
        return True
    except OSError:
        return False


def _write(cid, data):
    try:
        os.makedirs(DIR, exist_ok=True)
        tmp = _path(cid) + ".tmp"
        with open(tmp, "w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2)
        os.replace(tmp, _path(cid))
        try:
            os.chmod(_path(cid), 0o600)
        except OSError:
            pass
        return True
    except OSError:
        return False
