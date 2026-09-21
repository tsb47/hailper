"""Prompt templates and per-action metadata."""

import json

REWRITE_STYLES = [
    "clearer and more concise",
    "more professional and formal",
    "more friendly and conversational",
    "more persuasive and confident",
    "simpler, plain English",
    "expand with more detail",
    "fix grammar and spelling only",
]

TRANSLATE_LANGUAGES = [
    "English",
    "Māori",
    "French",
    "German",
    "Spanish",
    "Italian",
    "Portuguese",
    "Dutch",
    "Japanese",
    "Chinese (Simplified)",
    "Korean",
    "Arabic",
    "Hindi",
    "Russian",
]

# Languages offered directly in the right-click submenu (the rest via "More...")
TRANSLATE_TOP = ["English", "French", "German", "Spanish", "Japanese"]

SUMMARIZE_FORMATS = [
    "Key points",
    "Short paragraph",
    "TL;DR (one line)",
    "Executive summary",
    "Bullet list",
    "Action items",
    "Q&A",
]
LENGTHS = ["Short", "Medium", "Detailed"]
REWRITE_LENGTHS = ["Shorter", "Same", "Longer"]
CONTINUE_LENGTHS = ["One sentence", "One paragraph", "Two paragraphs", "Three paragraphs"]
TRANSLATE_REGISTERS = ["Neutral", "Formal", "Informal"]
PROOFREAD_CATEGORIES = ["All", "Spelling & grammar", "Style & clarity", "Conciseness"]
PROOFREAD_SEVERITIES = ["Errors only", "Errors + style"]

PROOFREAD_INSTRUCTION = (
    "Proofread the following text. Your ENTIRE reply must be a single JSON "
    "object with no other text, no code fences and no commentary, in exactly "
    "this shape:\n"
    '{"suggestions": [{"original": "<text exactly as it appears>", '
    '"replacement": "<corrected text>", "reason": "<short explanation>"}]}\n'
    "Each \"original\" must be copied verbatim from the text so it can be found "
    "and replaced. List spelling, grammar, punctuation and clarity problems. "
    "If there are no problems, reply {\"suggestions\": []}."
)

# Each action: primary (apply key, label), up to five secondary buttons, and up
# to two choices rendered as dropdowns.
ACTIONS = {
    "chat": {
        "title": "Chat with AI",
        "instruction": "",
        "prompt_label": "Message:",
        "result_label": "Conversation:",
        "auto_run": False,
        "primary": ("insert", "Insert reply"),
        "buttons": [
            ("copy", "Copy"),
            ("comment", "Comment"),
            ("clear", "New chat"),
            ("close", "Close"),
        ],
        "choices": [],
    },
    "summarize": {
        "title": "Summarize",
        "instruction": "Summarize the following text.",
        "prompt_label": "Instruction:",
        "result_label": "Summary:",
        "auto_run": True,
        "primary": ("newdoc", "New document"),
        "buttons": [
            ("insert", "Insert"),
            ("append", "Append"),
            ("comment", "Comment"),
            ("copy", "Copy"),
            ("close", "Close"),
        ],
        "choices": [
            {"key": "format", "label": "Format", "values": SUMMARIZE_FORMATS,
             "default": "Key points"},
            {"key": "length", "label": "Length", "values": LENGTHS,
             "default": "Medium"},
        ],
    },
    "rewrite": {
        "title": "Rewrite / Improve",
        "instruction": "Rewrite the following text.",
        "prompt_label": "Instruction:",
        "result_label": "Rewritten text:",
        "auto_run": True,
        "primary": ("replace", "Replace selection"),
        "buttons": [
            ("diff", "Diff"),
            ("insert", "Insert"),
            ("append", "Append"),
            ("copy", "Copy"),
            ("close", "Close"),
        ],
        "choices": [
            {"key": "style", "label": "Style", "values": REWRITE_STYLES,
             "default": REWRITE_STYLES[0]},
            {"key": "length", "label": "Length", "values": REWRITE_LENGTHS,
             "default": "Same"},
        ],
    },
    "continue": {
        "title": "Continue Writing",
        "instruction": "Continue writing from where the text ends.",
        "prompt_label": "Instruction:",
        "result_label": "Continuation:",
        "auto_run": True,
        "primary": ("insert", "Insert at cursor"),
        "buttons": [
            ("append", "Append to end"),
            ("comment", "Comment"),
            ("copy", "Copy"),
            ("close", "Close"),
        ],
        "choices": [
            {"key": "length", "label": "Length", "values": CONTINUE_LENGTHS,
             "default": "One paragraph"},
        ],
    },
    "translate": {
        "title": "Translate",
        "instruction": "Translate the following text.",
        "prompt_label": "Instruction:",
        "result_label": "Translation:",
        "auto_run": True,
        "primary": ("replace", "Replace selection"),
        "buttons": [
            ("newdoc", "New document"),
            ("insert", "Insert"),
            ("append", "Append"),
            ("copy", "Copy"),
            ("close", "Close"),
        ],
        "choices": [
            {"key": "lang", "label": "Language", "values": TRANSLATE_LANGUAGES,
             "default": "English"},
            {"key": "register", "label": "Register", "values": TRANSLATE_REGISTERS,
             "default": "Neutral"},
        ],
    },
    "proofread": {
        "title": "Proofread / Review",
        "instruction": PROOFREAD_INSTRUCTION,
        "display_instruction": "Check spelling, grammar and clarity.",
        "prompt_label": "Instruction:",
        "result_label": "Suggestions:",
        "auto_run": True,
        "primary": ("review", "Review suggestions"),
        "buttons": [
            ("adoptall", "Adopt all"),
            ("newdoc", "Report to document"),
            ("insert", "Insert report"),
            ("comment", "Comment"),
            ("close", "Close"),
        ],
        "choices": [
            {"key": "categories", "label": "Check", "values": PROOFREAD_CATEGORIES,
             "default": "All"},
            {"key": "severity", "label": "Level", "values": PROOFREAD_SEVERITIES,
             "default": "Errors + style"},
        ],
    },
    "explain": {
        "title": "Explain",
        "instruction": "Explain the following content clearly and concisely for a non-expert.",
        "prompt_label": "Instruction:",
        "result_label": "Explanation:",
        "auto_run": True,
        "primary": ("newdoc", "New document"),
        "buttons": [
            ("insert", "Insert"),
            ("append", "Append"),
            ("comment", "Comment"),
            ("copy", "Copy"),
            ("close", "Close"),
        ],
        "choices": [],
    },
    "notes": {
        "title": "Speaker Notes",
        "instruction": "Write concise speaker notes for the following slide content.",
        "prompt_label": "Instruction:",
        "result_label": "Speaker notes:",
        "auto_run": True,
        "primary": ("insert", "Insert"),
        "buttons": [
            ("copy", "Copy"),
            ("close", "Close"),
        ],
        "choices": [],
    },
    "custom": {
        "title": "Ask About Selection",
        "instruction": "Describe what you want me to do with the text below:",
        "prompt_label": "Instruction:",
        "result_label": "Result:",
        "auto_run": False,
        "primary": ("replace", "Replace selection"),
        "buttons": [
            ("insert", "Insert"),
            ("append", "Append"),
            ("comment", "Comment"),
            ("copy", "Copy"),
            ("close", "Close"),
        ],
        "choices": [],
    },
}

MAX_INPUT_CHARS = 16000

DOCUMENT_REQUEST_HINT = (
    "If you need the contents of the user's document to answer, reply with "
    "exactly this JSON and nothing else: {\"request\": \"document\"}. "
    "After you receive the document, answer normally."
)

EDIT_HINT = (
    "You may change the user's document by replying with exactly one of these "
    "JSON objects and nothing else:\n"
    "  {\"edit\": {\"find\": \"<exact existing text>\", \"text\": \"<replacement>\"}} "
    "to replace a specific passage wherever it appears;\n"
    "  {\"edit\": {\"action\": \"insert\", \"text\": \"<text>\"}} to insert at "
    "the cursor;\n"
    "  {\"edit\": {\"action\": \"append\", \"text\": \"<text>\"}} to add to the "
    "end of the document.\n"
    "Only do this when the user asks you to change the document; otherwise "
    "answer normally. When replacing a passage, copy the existing text exactly "
    "so it can be found."
)


def parse_directive(text):
    """Return ('document', None) or ('edit', {action, text}) or None."""
    if not text:
        return None
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`").strip()
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:].strip()
    candidates = [cleaned]
    candidates.extend(_json_objects(cleaned))
    for candidate in candidates:
        try:
            data = json.loads(candidate)
        except ValueError:
            continue
        if not isinstance(data, dict):
            continue
        if data.get("request") == "document":
            return ("document", None)
        edit = data.get("edit")
        if isinstance(edit, dict) and edit.get("text"):
            return ("edit", {
                "action": str(edit.get("action", "insert")).strip(),
                "find": str(edit.get("find", "")).strip(),
                "text": str(edit["text"]),
            })
        fmt = data.get("format")
        if isinstance(fmt, dict):
            return ("format", [fmt])
        if isinstance(fmt, list):
            ops = [item for item in fmt if isinstance(item, dict)]
            if ops:
                return ("format", ops)
    return None


def _truncate(text):
    if text is None:
        return ""
    if len(text) <= MAX_INPUT_CHARS:
        return text
    return text[:MAX_INPUT_CHARS] + "\n\n[... rest of document truncated ...]"


_CUSTOM_ACTIONS = {}


def register_custom_actions(mapping):
    global _CUSTOM_ACTIONS
    _CUSTOM_ACTIONS = dict(mapping or {})


def custom_actions():
    return dict(_CUSTOM_ACTIONS)


def all_actions():
    merged = dict(ACTIONS)
    merged.update(_CUSTOM_ACTIONS)
    return merged


def action_meta(action):
    if action in _CUSTOM_ACTIONS:
        return _CUSTOM_ACTIONS[action]
    return ACTIONS.get(action, ACTIONS["chat"])


def default_choices(action):
    result = {}
    for choice in action_meta(action).get("choices", []):
        result[choice["key"]] = choice.get("default")
    return result


def _json_objects(text):
    """Yield top-level balanced {...} substrings, ignoring braces in strings."""
    objects = []
    depth = 0
    start = -1
    in_string = False
    escaped = False
    for index, char in enumerate(text):
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            if depth == 0:
                start = index
            depth += 1
        elif char == "}":
            if depth > 0:
                depth -= 1
                if depth == 0 and start != -1:
                    objects.append(text[start:index + 1])
                    start = -1
    return objects


def parse_suggestions(text):
    """Parse a proofread JSON reply into a list of suggestion dicts."""
    if not text:
        return []
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`").strip()
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:].strip()
    data = None
    candidates = [cleaned]
    candidates.extend(_json_objects(cleaned))
    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
        except ValueError:
            continue
        if isinstance(parsed, dict) and isinstance(parsed.get("suggestions"), list):
            data = parsed
            break
    if data is None:
        return []
    items = data.get("suggestions")
    if not isinstance(items, list):
        return []
    result = []
    for item in items:
        if not isinstance(item, dict):
            continue
        original = str(item.get("original", "")).strip()
        replacement = str(item.get("replacement", "")).strip()
        reason = str(item.get("reason", "")).strip()
        if original and original != replacement:
            result.append({
                "original": original,
                "replacement": replacement,
                "reason": reason,
            })
    return result


def format_suggestions(suggestions):
    lines = []
    for index, item in enumerate(suggestions, 1):
        lines.append("%d. %s" % (index, item.get("reason") or "Suggested change"))
        lines.append("   was:   %s" % item["original"])
        lines.append("   fix:   %s" % item["replacement"])
        lines.append("")
    return "\n".join(lines).strip()


def _instruction_for(action, instruction, choices):
    choices = choices or {}
    instruction = (instruction or "").strip()

    if action == "summarize":
        return "Summarize the following text. Format: %s. Length: %s." % (
            choices.get("format", "Key points"), choices.get("length", "Medium"))
    if action == "rewrite":
        return ("Rewrite the following text so it is %s. Length: %s. "
                "Return only the rewritten text, with no commentary." % (
                    choices.get("style", REWRITE_STYLES[0]),
                    choices.get("length", "Same")))
    if action == "continue":
        return ("Continue writing naturally from where the text ends. Length: %s. "
                "Match the tone and style. Return only the continuation." % (
                    choices.get("length", "One paragraph")))
    if action == "translate":
        return ("Translate the following text into %s. Register: %s. "
                "Return only the translation." % (
                    choices.get("lang", "English"),
                    choices.get("register", "Neutral")))
    if action == "proofread":
        return (PROOFREAD_INSTRUCTION +
                "\nFocus: %s. Severity: %s." % (
                    choices.get("categories", "All"),
                    choices.get("severity", "Errors + style")))
    return instruction


def build_messages(action, text, instruction, choices=None, context=None):
    messages = []
    system_extra = ""

    if action == "chat":
        if context:
            system_extra = (
                "The user is working on a LibreOffice document. Here is the current "
                "document content, which you may refer to if relevant:\n\n---\n%s\n---"
                % _truncate(context)
            )
        messages.append({"role": "user", "content": instruction})
        return messages, system_extra

    body = _instruction_for(action, instruction, choices)
    text = _truncate(text)
    if text.strip():
        body += "\n\n---\n%s\n---" % text
    messages.append({"role": "user", "content": body})
    return messages, system_extra
