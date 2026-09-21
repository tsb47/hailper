"""Manage personas (add / edit / delete) stored in the config."""

import cp_config
import cp_personas
import cp_prompt
import cp_ui as ui

DLG_W = 440
DLG_H = 320
PAD = 10
LINE_H = 14
BTN_H = 24
MAP_PIXEL = 7


class _Bridge(object):
    def __init__(self, ctx, frame, config):
        self.ctx = ctx
        self.frame = frame
        self.config = config
        self.model = None
        self.dialog = None
        self.personas = []

    def build(self):
        ctx = self.ctx
        self.model = ui.smgr(ctx).createInstanceWithContext(
            "com.sun.star.awt.UnoControlDialogModel", ctx)
        self.model.setPropertyValue("Title", "HaiLPER - Personas")
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
        self.personas = cp_personas.get_personas(self.config)
        ui.set_string_list(self.dialog.getControl("list").getModel(),
                           [p.get("name", "?") for p in self.personas])

    def _selected(self):
        try:
            pos = self.dialog.getControl("list").getSelectedItemPos()
        except Exception:
            pos = -1
        return pos if 0 <= pos < len(self.personas) else -1

    def _ask(self, existing):
        name = cp_prompt.ask(self.ctx, self.frame, "Persona", "Name:",
                             existing.get("name", "") if existing else "")
        if not name:
            return None
        prompt = cp_prompt.ask(
            self.ctx, self.frame, "Persona", "System prompt:",
            existing.get("system_prompt", "") if existing else "")
        model = cp_prompt.ask(
            self.ctx, self.frame, "Persona",
            "Model override (blank = keep):",
            existing.get("model", "") if existing else "")
        return {
            "id": existing.get("id") if existing else "custom_%d" % (
                len(self.personas) + 1),
            "name": name,
            "system_prompt": prompt,
            "model": model.strip(),
            "temperature": existing.get("temperature") if existing else None,
            "actions": existing.get("actions") if existing else None,
            "starters": existing.get("starters", []) if existing else [],
        }

    def _add(self):
        persona = self._ask(None)
        if not persona:
            return
        self.personas.append(persona)
        self._save()

    def _edit(self):
        pos = self._selected()
        if pos < 0:
            return
        persona = self._ask(self.personas[pos])
        if not persona:
            return
        self.personas[pos] = persona
        self._save()

    def _delete(self):
        pos = self._selected()
        if pos < 0:
            return
        del self.personas[pos]
        self._save()

    def _save(self):
        self.config["personas"] = self.personas
        cp_config.save(self.config)
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


def show(ctx, frame, config):
    bridge = _Bridge(ctx, frame, config)
    bridge.build()
    bridge.run()
