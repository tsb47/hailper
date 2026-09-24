"""Compress older conversation turns into a short summary."""

SUMMARY_SYSTEM = (
    "You compress chat conversations. Produce a terse summary (at most 120 "
    "words) of the key facts, decisions, terminology and user preferences, so "
    "they can be recalled later. No preamble, no headings."
)


def summarize(provider_id, api_key, model, base_url, messages, timeout=60):
    """Return a short summary of the given messages (plain text)."""
    import cp_providers
    transcript = "\n".join(
        "%s: %s" % (message.get("role", "?"), message.get("content", ""))
        for message in messages if message.get("content"))
    if not transcript.strip():
        return ""
    return cp_providers.chat(
        provider_id, api_key, model, base_url,
        [{"role": "user",
          "content": "Summarise this conversation so far:\n\n" + transcript[:12000]}],
        system=SUMMARY_SYSTEM, temperature=0.2, max_tokens=300, timeout=timeout)
