"""Minimal Markdown parser and a plain-text renderer for the transcript.

LibreOffice has no rich-text dialog control, so the transcript is a readonly
plain-text box.  We render Markdown to *styled plain text* (headings, bullets,
aligned tables, code fences) so the output is easy to read.  ``apply_to_document``
(elsewhere) turns the same blocks into real Writer formatting on insert.
"""

import re

_HEADING = re.compile(r"^(#{1,6})\s+(.*)$")
_RULE = re.compile(r"^(-{3,}|\*{3,}|_{3,})$")
_BULLET = re.compile(r"^(\s*)([-*+])\s+(.*)$")
_ORDERED = re.compile(r"^(\s*)\d+[.)]\s+(.*)$")
_TABLE_SEP = re.compile(r"^\s*\|?[\s:\-|]+\|?\s*$")
_EMPHASIS_LINE = re.compile(r"^\*\*.+\*\*$|^__.+__$|^\*.+\*$|^_.+_$")


def _inline(text):
    text = re.sub(r"`([^`]+)`", r"\1", text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    text = re.sub(r"__([^_]+)__", r"\1", text)
    text = re.sub(r"\*([^*]+)\*", r"\1", text)
    text = re.sub(r"(?<!\w)_([^_]+)_(?!\w)", r"\1", text)
    text = re.sub(r"~~([^~]+)~~", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1 (\2)", text)
    return text.strip()


def _starts_block(line):
    stripped = line.strip()
    if not stripped:
        return True
    if stripped.startswith("```") or stripped.startswith(">"):
        return True
    if _HEADING.match(stripped) or _RULE.match(stripped):
        return True
    if _BULLET.match(stripped) or _ORDERED.match(stripped):
        return True
    if _EMPHASIS_LINE.match(stripped):
        return True
    return False


def _split_row(line):
    stripped = line.strip()
    if stripped.startswith("|"):
        stripped = stripped[1:]
    if stripped.endswith("|"):
        stripped = stripped[:-1]
    return [cell.strip() for cell in stripped.split("|")]


def parse(text):
    lines = (text or "").replace("\r\n", "\n").split("\n")
    blocks = []
    index = 0
    total = len(lines)
    while index < total:
        stripped = lines[index].strip()
        if not stripped:
            index += 1
            continue
        if stripped.startswith("```"):
            index += 1
            code = []
            while index < total and not lines[index].strip().startswith("```"):
                code.append(lines[index])
                index += 1
            index += 1
            blocks.append({"type": "code", "text": "\n".join(code)})
            continue
        match = _HEADING.match(stripped)
        if match:
            blocks.append({"type": "heading", "level": len(match.group(1)),
                           "text": match.group(2).strip()})
            index += 1
            continue
        if _RULE.match(stripped):
            blocks.append({"type": "rule"})
            index += 1
            continue
        if stripped.startswith(">"):
            quote = []
            while index < total and lines[index].strip().startswith(">"):
                quote.append(lines[index].strip()[1:].strip())
                index += 1
            blocks.append({"type": "quote", "text": "\n".join(quote)})
            continue
        if ("|" in stripped and index + 1 < total
                and "-" in lines[index + 1] and _TABLE_SEP.match(lines[index + 1])):
            rows = [_split_row(stripped)]
            index += 2
            while index < total and "|" in lines[index] and lines[index].strip():
                rows.append(_split_row(lines[index]))
                index += 1
            blocks.append({"type": "table", "rows": rows})
            continue
        match = _BULLET.match(stripped)
        if match:
            items = []
            while index < total:
                item = _BULLET.match(lines[index])
                if not item:
                    break
                items.append((len(item.group(1)) // 2, item.group(3).strip()))
                index += 1
            blocks.append({"type": "bullets", "items": items})
            continue
        match = _ORDERED.match(stripped)
        if match:
            items = []
            while index < total:
                item = _ORDERED.match(lines[index])
                if not item:
                    break
                items.append((len(item.group(1)) // 2, item.group(2).strip()))
                index += 1
            blocks.append({"type": "ordered", "items": items})
            continue
        if _EMPHASIS_LINE.match(stripped):
            blocks.append({"type": "subheading", "text": stripped})
            index += 1
            continue
        para = [stripped]
        index += 1
        while (index < total and lines[index].strip()
               and not _starts_block(lines[index])):
            para.append(lines[index].strip())
            index += 1
        blocks.append({"type": "paragraph", "text": " ".join(para)})
    return blocks


def _render_table(rows):
    if not rows:
        return []
    cols = max(len(row) for row in rows)
    grid = [[_inline(cell) for cell in row] + [""] * (cols - len(row))
            for row in rows]
    widths = [max(len(grid[r][c]) for r in range(len(grid))) for c in range(cols)]
    lines = []
    for row_index, row in enumerate(grid):
        lines.append(" " + " \u2502 ".join(
            row[c].ljust(widths[c]) for c in range(cols)) + " ")
        if row_index == 0:
            lines.append("\u2500" + "\u2500\u253c\u2500".join(
                "\u2500" * widths[c] for c in range(cols)) + "\u2500")
    return lines


def render_plain(blocks):
    out = []
    for block in blocks:
        kind = block["type"]
        if kind == "heading":
            label = _inline(block["text"])
            out.append(label)
            out.append("\u2500" * min(max(len(label), 3), 60))
        elif kind == "subheading":
            out.append("\u25b8 " + _inline(block["text"]))
        elif kind == "rule":
            out.append("\u2500" * 40)
        elif kind == "bullets":
            for indent, item in block["items"]:
                mark = "\u2022" if indent % 2 == 0 else "\u25e6"
                out.append("  " * indent + mark + " " + _inline(item))
        elif kind == "ordered":
            counters = {}
            for indent, item in block["items"]:
                counters[indent] = counters.get(indent, 0) + 1
                out.append("  " * indent + "%d. " % counters[indent] + _inline(item))
        elif kind == "code":
            for line in block["text"].split("\n"):
                out.append("\u2502 " + line)
        elif kind == "quote":
            for line in block["text"].split("\n"):
                out.append("\u258f " + _inline(line))
        elif kind == "table":
            out.extend(_render_table(block["rows"]))
        else:
            out.append(_inline(block["text"]))
        out.append("")
    return "\n".join(out).strip()


def render(text):
    return render_plain(parse(text))


def to_plain(text):
    """Markdown -> clean plain text (no markers, no decorative rules)."""
    lines = []
    for block in parse(text):
        kind = block["type"]
        if kind in ("heading", "subheading"):
            lines.append(_inline(block["text"]))
        elif kind == "bullets":
            for indent, item in block["items"]:
                lines.append("  " * indent + "\u2022 " + _inline(item))
        elif kind == "ordered":
            counters = {}
            for indent, item in block["items"]:
                counters[indent] = counters.get(indent, 0) + 1
                lines.append("  " * indent + "%d. " % counters[indent]
                             + _inline(item))
        elif kind == "code":
            for line in block["text"].split("\n"):
                lines.append("    " + line)
        elif kind == "quote":
            for line in block["text"].split("\n"):
                lines.append("> " + _inline(line))
        elif kind == "table":
            for row in block["rows"]:
                lines.append("   ".join(_inline(cell) for cell in row))
        elif kind == "rule":
            lines.append("\u2014" * 10)
        else:
            lines.append(_inline(block["text"]))
        lines.append("")
    return "\n".join(lines).strip()
