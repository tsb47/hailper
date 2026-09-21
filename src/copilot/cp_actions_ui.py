"""Manage custom actions (add / edit / delete) stored in actions.json."""

import cp_actions
import cp_prompt
import cp_ui as ui

DLG_W = 440
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
        self.actions = []

    def build(self):
        ctx = self.ctx
        self.model = ui.smgr(ctx).createInstanceWithContext(
            "com.sun.star.awt.UnoControlDialogModel", ctx)
        self.model.setPropertyValue("Title", "HaiLPER - Custom actions")
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

        add("com.sun.star.awt.UnoControlListBox", "list",
            PositionX=PAD, PositionY=PAD, Width=content_w,
            Height=DLG_H - 2 * BTN_H - 3 * PAD, Dropdown=False)
        by = DLG_H - BTN_H - PAD
        add("com.sun.star.awt.UnoControlButton", "btn_add",
            PositionX=PAD, PositionY=by, Width=70, Height=BTN_H, Label="Add")
        add("com.sun.star.awt.UnoControlButton", "btn_edit",
            PositionX=PAD + 76, PositionY=by, Width=70, Height=BTN_H, Label="Edit")
        add("com.sun.star.awt.UnoControlButton", "btn_delete",
            PositionX=PAD + 152, PositionY=by, Width=70, Height=BTN_H, Label="Delete")
        add("com.sun.star.awt.UnoControlButton", "btn_close",
            PositionX=DLG_W - 70 - PAD, PositionY=by, Width=70, Height=BTN_H,
            Label="Close", DefaultButton=True)

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

        self.dialog.getControl("btn_add").addActionListener(
            ui.ActionListener(lambda event: self._add()))
        self.dialog.getControl("btn_edit").addActionListener(
            ui.ActionListener(lambda event: self._edit()))
        self.dialog.getControl("btn_delete").addActionListener(
            ui.ActionListener(lambda event: self._delete()))
        self.dialog.getControl("btn_close").addActionListener(
            ui.ActionListener(lambda event: self._close()))
        self._reload()

    def _reload(self):
        self.actions = cp_actions.load()
        ui.set_string_list(self.dialog.getControl("list").getModel(),
                           [a["title"] for a in self.actions])

    def _selected(self):
        try:
            pos = self.dialog.getControl("list").getSelectedItemPos()
        except Exception:
            pos = -1
        if 0 <= pos < len(self.actions):
            return pos
        return -1

    def _ask(self, existing):
        title = cp_prompt.ask(self.ctx, self.frame, "Custom action",
                              "Title:", existing.get("title", "") if existing else "")
        if not title:
            return None
        instruction = cp_prompt.ask(
            self.ctx, self.frame, "Custom action",
            "Instruction / prompt:", existing.get("instruction", "") if existing else "")
        scope = cp_prompt.ask(
            self.ctx, self.frame, "Custom action",
            "Scope (selection or document):",
            existing.get("scope", "selection") if existing else "selection")
        return cp_actions.normalize({
            "id": existing.get("id") if existing else None,
            "title": title,
            "instruction": instruction,
            "scope": scope.strip().lower(),
            "primary": existing.get("primary") if existing else None,
        })

    def _add(self):
        action = self._ask(None)
        if not action:
            return
        self.actions.append(action)
        cp_actions.save(self.actions)
        cp_actions.register()
        self._reload()

    def _edit(self):
        pos = self._selected()
        if pos < 0:
            return
        action = self._ask(self.actions[pos])
        if not action:
            return
        self.actions[pos] = action
        cp_actions.save(self.actions)
        cp_actions.register()
        self._reload()

    def _delete(self):
        pos = self._selected()
        if pos < 0:
            return
        del self.actions[pos]
        cp_actions.save(self.actions)
        cp_actions.register()
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


def show(ctx, frame):
    bridge = _Bridge(ctx, frame)
    bridge.build()
    bridge.run()
