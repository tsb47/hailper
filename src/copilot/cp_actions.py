"""User-defined custom actions, stored in ~/.config/hailper/actions.json."""

import json
import os
import re

ACTIONS_PATH = os.path.join(os.path.expanduser("~"), ".config", "hailper",
                            "actions.json")

DEFAULT_BUTTONS = [
    ("insert", "Insert"),
    ("append", "Append"),
    ("comment", "Comment"),
    ("copy", "Copy"),
    ("close", "Close"),
]


def _slug(text):
    slug = re.sub(r"[^a-z0-9]+", "_", str(text or "").lower()).strip("_")
    return slug or "action"


def normalize(action):
    title = str(action.get("title") or action.get("name") or "Custom action").strip()
    action_id = str(action.get("id") or ("custom_" + _slug(title))).strip()
    scope = str(action.get("scope") or "selection").lower()
    if scope not in ("selection", "document"):
        scope = "selection"
    primary = action.get("primary")
    if not (isinstance(primary, (list, tuple)) and len(primary) == 2):
        primary = ("insert", "Insert") if scope == "document" \
            else ("replace", "Replace selection")
    choices = action.get("choices")
    if not isinstance(choices, list):
        choices = []
    return {
        "id": action_id,
        "title": title,
        "instruction": str(action.get("instruction") or action.get("prompt") or ""),
        "scope": scope,
        "auto_run": bool(action.get("auto_run", True)),
        "primary": [str(primary[0]), str(primary[1])],
        "choices": choices,
        "persona": str(action.get("persona") or ""),
    }


def load():
    try:
        with open(ACTIONS_PATH, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (ValueError, OSError):
        return []
    actions = data.get("actions") if isinstance(data, dict) else data
    if not isinstance(actions, list):
        return []
    return [normalize(item) for item in actions if isinstance(item, dict)]


def save(actions):
    try:
        os.makedirs(os.path.dirname(ACTIONS_PATH), exist_ok=True)
        tmp = ACTIONS_PATH + ".tmp"
        with open(tmp, "w", encoding="utf-8") as handle:
            json.dump({"version": 1, "actions": actions}, handle, indent=2)
        os.replace(tmp, ACTIONS_PATH)
        return True
    except OSError:
        return False


def as_meta(action):
    """Convert a stored action into the ACTIONS meta shape."""
    return {
        "title": action["title"],
        "instruction": action["instruction"],
        "prompt_label": "Instruction:",
        "result_label": action["title"] + ":",
        "auto_run": action["auto_run"],
        "primary": tuple(action["primary"]),
        "buttons": list(DEFAULT_BUTTONS),
        "choices": action["choices"],
        "scope": action["scope"],
        "custom": True,
    }


def register():
    """Load actions.json and register them with cp_prompts."""
    import cp_prompts
    mapping = {}
    for action in load():
        if action["id"] in cp_prompts.ACTIONS:  # never shadow built-ins
            continue
        mapping[action["id"]] = as_meta(action)
    cp_prompts.register_custom_actions(mapping)
    return mapping


def export_file(path, actions):
    with open(path, "w", encoding="utf-8") as handle:
        json.dump({"version": 1, "actions": actions}, handle, indent=2)
    return True


def import_file(path):
    with open(path, "r", encoding="utf-8") as handle:
        data = json.load(handle)
    actions = data.get("actions") if isinstance(data, dict) else data
    if not isinstance(actions, list):
        return []
    return [normalize(item) for item in actions if isinstance(item, dict)]
