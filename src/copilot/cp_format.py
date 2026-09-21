"""Apply formatting / layout operations to a Writer document via UNO.

The model emits a ``{"format": [ ...ops... ]}`` directive.  Each op is a small
dict with an optional ``target`` (``selection`` | ``paragraph`` | ``document``)
or ``find`` and one or more formatting keys.  Everything is wrapped in a single
undo context so the whole batch can be undone at once.
"""

try:
    import uno
except Exception:  # pragma: no cover - uno is present inside LibreOffice
    uno = None

WRITER = "writer"

# Integer values match the com.sun.star enums; using literals keeps this module
# importable without pulling in the whole type library.
_CHAR_WEIGHT_BOLD = 150.0
_CHAR_WEIGHT_NORMAL = 100.0
_FONT_SLANT_ITALIC = 2
_PARAGRAPH_ALIGN = {"left": 0, "right": 1, "justify": 2, "block": 2, "center": 3}
_UNDERLINE = {"single": 1, "double": 2, "dotted": 3, "dash": 4, "wave": 8}
_LINE_SPACING_PROP = 0

_PAGE_KEYS = ("page_margins", "landscape", "page_style")


def _cm(value):
    try:
        return int(round(float(value) * 1000))  # 1 cm = 1000 * (1/100 mm)
    except (TypeError, ValueError):
        return None


def _rgb(value):
    try:
        text = str(value).strip().lstrip("#")
        if len(text) == 6:
            return int(text, 16)
        if len(text) == 8:  # already 0xAARRGGBB-ish
            return int(text, 16) & 0xFFFFFF
    except (TypeError, ValueError):
        pass
    return None


def requires_confirmation(ops):
    for op in ops:
        if not isinstance(op, dict):
            continue
        if str(op.get("target", "")).lower() == "document":
            return True
        if any(key in op for key in _PAGE_KEYS):
            return True
    return False


def style_names(doc):
    """Return (paragraph, character, page) style name lists."""
    result = ([], [], [])
    try:
        families = doc.getStyleFamilies()
    except Exception:
        return result
    for index, family in enumerate(("ParagraphStyles", "CharacterStyles",
                                    "PageStyles")):
        try:
            container = families.getByName(family)
            if container is None:
                continue
            names = list(container.getElementNames())
            names.sort()
            result[index].append(names)
        except Exception:
            continue
    return (result[0][0] if result[0] else [],
            result[1][0] if result[1] else [],
            result[2][0] if result[2] else [])


def format_prompt(doc):
    para, char, page = style_names(doc)
    def _show(names):
        return ", ".join(names[:60]) + (" ..." if len(names) > 60 else "")
    return (
        "You may change formatting, styles and page layout by replying with "
        "exactly one JSON object and nothing else:\n"
        '  {"format": [ <op>, <op>, ... ]}\n'
        "Each op may set a \"target\" of \"selection\" (default), \"paragraph\", "
        "\"document\", or \"find\" with a \"find\" string (and optional "
        '"all": true). Supported keys:\n'
        "  character: bold, italic, underline (true|single|double|dotted|dash|"
        "wave), strikeout, font, size (pt), color, highlight (hex RRGGBB);\n"
        "  paragraph: para_style, char_style, align (left|center|right|justify), "
        "space_before/space_after (cm), line_spacing (1, 1.5, 2), "
        "indent_first/indent_left/indent_right (cm), keep_together;\n"
        "  page: page_style, landscape (bool), page_margins "
        "({top,bottom,left,right} in cm);\n"
        '  table: "insert_table": {"rows": n, "cols": n}.\n'
        "Use only existing style names. Example: "
        '{"format": [{"target": "selection", "para_style": "Heading 1"}, '
        '{"target": "paragraph", "align": "center"}]}\n'
        "Available paragraph styles: %s\n"
        "Available character styles: %s\n"
        "Available page styles: %s\n"
        "Only do this when the user asks you to format or lay out the document."
        % (_show(para), _show(char), _show(page))
    )


# --------------------------------------------------------------- targets
def _target_cursors(doc_ctx, op):
    doc = doc_ctx.doc
    text = doc.getText()
    find = op.get("find")
    if find:
        cursors = []
        try:
            descriptor = doc.createSearchDescriptor()
            descriptor.SearchString = str(find)
            descriptor.SearchCaseSensitive = False
            found = doc.findFirst(descriptor)
            everything = bool(op.get("all", True))
            while found is not None:
                cursors.append(text.createTextCursorByRange(found))
                if not everything:
                    break
                found = doc.findNext(found.getEnd(), descriptor)
        except Exception:
            return []
        return cursors
    target = str(op.get("target", "selection")).lower()
    if target == "document":
        cursor = text.createTextCursor()
        cursor.gotoStart(False)
        cursor.gotoEnd(True)
        return [cursor]
    if target == "paragraph":
        base = doc_ctx.selection if (doc_ctx.has_selection()
                                     and doc_ctx.selection is not None) \
            else doc_ctx.writer_view_cursor()
        if base is None:
            return []
        return [_paragraph_cursor(text, base)]
    # selection (default)
    if doc_ctx.has_selection() and doc_ctx.selection is not None:
        return [text.createTextCursorByRange(doc_ctx.selection)]
    view_cursor = doc_ctx.writer_view_cursor()
    if view_cursor is None:
        return []
    return [_paragraph_cursor(text, view_cursor)]


def _paragraph_cursor(text, base):
    cursor = text.createTextCursorByRange(base)
    try:
        cursor.gotoStartOfParagraph(False)
        cursor.gotoEndOfParagraph(True)
    except Exception:
        pass
    return cursor


# --------------------------------------------------------------- props
def _char_props(op):
    props = {}
    if "bold" in op:
        props["CharWeight"] = _CHAR_WEIGHT_BOLD if op["bold"] \
            else _CHAR_WEIGHT_NORMAL
    if "italic" in op:
        props["CharPosture"] = _FONT_SLANT_ITALIC if op["italic"] else 0
    if "underline" in op:
        value = op["underline"]
        if isinstance(value, str):
            props["CharUnderline"] = _UNDERLINE.get(value.lower(), 1)
        else:
            props["CharUnderline"] = 1 if value else 0
    if "strikeout" in op:
        props["CharStrikeout"] = 1 if op["strikeout"] else 0
    if "font" in op:
        props["CharFontName"] = str(op["font"])
    if "size" in op:
        try:
            props["CharHeight"] = float(op["size"])
        except (TypeError, ValueError):
            pass
    if "color" in op:
        color = _rgb(op["color"])
        if color is not None:
            props["CharColor"] = color
    if "highlight" in op:
        color = _rgb(op["highlight"])
        if color is not None:
            props["CharHighlight"] = color
    return props


def _para_props(op):
    props = {}
    if "para_style" in op:
        props["ParaStyleName"] = str(op["para_style"])
    if "char_style" in op:
        props["CharStyleName"] = str(op["char_style"])
    if "align" in op:
        align = _PARAGRAPH_ALIGN.get(str(op["align"]).lower())
        if align is not None:
            props["ParaAdjust"] = align
    for key, prop in (("space_before", "ParaTopMargin"),
                      ("space_after", "ParaBottomMargin"),
                      ("indent_first", "ParaFirstLineIndent"),
                      ("indent_left", "ParaLeftMargin"),
                      ("indent_right", "ParaRightMargin")):
        if key in op:
            value = _cm(op[key])
            if value is not None:
                props[prop] = value
    if "keep_together" in op:
        props["ParaKeepTogether"] = bool(op["keep_together"])
    if "line_spacing" in op and uno is not None:
        try:
            spacing = uno.createUnoStruct("com.sun.star.style.LineSpacing")
            spacing.Mode = _LINE_SPACING_PROP
            spacing.Height = int(round(float(op["line_spacing"]) * 100))
            props["ParaLineSpacing"] = spacing
        except Exception:
            pass
    return props


def _apply_page(doc, cursor, op):
    try:
        style_name = cursor.getPropertyValue("PageStyleName")
    except Exception:
        style_name = None
    if "page_style" in op:
        try:
            cursor.setPropertyValue("PageStyleName", str(op["page_style"]))
            style_name = str(op["page_style"])
        except Exception:
            pass
    if style_name is None:
        return
    try:
        style = doc.getStyleFamilies().getByName("PageStyles").getByName(style_name)
    except Exception:
        return
    margins = op.get("page_margins")
    if isinstance(margins, dict):
        for key, prop in (("top", "TopMargin"), ("bottom", "BottomMargin"),
                          ("left", "LeftMargin"), ("right", "RightMargin")):
            if key in margins:
                value = _cm(margins[key])
                if value is not None:
                    try:
                        style.setPropertyValue(prop, value)
                    except Exception:
                        pass
    if "landscape" in op:
        try:
            style.setPropertyValue("IsLandscape", bool(op["landscape"]))
        except Exception:
            pass


def _insert_table(doc, cursors, spec):
    if not cursors:
        raise RuntimeError("no cursor for the table")
    rows = max(1, int(spec.get("rows", 2)))
    cols = max(1, int(spec.get("cols", 2)))
    table = doc.createInstance("com.sun.star.text.TextTable")
    table.initialize(rows, cols)
    cursor = cursors[0]
    cursor.getText().insertTextContent(cursor, table, False)


def _describe(op):
    parts = []
    if "insert_table" in op:
        spec = op["insert_table"] or {}
        return "inserted a %sx%s table" % (spec.get("rows", "?"),
                                            spec.get("cols", "?"))
    for key in ("para_style", "char_style", "page_style"):
        if key in op:
            parts.append("%s=%s" % (key.replace("_", " "), op[key]))
    for key in ("bold", "italic", "underline", "strikeout", "font", "size",
                "color", "highlight", "align", "space_before", "space_after",
                "line_spacing", "indent_first", "indent_left", "indent_right",
                "keep_together"):
        if key in op:
            parts.append("%s=%s" % (key, op[key]))
    if "landscape" in op:
        parts.append("landscape=%s" % op["landscape"])
    if "page_margins" in op:
        parts.append("margins")
    target = op.get("find") or op.get("target", "selection")
    return "%s (%s)" % (", ".join(parts) or "formatting", target)


def _validate_styles(doc, op):
    para, char, page = style_names(doc)
    if "para_style" in op and str(op["para_style"]) not in para:
        raise RuntimeError("Unknown paragraph style: %s" % op["para_style"])
    if "char_style" in op and str(op["char_style"]) not in char:
        raise RuntimeError("Unknown character style: %s" % op["char_style"])
    if "page_style" in op and str(op["page_style"]) not in page:
        raise RuntimeError("Unknown page style: %s" % op["page_style"])


def apply_ops(doc_ctx, ops):
    """Apply formatting ops. Returns (applied_descriptions, errors)."""
    import cp_document

    doc = doc_ctx.doc
    if doc_ctx.kind != WRITER:
        return [], ["Formatting is only supported in Writer for now."]
    applied = []
    errors = []
    with cp_document.undo_context(doc, "HaiLPER formatting"):
        for op in ops:
            if not isinstance(op, dict):
                continue
            try:
                _validate_styles(doc, op)
                if "insert_table" in op:
                    _insert_table(doc, _target_cursors(doc_ctx, op),
                                  op["insert_table"] or {})
                    applied.append(_describe(op))
                    continue
                cursors = _target_cursors(doc_ctx, op)
                if not cursors:
                    raise RuntimeError("nothing to format (no selection)")
                char = _char_props(op)
                para = _para_props(op)
                for cursor in cursors:
                    for name, value in char.items():
                        cursor.setPropertyValue(name, value)
                    for name, value in para.items():
                        cursor.setPropertyValue(name, value)
                    if any(key in op for key in _PAGE_KEYS):
                        _apply_page(doc, cursor, op)
                applied.append(_describe(op))
            except Exception as error:  # noqa: BLE001
                errors.append(str(error))
    return applied, errors
