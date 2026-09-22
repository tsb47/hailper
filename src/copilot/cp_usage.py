"""Token usage recording and cost estimation.

Prices are USD per 1,000,000 tokens and are approximate; users can override
them per provider/model in ``usage.prices`` in the config.
"""

# (input, output) USD per 1M tokens, matched by model-name substring.
_PRICES = [
    ("gpt-4o-mini", (0.15, 0.60)),
    ("gpt-4.1-mini", (0.40, 1.60)),
    ("gpt-4.1-nano", (0.10, 0.40)),
    ("gpt-4.1", (2.00, 8.00)),
    ("gpt-4o", (2.50, 10.00)),
    ("o4-mini", (1.10, 4.40)),
    ("o3-mini", (1.10, 4.40)),
    ("deepseek-reasoner", (0.55, 2.19)),
    ("deepseek", (0.27, 1.10)),
    ("claude-3-5-haiku", (0.80, 4.00)),
    ("claude-3-7-sonnet", (3.00, 15.00)),
    ("claude-sonnet", (3.00, 15.00)),
    ("claude-haiku", (0.80, 4.00)),
    ("claude-opus", (15.00, 75.00)),
    ("gemini-2.5-pro", (1.25, 10.00)),
    ("gemini-2.5-flash", (0.30, 2.50)),
    ("gemini-2.0-flash", (0.10, 0.40)),
    ("gemini-1.5-pro", (1.25, 5.00)),
    ("gemini", (0.30, 1.20)),
    ("grok-3-mini", (0.30, 0.50)),
    ("grok-3", (3.00, 15.00)),
    ("grok", (2.00, 10.00)),
    ("mistral-large", (2.00, 6.00)),
    ("mistral", (0.20, 0.60)),
    ("llama-3.3-70b", (0.59, 0.79)),
    ("llama-3.1-70b", (0.59, 0.79)),
    ("llama-3.1-8b", (0.05, 0.08)),
    ("qwen-plus", (0.40, 1.20)),
    ("qwen", (0.30, 0.90)),
    ("kimi", (0.60, 2.50)),
    ("moonshot", (0.60, 2.50)),
    ("glm", (0.60, 2.20)),
    ("command-r", (0.15, 0.60)),
]

LOCAL_PROVIDERS = ("ollama", "lmstudio", "llamacpp", "atomic", "llmgateway")


def price_for(provider_id, model, config=None):
    overrides = {}
    if isinstance(config, dict):
        overrides = (config.get("usage") or {}).get("prices") or {}
    for key in ("%s/%s" % (provider_id, model), model):
        if key and key in overrides:
            value = overrides[key]
            if isinstance(value, dict):
                return (float(value.get("in", 0)), float(value.get("out", 0)))
            if isinstance(value, (list, tuple)) and len(value) == 2:
                return (float(value[0]), float(value[1]))
    name = (model or "").lower()
    for needle, prices in _PRICES:
        if needle in name:
            return prices
    if provider_id in LOCAL_PROVIDERS:
        return (0.0, 0.0)
    return (0.0, 0.0)


def cost(provider_id, model, usage, config=None):
    if not usage:
        return 0.0
    inp, out = price_for(provider_id, model, config)
    return ((usage.get("input", 0) or 0) * inp
            + (usage.get("output", 0) or 0) * out) / 1000000.0


def is_local(provider_id):
    return provider_id in LOCAL_PROVIDERS


def money(value):
    if value <= 0:
        return "free"
    if value < 0.01:
        return "$%.4f" % value
    if value < 1:
        return "$%.3f" % value
    return "$%.2f" % value


def format_line(provider_id, model, usage, session, context_window=None,
                config=None):
    """Build the compact usage line shown under the status."""
    usage = usage or {}
    inp = usage.get("input", 0) or 0
    out = usage.get("output", 0) or 0
    total = inp + out
    session = session or {}
    session_total = (session.get("tokens", 0) or 0)
    session_cost = session.get("cost", 0.0) or 0.0
    parts = ["last %s tok (in %s / out %s)"
             % (_group(total), _group(inp), _group(out))]
    if context_window:
        parts.append("%s / %s ctx" % (_group(total), _group(context_window)))
    if is_local(provider_id):
        parts.append("local \u00b7 free")
    else:
        value = cost(provider_id, model, usage, config)
        parts.append(money(value) if value > 0 else "$0.00")
    tail = "session %s tok" % _group(session_total)
    if not is_local(provider_id) and session_cost > 0:
        tail += " / %s" % money(session_cost)
    return "  \u00b7  ".join(parts) + "   \u2014   " + tail


def _group(number):
    try:
        return "{:,}".format(int(number))
    except (TypeError, ValueError):
        return str(number)
