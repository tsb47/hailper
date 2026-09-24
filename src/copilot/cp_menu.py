"""Small modal menu for the panel's ⋯ button (model, starters, history, agent)."""

import cp_personas
import cp_ui as ui

DLG_W = 320
PAD = 8
LINE_H = 13
BTN_H = 20
MAP_PIXEL = 7


class _Bridge(object):
    def __init__(self, ctx, frame, config, model_visible, agent_on):
        self.ctx = ctx
        self.frame = frame
        self.config = config
        self.model_visible = model_visible
        self.agent_on = agent_on
        self.starters = cp_personas.starters(config)[:4]
        self.model = None
        self.dialog = None
        self.result = (None, None)

    def build(self):
        ctx = self.ctx
        rows = 6 + len(self.starters) + (1 if self.starters else 0)
        height = PAD * 2 + rows * (BTN_H + 4) + LINE_H + 4
        self.model = ui.smgr(ctx).createInstanceWithContext(
            "com.sun.star.awt.UnoControlDialogModel", ctx)
        self.model.setPropertyValue("Title", "HaiLPER")
        try:
            self.model.setPropertyValue("MapUnit", MAP_PIXEL)
        except Exception:
            pass
        self.model.setPropertyValue("Width", DLG_W)
        self.model.setPropertyValue("Height", height)
        self.model.setPropertyValue("Moveable", True)
        self.model.setPropertyValue("Closeable", True)
        content_w = DLG_W - 2 * PAD

        def add(service, name, **props):
            self.model.insertByName(
                name, ui.create_model(self.model, service, name, **props))

        y = PAD
        add("com.sun.star.awt.UnoControlButton", "btn_model",
            PositionX=PAD, PositionY=y, Width=content_w, Height=BTN_H,
            Label="Model picker: %s" % ("shown" if self.model_visible else "hidden"))
        y += BTN_H + 4
        if self.starters:
            add("com.sun.star.awt.UnoControlFixedText", "starters_label",
                PositionX=PAD, PositionY=y, Width=content_w, Height=LINE_H,
                Label="Starter prompts:")
            y += LINE_H + 4
            for index, starter in enumerate(self.starters):
                add("com.sun.star.awt.UnoControlButton",
                    "starter_%d" % index,
                    PositionX=PAD, PositionY=y, Width=content_w, Height=BTN_H,
                    Label=starter[:52], FontHeight=5.0)
                y += BTN_H + 4
        add("com.sun.star.awt.UnoControlButton", "btn_history",
            PositionX=PAD, PositionY=y, Width=content_w, Height=BTN_H,
            Label="History\u2026")
        y += BTN_H + 4
        add("com.sun.star.awt.UnoControlButton", "btn_new",
            PositionX=PAD, PositionY=y, Width=content_w, Height=BTN_H,
            Label="New chat")
        y += BTN_H + 4
        add("com.sun.star.awt.UnoControlButton", "btn_agent",
            PositionX=PAD, PositionY=y, Width=content_w, Height=BTN_H,
            Label="Agent mode: %s" % ("on" if self.agent_on else "off"))
        y += BTN_H + 4
        add("com.sun.star.awt.UnoControlButton", "btn_context",
            PositionX=PAD, PositionY=y, Width=content_w, Height=BTN_H,
            Label="Show context\u2026")
        y += BTN_H + 4
        add("com.sun.star.awt.UnoControlButton", "btn_diagnostics",
            PositionX=PAD, PositionY=y, Width=content_w, Height=BTN_H,
            Label="Copy diagnostics")
        y += BTN_H + 4
        add("com.sun.star.awt.UnoControlButton", "btn_close",
            PositionX=PAD, PositionY=y, Width=content_w, Height=BTN_H,
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

        self.dialog.getControl("btn_model").addActionListener(
            ui.ActionListener(lambda event: self._pick("model")))
        self.dialog.getControl("btn_history").addActionListener(
            ui.ActionListener(lambda event: self._pick("history")))
        self.dialog.getControl("btn_new").addActionListener(
            ui.ActionListener(lambda event: self._pick("newchat")))
        self.dialog.getControl("btn_agent").addActionListener(
            ui.ActionListener(lambda event: self._pick("agent")))
        self.dialog.getControl("btn_context").addActionListener(
            ui.ActionListener(lambda event: self._pick("context")))
        self.dialog.getControl("btn_diagnostics").addActionListener(
            ui.ActionListener(lambda event: self._pick("diagnostics")))
        self.dialog.getControl("btn_close").addActionListener(
            ui.ActionListener(lambda event: self._pick("close")))
        for index, starter in enumerate(self.starters):
            control = self.dialog.getControl("starter_%d" % index)
            control.addActionListener(
                ui.ActionListener(
                    lambda event, text=starter: self._pick("starter", text)))

    def _pick(self, action, payload=None):
        self.result = (action, payload)
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
        return self.result


def show(ctx, frame, config, model_visible=False, agent_on=False):
    bridge = _Bridge(ctx, frame, config, model_visible, agent_on)
    bridge.build()
    return bridge.run()
