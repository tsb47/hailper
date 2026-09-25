"""Token estimation, model context windows, budgeting and relevance ranking."""

import math
import re

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


_WORD = re.compile(r"[A-Za-z0-9']+")
_URL_RE = re.compile(r"^https?://\S+$", re.IGNORECASE)
_EMAIL_RE = re.compile(r"^[\w.+-]+@[\w-]+\.[\w.-]+$")


def _tokenize(text):
    return [word.lower() for word in _WORD.findall(text or "")]


def word_count(text):
    return len((text or "").split())


def looks_url(text):
    return bool(_URL_RE.match((text or "").strip()))


def looks_email(text):
    return bool(_EMAIL_RE.match((text or "").strip()))


def budget_tokens(provider_id, model, config=None, reserve=1200, ratio=None):
    """Tokens available for the prompt (a fraction of the model window)."""
    if ratio is None:
        ratio = float(((config or {}).get("context") or {}).get(
            "budget_ratio", 0.55))
    window = context_window(provider_id, model, config)
    return max(512, int(window * ratio) - reserve)


def select_relevant(instruction, paragraphs, k=6):
    """Rank paragraphs against the instruction with a BM25-style score.

    Returns a list of (index, text, score), highest first, score > 0 only.
    """
    query = _tokenize(instruction)
    if not query or not paragraphs:
        return []
    docs = [_tokenize(p) for p in paragraphs]
    count = len(docs)
    avg = sum(len(doc) for doc in docs) / float(max(1, count))
    df = {}
    for doc in docs:
        for term in set(doc):
            df[term] = df.get(term, 0) + 1

    def idf(term):
        return math.log(1 + (count - df.get(term, 0) + 0.5)
                        / (df.get(term, 0) + 0.5))

    k1, b = 1.2, 0.75
    scored = []
    for index, doc in enumerate(docs):
        if not doc:
            continue
        tf = {}
        for term in doc:
            tf[term] = tf.get(term, 0) + 1
        score = 0.0
        for term in set(query):
            if term not in tf:
                continue
            denom = tf[term] + k1 * (1 - b + b * len(doc) / (avg or 1.0))
            score += idf(term) * (tf[term] * (k1 + 1)) / denom
        if score > 0:
            scored.append((index, paragraphs[index], score))
    scored.sort(key=lambda item: item[2], reverse=True)
    return scored[:max(1, int(k))]


def fit_blocks(blocks, budget):
    """Assemble (name, text) blocks in priority order within a token budget.

    Returns (text, used_tokens).
    """
    out = []
    used = 0
    for _name, text in blocks:
        if not text:
            continue
        remaining = budget - used
        if remaining <= 0:
            break
        cost = estimate_tokens(text)
        if cost <= remaining:
            out.append(text)
            used += cost
        else:
            trimmed = fit_to_budget(text, remaining)
            out.append(trimmed)
            used += estimate_tokens(trimmed)
            break
    return "\n\n".join(out), used


def trim_history(messages, budget, keep_turns=8):
    """Keep the most recent messages within a token budget.

    Returns (messages, used_tokens). Older messages are added back from newest
    to oldest while the budget allows.
    """
    messages = list(messages or [])
    keep = max(1, int(keep_turns or 8))
    tail = messages[-keep:]
    head = messages[:-keep]

    def cost(message):
        content = message.get("content", "") if isinstance(message, dict) else str(message)
        return estimate_tokens(content)

    used = sum(cost(message) for message in tail)
    kept_head = []
    for message in reversed(head):
        if used + cost(message) <= budget:
            kept_head.insert(0, message)
            used += cost(message)
        else:
            break
    return kept_head + tail, used
