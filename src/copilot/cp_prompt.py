"""Small modal text-input dialog (used for 'Refine')."""

import cp_ui as ui


DLG_W = 420
DLG_H = 150
PAD = 10
LINE_H = 14
BTN_H = 22
MAP_PIXEL = 7


class _Bridge(object):
    def __init__(self, ctx, frame, title, label, default):
        self.ctx = ctx
        self.frame = frame
        self.title = title
        self.label = label
        self.default = default
        self.answer = ""
        self.model = None
        self.dialog = None

    def build(self):
        ctx = self.ctx
        self.model = ui.smgr(ctx).createInstanceWithContext(
            "com.sun.star.awt.UnoControlDialogModel", ctx)
        self.model.setPropertyValue("Title", self.title)
        try:
            self.model.setPropertyValue("MapUnit", MAP_PIXEL)
        except Exception:
            pass
        self.model.setPropertyValue("Width", DLG_W)
        self.model.setPropertyValue("Height", DLG_H)
        self.model.setPropertyValue("Moveable", True)
        self.model.setPropertyValue("Closeable", True)
        content_w = DLG_W - 2 * PAD

        def add(service, name, **props):
            self.model.insertByName(
                name, ui.create_model(self.model, service, name, **props))

        add("com.sun.star.awt.UnoControlFixedText", "label",
            PositionX=PAD, PositionY=PAD, Width=content_w, Height=LINE_H,
            Label=self.label)
        add("com.sun.star.awt.UnoControlEdit", "input",
            PositionX=PAD, PositionY=PAD + LINE_H + 4, Width=content_w,
            Height=LINE_H + 10, Text=self.default, MultiLine=True,
            VScroll=True)
        add("com.sun.star.awt.UnoControlButton", "ok",
            PositionX=content_w - 2 * 80 - 6 + PAD, PositionY=DLG_H - BTN_H - PAD,
            Width=80, Height=BTN_H, Label="OK", DefaultButton=True)
        add("com.sun.star.awt.UnoControlButton", "cancel",
            PositionX=content_w - 80 + PAD, PositionY=DLG_H - BTN_H - PAD,
            Width=80, Height=BTN_H, Label="Cancel")

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

        self.dialog.getControl("ok").addActionListener(
            ui.ActionListener(lambda event: self.on_ok()))
        self.dialog.getControl("cancel").addActionListener(
            ui.ActionListener(lambda event: self.on_cancel()))
        try:
            self.dialog.getControl("input").setFocus()
        except Exception:
            pass

    def on_ok(self):
        self.answer = ui.get_text(self.dialog, "input").strip()
        self._close()

    def on_cancel(self):
        self.answer = ""
        self._close()

    def _close(self):
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
        return self.answer


def ask(ctx, frame, title, label, default=""):
    bridge = _Bridge(ctx, frame, title, label, default)
    bridge.build()
    return bridge.run()
