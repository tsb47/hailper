"""Build a redacted diagnostics report for support/debugging."""

import os
import re

LOG_PATH = os.path.join(os.path.expanduser("~"), ".config", "hailper", "hailper.log")

_SECRET_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_\-]{8,}"),
    re.compile(r"AIza[0-9A-Za-z_\-]{20,}"),
    re.compile(r"xai-[A-Za-z0-9_\-]{8,}"),
    re.compile(r"(?i)(authorization\s*[:=]\s*)(\S+)"),
    re.compile(r"(?i)(api[_-]?key\"?\s*[:=]\s*\"?)([^\"\s,]+)"),
]


def redact(text):
    if not text:
        return ""
    for pattern in _SECRET_PATTERNS:
        text = pattern.sub(lambda m: (m.group(1) if m.groups() else "") + "***REDACTED***", text)
    return text


def _version():
    try:
        here = os.path.dirname(os.path.abspath(__file__))
        root = os.path.dirname(here)
        with open(os.path.join(root, "description.xml"), encoding="utf-8") as handle:
            match = re.search(r'<version value="([^"]+)"', handle.read())
            if match:
                return match.group(1)
    except OSError:
        pass
    return "unknown"


def build(config=None, last_error=None, log_tail=40):
    config = config or {}
    flags = ("allow_edits", "allow_document_access", "allow_formatting",
             "allow_web", "track_changes", "stream", "remember_keys")
    lines = [
        "HaiLPER diagnostics",
        "version: %s" % _version(),
        "provider: %s" % config.get("provider", "?"),
        "model: %s" % ((config.get("providers", {}).get(
            config.get("provider", ""), {}) or {}).get("model", "?")),
        "persona: %s" % config.get("persona", "?"),
        "settings: " + ", ".join(
            "%s=%s" % (flag, config.get(flag)) for flag in flags),
        "last error: %s" % (last_error or "(none)"),
    ]
    try:
        with open(LOG_PATH, "r", encoding="utf-8", errors="replace") as handle:
            tail = handle.readlines()[-log_tail:]
        if tail:
            lines.append("log tail:")
            lines.extend(line.rstrip("\n") for line in tail)
    except OSError:
        lines.append("log tail: (no log file)")
    return redact("\n".join(lines))
