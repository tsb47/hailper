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

import cp_config
import cp_document
import cp_prompts
import cp_providers
import cp_ui as ui


DLG_W = 170
DLG_H = 326
PAD = 6
LINE_H = 12
BTN_H = 16
RESULT_H = 120
RESULT_MIN = 60
RESULT_MAX = 140
MAP_PIXEL = 7
POS_FLAGS = 3  # com.sun.star.awt.PosSize.X | PosSize.Y
SLOTS = 6

QUICK_ACTIONS = [
    ("chat", "Chat"),
    ("summarize", "Summarize"),
    ("rewrite", "Rewrite"),
    ("translate", "Translate"),
    ("proofread", "Proofread"),
    ("continue", "Continue"),
    ("explain", "Explain"),
]

_ICON_URL = ("vnd.sun.star.extension://io.github.rokusaburo.hailper/"
             "icons/%s-22%s.png")


def _mode_icon(action, active):
    return _ICON_URL % (action, "-on" if active else "")

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

        for index, (key, label) in enumerate(QUICK_ACTIONS):
            add("com.sun.star.awt.UnoControlButton", "mode_%d" % index,
                PositionX=0, PositionY=0, Width=1, Height=BTN_H,
                HelpText=label)
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
            PositionX=0, PositionY=0, Width=content_w, Height=LINE_H,
            Label="", Align=0)
        add("com.sun.star.awt.UnoControlFixedText", "result_label",
            PositionX=0, PositionY=0, Width=content_w, Height=LINE_H, Label="Result:")
        add("com.sun.star.awt.UnoControlEdit", "result",
            PositionX=0, PositionY=0, Width=content_w, Height=RESULT_H,
            MultiLine=True, ReadOnly=True, VScroll=True, HScroll=False)
        add("com.sun.star.awt.UnoControlFixedText", "status",
            PositionX=0, PositionY=0, Width=content_w, Height=LINE_H, Label="")
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
        for index in range(len(QUICK_ACTIONS)):
            try:
                self.dialog.getControl("mode_%d" % index).addActionListener(
                    ui.ActionListener(
                        lambda event, i=index: self.on_mode_button(i)))
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
        if controls_ready:
            self._ensure_scale()
        if controls_ready:
            for name in ("instruction", "generate", "provider_label",
                         "result_label", "result", "status"):
                try:
                    self.dialog.getControl(name).setVisible(True)
                except Exception:
                    pass
            for index in range(len(QUICK_ACTIONS)):
                try:
                    self.dialog.getControl("mode_%d" % index).setVisible(True)
                except Exception:
                    pass
            self._update_mode_buttons()
        content_w = DLG_W - 2 * PAD
        visible = getattr(self, "visible_choices", [])
        positions = {}
        y = PAD
        cols = len(QUICK_ACTIONS)
        gap = 3
        mw = (content_w - gap * (cols - 1)) // cols
        for index in range(cols):
            positions["mode_%d" % index] = (
                PAD + index * (mw + gap), y, mw, BTN_H)
        y += BTN_H + 4
        for index in range(2):
            if index < len(visible):
                positions["choice_label_%d" % index] = (PAD, y + 1, 58, LINE_H)
                positions["choice_%d" % index] = (
                    PAD + 60, y - 1, content_w - 60, LINE_H + 4)
                y += LINE_H + 4

        # Conversation transcript, with the input below it (chat layout).
        positions["result_label"] = (PAD, y, content_w, LINE_H)
        y += LINE_H + 2
        result_y = y
        fixed_below = (42 + (BTN_H + 4) + (LINE_H + 2) + (LINE_H + 4)
                       + (2 * BTN_H + 2) + PAD)
        scale = getattr(self, "scale", 1.0) or 1.0
        result_h = RESULT_H
        available = getattr(self, "available_px", 0)
        if available:
            result_h = max(RESULT_MIN,
                           min(RESULT_MAX,
                               (available / scale) - result_y - fixed_below - 40))
        positions["result"] = (PAD, result_y, content_w, result_h)
        y = result_y + result_h + 4

        positions["instruction"] = (PAD, y, content_w, 40)
        y += 42
        positions["generate"] = (PAD, y, content_w, BTN_H + 2)
        y += BTN_H + 4
        positions["provider_label"] = (PAD, y, content_w, LINE_H)
        y += LINE_H + 2
        positions["status"] = (PAD, y, content_w, LINE_H)
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
        positions["result_label"] = (PAD, y, content_w, LINE_H)
        y += LINE_H + 2
        result_y = y
        # Keep flow panels compact so the action buttons are always visible.
        result_h = RESULT_MIN
        positions["result"] = (PAD, result_y, content_w, result_h)
        y = result_y + result_h + 4
        positions["status"] = (PAD, y, content_w, LINE_H)
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
                     "provider_label", "choice_label_0", "choice_0",
                     "choice_label_1", "choice_1"):
            try:
                self.dialog.getControl(name).setVisible(False)
            except Exception:
                pass
        for index in range(len(QUICK_ACTIONS)):
            try:
                self.dialog.getControl("mode_%d" % index).setVisible(False)
            except Exception:
                pass
        for name in ("result_label", "result", "status"):
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

    def on_mode_button(self, index):
        if self.flow:
            return
        if 0 <= index < len(QUICK_ACTIONS):
            key = QUICK_ACTIONS[index][0]
            if key != self.action:
                self.set_action(key)

    def _update_mode_buttons(self):
        for index, (key, _label) in enumerate(QUICK_ACTIONS):
            control = self.dialog.getControl("mode_%d" % index)
            if control is None:
                continue
            active = (key == self.action)
            try:
                control.getModel().setPropertyValue(
                    "ImageURL", _mode_icon(key, active))
            except Exception:
                pass

    def apply_meta(self):
        is_chat = self.action == "chat"
        ui.set_text(self.dialog, "result_label", "Conversation:")
        self._update_mode_buttons()
        display = self.meta.get("display_instruction",
                                self.meta.get("instruction", ""))
        instruction = "" if is_chat else display
        if not ui.get_text(self.dialog, "instruction").strip() or is_chat:
            ui.set_text(self.dialog, "instruction", instruction)

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
        ui.set_text(self.dialog, "provider_label", "%s / %s" % (spec["label"], model))

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
                indented = "\n".join("  " + line
                                     for line in message.split("\n"))
                blocks.append("HaiLPER\n%s" % indented)
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
        instruction = ui.get_text(self.dialog, "instruction").strip()
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

        system = self.config.get("system_prompt", "")
        if system_extra:
            system = (system + "\n\n" + system_extra) if system else system_extra
        system = self._with_hints(system)

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
        if hints:
            block = "\n\n".join(hints)
            system = (system + "\n\n" + block) if system else block
        return system

    def _start_request(self, messages, system):
        provider_id, spec, api_key, model, base_url = cp_config.active_provider(self.config)
        temperature = float(self.config.get("temperature", 0.3))
        max_tokens = int(self.config.get("max_tokens", 1024))
        timeout = int(self.config.get("timeout", 120))
        self.gen_id += 1
        self._set_busy(True)
        self._set_status("Contacting %s (%s)..." % (spec["label"], model))
        threading.Thread(
            target=self._worker,
            args=(self.gen_id, provider_id, api_key, model, base_url, messages,
                  system, temperature, max_tokens, timeout),
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

    def on_stop(self):
        self.gen_id += 1
        self._set_busy(False)
        self._set_status("Cancelled.")

    def _worker(self, gen_id, provider_id, api_key, model, base_url, messages, system,
                temperature, max_tokens, timeout):
        try:
            reply = cp_providers.chat(
                provider_id, api_key, model, base_url, messages, system,
                temperature, max_tokens, timeout,
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
        ui.log("on_result ok=%s error=%r"
               % (payload.get("ok"), payload.get("error")))
        self._set_busy(False)
        if not payload.get("ok"):
            self._set_status("Error: %s" % payload.get("error", "unknown error"))
            self.add_history_line("HaiLPER", "(error: %s)"
                                  % payload.get("error", ""))
            return

        text = payload.get("text", "")

        # Tool-like directives: request the document, or edit it directly.
        directive = None
        if self.pending_action == "chat" or self.config.get("allow_edits"):
            directive = cp_prompts.parse_directive(text)
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

    def _apply_to_document(self, mode):
        text = self._result_for_apply().strip()
        if not text:
            self._set_status("Nothing to use yet.")
            return
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
        ui.set_text(self.dialog, "result_label",
                    "Review (%d of %d)" % (self.review_index + 1, total))
        self._set_status("Fixed %d, ignored %d"
                         % (self.review_fixed, self.review_ignored))
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
        ui.set_text(self.dialog, "result_label", "Review draft")
        self._set_status("Adopt this, reject it, or refine it.")

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
        ui.set_text(self.dialog, "instruction", prompt)
        try:
            self.dialog.getControl("instruction").setFocus()
        except Exception:
            pass
        self._set_status("Add a question and press Send.")

    def on_clear(self):
        self.history = []
        self.result_text = ""
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
