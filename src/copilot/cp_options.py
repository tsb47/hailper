"""Settings dialog: choose provider, model, API key and generation options."""

import uno
import unohelper

from com.sun.star.awt import XActionListener
from com.sun.star.awt import XItemListener

import cp_config
import cp_providers


DLG_W = 560
DLG_H = 440
PAD = 10
LINE_H = 18
BTN_H = 24
MAP_PIXEL = 7


def _smgr(ctx):
    return ctx.getServiceManager()


def _create_model(dialog_model, service, name, **props):
    model = dialog_model.createInstance(service + "Model")
    model.setPropertyValue("Name", name)
    for key, value in props.items():
        model.setPropertyValue(key, value)
    return model


def _set_string_list(control_model, values):
    uno.invoke(
        control_model, "setPropertyValue",
        ("StringItemList", uno.Any("[]string", tuple(values))),
    )


class _ActionListener(unohelper.Base, XActionListener):
    def __init__(self, callback):
        self._callback = callback

    def actionPerformed(self, event):
        self._callback(event)

    def disposing(self, event):
        pass


class _ItemListener(unohelper.Base, XItemListener):
    def __init__(self, callback):
        self._callback = callback

    def itemStateChanged(self, event):
        self._callback(event)

    def disposing(self, event):
        pass


class _OptionsBridge(object):
    def __init__(self, ctx, frame, config):
        self.ctx = ctx
        self.frame = frame
        self.config = config
        self.saved = False
        self._label_to_id = {}
        self._id_to_label = {}
        for pid, spec in cp_providers.PROVIDERS.items():
            label = "%s  (%s)" % (spec["label"], pid)
            self._label_to_id[label] = pid
            self._id_to_label[pid] = label
        self.model = None
        self.dialog = None
        self._model_cache = {}

    # ---------------------------------------------------------------- building
    def build(self):
        ctx = self.ctx
        self.model = _smgr(ctx).createInstanceWithContext(
            "com.sun.star.awt.UnoControlDialogModel", ctx
        )
        self.model.setPropertyValue("Title", "HaiLPER - Settings")
        try:
            self.model.setPropertyValue("MapUnit", MAP_PIXEL)
        except Exception:
            pass
        self.model.setPropertyValue("Width", DLG_W)
        self.model.setPropertyValue("Height", DLG_H)
        self.model.setPropertyValue("Moveable", True)
        self.model.setPropertyValue("Closeable", True)

        field_x = 120
        field_w = DLG_W - field_x - PAD
        step = LINE_H + 10
        y = PAD

        self._add_label("provider_label", PAD, y, "Provider:", 105)
        combo = _create_model(
            self.model, "com.sun.star.awt.UnoControlComboBox", "provider",
            PositionX=field_x, PositionY=y, Width=field_w,
            Height=LINE_H + 6, Dropdown=True, LineCount=22,
        )
        _set_string_list(combo, self._id_to_label.values())
        pid = self.config.get("provider", "ollama")
        combo.setPropertyValue("Text", self._id_to_label.get(pid, list(self._label_to_id)[0]))
        self.model.insertByName("provider", combo)

        y += step
        self._add_label("key_label", PAD, y, "API key:", 105)
        self.model.insertByName(
            "api_key",
            _create_model(
                self.model, "com.sun.star.awt.UnoControlEdit", "api_key",
                PositionX=field_x, PositionY=y, Width=field_w,
                Height=LINE_H + 6, EchoChar=42,
            ),
        )

        y += step
        self._add_label("model_label", PAD, y, "Model:", 105)
        model_combo = _create_model(
            self.model, "com.sun.star.awt.UnoControlComboBox", "model",
            PositionX=field_x, PositionY=y, Width=field_w,
            Height=LINE_H + 6, Dropdown=True, LineCount=22,
        )
        _set_string_list(model_combo, ())
        self.model.insertByName("model", model_combo)

        y += step
        self._add_label("base_label", PAD, y, "Base URL:", 105)
        self.model.insertByName(
            "base_url",
            _create_model(
                self.model, "com.sun.star.awt.UnoControlEdit", "base_url",
                PositionX=field_x, PositionY=y, Width=field_w,
                Height=LINE_H + 6,
            ),
        )

        y += step
        self._add_label("temp_label", PAD, y, "Temperature:", 105)
        self.model.insertByName(
            "temperature",
            _create_model(
                self.model, "com.sun.star.awt.UnoControlEdit", "temperature",
                PositionX=field_x, PositionY=y, Width=70, Height=LINE_H + 6,
            ),
        )
        self._add_label("tokens_label", 220, y, "Max tokens:", 85)
        self.model.insertByName(
            "max_tokens",
            _create_model(
                self.model, "com.sun.star.awt.UnoControlEdit", "max_tokens",
                PositionX=310, PositionY=y, Width=70, Height=LINE_H + 6,
            ),
        )

        y += step
        self._add_label("timeout_label", PAD, y, "Timeout (s):", 105)
        self.model.insertByName(
            "timeout",
            _create_model(
                self.model, "com.sun.star.awt.UnoControlEdit", "timeout",
                PositionX=field_x, PositionY=y, Width=70, Height=LINE_H + 6,
            ),
        )
        self.model.insertByName(
            "timeout_hint",
            _create_model(
                self.model, "com.sun.star.awt.UnoControlFixedText", "timeout_hint",
                PositionX=200, PositionY=y + 3, Width=field_w - 80, Height=LINE_H,
                Label="seconds (increase for slow local models)",
            ),
        )

        y += step
        self.model.insertByName(
            "allow_edits",
            _create_model(
                self.model, "com.sun.star.awt.UnoControlCheckBox", "allow_edits",
                PositionX=field_x, PositionY=y, Width=field_w, Height=LINE_H,
                Label="Allow HaiLPER to edit the document directly",
            ),
        )
        y += LINE_H + 4
        self.model.insertByName(
            "allow_document_access",
            _create_model(
                self.model, "com.sun.star.awt.UnoControlCheckBox",
                "allow_document_access", PositionX=field_x, PositionY=y,
                Width=field_w, Height=LINE_H,
                Label="Allow HaiLPER to request document contents",
            ),
        )

        y += LINE_H + 4
        self.model.insertByName(
            "track_changes",
            _create_model(
                self.model, "com.sun.star.awt.UnoControlCheckBox",
                "track_changes", PositionX=field_x, PositionY=y,
                Width=field_w, Height=LINE_H,
                Label="Apply Rewrite / Proofread as tracked changes",
            ),
        )

        y += LINE_H + 8
        self._add_label("system_label", PAD, y, "System prompt:", 105)
        system_height = DLG_H - y - BTN_H - 2 * PAD - 6
        self.model.insertByName(
            "system_prompt",
            _create_model(
                self.model, "com.sun.star.awt.UnoControlEdit", "system_prompt",
                PositionX=field_x, PositionY=y, Width=field_w,
                Height=system_height, MultiLine=True,
                VScroll=True, HScroll=True,
            ),
        )

        by = DLG_H - BTN_H - PAD
        self.model.insertByName(
            "btn_save",
            _create_model(
                self.model, "com.sun.star.awt.UnoControlButton", "btn_save",
                PositionX=DLG_W - 2 * 80 - PAD - 6, PositionY=by,
                Width=80, Height=BTN_H, Label="Save", DefaultButton=True,
            ),
        )
        self.model.insertByName(
            "btn_cancel",
            _create_model(
                self.model, "com.sun.star.awt.UnoControlButton", "btn_cancel",
                PositionX=DLG_W - 80 - PAD, PositionY=by,
                Width=80, Height=BTN_H, Label="Cancel",
            ),
        )

        self.dialog = _smgr(ctx).createInstanceWithContext(
            "com.sun.star.awt.UnoControlDialog", ctx
        )
        self.dialog.setModel(self.model)
        toolkit = _smgr(ctx).createInstanceWithContext("com.sun.star.awt.Toolkit", ctx)
        parent = None
        try:
            parent = self.frame.getContainerWindow()
        except Exception:
            parent = None
        self.dialog.createPeer(toolkit, parent)

        self.dialog.getControl("provider").addItemListener(
            _ItemListener(lambda e: self._load_provider())
        )
        self.dialog.getControl("btn_save").addActionListener(
            _ActionListener(lambda e: self._save())
        )
        self.dialog.getControl("btn_cancel").addActionListener(
            _ActionListener(lambda e: self._cancel())
        )

        self._load_provider()

    def _add_label(self, name, x, y, label, width=105):
        self.model.insertByName(
            name,
            _create_model(
                self.model, "com.sun.star.awt.UnoControlFixedText", name,
                PositionX=x, PositionY=y + 3, Width=width, Height=LINE_H,
                Label=label,
            ),
        )

    # ---------------------------------------------------------------- helpers
    def _get(self, name):
        control = self.dialog.getControl(name)
        return control.getText() if control is not None else ""

    def _set(self, name, value):
        control = self.dialog.getControl(name)
        if control is not None:
            control.setText(str(value))

    def _get_state(self, name):
        control = self.dialog.getControl(name)
        try:
            return control.getState() == 1
        except Exception:
            return False

    def _set_state(self, name, value):
        control = self.dialog.getControl(name)
        if control is not None:
            control.getModel().setPropertyValue("State", 1 if value else 0)

    def _selected_provider(self):
        label = self._get("provider")
        return self._label_to_id.get(label, self.config.get("provider", "ollama"))

    def _load_provider(self):
        pid = self._selected_provider()
        entry = self.config.get("providers", {}).get(pid, {})
        spec = cp_providers.PROVIDERS.get(pid, {})
        self._set("api_key", entry.get("api_key", ""))
        self._set("model", entry.get("model") or spec.get("default_model", ""))
        self._set("base_url", entry.get("base_url") or spec.get("base_url", ""))
        self._set("temperature", self.config.get("temperature", 0.3))
        self._set("max_tokens", self.config.get("max_tokens", 1024))
        self._set("timeout", self.config.get("timeout", 120))
        self._set("system_prompt", self.config.get("system_prompt", ""))
        self._set_state("allow_edits", self.config.get("allow_edits", False))
        self._set_state("allow_document_access",
                        self.config.get("allow_document_access", True))
        self._set_state("track_changes", self.config.get("track_changes", True))
        models = list(spec.get("models", []))
        if not models and pid not in self._model_cache:
            base = self._get("base_url").strip()
            key = self._get("api_key").strip()
            if base and (not spec.get("requires_key") or key):
                try:
                    models = cp_providers.list_models(pid, key, base, timeout=8)
                except Exception:
                    models = []
                self._model_cache[pid] = models
        if not models:
            models = self._model_cache.get(pid, [])
        try:
            _set_string_list(
                self.dialog.getControl("model").getModel(), models,
            )
        except Exception:
            pass

    def _save(self):
        pid = self._selected_provider()
        providers = self.config.setdefault("providers", {})
        entry = providers.setdefault(pid, {})
        entry["api_key"] = self._get("api_key").strip()
        entry["model"] = self._get("model").strip()
        entry["base_url"] = self._get("base_url").strip()

        self.config["provider"] = pid
        try:
            self.config["temperature"] = float(self._get("temperature") or 0.3)
        except ValueError:
            self.config["temperature"] = 0.3
        try:
            self.config["max_tokens"] = int(float(self._get("max_tokens") or 1024))
        except ValueError:
            self.config["max_tokens"] = 1024
        try:
            self.config["timeout"] = int(float(self._get("timeout") or 120))
        except ValueError:
            self.config["timeout"] = 120
        self.config["system_prompt"] = self._get("system_prompt")
        self.config["allow_edits"] = self._get_state("allow_edits")
        self.config["allow_document_access"] = self._get_state("allow_document_access")
        self.config["track_changes"] = self._get_state("track_changes")

        cp_config.save(self.config)
        self.saved = True
        self._close()

    def _cancel(self):
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
        return self.saved


def show(ctx, frame, config):
    bridge = _OptionsBridge(ctx, frame, config)
    bridge.build()
    return bridge.run()
