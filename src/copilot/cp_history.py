"""Modal conversation-history picker."""

import cp_conversations
import cp_ui as ui

DLG_W = 400
DLG_H = 320
PAD = 10
LINE_H = 14
BTN_H = 24
MAP_PIXEL = 7


class _Bridge(object):
    def __init__(self, ctx, frame):
        self.ctx = ctx
        self.frame = frame
        self.model = None
        self.dialog = None
        self.items = []
        self.result = (None, None)

    def build(self):
        ctx = self.ctx
        self.model = ui.smgr(ctx).createInstanceWithContext(
            "com.sun.star.awt.UnoControlDialogModel", ctx)
        self.model.setPropertyValue("Title", "HaiLPER - Conversations")
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

        add("com.sun.star.awt.UnoControlFixedText", "title",
            PositionX=PAD, PositionY=PAD, Width=content_w, Height=LINE_H,
            Label="Saved conversations:")
        add("com.sun.star.awt.UnoControlListBox", "list",
            PositionX=PAD, PositionY=PAD + LINE_H + 4, Width=content_w,
            Height=DLG_H - 3 * BTN_H - 4 * PAD - LINE_H, Dropdown=False,
            MultiSelection=False)
        by = DLG_H - BTN_H - PAD
        add("com.sun.star.awt.UnoControlButton", "btn_load",
            PositionX=PAD, PositionY=by, Width=90, Height=BTN_H,
            Label="Open", DefaultButton=True)
        add("com.sun.star.awt.UnoControlButton", "btn_delete",
            PositionX=PAD + 96, PositionY=by, Width=90, Height=BTN_H,
            Label="Delete")
        add("com.sun.star.awt.UnoControlButton", "btn_new",
            PositionX=PAD + 192, PositionY=by, Width=90, Height=BTN_H,
            Label="New chat")
        add("com.sun.star.awt.UnoControlButton", "btn_cancel",
            PositionX=DLG_W - 90 - PAD, PositionY=by, Width=90, Height=BTN_H,
            Label="Close")

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

        self.dialog.getControl("btn_load").addActionListener(
            ui.ActionListener(lambda event: self._pick("load")))
        self.dialog.getControl("btn_delete").addActionListener(
            ui.ActionListener(lambda event: self._delete()))
        self.dialog.getControl("btn_new").addActionListener(
            ui.ActionListener(lambda event: self._pick("new")))
        self.dialog.getControl("btn_cancel").addActionListener(
            ui.ActionListener(lambda event: self._close()))
        self._reload()

    def _reload(self):
        self.items = cp_conversations.list_conversations()
        labels = ["%s  (%d)" % (item["name"], item["count"]) for item in self.items]
        ui.set_string_list(self.dialog.getControl("list").getModel(), labels)
        try:
            if labels:
                self.dialog.getControl("list").selectItemPos(0, True)
        except Exception:
            pass

    def _selected_id(self):
        try:
            pos = self.dialog.getControl("list").getSelectedItemPos()
        except Exception:
            pos = -1
        if 0 <= pos < len(self.items):
            return self.items[pos]["id"]
        return None

    def _pick(self, action):
        cid = self._selected_id()
        if action == "load" and not cid:
            return
        self.result = (action, cid)
        self._close()

    def _delete(self):
        cid = self._selected_id()
        if cid:
            cp_conversations.delete(cid)
            self.result = ("delete", cid)
            self._reload()

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
        return self.result


def show(ctx, frame):
    bridge = _Bridge(ctx, frame)
    bridge.build()
    return bridge.run()
