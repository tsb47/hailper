"""Token estimation, model context windows, and budget-aware truncation."""

import math

# Approximate context windows (tokens) by model-name substring; overridden by
# the user's ``usage.context_limits`` config.  Longest/most specific keys should
# be listed first.
_LIMITS = [
    ("gemini-2.5-pro", 1048576),
    ("gemini", 1000000),
    ("gpt-4.1", 1047576),
    ("gpt-4o", 128000),
    ("o4", 200000),
    ("o3", 200000),
    ("claude", 200000),
    ("deepseek", 65536),
    ("grok", 131072),
    ("llama-3.3", 131072),
    ("llama-3.1", 131072),
    ("qwen", 131072),
    ("mistral", 131072),
    ("mixtral", 32768),
    ("kimi", 131072),
    ("moonshot", 131072),
    ("glm", 131072),
    ("command-r", 131072),
    ("phi", 16384),
]

LOCAL_DEFAULT = 8192
UNKNOWN_DEFAULT = 32768


def estimate_tokens(text):
    """Rough token estimate (~4 characters per token)."""
    if not text:
        return 0
    return max(1, int(math.ceil(len(text) / 4.0)))


def context_window(provider_id, model, config=None):
    overrides = {}
    if isinstance(config, dict):
        overrides = (config.get("usage") or {}).get("context_limits") or {}
    for key in ("%s/%s" % (provider_id, model), model):
        if key and key in overrides:
            try:
                return int(overrides[key])
            except (TypeError, ValueError):
                pass
    name = (model or "").lower()
    for needle, limit in _LIMITS:
        if needle in name:
            return limit
    if provider_id in ("ollama", "lmstudio", "llamacpp", "atomic", "llmgateway"):
        return LOCAL_DEFAULT
    return UNKNOWN_DEFAULT


def fit_to_budget(text, budget_tokens, note="\n\n[... content trimmed to fit ...]"):
    """Truncate text (keeping the start and end) to roughly budget_tokens."""
    if not text:
        return ""
    budget_chars = max(200, int(budget_tokens) * 4)
    if len(text) <= budget_chars:
        return text
    head = int(budget_chars * 0.7)
    tail = budget_chars - head
    return text[:head] + note + (text[-tail:] if tail > 0 else "")
