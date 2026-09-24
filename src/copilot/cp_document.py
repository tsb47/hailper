"""Read from and write to the active LibreOffice document via UNO."""

from contextlib import contextmanager
from contextlib import nullcontext

import uno
from com.sun.star.text.ControlCharacter import PARAGRAPH_BREAK


WRITER = "writer"
CALC = "calc"
IMPRESS = "impress"
UNKNOWN = "unknown"


def _supports(obj, service):
    try:
        return obj.supportsService(service)
    except Exception:
        return False


def _first_range(selection):
    """Writer returns an XTextRanges collection; unwrap to a single XTextRange."""
    if selection is None:
        return None
    if hasattr(selection, "getString"):
        return selection
    try:
        if hasattr(selection, "getCount") and selection.getCount() > 0:
            return selection.getByIndex(0)
    except Exception:
        pass
    return selection


@contextmanager
def record_changes(doc):
    """Enable Writer change tracking for the duration of the block.

    The previous RecordChanges state is restored afterwards, so the user's own
    setting is never left switched on.
    """
    previous = None
    if _supports(doc, "com.sun.star.text.TextDocument"):
        try:
            previous = doc.getPropertyValue("RecordChanges")
        except Exception:
            previous = None
        try:
            doc.setPropertyValue("RecordChanges", True)
        except Exception:
            previous = None
    try:
        yield
    finally:
        if previous is not None:
            try:
                doc.setPropertyValue("RecordChanges", previous)
            except Exception:
                pass


def undo_last(doc):
    """Undo the most recent undoable action; returns True on success."""
    try:
        supplier = doc.queryInterface(
            uno.getTypeByName("com.sun.star.document.XUndoManagerSupplier"))
        manager = supplier.getUndoManager()
        if manager is not None and manager.isUndoPossible():
            manager.undo()
            return True
    except Exception:
        pass
    return False


@contextmanager
def undo_context(doc, title="HaiLPER"):
    """Group the enclosed edits into a single undo step when possible."""
    manager = None
    try:
        supplier = doc.queryInterface(
            uno.getTypeByName("com.sun.star.document.XUndoManagerSupplier")
        )
        if supplier is not None:
            manager = supplier.getUndoManager()
    except Exception:
        manager = None
    try:
        if manager is not None:
            manager.enterUndoContext(title)
    except Exception:
        manager = None
    try:
        yield
    finally:
        if manager is not None:
            try:
                manager.leaveUndoContext()
            except Exception:
                pass


def detect_kind(doc):
    if doc is None:
        return UNKNOWN
    if _supports(doc, "com.sun.star.text.TextDocument"):
        return WRITER
    if _supports(doc, "com.sun.star.sheet.SpreadsheetDocument"):
        return CALC
    if _supports(doc, "com.sun.star.presentation.PresentationDocument"):
        return IMPRESS
    if _supports(doc, "com.sun.star.drawing.DrawingDocument"):
        return IMPRESS
    return UNKNOWN


def insert_multiline(text, cursor, value):
    """Insert text at a Writer cursor, turning newlines into paragraphs."""
    lines = value.split("\n")
    for index, line in enumerate(lines):
        if index > 0:
            text.insertControlCharacter(cursor, PARAGRAPH_BREAK, False)
        if line:
            text.insertString(cursor, line, False)


def create_document_with_text(ctx, text, activate=True):
    """Create a new Writer document containing text and return it."""
    try:
        desktop = ctx.getByName("/singletons/com.sun.star.frame.theDesktop")
        document = desktop.loadComponentFromURL(
            "private:factory/swriter", "_blank", 0, ()
        )
        body = document.getText()
        cursor = body.createTextCursor()
        insert_multiline(body, cursor, text)
        if activate:
            try:
                controller = document.getCurrentController()
                controller.getFrame().getContainerWindow().setFocus()
            except Exception:
                pass
        return document
    except Exception:
        return None


def replace_first(document, original, replacement, tracked=False):
    """Replace the first occurrence of original in a Writer document."""
    if not original:
        return False
    try:
        descriptor = document.createSearchDescriptor()
        descriptor.SearchString = original
        descriptor.SearchCaseSensitive = True
        found = document.findFirst(descriptor)
        if found is None:
            return False
        with (record_changes(document) if tracked else nullcontext()):
            found.setString(replacement)
        return True
    except Exception:
        return False


class DocumentContext(object):
    """Captures the target document plus the current selection.

    The selection is captured when the dialog opens so that interacting with
    the dialog does not disturb what will be edited.
    """

    def __init__(self, ctx, doc):
        self.ctx = ctx
        self.doc = doc
        self.kind = detect_kind(doc)
        self.controller = None
        self.selection = None
        self.selected_text = ""
        self._capture()

    # ------------------------------------------------------------------ setup
    def _capture(self):
        try:
            self.controller = self.doc.getCurrentController()
        except Exception:
            self.controller = None
        if self.controller is None:
            return
        try:
            self.selection = self.controller.getSelection()
        except Exception:
            self.selection = None
        if self.kind == WRITER:
            self.selection = _first_range(self.selection)
            self.selected_text = self._writer_selection_text()
        elif self.kind == CALC:
            self.selected_text = self._calc_selection_text()

    # ------------------------------------------------------------------- read
    def _writer_selection_text(self):
        if self.selection is None:
            return ""
        try:
            text = self.selection.getString()
        except Exception:
            return ""
        return text or ""

    def _calc_selection_text(self):
        if self.selection is None:
            return ""
        try:
            if hasattr(self.selection, "getDataArray"):
                rows = self.selection.getDataArray()
                return "\n".join("\t".join(str(cell) for cell in row) for row in rows)
        except Exception:
            pass
        try:
            return self.selection.getString()
        except Exception:
            return ""

    def has_selection(self):
        return bool(self.selected_text.strip())

    def full_text(self):
        if self.kind == WRITER:
            try:
                return self.doc.getText().getString()
            except Exception:
                return ""
        if self.kind == CALC:
            return self._calc_full_text()
        if self.kind == IMPRESS:
            return self._impress_full_text()
        return ""

    def _calc_full_text(self):
        lines = []
        try:
            sheets = self.doc.getSheets()
            for index in range(sheets.getCount()):
                sheet = sheets.getByIndex(index)
                lines.append("[Sheet: %s]" % sheet.getName())
                cursor = sheet.createCursor()
                cursor.gotoStartOfUsedArea(False)
                cursor.gotoEndOfUsedArea(True)
                data = cursor.getDataArray()
                for row in data:
                    if any(str(cell).strip() for cell in row):
                        lines.append("\t".join(str(cell) for cell in row))
        except Exception:
            return ""
        return "\n".join(lines)

    def _impress_full_text(self):
        lines = []
        try:
            pages = self.doc.getDrawPages()
            for page_index in range(pages.getCount()):
                page = pages.getByIndex(page_index)
                lines.append("[Slide %d]" % (page_index + 1))
                for shape_index in range(page.getCount()):
                    shape = page.getByIndex(shape_index)
                    text = ""
                    try:
                        text = shape.getText().getString()
                    except Exception:
                        text = ""
                    if not text:
                        try:
                            text = shape.getString()
                        except Exception:
                            text = ""
                    if text and text.strip():
                        lines.append(text)
        except Exception:
            return ""
        return "\n".join(lines)

    def outline_text(self, max_items=80):
        """Return an indented heading outline (Writer only)."""
        if self.kind != WRITER:
            return ""
        lines = []
        try:
            text = self.doc.getText()
            enum = text.createEnumeration()
            para_styles = self.doc.getStyleFamilies().getByName("ParagraphStyles")
            count = 0
            while enum.hasMoreElements() and count < max_items:
                element = enum.nextElement()
                if not _supports(element, "com.sun.star.text.Paragraph"):
                    continue
                content = element.getString().strip()
                if not content:
                    continue
                try:
                    style_name = element.getPropertyValue("ParaStyleName")
                except Exception:
                    continue
                level = 0
                try:
                    level = para_styles.getByName(style_name).getPropertyValue("OutlineLevel")
                except Exception:
                    level = 0
                if level and level > 0:
                    lines.append("%s%s" % ("  " * (int(level) - 1), content[:80]))
                    count += 1
        except Exception:
            return ""
        return "\n".join(lines)

    # ----------------------------------------------------------- structure
    def _writer_paragraphs(self):
        paragraphs = []
        try:
            text = self.doc.getText()
            enum = text.createEnumeration()
            styles = self.doc.getStyleFamilies().getByName("ParagraphStyles")
            while enum.hasMoreElements():
                element = enum.nextElement()
                if not _supports(element, "com.sun.star.text.Paragraph"):
                    continue
                try:
                    style_name = element.getPropertyValue("ParaStyleName")
                except Exception:
                    style_name = ""
                level = 0
                try:
                    level = styles.getByName(style_name).getPropertyValue("OutlineLevel")
                except Exception:
                    level = 0
                paragraphs.append({"text": element.getString(),
                                   "style": style_name,
                                   "level": int(level or 0)})
        except Exception:
            return []
        return paragraphs

    def _current_paragraph_index(self):
        cursor = self.writer_view_cursor()
        if cursor is None:
            return -1, ""
        try:
            probe = self.doc.getText().createTextCursorByRange(cursor.getStart())
            probe.gotoStartOfParagraph(False)
            probe.gotoEndOfParagraph(True)
            current = probe.getString()
        except Exception:
            current = ""
        paragraphs = self._writer_paragraphs()
        for index, paragraph in enumerate(paragraphs):
            if paragraph["text"] == current:
                return index, current
        return -1, current

    def section_heading(self):
        """Return (level, text) of the nearest preceding heading, or (0, '')."""
        if self.kind != WRITER:
            return (0, "")
        index, _text = self._current_paragraph_index()
        paragraphs = self._writer_paragraphs()
        if index < 0:
            index = len(paragraphs)
        for position in range(min(index, len(paragraphs) - 1), -1, -1):
            paragraph = paragraphs[position]
            if paragraph["level"] > 0 and paragraph["text"].strip():
                return (paragraph["level"], paragraph["text"].strip())
        return (0, "")

    def section_text(self, max_chars=6000):
        """Text of the current section (heading to the next same/higher one)."""
        if self.kind != WRITER:
            return ""
        index, _text = self._current_paragraph_index()
        paragraphs = self._writer_paragraphs()
        if not paragraphs:
            return ""
        if index < 0:
            index = len(paragraphs)
        start = 0
        level = 0
        for position in range(min(index, len(paragraphs) - 1), -1, -1):
            if paragraphs[position]["level"] > 0:
                start = position
                level = paragraphs[position]["level"]
                break
        lines = []
        length = 0
        for position in range(start, len(paragraphs)):
            paragraph = paragraphs[position]
            if position > start and paragraph["level"] and paragraph["level"] <= level:
                break
            lines.append(paragraph["text"])
            length += len(paragraph["text"])
            if length >= max_chars:
                break
        return "\n".join(lines).strip()[:max_chars]

    def surrounding(self, count=2):
        """The +/- count paragraphs around the cursor (list of strings)."""
        if self.kind != WRITER:
            return []
        index, _text = self._current_paragraph_index()
        paragraphs = self._writer_paragraphs()
        if index < 0:
            return []
        low = max(0, index - count)
        high = min(len(paragraphs), index + count + 1)
        return [paragraphs[position]["text"] for position in range(low, high)
                if paragraphs[position]["text"].strip()]

    def paragraphs(self):
        """A flat list of non-empty paragraphs (Writer) or lines."""
        texts = [paragraph["text"] for paragraph in self._writer_paragraphs()
                 if paragraph["text"].strip()]
        if texts:
            return texts
        return [line for line in self.full_text().split("\n") if line.strip()]

    def metadata(self):
        title = ""
        author = ""
        try:
            supplier = self.doc.queryInterface(
                uno.getTypeByName("com.sun.star.document.XDocumentPropertiesSupplier"))
            props = supplier.getDocumentProperties()
            title = props.Title or ""
            author = props.Author or ""
        except Exception:
            pass
        read_only = False
        try:
            read_only = bool(self.doc.isReadOnly())
        except Exception:
            pass
        track_changes = None
        try:
            track_changes = bool(self.doc.getPropertyValue("RecordChanges"))
        except Exception:
            track_changes = None
        text = ""
        try:
            text = self.full_text()
        except Exception:
            pass
        return {"kind": self.kind, "title": title, "author": author,
                "words": len(text.split()), "read_only": read_only,
                "track_changes": track_changes}

    def target_text(self):
        """Selection when there is one, otherwise the whole document."""
        if self.has_selection():
            return self.selected_text
        return self.full_text()

    # ------------------------------------------------------------------ write
    def writer_view_cursor(self):
        try:
            return self.controller.getViewCursor()
        except Exception:
            return None

    def _writer_insert_multiline(self, text_range, value):
        text = text_range.getText()
        cursor = text.createTextCursorByRange(text_range.getStart())
        insert_multiline(text, cursor, value)

    def replace_selection(self, value, tracked=False):
        if self.kind == WRITER:
            with (record_changes(self.doc) if tracked else nullcontext()):
                if self.has_selection() and self.selection is not None:
                    self.selection.setString("")
                    self._writer_insert_multiline(self.selection, value)
                else:
                    self.insert_at_cursor(value)
            return True
        if self.kind == CALC:
            return self._calc_write(value, overwrite=True)
        if self.kind == IMPRESS:
            return self._impress_write(value, overwrite=True)
        return False

    def insert_at_cursor(self, value, tracked=False):
        if self.kind == WRITER:
            cursor = self.writer_view_cursor()
            if cursor is None:
                return False
            with (record_changes(self.doc) if tracked else nullcontext()):
                self._writer_insert_multiline(cursor, value)
            return True
        if self.kind == CALC:
            return self._calc_write(value, overwrite=False)
        if self.kind == IMPRESS:
            return self._impress_write(value, overwrite=False)
        return False

    # ------------------------------------------------------- formatted insert
    def insert_markdown(self, markdown_text, mode="insert"):
        """Render Markdown into the document with real Writer formatting."""
        if self.kind != WRITER:
            return False
        import cp_markdown
        blocks = cp_markdown.parse(markdown_text)
        text = self.doc.getText()
        cursor = self._markdown_cursor(text, mode == "replace")
        if cursor is None:
            return False
        state = {"first": True}

        def new_paragraph():
            if not state["first"]:
                text.insertControlCharacter(cursor, PARAGRAPH_BREAK, False)
            state["first"] = False

        # When appending at a cursor that is inside existing text, start on a
        # fresh paragraph so the first block is not glued to it.
        if mode != "replace":
            try:
                para = text.createTextCursorByRange(cursor.getStart())
                para.gotoStartOfParagraph(False)
                para.gotoEndOfParagraph(True)
                if para.getString().strip():
                    text.insertControlCharacter(cursor, PARAGRAPH_BREAK, False)
            except Exception:
                pass

        with undo_context(self.doc, "HaiLPER formatted insert"):
            for block in blocks:
                kind = block["type"]
                if kind == "heading":
                    new_paragraph()
                    self._insert_runs(cursor, block["text"])
                    if not self._try_para_style(
                            cursor, "Heading %d" % min(block["level"], 10)):
                        self._apply_range_prop(cursor, "CharWeight", 150.0)
                        self._apply_range_prop(cursor, "CharHeight", 14.0)
                elif kind == "subheading":
                    new_paragraph()
                    self._insert_runs(cursor, block["text"])
                    self._apply_range_prop(cursor, "CharWeight", 150.0)
                elif kind == "paragraph":
                    new_paragraph()
                    self._insert_runs(cursor, block["text"])
                elif kind in ("bullets", "ordered"):
                    counters = {}
                    for indent, item in block["items"]:
                        new_paragraph()
                        if kind == "bullets":
                            prefix = "    " * indent + "\u2022 "
                        else:
                            counters[indent] = counters.get(indent, 0) + 1
                            prefix = "    " * indent + "%d. " % counters[indent]
                        text.insertString(cursor, prefix, False)
                        self._insert_runs(cursor, item)
                elif kind == "code":
                    for line in block["text"].split("\n"):
                        new_paragraph()
                        self._insert_runs(cursor, line)
                        self._apply_range_prop(cursor, "CharFontName",
                                               "Liberation Mono")
                elif kind == "quote":
                    for line in block["text"].split("\n"):
                        new_paragraph()
                        self._insert_runs(cursor, line)
                        self._apply_range_prop(cursor, "CharPosture", 2)
                elif kind == "rule":
                    new_paragraph()
                    text.insertString(cursor, "\u2500" * 40, False)
                elif kind == "table":
                    new_paragraph()
                    cursor = self._insert_markdown_table(text, cursor,
                                                         block["rows"])
        return True

    def insert_table(self, rows, cols):
        if self.kind != WRITER:
            return False
        try:
            text = self.doc.getText()
            view = self.writer_view_cursor()
            if view is None:
                return False
            table = self.doc.createInstance("com.sun.star.text.TextTable")
            table.initialize(max(1, int(rows)), max(1, int(cols)))
            cursor = text.createTextCursorByRange(view.getStart())
            text.insertTextContent(cursor, table, False)
            return True
        except Exception:
            return False

    def _markdown_cursor(self, text, replace):
        if replace and self.has_selection() and self.selection is not None:
            cursor = text.createTextCursorByRange(self.selection)
            try:
                cursor.setString("")
            except Exception:
                pass
            return cursor
        view = self.writer_view_cursor()
        if view is None:
            return None
        return text.createTextCursorByRange(view)

    _INLINE = None

    def _insert_runs(self, cursor, value):
        import re
        import cp_markdown
        if self._INLINE is None:
            self._INLINE = re.compile(
                r"(\*\*[^*]+\*\*|__[^_]+__|\*[^*]+\*|_[^_]+_|`[^`]+`)")
        text = cursor.getText()
        position = 0
        for match in self._INLINE.finditer(value):
            if match.start() > position:
                text.insertString(cursor, cp_markdown._inline(
                    value[position:match.start()]), False)
            token = match.group(0)
            if token.startswith("**") or token.startswith("__"):
                self._insert_run(cursor, token[2:-2], {"CharWeight": 150.0})
            elif token.startswith("`"):
                self._insert_run(cursor, token[1:-1],
                                 {"CharFontName": "Liberation Mono"})
            else:
                self._insert_run(cursor, token[1:-1], {"CharPosture": 2})
            position = match.end()
        if position < len(value):
            text.insertString(cursor, cp_markdown._inline(value[position:]), False)

    def _insert_run(self, cursor, value, props):
        text = cursor.getText()
        start = cursor.getStart()
        text.insertString(cursor, value, False)
        for prop, val in props.items():
            try:
                rng = text.createTextCursorByRange(start)
                rng.gotoRange(cursor.getEnd(), True)
                rng.setPropertyValue(prop, val)
            except Exception:
                pass

    def _apply_range_prop(self, cursor, prop, value):
        try:
            para = cursor.getText().createTextCursorByRange(cursor.getStart())
            para.gotoStartOfParagraph(False)
            para.gotoEndOfParagraph(True)
            para.setPropertyValue(prop, value)
        except Exception:
            pass

    def _try_para_style(self, cursor, style):
        try:
            names = self.doc.getStyleFamilies().getByName(
                "ParagraphStyles").getElementNames()
            if style not in names:
                return False
            self._apply_range_prop(cursor, "ParaStyleName", style)
            return True
        except Exception:
            return False

    def _insert_markdown_table(self, text, cursor, rows):
        if not rows:
            return cursor
        cols = max(len(row) for row in rows)
        table = self.doc.createInstance("com.sun.star.text.TextTable")
        table.initialize(len(rows), cols)
        text.insertTextContent(cursor, table, False)
        for row_index, row in enumerate(rows):
            for col in range(cols):
                value = row[col] if col < len(row) else ""
                try:
                    table.getCellByPosition(col, row_index).setString(value)
                except Exception:
                    pass
        try:
            return text.createTextCursorByRange(table.getEnd())
        except Exception:
            return cursor

    def append(self, value):
        if self.kind == WRITER:
            try:
                text = self.doc.getText()
                cursor = text.createTextCursor()
                cursor.gotoEnd(False)
                text.insertControlCharacter(cursor, PARAGRAPH_BREAK, False)
                self._writer_insert_multiline(cursor, value)
                return True
            except Exception:
                return False
        return self.insert_at_cursor(value)

    def add_comment(self, value):
        if self.kind != WRITER:
            return False
        try:
            annotation = self.doc.createInstance("com.sun.star.text.textfield.Annotation")
            annotation.setPropertyValue("Content", value)
            annotation.setPropertyValue("Author", "HaiLPER")
            text = self.doc.getText()
            if self.selection is not None and self.has_selection():
                cursor = text.createTextCursorByRange(self.selection)
            else:
                view_cursor = self.writer_view_cursor()
                cursor = text.createTextCursorByRange(view_cursor.getStart())
            text.insertTextContent(cursor, annotation, False)
            return True
        except Exception:
            return False

    def _calc_write(self, value, overwrite):
        try:
            sheet = self.controller.getActiveSheet()
            cell = self.controller.getSelection()
            if not hasattr(cell, "getCellAddress"):
                return False
            address = cell.getCellAddress()
            target = sheet.getCellByPosition(address.Column, address.Row)
            if overwrite:
                target.setString(value)
            else:
                existing = target.getString()
                target.setString((existing + "\n" + value) if existing else value)
            return True
        except Exception:
            return False

    def _impress_write(self, value, overwrite):
        try:
            controller = self.controller
            page = controller.getCurrentPage()
            if overwrite:
                shape = self._impress_selected_shape()
                if shape is not None:
                    try:
                        shape.setString(value)
                        return True
                    except Exception:
                        pass
            shape = self.doc.createInstance("com.sun.star.drawing.TextShape")
            width = 16000
            try:
                width = page.getPropertyValue("Width") - 2000
            except Exception:
                pass
            shape.setPropertyValue("Position", _point(1000, 1000))
            shape.setPropertyValue("Size", _size(width, 8000))
            page.add(shape)
            shape.setString(value)
            return True
        except Exception:
            return False

    def _impress_selected_shape(self):
        selected = self.selection
        if selected is None:
            return None
        try:
            if hasattr(selected, "getCount") and selected.getCount() > 0:
                return selected.getByIndex(0)
        except Exception:
            pass
        if hasattr(selected, "setString"):
            return selected
        return None


def _point(x, y):
    point = uno.createUnoStruct("com.sun.star.awt.Point")
    point.X = x
    point.Y = y
    return point


def _size(width, height):
    size = uno.createUnoStruct("com.sun.star.awt.Size")
    size.Width = width
    size.Height = height
    return size
