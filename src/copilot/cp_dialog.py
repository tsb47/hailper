"""A persistent, modeless HaiLPER side panel.

The panel docks to the right edge of the frame, follows window move/resize, and
runs generation on a worker thread (marshalled back with AsyncCallback) so the
document stays usable while the model is thinking.

Each action presents its own contextual set of buttons (for example Summarize
offers "New document", Proofread offers "Review suggestions").
"""

import threading
import time

import uno
import unohelper

from com.sun.star.awt import XTopWindowListener
from com.sun.star.awt import XWindowListener

import cp_actions
import cp_agents
import cp_config
import cp_context
import cp_conversations
import cp_document
import cp_format
import cp_history
import cp_markdown
import cp_menu
import cp_personas
import cp_prompts
import cp_providers
import cp_usage
import cp_ui as ui


DLG_W = 170
DLG_H = 326
PAD = 4
LINE_H = 10
BTN_H = 13
RESULT_H = 90
RESULT_MIN = 44
RESULT_MAX = 400
RESULT_CHROME_PX = 150
FONT_H = 8
MAP_PIXEL = 7
POS_FLAGS = 3  # com.sun.star.awt.PosSize.X | PosSize.Y
SLOTS = 6

_ICON_BASE = ("vnd.sun.star.extension://io.github.rokusaburo.hailper/"
              "icons/%s.png")

_PLACEHOLDERS = {
    "chat": "Ask anything about this document\u2026",
    "summarize": "Extra focus or length (optional)\u2026",
    "rewrite": "How should I rewrite it? (optional)\u2026",
    "translate": "Target terms or context (optional)\u2026",
    "proofread": "Focus areas (optional)\u2026",
    "continue": "Where should it go next? (optional)\u2026",
    "explain": "What should I explain? (optional)\u2026",
    "custom": "Describe what you want me to do\u2026",
}
_PLACEHOLDER_GREY = 0x9A9A9A

_panel = None


class _FrameListener(unohelper.Base, XWindowListener):
    def __init__(self, bridge):
        self.bridge = bridge

    def windowResized(self, event):
        self.bridge.dock()

    def windowMoved(self, event):
        self.bridge.dock()

    def windowShown(self, event):
        pass

    def windowHidden(self, event):
        pass

    def disposing(self, event):
        pass


class _PanelWindowListener(unohelper.Base, XTopWindowListener):
    def __init__(self, bridge):
        self.bridge = bridge

    def windowOpened(self, event):
        pass

    def windowClosing(self, event):
        self.bridge.hide()

    def windowClosed(self, event):
        self.bridge.alive = False

    def windowMinimized(self, event):
        pass

    def windowNormalized(self, event):
        pass

    def windowActivated(self, event):
        pass

    def windowDeactivated(self, event):
        pass

    def disposing(self, event):
        self.bridge.alive = False


class _Bridge(object):
    def __init__(self, ctx, frame, action, config):
        self.ctx = ctx
        self.frame = frame
        self.config = config
        self.action = action
        self.meta = cp_prompts.action_meta(action)
        self.result_text = ""
        self.suggestions = []
        self.slot_keys = []
        self.alive = True
        self.busy = False
        self.built = False
        self.history = []
        self.pending_action = action
        self.gen_id = 0
        self.visible_choices = []
        self.on_layout = None
        self.scope = None
        self.scale = None
        self.captured_text = ""
        self.available_px = 0
        self.doc_requested = False
        self.reviewing = False
        self.review_index = 0
        self.review_fixed = 0
        self.review_ignored = 0
        self.review_slots = []
        self.flow = None
        self.flow_action = None
        self.flow_doc_ctx = None
        self.proposal = ""
        self.refining = False
        self.streaming = False
        self.streaming_partial = ""
        self.model_picker_visible = False
        self.agent_mode = bool((config.get("agents") or {}).get("enabled", False))
        self.agent_active = False
        self.agent_steps = 0
        self.agent_max = 0
        self.agent_messages = None
        self.agent_system = ""
        self.last_usage = None
        self.session_usage = {"tokens": 0, "cost": 0.0, "calls": 0}
        self.action_titles = []
        self.visible_action_keys = []
        self.conversation_id = None
        self.starter_chips = []
        self._chips_visible = False
        self.feedback_mode = None
        try:
            cp_actions.register()
        except Exception:
            pass

        self.async_callback = ui.smgr(ctx).createInstanceWithContext(
            "com.sun.star.awt.AsyncCallback", ctx
        )
        self.callback_object = ui.Callback(self._on_result)

        self.model = None
        self.dialog = None
        self.frame_listener = None
        self.is_sidebar = False

    # ------------------------------------------------------------- documents
    def _current_document(self):
        try:
            controller = self.frame.getController()
            if controller is not None:
                model = controller.getModel()
                if model is not None:
                    return model
        except Exception:
            pass
        try:
            desktop = self.ctx.getByName(
                "/singletons/com.sun.star.frame.theDesktop"
            )
        except Exception:
            return None
        try:
            frame = desktop.getCurrentFrame()
            if frame is not None:
                controller = frame.getController()
                if controller is not None:
                    model = controller.getModel()
                    if model is not None:
                        return model
        except Exception:
            pass
        try:
            return desktop.getCurrentComponent()
        except Exception:
            return None

    def _current_doc_ctx(self):
        document = self._current_document()
        if document is None:
            return None
        return cp_document.DocumentContext(self.ctx, document)

    # ------------------------------------------------------------- building
    def build_into(self, host_window, peer_parent=None, is_sidebar=False):
        """Build the controls into an existing host window.

        host_window is either a com.sun.star.awt.UnoControlDialog (floating
        panel) or a ContainerWindowProvider window (sidebar panel).
        """
        ctx = self.ctx
        self.dialog = host_window
        self.is_sidebar = is_sidebar
        self.model = ui.smgr(ctx).createInstanceWithContext(
            "com.sun.star.awt.UnoControlDialogModel", ctx
        )
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

        persona_choice = ui.create_model(
            self.model, "com.sun.star.awt.UnoControlComboBox", "persona_choice",
            PositionX=0, PositionY=0, Width=58, Height=LINE_H + 4,
            Dropdown=True, HelpText="Persona")
        self.model.insertByName("persona_choice", persona_choice)
        action_choice = ui.create_model(
            self.model, "com.sun.star.awt.UnoControlComboBox", "action_choice",
            PositionX=0, PositionY=0, Width=content_w - 78, Height=LINE_H + 4,
            Dropdown=True, HelpText="Action")
        self.model.insertByName("action_choice", action_choice)
        add("com.sun.star.awt.UnoControlEdit", "instruction",
            PositionX=0, PositionY=0, Width=content_w, Height=40,
            MultiLine=True, VScroll=True, HScroll=False)
        for index in range(2):
            add("com.sun.star.awt.UnoControlFixedText", "choice_label_%d" % index,
                PositionX=0, PositionY=0, Width=60, Height=LINE_H, Label="")
            combo = ui.create_model(
                self.model, "com.sun.star.awt.UnoControlComboBox",
                "choice_%d" % index, PositionX=0, PositionY=0,
                Width=content_w, Height=LINE_H + 4, Dropdown=True)
            self.model.insertByName("choice_%d" % index, combo)
        add("com.sun.star.awt.UnoControlButton", "generate",
            PositionX=0, PositionY=0, Width=content_w, Height=BTN_H + 2,
            Label="Send", DefaultButton=True)

        add("com.sun.star.awt.UnoControlFixedText", "provider_label",
            PositionX=0, PositionY=0, Width=30, Height=LINE_H,
            Label="Model:", Align=0)
        model_choice = ui.create_model(
            self.model, "com.sun.star.awt.UnoControlComboBox", "model_choice",
            PositionX=0, PositionY=0, Width=content_w - 32,
            Height=LINE_H + 3, Dropdown=True)
        self.model.insertByName("model_choice", model_choice)
        add("com.sun.star.awt.UnoControlButton", "menu_btn",
            PositionX=0, PositionY=0, Width=16, Height=LINE_H + 4,
            ImageURL=_ICON_BASE % "menu-16.png",
            HelpText="Menu: model, starters, history, agent")
        add("com.sun.star.awt.UnoControlEdit", "result",
            PositionX=0, PositionY=0, Width=content_w, Height=RESULT_H,
            MultiLine=True, ReadOnly=True, VScroll=True, HScroll=False)
        for index in range(3):
            add("com.sun.star.awt.UnoControlButton", "chip_%d" % index,
                PositionX=0, PositionY=0, Width=content_w, Height=10,
                Label="", FontHeight=5.0,
                HelpText="Starter prompt")
        add("com.sun.star.awt.UnoControlFixedText", "status",
            PositionX=0, PositionY=0, Width=content_w, Height=LINE_H, Label="")
        add("com.sun.star.awt.UnoControlButton", "feedback_btn",
            PositionX=0, PositionY=0, Width=56, Height=LINE_H + 4,
            Label="Undo", FontHeight=5.0,
            HelpText="Undo the last change, or retry after an error")
        add("com.sun.star.awt.UnoControlFixedText", "usage_label",
            PositionX=0, PositionY=0, Width=content_w, Height=LINE_H,
            Label="", FontHeight=4.5, TextColor=0x9A9A9A)
        for slot in range(SLOTS):
            add("com.sun.star.awt.UnoControlButton", "btn_%d" % slot,
                PositionX=0, PositionY=0, Width=1, Height=BTN_H, Label="")

        self._relayout(controls_ready=False)

        self.dialog.setModel(self.model)
        toolkit = ui.smgr(ctx).createInstanceWithContext("com.sun.star.awt.Toolkit", ctx)
        self.dialog.createPeer(toolkit, peer_parent)

        self.dialog.getControl("generate").addActionListener(
            ui.ActionListener(lambda event: self.on_generate())
        )
        try:
            self.dialog.getControl("action_choice").addItemListener(
                ui.ItemListener(lambda event: self.on_action_changed()))
        except Exception:
            pass
        try:
            self.dialog.getControl("persona_choice").addItemListener(
                ui.ItemListener(lambda event: self.on_persona_changed()))
        except Exception:
            pass
        try:
            self.dialog.getControl("instruction").addTextListener(
                ui.TextListener(lambda event: self.on_instruction_changed()))
        except Exception:
            pass
        for index in range(3):
            try:
                self.dialog.getControl("chip_%d" % index).addActionListener(
                    ui.ActionListener(lambda event, i=index: self.on_chip(i)))
            except Exception:
                pass
        try:
            self.dialog.getControl("model_choice").addItemListener(
                ui.ItemListener(lambda event: self.on_model_changed()))
        except Exception:
            pass
        try:
            self.dialog.getControl("menu_btn").addActionListener(
                ui.ActionListener(lambda event: self.on_menu()))
        except Exception:
            pass
        try:
            self.dialog.getControl("feedback_btn").addActionListener(
                ui.ActionListener(lambda event: self.on_feedback()))
        except Exception:
            pass
        try:
            self._normal_text_color = self.dialog.getControl(
                "instruction").getModel().getPropertyValue("TextColor")
        except Exception:
            self._normal_text_color = 0
        try:
            self.dialog.getControl("instruction").addFocusListener(
                ui.FocusListener(self.on_instruction_focus_gained,
                                 self.on_instruction_focus_lost))
        except Exception:
            pass

        for slot in range(SLOTS):
            self.dialog.getControl("btn_%d" % slot).addActionListener(
                ui.ActionListener(lambda event, s=slot: self._on_slot(s))
            )
        if not is_sidebar:
            try:
                self.dialog.addTopWindowListener(_PanelWindowListener(self))
            except Exception:
                pass
        self.built = True
        self._set_feedback(None)
        self.apply_meta()

    # ------------------------------------------------------------- layout
    def _place(self, name, x, y, w, h):
        try:
            model = self.model.getByName(name)
            model.setPropertyValue("PositionX", x)
            model.setPropertyValue("PositionY", y)
            model.setPropertyValue("Width", w)
            model.setPropertyValue("Height", h)
        except Exception:
            pass

    def _ensure_scale(self):
        if getattr(self, "scale", None):
            return
        self.scale = 1.0
        try:
            width = self.dialog.getControl("generate").getPosSize().Width
            if width > 0:
                self.scale = width / float(DLG_W - 2 * PAD)
        except Exception:
            pass

    def _set_rect(self, name, x, y, w, h):
        scale = getattr(self, "scale", 1.0) or 1.0
        try:
            self.dialog.getControl(name).setPosSize(
                int(round(x * scale)), int(round(y * scale)),
                int(round(w * scale)), int(round(h * scale)), 15)
        except Exception:
            pass

    def _relayout(self, controls_ready=True):
        if getattr(self, "flow", None):
            self._relayout_flow(controls_ready)
            return
        show_model = bool(getattr(self, "model_picker_visible", False))
        if controls_ready:
            self._ensure_scale()
            for name in ("instruction", "generate", "result",
                         "status", "usage_label",
                         "action_choice", "persona_choice",
                         "menu_btn"):
                try:
                    self.dialog.getControl(name).setVisible(True)
                except Exception:
                    pass
            for name in ("provider_label", "model_choice"):
                try:
                    self.dialog.getControl(name).setVisible(show_model)
                except Exception:
                    pass
            self._update_action_selector()
            self._update_persona_selector()
            self._update_usage_line()
            self._update_chips()
        content_w = DLG_W - 2 * PAD
        visible = getattr(self, "visible_choices", [])
        positions = {}
        y = PAD
        # One compact row: Persona (main) | Action | ⋯ menu.
        positions["persona_choice"] = (PAD, y, 58, LINE_H + 4)
        positions["action_choice"] = (PAD + 62, y, content_w - 80, LINE_H + 4)
        positions["menu_btn"] = (PAD + content_w - 16, y, 16, LINE_H + 4)
        y += LINE_H + 6
        for index in range(2):
            if index < len(visible):
                positions["choice_label_%d" % index] = (PAD, y + 1, 48, LINE_H + 3)
                positions["choice_%d" % index] = (
                    PAD + 50, y, content_w - 50, LINE_H + 3)
                y += LINE_H + 5

        result_y = y

        # Everything below the transcript: input, send, scope, status, buttons
        # and the subtle usage line at the very bottom.
        below = (28 + (BTN_H + 4) + (LINE_H + 4)
                 + (2 * BTN_H + 2) + (LINE_H + 4) + PAD)
        if show_model:
            below += LINE_H + 4
        if getattr(self, "_chips_visible", False):
            below += 3 * 12 + 2

        scale = getattr(self, "scale", 1.0) or 1.0
        result_h = RESULT_H
        available = getattr(self, "available_px", 0)
        if available:
            budget = max(RESULT_MIN, (available - RESULT_CHROME_PX) / scale)
            result_h = max(RESULT_MIN,
                           min(RESULT_MAX, budget - result_y - below))
        positions["result"] = (PAD, result_y, content_w, result_h)
        y = result_y + result_h + 4

        if getattr(self, "_chips_visible", False):
            for index in range(min(3, len(self.starter_chips))):
                positions["chip_%d" % index] = (PAD, y, content_w, 10)
                y += 12
            y += 2

        positions["instruction"] = (PAD, y, content_w, 26)
        y += 28
        positions["generate"] = (PAD, y, content_w, BTN_H + 2)
        y += BTN_H + 4
        if show_model:
            positions["provider_label"] = (PAD, y, 30, LINE_H)
            positions["model_choice"] = (PAD + 32, y, content_w - 32, LINE_H + 3)
            y += LINE_H + 4
        positions["status"] = (PAD, y, content_w - 58, LINE_H)
        positions["feedback_btn"] = (PAD + content_w - 56, y - 1, 56, LINE_H + 3)
        y += LINE_H + 4
        bw = (content_w - 2 * 4) // 3
        for slot in range(SLOTS):
            row = slot // 3
            col = slot % 3
            positions["btn_%d" % slot] = (
                PAD + col * (bw + 4), y + row * (BTN_H + 2), bw, BTN_H)
        y += 2 * BTN_H + 2
        positions["usage_label"] = (PAD, y + 2, content_w, LINE_H)
        total = y + 2 + LINE_H + PAD

        for name, rect in positions.items():
            self._place(name, *rect)
        try:
            self.model.setPropertyValue("Height", total)
        except Exception:
            pass

        if not controls_ready:
            return
        self._ensure_scale()
        for index in range(2):
            show = index < len(visible)
            try:
                self.dialog.getControl("choice_label_%d" % index).setVisible(show)
                self.dialog.getControl("choice_%d" % index).setVisible(show)
            except Exception:
                pass
        for name, rect in positions.items():
            self._set_rect(name, *rect)
        self._notify_layout()

    def _notify_layout(self):
        callback = getattr(self, "on_layout", None)
        if callable(callback):
            try:
                callback()
            except Exception:
                pass

    def _relayout_flow(self, controls_ready=True):
        if controls_ready:
            self._ensure_scale()
        content_w = DLG_W - 2 * PAD
        positions = {}
        y = PAD
        result_y = y
        # Keep flow panels compact so the action buttons are always visible.
        result_h = RESULT_MIN
        positions["result"] = (PAD, result_y, content_w, result_h)
        y = result_y + result_h + 4
        positions["status"] = (PAD, y, content_w - 58, LINE_H)
        positions["feedback_btn"] = (PAD + content_w - 56, y - 1, 56, LINE_H + 3)
        y += LINE_H + 4
        bw = (content_w - 2 * 4) // 3
        for slot in range(SLOTS):
            row = slot // 3
            col = slot % 3
            positions["btn_%d" % slot] = (
                PAD + col * (bw + 4), y + row * (BTN_H + 2), bw, BTN_H)
        total = y + 2 * BTN_H + 2 + PAD

        for name, rect in positions.items():
            self._place(name, *rect)
        try:
            self.model.setPropertyValue("Height", total)
        except Exception:
            pass
        if not controls_ready:
            return
        for name in ("instruction", "generate",
                     "provider_label", "model_choice",
                     "choice_label_0", "choice_0",
                     "choice_label_1", "choice_1",
                     "action_choice", "persona_choice", "usage_label",
                     "menu_btn",
                     "chip_0", "chip_1", "chip_2"):
            try:
                self.dialog.getControl(name).setVisible(False)
            except Exception:
                pass
        for name in ("result", "status", "feedback_btn"):
            try:
                self.dialog.getControl(name).setVisible(True)
            except Exception:
                pass
        for name, rect in positions.items():
            self._set_rect(name, *rect)
        self._notify_layout()

    # ------------------------------------------------------------- meta
    def set_action(self, action):
        changed = action != self.action
        self.action = action
        self.meta = cp_prompts.action_meta(action)
        if changed:
            self.suggestions = []
        if self.built:
            self.apply_meta()

    def on_action_changed(self):
        if self.flow:
            return
        title = ui.get_text(self.dialog, "action_choice").strip()
        key = self._key_for_title(title)
        if key and key != self.action:
            self.set_action(key)

    def _key_for_title(self, title):
        for key, label in self._action_pairs():
            if label == title:
                return key
        # custom actions use their title directly
        for key in cp_prompts.custom_actions():
            if cp_prompts.action_meta(key).get("title") == title:
                return key
        return None

    def parsed_action_title(self, key):
        return cp_prompts.action_meta(key).get("title", key.title())

    def on_persona_changed(self):
        if self.flow:
            return
        name = ui.get_text(self.dialog, "persona_choice").strip()
        for persona in cp_personas.get_personas(self.config):
            if persona.get("name") == name:
                self.config["persona"] = persona.get("id")
                cp_config.save(self.config)
                self.apply_meta()
                return

    def on_instruction_changed(self):
        before = getattr(self, "_chips_visible", False)
        self._update_chips()
        if self._chips_visible != before and self.built:
            self._relayout(controls_ready=True)

    def _update_chips(self):
        starters = cp_personas.starters(self.config)[:3]
        self.starter_chips = starters
        prompt = ui.get_text(self.dialog, "instruction")
        typing = bool(prompt.strip()) and prompt != getattr(self, "placeholder", None)
        self._chips_visible = ((not self.history) and bool(starters)
                               and not typing)
        for index in range(3):
            try:
                control = self.dialog.getControl("chip_%d" % index)
                if self._chips_visible and index < len(starters):
                    control.setLabel(starters[index][:44])
                    control.setVisible(True)
                else:
                    control.setVisible(False)
            except Exception:
                pass

    def on_chip(self, index):
        if 0 <= index < len(getattr(self, "starter_chips", [])):
            self._set_instruction_text(self.starter_chips[index], grey=False)
            try:
                self.dialog.getControl("instruction").setFocus()
            except Exception:
                pass

    def on_history(self):
        action, cid = cp_history.show(self.ctx, self.frame)
        if action == "new":
            self.on_clear()
            self.conversation_id = None
            self._set_status("Started a new conversation.")
        elif action == "load" and cid:
            self._load_conversation(cid)

    def _load_conversation(self, cid):
        data = cp_conversations.load(cid)
        if not data:
            self._set_status("Could not load that conversation.")
            return
        self.conversation_id = cid
        self.history = [(m.get("who", "HaiLPER"), m.get("text", ""))
                        for m in data.get("messages", [])]
        self._refresh_history_view()
        self._set_status("Loaded \u201c%s\u201d." % (data.get("name") or "conversation"))

    def _persist_conversation(self):
        if not (self.config.get("history") or {}).get("persist", True):
            return
        messages = [{"who": who, "text": text} for who, text in self.history]
        if not messages:
            return
        name = ""
        for who, text in self.history:
            if who == "You":
                name = text.strip().split("\n")[0][:60]
                break
        meta = {"provider": self.config.get("provider"),
                "model": cp_config.active_provider(self.config)[3],
                "persona": self.config.get("persona")}
        if self.conversation_id:
            cp_conversations.update(self.conversation_id, name, messages, meta)
        else:
            self.conversation_id = cp_conversations.save(name, messages, meta)

    def on_toggle_agent(self):
        self.agent_mode = not self.agent_mode
        self._set_status("Agent mode on \u2014 multi-step." if self.agent_mode
                         else "Agent mode off.")

    def _update_usage_line(self):
        show = (self.config.get("usage") or {}).get("show", True)
        try:
            control = self.dialog.getControl("usage_label")
            control.setVisible(bool(show))
            if not show:
                return
            pid, spec, _key, model, _base = cp_config.active_provider(self.config)
            window = cp_context.context_window(pid, model, self.config)
            if self.last_usage is None and not self.session_usage.get("tokens"):
                control.setText("%s  \u00b7  %s  \u00b7  %s ctx"
                                % (spec.get("label", pid), model,
                                   "{:,}".format(window)))
                return
            control.setText(cp_usage.format_line(
                pid, model, self.last_usage or {"input": 0, "output": 0},
                self.session_usage, window, self.config))
        except Exception:
            pass

    def _record_usage(self, usage):
        if not usage:
            return
        self.last_usage = usage
        total = (usage.get("input", 0) or 0) + (usage.get("output", 0) or 0)
        self.session_usage["tokens"] = self.session_usage.get("tokens", 0) + total
        self.session_usage["calls"] = self.session_usage.get("calls", 0) + 1
        pid, _spec, _key, model, _base = cp_config.active_provider(self.config)
        self.session_usage["cost"] = (self.session_usage.get("cost", 0.0)
                                      + cp_usage.cost(pid, model, usage, self.config))
        ui.log("usage in=%s out=%s session_tokens=%s cost=%s"
               % (usage.get("input"), usage.get("output"),
                  self.session_usage.get("tokens"),
                  cp_usage.money(self.session_usage.get("cost", 0.0))))
        self._update_usage_line()

    def _placeholder_for(self, action):
        if action in cp_prompts.custom_actions():
            return "Add context (optional)\u2026"
        return _PLACEHOLDERS.get(action, "Type a message\u2026")

    def _set_instruction_text(self, value, grey=False):
        try:
            control = self.dialog.getControl("instruction")
            control.setText(value)
            control.getModel().setPropertyValue(
                "TextColor", _PLACEHOLDER_GREY if grey
                else getattr(self, "_normal_text_color", 0))
        except Exception:
            pass

    def _refresh_placeholder(self):
        placeholder = self._placeholder_for(self.action)
        previous = getattr(self, "placeholder", None)
        self.placeholder = placeholder
        current = ui.get_text(self.dialog, "instruction")
        if not current.strip() or (previous and current == previous):
            self._set_instruction_text(placeholder, grey=True)

    def on_instruction_focus_gained(self):
        if ui.get_text(self.dialog, "instruction") == getattr(self, "placeholder", None):
            self._set_instruction_text("", grey=False)

    def on_instruction_focus_lost(self):
        if not ui.get_text(self.dialog, "instruction").strip():
            self._refresh_placeholder()

    def _instruction_value(self):
        text = ui.get_text(self.dialog, "instruction").strip()
        if text and text == getattr(self, "placeholder", None):
            return ""
        return text

    def on_menu(self):
        action, payload = cp_menu.show(
            self.ctx, self.frame, self.config,
            self.model_picker_visible, self.agent_mode)
        if action == "model":
            self.on_toggle_model()
        elif action == "starter" and payload:
            self._set_instruction_text(payload, grey=False)
            try:
                self.dialog.getControl("instruction").setFocus()
            except Exception:
                pass
        elif action == "history":
            self.on_history()
        elif action == "newchat":
            self.on_clear()
        elif action == "agent":
            self.on_toggle_agent()

    def on_toggle_model(self):
        self.model_picker_visible = not self.model_picker_visible
        self._relayout(controls_ready=True)
        self._set_status("Model picker shown." if self.model_picker_visible
                         else "Model picker hidden.")

    def on_model_changed(self):
        model = ui.get_text(self.dialog, "model_choice").strip()
        if not model:
            return
        pid, _spec, _key, current, _base = cp_config.active_provider(self.config)
        if model == current:
            return
        entry = self.config.setdefault("providers", {}).setdefault(pid, {})
        entry["model"] = model
        cp_config.save(self.config)
        self._set_status("Model set to %s." % model)

    def _action_pairs(self):
        persona = cp_personas.active(self.config)
        pairs = []
        builtin = [
            ("chat", "Chat"),
            ("summarize", "Summarize"),
            ("rewrite", "Rewrite"),
            ("translate", "Translate"),
            ("proofread", "Proofread"),
            ("continue", "Continue"),
            ("explain", "Explain"),
            ("custom", "Ask About Selection"),
        ]
        for key, label in builtin:
            if cp_personas.allows(persona, key):
                pairs.append((key, label))
        for key in cp_prompts.custom_actions():
            if cp_personas.allows(persona, key):
                pairs.append((key, cp_prompts.action_meta(key).get("title", key)))
        return pairs

    def _update_action_selector(self):
        pairs = self._action_pairs()
        self.visible_action_keys = [key for key, _label in pairs]
        labels = [label for _key, label in pairs]
        current = None
        for key, label in pairs:
            if key == self.action:
                current = label
        try:
            combo = self.dialog.getControl("action_choice")
            ui.set_string_list(combo.getModel(), labels)
            if current is None and labels:
                current = labels[0]
                self.action = pairs[0][0]
                self.meta = cp_prompts.action_meta(self.action)
            if current is not None:
                combo.setText(current)
        except Exception:
            pass

    def _update_persona_selector(self):
        personas = cp_personas.get_personas(self.config)
        labels = [persona.get("name", "?") for persona in personas]
        active = cp_personas.active(self.config)
        try:
            combo = self.dialog.getControl("persona_choice")
            ui.set_string_list(combo.getModel(), labels)
            combo.setText(active.get("name", ""))
        except Exception:
            pass

    def apply_meta(self):
        is_chat = self.action == "chat"
        self._update_action_selector()
        self._update_persona_selector()
        self._update_usage_line()
        display = self.meta.get("display_instruction",
                                self.meta.get("instruction", ""))
        if is_chat:
            ui.set_text(self.dialog, "instruction", "")
        else:
            ui.set_text(self.dialog, "instruction", display)
        self._refresh_placeholder()

        choices = self.meta.get("choices", [])
        self.visible_choices = choices
        remembered = self.config.get("action_choices", {}).get(self.action, {})
        for index in range(2):
            combo = self.dialog.getControl("choice_%d" % index)
            if index < len(choices):
                spec = choices[index]
                ui.set_string_list(combo.getModel(), spec["values"])
                value = remembered.get(spec["key"]) or spec.get("default") \
                    or spec["values"][0]
                if value not in spec["values"]:
                    value = spec["values"][0]
                combo.setText(value)
                ui.set_text(self.dialog, "choice_label_%d" % index,
                            spec["label"] + ":")
            else:
                combo.setText("")
        if self.built:
            self._relayout()

        provider_id, spec, _key, model, _base = cp_config.active_provider(self.config)
        models = list(spec.get("models", []))
        if model and model not in models:
            models.insert(0, model)
        try:
            control = self.dialog.getControl("model_choice")
            ui.set_string_list(control.getModel(), models)
            ui.set_text(self.dialog, "model_choice", model)
            control.getModel().setPropertyValue(
                "HelpText", "%s / %s" % (spec["label"], model))
        except Exception:
            pass

        specs = [self.meta.get("primary", ("insert", "Insert"))]
        specs.extend(self.meta.get("buttons", []))
        if (self.action == "rewrite" and specs
                and self.config.get("track_changes", True)):
            key, _label = specs[0]
            specs[0] = (key, "Suggest (tracked)")
        self.slot_keys = [key for key, _label in specs]
        for slot in range(SLOTS):
            control = self.dialog.getControl("btn_%d" % slot)
            if slot < len(specs):
                _key, label = specs[slot]
                control.setLabel(label)
                control.setVisible(True)
            else:
                control.setVisible(False)
                control.setLabel("")

    # ------------------------------------------------------------- history
    def _refresh_history_view(self):
        blocks = []
        for who, message in self.history:
            if who == "You":
                blocks.append("\u203a You\n%s" % message)
            else:
                blocks.append("HaiLPER\n%s" % cp_markdown.render(message))
        if self.streaming_partial:
            blocks.append("HaiLPER\n%s\u258c"
                          % cp_markdown.render(self.streaming_partial))
        separator = "\n\n" + ("\u00b7 " * 18).strip() + "\n\n"
        self.result_text = separator.join(blocks).strip()
        ui.set_text(self.dialog, "result", self.result_text)
        try:
            end = len(self.result_text)
            self.dialog.getControl("result").setSelection(
                uno.createUnoStruct("com.sun.star.awt.Selection", end, end))
        except Exception:
            pass

    def add_history_line(self, speaker, text):
        self.history.append((speaker, text))
        self._refresh_history_view()
        try:
            self._update_chips()
            if self.built:
                self._relayout(controls_ready=True)
        except Exception:
            pass
        try:
            self._persist_conversation()
        except Exception:
            pass

    def history_as_messages(self):
        return [
            {"role": "user" if who == "You" else "assistant", "content": message}
            for who, message in self.history
        ]

    # ------------------------------------------------------------- show/dock
    def dock(self):
        if self.is_sidebar or not self.built or self.dialog is None:
            return
        try:
            parent_rect = self.frame.getContainerWindow().getPosSize()
            peer = self.dialog.getPeer()
            size = peer.getSize()
            x = parent_rect.X + parent_rect.Width - size.Width - 12
            y = parent_rect.Y + 24
            if x < 0:
                x = 0
            if y < 0:
                y = 0
            peer.setPosSize(x, y, size.Width, size.Height, POS_FLAGS)
        except Exception:
            pass

    def show_panel(self):
        if not self.built:
            dialog = ui.smgr(self.ctx).createInstanceWithContext(
                "com.sun.star.awt.UnoControlDialog", self.ctx
            )
            parent = None
            try:
                parent = self.frame.getContainerWindow()
            except Exception:
                parent = None
            self.build_into(dialog, parent)
        if not self.alive:
            return
        self.dock()
        try:
            self.dialog.setVisible(True)
        except Exception:
            pass
        if self.frame_listener is None:
            try:
                self.frame_listener = _FrameListener(self)
                self.frame.getContainerWindow().addWindowListener(self.frame_listener)
            except Exception:
                self.frame_listener = None

    def hide(self):
        try:
            self.dialog.setVisible(False)
        except Exception:
            pass

    # ------------------------------------------------------------- generation
    def _current_choices(self):
        result = {}
        for index, spec in enumerate(getattr(self, "visible_choices", [])):
            value = ui.get_text(self.dialog, "choice_%d" % index).strip()
            result[spec["key"]] = value or spec.get("default")
        return result

    def _remember_choices(self, choices):
        if not choices:
            return
        store = self.config.setdefault("action_choices", {})
        store[self.action] = dict(choices)
        cp_config.save(self.config)

    def set_choices(self, choices):
        """Apply choices (e.g. from a context menu) to the current action."""
        if not choices:
            return
        store = self.config.setdefault("action_choices", {})
        store.setdefault(self.action, {}).update(choices)
        self.apply_meta()

    def on_generate(self):
        ui.log("on_generate action=%s busy=%s" % (self.action, self.busy))
        if self.busy:
            self.on_stop()
            return
        instruction = self._instruction_value()
        if self.action == "chat":
            if not instruction:
                self._set_status("Type a message first.")
                return
        elif not instruction:
            self._set_status("Please enter an instruction first.")
            return

        choices = self._current_choices()
        self._remember_choices(choices)

        doc_ctx = self._current_doc_ctx()
        # Scope is automatic: the selection when there is one, else the document.
        if doc_ctx is not None:
            self.scope = "selection" if doc_ctx.has_selection() else "document"
        self.flow_doc_ctx = doc_ctx if (doc_ctx is not None
                                        and doc_ctx.has_selection()) else None
        text = ""
        if self.captured_text:
            text = self.captured_text
        elif doc_ctx is not None:
            if self.scope == "document":
                text = doc_ctx.full_text()
            elif self.scope == "selection" and doc_ctx.has_selection():
                text = doc_ctx.selected_text
            else:
                text = doc_ctx.target_text()
        if self.action == "chat":
            context = self.captured_text or (
                doc_ctx.target_text() if doc_ctx is not None else "")
        else:
            context = None

        if self.action == "chat":
            messages = self.history_as_messages()
            messages.append({"role": "user", "content": instruction})
            system_extra = cp_prompts._truncate(context) if context else ""
        else:
            messages, system_extra = cp_prompts.build_messages(
                self.action, text, instruction, choices, context
            )
        self.captured_text = ""
        self.doc_requested = False

        self.pending_action = self.action
        if self.action != "proofread":
            self.suggestions = []

        # Give the model the document outline for structural awareness.
        if (self.action in ("chat", "summarize")
                and doc_ctx is not None
                and self.config.get("allow_document_access", True)):
            try:
                outline = doc_ctx.outline_text()
                if outline:
                    system_extra = ((system_extra + "\n\nDocument outline:\n" + outline)
                                    if system_extra
                                    else ("Document outline:\n" + outline))
            except Exception:
                pass

        persona = cp_personas.active(self.config)
        system = self.config.get("system_prompt", "")
        persona_prompt = persona.get("system_prompt") or ""
        if persona_prompt:
            system = (persona_prompt + "\n\n" + system) if system else persona_prompt
        if system_extra:
            system = (system + "\n\n" + system_extra) if system else system_extra
        system = self._with_hints(system)

        agent_on = self.agent_mode or bool(
            (self.config.get("agents") or {}).get("enabled", False))
        if agent_on:
            system = (system + "\n\n" + cp_agents.AGENT_HINT) if system \
                else cp_agents.AGENT_HINT
            self.agent_active = True
            self.agent_steps = int((self.config.get("agents") or {}).get(
                "max_steps", 8) or 8)
            self.agent_max = self.agent_steps
            self.agent_messages = list(messages)
            self.agent_system = system

        if self.action == "chat":
            self.add_history_line("You", instruction)
            ui.set_text(self.dialog, "instruction", "")
        else:
            title = self.meta.get("title", self.action.title())
            detail = " \u00b7 ".join(str(v) for v in choices.values())
            self.add_history_line(
                "You", title + ((" \u2014 " + detail) if detail else ""))

        self._start_request(messages, system)

    def _with_hints(self, system):
        hints = []
        if self.config.get("allow_edits"):
            hints.append(cp_prompts.EDIT_HINT)
        if self.config.get("allow_document_access") and self.action == "chat":
            hints.append(cp_prompts.DOCUMENT_REQUEST_HINT)
        if self.config.get("allow_formatting"):
            try:
                doc_ctx = self._current_doc_ctx()
                if doc_ctx is not None and doc_ctx.kind == cp_document.WRITER:
                    hints.append(cp_format.format_prompt(doc_ctx.doc))
            except Exception as error:  # noqa: BLE001
                ui.log("format prompt failed: %r" % error)
        if hints:
            block = "\n\n".join(hints)
            system = (system + "\n\n" + block) if system else block
        return system

    def _start_request(self, messages, system):
        provider_id, spec, api_key, model, base_url = cp_config.active_provider(self.config)
        persona = cp_personas.active(self.config)
        if persona.get("model"):
            model = persona["model"]
        if persona.get("temperature") is not None:
            try:
                temperature = float(persona["temperature"])
            except (TypeError, ValueError):
                temperature = float(self.config.get("temperature", 0.3))
        else:
            temperature = float(self.config.get("temperature", 0.3))
        max_tokens = int(self.config.get("max_tokens", 1024))
        timeout = int(self.config.get("timeout", 120))
        stream = bool(self.config.get("stream", True)) \
            and self.pending_action != "proofread"
        self.gen_id += 1
        self.streaming = False
        self.streaming_partial = ""
        self._set_feedback(None)
        ui.log("start_request provider=%s model=%s stream=%s"
               % (provider_id, model, stream))
        self._set_busy(True)
        self._set_status("Contacting %s (%s)..." % (spec["label"], model))
        threading.Thread(
            target=self._worker,
            args=(self.gen_id, provider_id, api_key, model, base_url, messages,
                  system, temperature, max_tokens, timeout, stream),
            daemon=True,
        ).start()

    def _apply_directive_edit(self, edit):
        action = edit.get("action", "")
        text = edit.get("text", "")
        find = edit.get("find", "")
        document = self._current_document()
        if document is None or not text:
            return False
        if find:
            return cp_document.replace_first(document, find, text)
        if action == "append":
            return self._current_doc_ctx().append(text)
        if action == "replace":
            return self._current_doc_ctx().replace_selection(text)
        return self._current_doc_ctx().insert_at_cursor(text)

    def _apply_format_ops(self, ops):
        doc_ctx = self._current_doc_ctx()
        if doc_ctx is None:
            self._set_status("No document is open.")
            return
        if cp_format.requires_confirmation(ops):
            if not ui.confirm(self.ctx, self.frame, "HaiLPER",
                              "Apply document-wide or page-layout changes?"):
                self.add_history_line("HaiLPER", "Formatting cancelled.")
                self._set_status("Formatting cancelled.")
                return
        applied, errors = cp_format.apply_ops(doc_ctx, ops)
        if applied:
            self.add_history_line(
                "HaiLPER", "Applied formatting: " + "; ".join(applied) + ".")
        if errors:
            self.add_history_line(
                "HaiLPER", "Some formatting failed: " + "; ".join(errors))
        if applied:
            self._set_status("Applied %d formatting change(s)." % len(applied))
        elif errors:
            self._set_status("Could not apply formatting: " + "; ".join(errors))
        else:
            self._set_status("No formatting changes.")

    def _agent_step(self, directive, text):
        step_no = self.agent_max - self.agent_steps + 1
        try:
            if directive[0] == "document":
                doc_ctx = self._current_doc_ctx()
                result = ("Document contents:\n\n"
                          + (cp_prompts._truncate(doc_ctx.full_text())
                             if doc_ctx else ""))
            elif directive[0] == "edit":
                ok = self._apply_directive_edit(directive[1])
                result = "Edit applied." if ok else "Edit could not be applied."
            elif directive[0] == "format":
                applied, errors = cp_format.apply_ops(
                    self._current_doc_ctx(), directive[1])
                result = ("Formatting applied: " + "; ".join(applied)) if applied \
                    else ("Formatting failed: " + "; ".join(errors or ["nothing to do"]))
            else:
                result = "Unknown tool."
        except Exception as error:  # noqa: BLE001
            result = "Tool error: %s" % error
        self.add_history_line(
            "HaiLPER", "\u2699 Step %d: %s\n%s"
            % (step_no, cp_agents.describe(directive),
               result.split("\n")[0][:100]))
        self.agent_steps -= 1
        if self.agent_steps <= 0:
            self.add_history_line("HaiLPER", "Agent stopped after the step limit.")
            self._agent_finish()
            return
        self.agent_messages.append({"role": "assistant", "content": text})
        self.agent_messages.append(
            {"role": "user", "content": "Tool result:\n" + result})
        self._set_status("Agent mode: step %d\u2026"
                         % (self.agent_max - self.agent_steps + 1))
        self._start_request(self.agent_messages, self.agent_system)

    def _agent_finish(self):
        self.agent_active = False
        self.agent_steps = 0
        self._set_busy(False)

    def on_stop(self):
        self.gen_id += 1
        self.agent_active = False
        self.agent_steps = 0
        self._set_busy(False)
        self._set_status("Cancelled.")

    def _worker(self, gen_id, provider_id, api_key, model, base_url, messages, system,
                temperature, max_tokens, timeout, stream=False):
        def on_chunk(delta):
            if gen_id != self.gen_id:
                raise RuntimeError("cancelled")
            try:
                self.async_callback.addCallback(
                    self.callback_object, ui.payload(delta=delta, gen=gen_id))
            except Exception:
                pass

        def on_usage(usage):
            if not usage:
                return
            try:
                self.async_callback.addCallback(
                    self.callback_object,
                    ui.payload(usage_in=int(usage.get("input", 0) or 0),
                               usage_out=int(usage.get("output", 0) or 0),
                               gen=gen_id))
            except Exception:
                pass

        try:
            if stream:
                reply = cp_providers.chat_stream(
                    provider_id, api_key, model, base_url, messages, system,
                    temperature, max_tokens, timeout, on_chunk, on_usage,
                )
            else:
                reply = cp_providers.chat(
                    provider_id, api_key, model, base_url, messages, system,
                    temperature, max_tokens, timeout, on_usage=on_usage,
                )
            payload = ui.payload(ok=True, text=reply, gen=gen_id)
        except Exception as error:  # noqa: BLE001
            payload = ui.payload(ok=False, error=str(error), gen=gen_id)
        try:
            self.async_callback.addCallback(self.callback_object, payload)
        except Exception:
            pass

    def _on_result(self, data):
        if not self.alive:
            return
        payload = ui.read_payload(data)
        if payload.get("gen") != self.gen_id:
            return
        if "usage_in" in payload or "usage_out" in payload:
            self._record_usage({"input": payload.get("usage_in", 0) or 0,
                                "output": payload.get("usage_out", 0) or 0})
            return
        delta = payload.get("delta")
        if delta is not None:
            if not self.streaming:
                self.streaming = True
                self.streaming_partial = ""
            self.streaming_partial += delta
            self._refresh_history_view()
            self._set_status("Receiving\u2026")
            return
        self.streaming = False
        self.streaming_partial = ""
        ui.log("on_result ok=%s error=%r"
               % (payload.get("ok"), payload.get("error")))
        self._set_busy(False)
        if not payload.get("ok"):
            error = payload.get("error", "unknown error")
            self.add_history_line("HaiLPER", "\u26a0\ufe0f %s" % error)
            lowered = str(error).lower()
            if any(token in lowered for token in
                   ("api key", "authentication", "401", "403", "unauthor")):
                self._set_status(
                    "Auth error \u2014 open HaiLPER \u203a Settings to fix the key.")
            elif "timed out" in lowered:
                self._set_status("Request timed out \u2014 raise the timeout in Settings.")
            else:
                self._set_status("Error: %s" % error)
            self._set_feedback("retry")
            return

        raw = payload.get("text", "")
        text = cp_prompts.strip_directives(raw)

        # Tool-like directives: request the document, edit it, or format it.
        directive = None
        if (self.pending_action == "chat" or self.config.get("allow_edits")
                or self.config.get("allow_formatting")):
            directive = cp_prompts.parse_directive(raw)
        if self.agent_active and not directive:
            self.agent_active = False  # final plain-text answer
        if directive and self.agent_active:
            self._agent_step(directive, raw)
            return
        if (directive and directive[0] == "document"
                and not self.doc_requested
                and self.config.get("allow_document_access")):
            self.doc_requested = True
            doc_ctx = self._current_doc_ctx()
            doc_text = cp_prompts._truncate(doc_ctx.full_text()) if doc_ctx else ""
            messages = self.history_as_messages()
            messages.append({
                "role": "user",
                "content": "Here are the document contents:\n\n" + doc_text,
            })
            self.add_history_line("HaiLPER", "(reading the document\u2026)")
            self._start_request(messages, self.config.get("system_prompt", ""))
            return
        if directive and directive[0] == "edit" and self.config.get("allow_edits"):
            applied = self._apply_directive_edit(directive[1])
            self.add_history_line(
                "HaiLPER",
                ("Applied edit (%s)." % directive[1].get("action"))
                if applied else "I could not apply that edit.")
            self._set_status("Edit applied." if applied else "Could not apply the edit.")
            return
        if (directive and directive[0] == "format"
                and self.config.get("allow_formatting")):
            self._apply_format_ops(directive[1])
            return

        if self.refining:
            self.proposal = text
            self.refining = False
            self._show_proposal()
            return

        if self.pending_action in ("rewrite", "translate", "continue"):
            self._enter_proposal(text)
            return

        if self.pending_action == "proofread":
            self.suggestions = cp_prompts.parse_suggestions(text)
            if self.suggestions:
                self.add_history_line(
                    "HaiLPER", "Found %d suggestion(s). Starting review."
                    % len(self.suggestions))
                self._enter_review()
            else:
                self.add_history_line("HaiLPER", text)
                self._set_status("No suggestions found.")
        else:
            self.add_history_line("HaiLPER", text)
            self._set_status("Done. %d characters." % len(text))

    # ------------------------------------------------------------- apply
    def _result_for_apply(self):
        for speaker, message in reversed(self.history):
            if speaker != "You":
                return message
        return ""

    def _dispatch_apply(self, key):
        if key in ("insert", "replace", "append", "comment"):
            self._apply_to_document(key)
        elif key == "insert_formatted":
            self._apply_markdown()
        elif key == "copy":
            self.on_copy()
        elif key == "newdoc":
            self.on_new_document()
        elif key == "review":
            self.on_review()
        elif key == "adoptall" or key == "fixall":
            self.on_adopt_all()
        elif key == "diff":
            self.on_diff()
        elif key == "add_to_chat":
            self.on_add_to_chat()
        elif key == "regenerate":
            self.on_generate()
        elif key == "clear":
            self.on_clear()
        elif key == "close":
            self.on_close()

    def _on_slot(self, slot):
        if self.flow:
            if slot < len(self.slot_keys):
                self._flow_action(self.slot_keys[slot])
            return
        if slot < len(self.slot_keys):
            self._dispatch_apply(self.slot_keys[slot])

    def _flow_action(self, key):
        if self.flow == "review":
            self._review_action(key)
        elif self.flow == "proposal":
            self._proposal_action(key)

    def _apply_markdown(self):
        text = self._result_for_apply().strip()
        if not text:
            self._set_status("Nothing to insert yet.")
            return
        doc_ctx = self._current_doc_ctx()
        if doc_ctx is None:
            self._set_status("No document is open.")
            return
        replace = (doc_ctx.kind == cp_document.WRITER
                   and doc_ctx.has_selection())
        ok = doc_ctx.insert_markdown(text, "replace" if replace else "insert")
        self._set_status("Inserted formatted text."
                         if ok else "Formatted insert works in Writer only.")
        if ok:
            self._set_last_applied("Formatted text inserted")

    def _set_feedback(self, mode):
        self.feedback_mode = mode
        try:
            control = self.dialog.getControl("feedback_btn")
            if mode:
                control.setLabel("Undo" if mode == "undo" else "Retry")
                control.setVisible(True)
            else:
                control.setVisible(False)
        except Exception:
            pass

    def on_feedback(self):
        mode = self.feedback_mode
        self._set_feedback(None)
        if mode == "undo":
            document = self._current_document()
            if document is not None and cp_document.undo_last(document):
                self._set_status("Undone.")
            else:
                self._set_status("Nothing to undo.")
        elif mode == "retry":
            self.on_generate()

    def _set_last_applied(self, message):
        self.last_applied = message
        self._set_status("%s \u00b7 Undo to revert." % message)
        self._set_feedback("undo")

    def _apply_to_document(self, mode):
        raw = self._result_for_apply().strip()
        if not raw:
            self._set_status("Nothing to use yet.")
            return
        text = cp_markdown.to_plain(raw) or raw
        doc_ctx = self._current_doc_ctx()
        if doc_ctx is None:
            self._set_status("No document is open.")
            return
        if mode == "insert":
            ok, message = doc_ctx.insert_at_cursor(text), "Inserted at the cursor."
        elif mode == "replace":
            ok, message = doc_ctx.replace_selection(text), "Replaced the selection."
        elif mode == "append":
            ok, message = doc_ctx.append(text), "Appended to the document."
        else:
            ok, message = doc_ctx.add_comment(text), "Added as a comment."
        self._set_status(message if ok else "Could not apply to this document.")
        if ok:
            self._set_feedback("undo")

    def on_copy(self):
        text = _visible_text(self.dialog, self._result_for_apply())
        if text and ui.copy_to_clipboard(self.ctx, text):
            self._set_status("Copied to clipboard.")
        else:
            self._set_status("Nothing to copy.")

    def on_new_document(self):
        text = self._result_for_apply().strip()
        if not text:
            self._set_status("Nothing to put in a document yet.")
            return
        document = cp_document.create_document_with_text(self.ctx, text)
        self._set_status(
            "Created a new document." if document is not None
            else "Could not create a document."
        )

    # ------------------------------------------------------- inline review
    def on_review(self):
        if not self.suggestions:
            self._set_status("No suggestions to review.")
            return
        self._enter_review()

    def _enter_review(self):
        if not self.suggestions:
            return
        self.flow = "review"
        self.reviewing = True
        self.review_index = 0
        self.review_fixed = 0
        self.review_ignored = 0
        labels = [("adopt", "Adopt"), ("reject", "Reject"),
                  ("prev", "Previous"), ("next", "Next"),
                  ("adoptall", "Adopt all"), ("finish", "Finish")]
        self.slot_keys = [key for key, _label in labels]
        for index, (_key, label) in enumerate(labels):
            try:
                control = self.dialog.getControl("btn_%d" % index)
                control.setLabel(label)
                control.setVisible(True)
            except Exception:
                pass
        self._relayout(controls_ready=True)
        self._show_review()

    def _show_review(self):
        if not (0 <= self.review_index < len(self.suggestions)):
            self._exit_review()
            return
        item = self.suggestions[self.review_index]
        total = len(self.suggestions)
        text = (
            "Suggestion %d of %d\n\n"
            "Original:\n  %s\n\n"
            "Suggested:\n  %s\n\n"
            "Reason:\n  %s"
            % (self.review_index + 1, total,
               item.get("original", ""), item.get("replacement", ""),
               item.get("reason", ""))
        )
        self.result_text = text
        ui.set_text(self.dialog, "result", text)
        self._set_status("Review %d of %d \u00b7 fixed %d, ignored %d"
                         % (self.review_index + 1, total,
                            self.review_fixed, self.review_ignored))
        try:
            self.dialog.getControl("btn_2").setEnable(self.review_index > 0)
        except Exception:
            pass

    def _review_action(self, key):
        if key == "adopt":
            self._review_adopt()
        elif key == "reject":
            self.review_ignored += 1
            self.review_index += 1
            self._show_review()
        elif key == "prev":
            self.review_index = max(0, self.review_index - 1)
            self._show_review()
        elif key == "next":
            self.review_index += 1
            self._show_review()
        elif key == "adoptall":
            self._review_adopt_all()
        elif key == "finish":
            self._exit_review()

    def _review_adopt(self):
        document = self._current_document()
        if document is None:
            self._set_status("No document is open.")
            return
        item = self.suggestions[self.review_index]
        tracked = self.config.get("track_changes", True)
        if cp_document.replace_first(document, item["original"],
                                     item["replacement"], tracked=tracked):
            self.review_fixed += 1
            self._set_feedback("undo")
        else:
            self.review_ignored += 1
            self._set_status("Could not find the original text; skipped.")
        self.review_index += 1
        self._show_review()

    def _review_adopt_all(self):
        document = self._current_document()
        if document is None:
            self._set_status("No document is open.")
            return
        adopted = 0
        tracked = self.config.get("track_changes", True)
        with cp_document.undo_context(document, "HaiLPER proofread"):
            for item in self.suggestions:
                if cp_document.replace_first(document, item["original"],
                                             item["replacement"], tracked=tracked):
                    adopted += 1
        self.review_fixed += adopted
        self.review_index = len(self.suggestions)
        self._set_status("Adopted %d suggestion(s)." % adopted)
        if adopted:
            self._set_feedback("undo")
        self._exit_review()

    def _exit_review(self):
        self.reviewing = False
        self.flow = None
        self.slot_keys = []
        adopted = self.review_fixed
        rejected = self.review_ignored
        self.set_action("chat")
        self.add_history_line(
            "HaiLPER", "Proofread review finished. Adopted %d, rejected %d."
            % (adopted, rejected))
        self.apply_meta()

    def on_adopt_all(self):
        self._review_adopt_all()

    # -------------------------------------------------- proposal (rewrite etc.)
    def _enter_proposal(self, text):
        if not text:
            return
        self.flow = "proposal"
        self.flow_action = self.action
        self.proposal = text
        labels = [("adopt", "Adopt"), ("reject", "Reject"),
                  ("refine", "Refine"), ("copy", "Copy"), ("close", "Close")]
        if (self.flow_action == "rewrite"
                and self.config.get("track_changes", True)):
            labels[0] = ("adopt", "Adopt (tracked)")
        self.slot_keys = [key for key, _label in labels]
        for index, (_key, label) in enumerate(labels):
            try:
                control = self.dialog.getControl("btn_%d" % index)
                control.setLabel(label)
                control.setVisible(True)
            except Exception:
                pass
        for index in range(len(labels), SLOTS):
            try:
                self.dialog.getControl("btn_%d" % index).setVisible(False)
            except Exception:
                pass
        self._relayout(controls_ready=True)
        self._show_proposal()

    def _show_proposal(self):
        original = ""
        doc_ctx = self._current_doc_ctx()
        if doc_ctx is not None and doc_ctx.has_selection():
            original = doc_ctx.selected_text
        parts = []
        if original:
            parts.append("Original:\n%s" % original)
        parts.append("Suggested %s:\n%s"
                     % (self.flow_action, self.proposal))
        text = "\n\n".join(parts)
        self.result_text = text
        ui.set_text(self.dialog, "result", text)
        self._set_status("Draft \u00b7 adopt, reject or refine it.")

    def _proposal_action(self, key):
        if key == "adopt":
            self.on_adopt()
        elif key == "reject":
            self.on_reject_proposal()
        elif key == "refine":
            self.on_refine()
        elif key == "copy":
            ui.copy_to_clipboard(self.ctx, self.proposal)
            self._set_status("Copied to clipboard.")
        elif key == "close":
            self._exit_proposal()

    def on_adopt(self):
        doc_ctx = self.flow_doc_ctx or self._current_doc_ctx()
        if doc_ctx is None:
            self._set_status("No document is open.")
            return
        action = self.flow_action
        tracked = (action == "rewrite"
                   and self.config.get("track_changes", True)
                   and doc_ctx.kind == cp_document.WRITER)
        if action == "continue":
            ok = doc_ctx.insert_at_cursor(self.proposal)
        elif doc_ctx.has_selection():
            ok = doc_ctx.replace_selection(self.proposal, tracked=tracked)
        else:
            ok = doc_ctx.insert_at_cursor(self.proposal, tracked=tracked)
        message = ("Adopted the %s." % action) if ok \
            else ("Could not apply the %s." % action)
        self.add_history_line("HaiLPER", message)
        if ok:
            self._set_feedback("undo")
        self._exit_proposal()

    def on_reject_proposal(self):
        self.add_history_line("HaiLPER", "Rejected the %s." % self.flow_action)
        self._exit_proposal()

    def on_refine(self):
        import cp_prompt
        instruction = cp_prompt.ask(
            self.ctx, self.frame, "Refine",
            "What should I change?", "")
        if not instruction:
            return
        self._start_refine(instruction)

    def _start_refine(self, instruction):
        base = self.proposal
        content = (
            "Here is the current draft:\n\n%s\n\n"
            "Refine it as follows: %s\n"
            "Return only the revised text." % (base, instruction))
        self.refining = True
        self.pending_action = self.flow_action
        self._start_request([{"role": "user", "content": content}],
                            self.config.get("system_prompt", ""))

    def _exit_proposal(self):
        self.flow = None
        self.flow_action = None
        self.proposal = ""
        self.slot_keys = []
        self.set_action("chat")
        self.apply_meta()

    def on_diff(self):
        text = self._result_for_apply().strip()
        if not text:
            self._set_status("Nothing to compare yet.")
            return
        doc_ctx = self._current_doc_ctx()
        if doc_ctx is None:
            self._set_status("No document is open.")
            return
        original = doc_ctx.selected_text if doc_ctx.has_selection() \
            else doc_ctx.target_text()
        import cp_diff
        cp_diff.show(self.ctx, self.frame, original, text, doc_ctx)

    def on_add_to_chat(self):
        doc_ctx = self._current_doc_ctx()
        selection = doc_ctx.selected_text if doc_ctx is not None else ""
        self.seed_chat(selection)

    def seed_chat(self, text):
        if self.action != "chat":
            self.set_action("chat")
        prompt = "About this:\n%s\n\n" % text if text else ""
        self._set_instruction_text(prompt, grey=not bool(prompt))
        try:
            self.dialog.getControl("instruction").setFocus()
        except Exception:
            pass
        self._set_status("Add a question and press Send.")

    def on_clear(self):
        self.history = []
        self.result_text = ""
        self.conversation_id = None
        ui.set_text(self.dialog, "result", "")
        ui.set_text(self.dialog, "instruction", "")
        self.set_action("chat")
        self._set_status("Started a new conversation.")

    def on_close(self):
        self.hide()
        self._set_status("Panel hidden. Choose an action to reopen it.")

    # ------------------------------------------------------------- ui utils
    def _set_status(self, message):
        try:
            ui.set_text(self.dialog, "status", message)
        except Exception:
            pass

    def _set_busy(self, busy):
        self.busy = busy
        try:
            generate = self.dialog.getControl("generate")
            generate.setLabel("Stop" if busy else "Send")
            generate.setEnable(True)
        except Exception:
            pass
        for slot in range(SLOTS):
            try:
                self.dialog.getControl("btn_%d" % slot).setEnable(not busy)
            except Exception:
                pass


def _visible_text(dialog, fallback):
    """The selected text in the result box if any, else the whole result."""
    try:
        control = dialog.getControl("result")
        selected = control.getSelectedText()
        if selected:
            return selected
    except Exception:
        pass
    return fallback


def _set_when_ready(bridge, name, value):
    if bridge.dialog is not None:
        ui.set_text(bridge.dialog, name, value)


# ------------------------------------------------------------------ sidebar
# State shared between the sidebar factory component and the command handler.
# Both must reference the same module (cp_dialog), because LibreOffice loads the
# component file under a module name that differs from a normal import.
_sidebar_bridge = None
_sidebar_pending = {}
_sidebar_visible = False
_sidebar_ever_seen = False
DECK_ID = "io.github.rokusaburo.hailper.deck"


def _set_last_active_deck(ctx):
    try:
        from com.sun.star.beans import PropertyValue

        provider = ui.smgr(ctx).createInstanceWithContext(
            "com.sun.star.configuration.ConfigurationProvider", ctx)
        prop = PropertyValue()
        prop.Name = "nodepath"
        prop.Value = "org.openoffice.Office.UI.Sidebar/Content"
        config = provider.createInstanceWithArguments(
            "com.sun.star.configuration.ConfigurationUpdateAccess", (prop,))
        decks = (
            "Writer,io.github.rokusaburo.hailper.deck",
            "WriterVariants,io.github.rokusaburo.hailper.deck",
            "Calc,io.github.rokusaburo.hailper.deck",
            "Impress,io.github.rokusaburo.hailper.deck",
            "Draw,io.github.rokusaburo.hailper.deck",
            "any,io.github.rokusaburo.hailper.deck",
        )
        uno.invoke(config, "setPropertyValue",
                   ("LastActiveDeck", uno.Any("[]string", decks)))
        config.commitChanges()
        ui.log("_set_last_active_deck: committed")
    except Exception as error:
        ui.log("_set_last_active_deck failed: %r" % error)


def _provider_for_frame(frame):
    candidates = [frame]
    try:
        candidates.append(frame.getController())
    except Exception:
        pass
    type_obj = uno.getTypeByName("com.sun.star.ui.XSidebarProvider")
    for candidate in candidates:
        if candidate is None:
            continue
        try:
            provider = candidate.queryInterface(type_obj)
            if provider is not None:
                return provider
        except Exception:
            pass
    return None


def sidebar_ensure(ctx, frame):
    provider = _provider_for_frame(frame)
    if provider is not None:
        try:
            provider.setVisible(True)
            provider.showDecks(True)
            decks = provider.getDecks()
            try:
                deck = decks.getByName(DECK_ID)
            except Exception:
                deck = None
            if deck is not None:
                deck.activate(True)
            return provider
        except Exception:
            pass
    if not _sidebar_visible:
        # A panel may still be created asynchronously (sidebar already open).
        # Give it a moment, then open the sidebar and select our deck.
        _set_last_active_deck(ctx)
        _schedule_sidebar_fallback(ctx, frame)
    return None


_fallback_async = None
_fallback_scheduled = False


def _schedule_sidebar_fallback(ctx, frame):
    """After a short delay, if the panel still is not up, toggle the sidebar.

    Handles the case where the sidebar is closed: .uno:Sidebar opens it, then
    the deck command selects ours. If the panel already appeared (sidebar was
    open), nothing further happens.
    """
    global _fallback_scheduled, _fallback_async
    if _fallback_scheduled:
        return
    _fallback_scheduled = True
    try:
        if _fallback_async is None:
            _fallback_async = ui.smgr(ctx).createInstanceWithContext(
                "com.sun.star.awt.AsyncCallback", ctx)
        callback = ui.Callback(lambda data: _run_sidebar_fallback(*data))
    except Exception:
        _fallback_scheduled = False
        return

    def worker():
        time.sleep(3.0)
        global _fallback_scheduled
        _fallback_scheduled = False
        try:
            _fallback_async.addCallback(callback, (ctx, frame))
        except Exception:
            pass

    threading.Thread(target=worker, daemon=True).start()


def _run_sidebar_fallback(ctx, frame):
    if _sidebar_bridge is not None and _sidebar_bridge.alive:
        return
    if _sidebar_ever_seen:
        # The sidebar is (or was) open; do not toggle it closed.
        return
    try:
        helper = ui.smgr(ctx).createInstanceWithContext(
            "com.sun.star.frame.DispatchHelper", ctx)
        helper.executeDispatch(frame, ".uno:Sidebar", "", 0, ())
        ui.log("sidebar_ensure: opened sidebar")
    except Exception as error:
        ui.log("sidebar_ensure: fallback failed %r" % error)
    # Select our deck a moment later, once the sidebar window exists; retry a
    # few times while the sidebar opens.
    _schedule_deck_select(ctx, frame, 0)


def _schedule_deck_select(ctx, frame, attempt):
    try:
        callback = ui.Callback(lambda data: _run_deck_select(*data))
    except Exception:
        return

    def worker():
        time.sleep(1.5)
        try:
            _fallback_async.addCallback(callback, (ctx, frame, attempt))
        except Exception:
            pass

    threading.Thread(target=worker, daemon=True).start()


def _run_deck_select(ctx, frame, attempt):
    if _sidebar_bridge is not None and _sidebar_bridge.alive:
        return
    try:
        helper = ui.smgr(ctx).createInstanceWithContext(
            "com.sun.star.frame.DispatchHelper", ctx)
        helper.executeDispatch(
            frame, ".uno:SidebarDeck.%s" % DECK_ID, "", 0, ())
        ui.log("sidebar_ensure: selected deck (attempt %d)" % attempt)
    except Exception as error:
        ui.log("sidebar_ensure: deck select failed %r" % error)
    if attempt < 3:
        _schedule_deck_select(ctx, frame, attempt + 1)


CHOICE_KEYS = ("style", "length", "lang", "register", "categories",
               "severity", "format")


def sidebar_show(ctx, frame, action, config, params=None):
    """Open the sidebar deck and apply an action to the live panel."""
    params = dict(params or {})
    global _sidebar_bridge
    ui.log("sidebar_show action=%r bridge=%s visible=%s"
           % (action, _sidebar_bridge is not None, _sidebar_visible))
    try:
        import cp_contextmenu
        cp_contextmenu.ensure_registered(ctx, frame)
    except Exception as error:
        ui.log("context menu ensure failed: %r" % error)

    if _sidebar_bridge is not None and _sidebar_bridge.alive:
        _sidebar_pending.clear()
        _apply_sidebar_action(_sidebar_bridge, frame, action, config, params)
        return _sidebar_bridge

    # No live panel yet: remember the action for the panel that is about to be
    # created, then make sure the sidebar (and our deck) is shown.
    _sidebar_pending["action"] = action
    _sidebar_pending["config"] = config
    _sidebar_pending["params"] = params
    sidebar_ensure(ctx, frame)

    if _sidebar_bridge is not None and _sidebar_bridge.alive:
        # The panel was created by sidebar_ensure and may already be generating.
        # on_generate() is guarded against re-entry, so this is safe.
        _apply_sidebar_action(_sidebar_bridge, frame, action, config, params)
        _sidebar_pending.clear()
        return _sidebar_bridge

    if _sidebar_visible:
        ui.show_message_box(
            ctx, frame, "HaiLPER",
            "Open the 'HaiLPER' tab in the sidebar to run this action.",
        )
    return None


def _apply_sidebar_action(bridge, frame, action, config, params=None):
    params = params or {}
    if frame is not None:
        bridge.frame = frame
    bridge.config = config

    if action == "chat_about":
        bridge.set_action("chat")
        doc_ctx = bridge._current_doc_ctx()
        bridge.seed_chat(doc_ctx.selected_text if doc_ctx is not None else "")
        return

    bridge.set_action(action)
    bridge.scope = params.get("scope")
    bridge.captured_text = params.get("captured_text", "") or ""
    choices = {key: params[key] for key in CHOICE_KEYS if params.get(key)}
    if choices:
        bridge.set_choices(choices)

    run = params.get("run")
    if run == "1":
        bridge.on_generate()
    elif run == "0":
        pass
    elif bridge.meta.get("auto_run"):
        bridge.on_generate()


def show(ctx, frame, action, config):
    """Open (or reuse) the floating Copilot panel and apply the action."""
    global _panel
    if _panel is None or not _panel.alive:
        _panel = _Bridge(ctx, frame, action, config)
    else:
        _panel.frame = frame
        _panel.config = config
        _panel.set_action(action)
    _panel.show_panel()
    if _panel.meta.get("auto_run"):
        _panel.on_generate()
    return _panel
