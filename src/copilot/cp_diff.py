"""Modal compare window: original vs suggested, with Accept / Copy / Close."""

import uno

from com.sun.star.awt import XKeyListener

import cp_ui as ui


DLG_W = 460
DLG_H = 340
PAD = 8
LINE_H = 12
BTN_H = 18
MAP_PIXEL = 7


class _Bridge(object):
    def __init__(self, ctx, frame, original, suggested, doc_ctx):
        self.ctx = ctx
        self.frame = frame
        self.original = original or ""
        self.suggested = suggested or ""
        self.doc_ctx = doc_ctx
        self.model = None
        self.dialog = None

    def build(self):
        ctx = self.ctx
        self.model = ui.smgr(ctx).createInstanceWithContext(
            "com.sun.star.awt.UnoControlDialogModel", ctx)
        self.model.setPropertyValue("Title", "HaiLPER - Compare")
        try:
            self.model.setPropertyValue("MapUnit", MAP_PIXEL)
        except Exception:
            pass
        self.model.setPropertyValue("Width", DLG_W)
        self.model.setPropertyValue("Height", DLG_H)
        self.model.setPropertyValue("Moveable", True)
        self.model.setPropertyValue("Closeable", True)
        content_w = DLG_W - 2 * PAD
        edit_h = (DLG_H - 5 * PAD - 3 * LINE_H - BTN_H) // 2

        def add(service, name, **props):
            self.model.insertByName(
                name, ui.create_model(self.model, service, name, **props))

        add("com.sun.star.awt.UnoControlFixedText", "orig_label",
            PositionX=PAD, PositionY=PAD, Width=content_w, Height=LINE_H,
            Label="Original:")
        add("com.sun.star.awt.UnoControlEdit", "orig",
            PositionX=PAD, PositionY=PAD + LINE_H + 2,
            Width=content_w, Height=edit_h,
            MultiLine=True, ReadOnly=True, VScroll=True)
        y = PAD + LINE_H + 2 + edit_h + PAD
        add("com.sun.star.awt.UnoControlFixedText", "new_label",
            PositionX=PAD, PositionY=y, Width=content_w, Height=LINE_H,
            Label="Suggested:")
        add("com.sun.star.awt.UnoControlEdit", "new",
            PositionX=PAD, PositionY=y + LINE_H + 2,
            Width=content_w, Height=edit_h,
            MultiLine=True, ReadOnly=True, VScroll=True)
        by = DLG_H - BTN_H - PAD
        bw = 76
        add("com.sun.star.awt.UnoControlButton", "accept",
            PositionX=content_w - 3 * bw - 2 * 6 + PAD, PositionY=by,
            Width=bw, Height=BTN_H, Label="Accept", DefaultButton=True)
        add("com.sun.star.awt.UnoControlButton", "copy",
            PositionX=content_w - 2 * bw - 6 + PAD, PositionY=by,
            Width=bw, Height=BTN_H, Label="Copy")
        add("com.sun.star.awt.UnoControlButton", "close",
            PositionX=content_w - bw + PAD, PositionY=by,
            Width=bw, Height=BTN_H, Label="Close")

        self.dialog = ui.smgr(ctx).createInstanceWithContext(
            "com.sun.star.awt.UnoControlDialog", ctx)
        self.dialog.setModel(self.model)
        toolkit = ui.smgr(ctx).createInstanceWithContext("com.sun.star.awt.Toolkit", ctx)
        parent = None
        try:
            parent = self.frame.getContainerWindow()
        except Exception:
            parent = None
        self.dialog.createPeer(toolkit, parent)

        ui.set_text(self.dialog, "orig", self.original)
        ui.set_text(self.dialog, "new", self.suggested)
        self.dialog.getControl("accept").addActionListener(
            ui.ActionListener(lambda event: self.on_accept()))
        self.dialog.getControl("copy").addActionListener(
            ui.ActionListener(lambda event: self.on_copy()))
        self.dialog.getControl("close").addActionListener(
            ui.ActionListener(lambda event: self.on_close()))

    def on_accept(self):
        if self.doc_ctx is None:
            return
        if self.doc_ctx.has_selection():
            self.doc_ctx.replace_selection(self.suggested)
        else:
            self.doc_ctx.insert_at_cursor(self.suggested)
        self.on_close()

    def on_copy(self):
        ui.copy_to_clipboard(self.ctx, self.suggested)
        self.on_close()

    def on_close(self):
        try:
            self.dialog.endExecute()
        except Exception:
            pass
        try:
            self.dialog.dispose()
        except Exception:
            pass

    def run(self):
        self.dialog.execute()


def show(ctx, frame, original, suggested, doc_ctx):
    bridge = _Bridge(ctx, frame, original, suggested, doc_ctx)
    bridge.build()
    bridge.run()
