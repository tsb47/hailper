"""Personas: system-prompt presets that also set model/temperature/actions."""

DEFAULT_PERSONA = "general"

BUILTIN = [
    {
        "id": "general",
        "name": "General",
        "system_prompt": "",
        "model": "",
        "temperature": None,
        "actions": None,
        "starters": ["Summarise this document",
                     "Explain the selected text",
                     "Draft a short reply to this"],
    },
    {
        "id": "editor",
        "name": "Editor",
        "system_prompt": (
            "You are a meticulous copy editor. Improve clarity, grammar, "
            "punctuation and flow while preserving the author's voice and "
            "meaning. Prefer plain English and consistent style."),
        "model": "",
        "temperature": 0.2,
        "actions": None,
        "starters": ["Copy-edit the selection",
                     "Tighten this paragraph",
                     "Make this plainer English"],
    },
    {
        "id": "reviewer",
        "name": "Reviewer",
        "system_prompt": (
            "You are a careful, sceptical reviewer. Identify risks, "
            "inconsistencies, ambiguities, missing information and anything "
            "that could be misunderstood. Be specific and concise."),
        "model": "",
        "temperature": 0.3,
        "actions": ["chat", "summarize", "proofread", "explain"],
        "starters": ["What is wrong with this?",
                     "List inconsistencies",
                     "What is missing?"],
    },
    {
        "id": "researcher",
        "name": "Researcher",
        "system_prompt": (
            "You are a research assistant. Explain concepts clearly, compare "
            "viewpoints and give balanced, well-structured answers. Say when "
            "you are unsure rather than inventing facts."),
        "model": "",
        "temperature": 0.5,
        "actions": None,
        "starters": ["Explain this in depth",
                     "Compare the options",
                     "Give background and context"],
    },
]


def default_personas():
    import copy
    return copy.deepcopy(BUILTIN)


def get_personas(config):
    personas = None
    if isinstance(config, dict):
        personas = config.get("personas")
    if not personas:
        return default_personas()
    return personas


def get_persona(config, persona_id):
    for persona in get_personas(config):
        if persona.get("id") == persona_id:
            return persona
    personas = get_personas(config)
    if personas:
        return personas[0]
    return BUILTIN[0]


def active(config):
    pid = DEFAULT_PERSONA
    if isinstance(config, dict):
        pid = config.get("persona") or DEFAULT_PERSONA
    return get_persona(config, pid)


def allows(persona, action_key):
    allowed = (persona or {}).get("actions")
    return allowed is None or action_key in allowed


def starters(config, persona_id=None):
    persona = get_persona(config, persona_id) if persona_id \
        else active(config)
    result = list(persona.get("starters") or [])
    return result
