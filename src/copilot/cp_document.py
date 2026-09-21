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
