"""Multi-step agent mode: a bounded loop of tool directives."""

AGENT_HINT = (
    "You are in AGENT MODE. Work towards the user's goal in small steps using "
    "the tools below. Reply with exactly ONE JSON directive per turn and "
    "nothing else; after each one you will receive a message beginning with "
    "\"Tool result:\" and may take another step. When the task is complete, "
    "reply with a short plain-text summary and NO JSON.\n"
    "Tools:\n"
    "  {\"request\": \"document\"} to read the document text;\n"
    "  {\"edit\": {\"find\": \"<exact text>\", \"text\": \"<replacement>\"}} to "
    "replace a passage;\n"
    "  {\"edit\": {\"action\": \"insert\", \"text\": \"<text>\"}} to insert at "
    "the cursor;\n"
    "  {\"edit\": {\"action\": \"append\", \"text\": \"<text>\"}} to append;\n"
    "  {\"format\": [ {\"target\": \"selection\", \"bold\": true, ... }, ... ]} "
    "to apply formatting/styles/layout.\n"
    "Do not invent text that is not in the document when using \"find\"."
)


def describe(directive):
    if not directive:
        return "step"
    kind = directive[0]
    if kind == "document":
        return "read the document"
    if kind == "edit":
        edit = directive[1] or {}
        if edit.get("find"):
            return "edit text"
        return "edit (%s)" % edit.get("action", "insert")
    if kind == "format":
        return "formatting (%d op%s)" % (len(directive[1]), 
                                         "s" if len(directive[1]) != 1 else "")
    return str(kind)
