"""Persistent settings for the Copilot extension."""

import json
import os
import stat

import cp_personas
import cp_secrets
from cp_providers import PROVIDERS

CONFIG_DIR = os.path.join(os.path.expanduser("~"), ".config", "hailper")
CONFIG_PATH = os.path.join(CONFIG_DIR, "config.json")
LEGACY_CONFIG_PATH = os.path.join(
    os.path.expanduser("~"), ".config", "libreoffice-copilot", "config.json"
)

DEFAULT_SYSTEM_PROMPT = (
    "You are HaiLPER, an assistant embedded in LibreOffice. "
    "You help the user read, analyse, edit and extend their documents. "
    "Reply with plain, ready-to-paste text unless the user asks for markup. "
    "Never wrap the whole answer in quotation marks or code fences unless the "
    "user explicitly asks for code. Be accurate and do not invent facts."
)


def _provider_defaults():
    result = {}
    for pid, spec in PROVIDERS.items():
        result[pid] = {
            "api_key": "",
            "model": spec["default_model"],
            "base_url": spec["base_url"],
        }
    return result


DEFAULTS = {
    "schema": 4,
    "provider": "ollama",
    "temperature": 0.3,
    "max_tokens": 1024,
    "timeout": 120,
    "system_prompt": DEFAULT_SYSTEM_PROMPT,
    "providers": _provider_defaults(),
    "action_choices": {},
    "allow_edits": True,
    "allow_document_access": True,
    "allow_formatting": True,
    "track_changes": True,
    "remember_keys": True,
    "stream": True,
    "persona": cp_personas.DEFAULT_PERSONA,
    "personas": cp_personas.default_personas(),
    "usage": {"show": True, "prices": {}, "context_limits": {}},
    "agents": {"enabled": False, "max_steps": 8},
    "history": {"persist": True},
}


def _deep_merge(base, override):
    merged = dict(base)
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def load():
    config = json.loads(json.dumps(DEFAULTS))
    path = CONFIG_PATH
    legacy = False
    if not os.path.exists(path) and os.path.exists(LEGACY_CONFIG_PATH):
        path = LEGACY_CONFIG_PATH
        legacy = True
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as handle:
                stored = json.load(handle)
            if isinstance(stored, dict):
                config = _deep_merge(config, stored)
                if legacy:
                    save(config)
        except (ValueError, OSError):
            pass
    if migrate_keys(config):
        save(config)
    return config


def migrate_keys(config):
    """Move any plaintext API keys from the config into the OS keyring.

    Returns True when the config was changed (so it can be re-saved without
    the keys).
    """
    if not cp_secrets.available():
        return False
    changed = False
    for pid, entry in config.get("providers", {}).items():
        if not isinstance(entry, dict):
            continue
        key = (entry.get("api_key") or "").strip()
        if key:
            if cp_secrets.set(pid, key):
                entry["api_key"] = ""
                changed = True
    return changed


def save(config):
    try:
        os.makedirs(CONFIG_DIR, exist_ok=True)
        tmp_path = CONFIG_PATH + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as handle:
            json.dump(config, handle, indent=2)
        os.replace(tmp_path, CONFIG_PATH)
        try:
            os.chmod(CONFIG_PATH, stat.S_IRUSR | stat.S_IWUSR)
        except OSError:
            pass
        return True
    except OSError:
        return False


def active_provider(config):
    """Return (provider_id, spec, api_key, model, base_url) for the active provider."""
    pid = config.get("provider", "ollama")
    spec = PROVIDERS.get(pid) or PROVIDERS["ollama"]
    entry = config.get("providers", {}).get(pid, {})
    api_key = ""
    stored = cp_secrets.get(pid)
    if stored:
        api_key = stored.strip()
    if not api_key:
        # Fall back to the session-only / legacy plaintext value.
        api_key = (entry.get("api_key") or "").strip()
    model = (entry.get("model") or spec["default_model"]).strip()
    base_url = (entry.get("base_url") or spec["base_url"]).strip()
    return pid, spec, api_key, model, base_url
