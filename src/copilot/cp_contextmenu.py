"""Right-click 'HaiLPER' context menu via XContextMenuInterceptor.

Registered always-on through Jobs.xcu (onDocumentOpened / onCreate), and as a
fallback whenever the panel or a command is used.
"""

import os
import sys

import uno
import unohelper

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from urllib.parse import quote

from com.sun.star.container import XIndexContainer
from com.sun.star.lang import XMultiServiceFactory
from com.sun.star.task import XJob
from com.sun.star.ui import XContextMenuInterceptor
from com.sun.star.ui import XContextMenuInterception
from com.sun.star.ui.ContextMenuInterceptorAction import CONTINUE_MODIFIED
from com.sun.star.ui.ContextMenuInterceptorAction import IGNORED

import cp_document
import cp_prompts
import cp_ui as ui


IMPL_FACTORY = "io.github.rokusaburo.hailper.ContextMenuJob"
PROTOCOL = "io.github.rokusaburo.hailper:"

_XMULTI = uno.getTypeByName("com.sun.star.lang.XMultiServiceFactory")
_XPROPSET = uno.getTypeByName("com.sun.star.beans.XPropertySet")
_XINDEX = uno.getTypeByName("com.sun.star.container.XIndexContainer")
_XINTERCEPTION = uno.getTypeByName("com.sun.star.ui.XContextMenuInterception")

_registered = set()
_interceptors = []


def _command(action, run=True, **params):
    query = {"run": "1" if run else "0"}
    query.update({k: v for k, v in params.items() if v})
    pairs = "&".join("%s=%s" % (key, quote(str(value)))
                     for key, value in query.items())
    return "%s%s?%s" % (PROTOCOL, action, pairs)


def _range_text(selection):
    if selection is None:
        return ""
    try:
        if not hasattr(selection, "getString") and hasattr(selection, "getCount"):
            if selection.getCount() > 0:
                return _range_text(selection.getByIndex(0))
    except Exception:
        pass
    try:
        return selection.getString() or ""
    except Exception:
        return ""


def _selection_text(event):
    supplier = event.Selection
    if supplier is None:
        return ""
    try:
        return _range_text(supplier.getSelection())
    except Exception:
        return ""


class ContextMenuInterceptor(unohelper.Base, XContextMenuInterceptor):
    def __init__(self, ctx, controller):
        self.ctx = ctx
        self.controller = controller

    def notifyContextMenuExecute(self, event):
        try:
            container = event.ActionTriggerContainer
            if container is None:
                return IGNORED
            factory = container.queryInterface(_XMULTI)
            if factory is None:
                return IGNORED
            if self._has_our_menu(container):
                return CONTINUE_MODIFIED
            selected = bool(_selection_text(event).strip())
            self._build_menu(factory, container, self._document_kind(), selected)
            return CONTINUE_MODIFIED
        except Exception as error:
            ui.log("context menu error: %r" % error)
            return IGNORED

    def _has_our_menu(self, container):
        try:
            for index in range(container.getCount()):
                try:
                    props = container.getByIndex(index).queryInterface(_XPROPSET)
                    if props is not None and props.getPropertyValue("Text") == "HaiLPER":
                        return True
                except Exception:
                    pass
        except Exception:
            pass
        return False

    def _document_kind(self):
        try:
            return cp_document.detect_kind(self.controller.getModel())
        except Exception:
            return cp_document.UNKNOWN

    # ------------------------------------------------------------- builders
    def _trigger(self, factory, text, command):
        trigger = factory.createInstance("com.sun.star.ui.ActionTrigger")
        props = trigger.queryInterface(_XPROPSET)
        props.setPropertyValue("Text", text)
        props.setPropertyValue("CommandURL", command)
        return trigger

    def _submenu(self, factory):
        return factory.createInstance(
            "com.sun.star.ui.ActionTriggerContainer").queryInterface(_XINDEX)

    def _append(self, container, item):
        container.insertByIndex(container.getCount(), item)

    def _append_action(self, factory, container, text, command):
        self._append(container, self._trigger(factory, text, command))

    def _append_submenu(self, factory, parent, text, entries):
        sub = self._submenu(factory)
        for label, command in entries:
            self._append_action(factory, sub, label, command)
        trigger = self._trigger(factory, text, "")
        trigger.queryInterface(_XPROPSET).setPropertyValue("SubContainer", sub)
        self._append(parent, trigger)

    def _translate_submenu(self, factory, menu):
        entries = [(lang, _command("translate", lang=lang))
                   for lang in cp_prompts.TRANSLATE_TOP]
        entries.append(("More\u2026", _command("translate", run=False)))
        self._append_submenu(factory, menu, "Translate to", entries)

    def _flat_items(self, kind, selected):
        labels = []
        if selected:
            if kind == cp_document.CALC:
                labels = [("Summarize range", _command("summarize", scope="selection")),
                          ("Rewrite", _command("rewrite")),
                          ("Fix spelling", _command("proofread",
                                                    categories="Spelling & grammar")),
                          ("Explain formula", _command("explain"))]
            elif kind == cp_document.IMPRESS:
                labels = [("Rewrite", _command("rewrite")),
                          ("Summarize slide", _command("summarize", scope="selection")),
                          ("Speaker notes", _command("notes"))]
            else:
                labels = [("Summarize", _command("summarize")),
                          ("Rewrite", _command("rewrite")),
                          ("Proofread", _command("proofread")),
                          ("Continue writing", _command("continue")),
                          ("Explain", _command("explain"))]
        else:
            labels = [("Summarize document", _command("summarize", scope="document")),
                      ("Explain document", _command("explain", scope="document")),
                      ("Continue writing", _command("continue", scope="document"))]
        labels.append(("Ask\u2026", _command("custom", run=False)))
        labels.append(("Add to chat", _command("chat_about", run=False)))
        return [("HaiLPER: " + text, command) for text, command in labels]

    def _build_menu(self, factory, container, kind, selected):
        try:
            self._build_submenu(factory, container, kind, selected)
        except Exception as error:
            ui.log("context submenu failed, using flat menu: %r" % error)
            for label, command in self._flat_items(kind, selected):
                self._append_action(factory, container, label, command)

    def _build_submenu(self, factory, container, kind, selected):
        menu = self._submenu(factory)

        if selected:
            if kind == cp_document.CALC:
                self._append_action(factory, menu, "Summarize range",
                                    _command("summarize", scope="selection"))
                self._append_action(factory, menu, "Rewrite", _command("rewrite"))
                self._translate_submenu(factory, menu)
                self._append_action(factory, menu, "Fix spelling",
                                    _command("proofread",
                                             categories="Spelling & grammar"))
                self._append_action(factory, menu, "Explain formula",
                                    _command("explain"))
            elif kind == cp_document.IMPRESS:
                self._append_action(factory, menu, "Rewrite text", _command("rewrite"))
                self._append_action(factory, menu, "Summarize slide",
                                    _command("summarize", scope="selection"))
                self._translate_submenu(factory, menu)
                self._append_action(factory, menu, "Speaker notes", _command("notes"))
            else:
                styles = [(style, _command("rewrite", style=style))
                          for style in cp_prompts.REWRITE_STYLES]
                self._append_submenu(factory, menu, "Rewrite as", styles)
                self._append_action(factory, menu, "Summarize", _command("summarize"))
                self._translate_submenu(factory, menu)
                self._append_action(factory, menu, "Proofread", _command("proofread"))
                self._append_action(factory, menu, "Continue writing",
                                    _command("continue"))
                self._append_action(factory, menu, "Explain", _command("explain"))
        else:
            self._append_action(factory, menu, "Summarize document",
                                _command("summarize", scope="document"))
            self._translate_submenu(factory, menu)
            self._append_action(factory, menu, "Explain document",
                                _command("explain", scope="document"))
            if kind != cp_document.CALC:
                self._append_action(factory, menu, "Continue writing",
                                    _command("continue", scope="document"))

        self._append_action(factory, menu, "Ask AI\u2026",
                            _command("custom", run=False))
        self._append_action(factory, menu, "Add to chat",
                            _command("chat_about", run=False))

        separator = factory.createInstance("com.sun.star.ui.ActionTriggerSeparator")
        try:
            from com.sun.star.ui.ActionTriggerSeparatorType import LINE
            separator.queryInterface(_XPROPSET).setPropertyValue(
                "SeparatorType", LINE)
        except Exception:
            pass
        self._append(container, separator)

        trigger = self._trigger(factory, "HaiLPER", "")
        trigger.queryInterface(_XPROPSET).setPropertyValue("SubContainer", menu)
        self._append(container, trigger)


# ------------------------------------------------------------------ lifecycle
def _register_controller(ctx, controller):
    try:
        key = id(controller)
    except Exception:
        return
    if key in _registered:
        return
    for existing in _interceptors:
        try:
            if existing.controller == controller:
                _registered.add(key)
                return
        except Exception:
            pass
    try:
        interception = controller.queryInterface(_XINTERCEPTION)
        if interception is None:
            return
        interceptor = ContextMenuInterceptor(ctx, controller)
        interception.registerContextMenuInterceptor(interceptor)
        _registered.add(key)
        _interceptors.append(interceptor)
        ui.log("context menu interceptor registered")
    except Exception as error:
        ui.log("context menu register failed: %r" % error)


def ensure_registered(ctx, frame):
    if frame is None:
        try:
            frame = ctx.getByName(
                "/singletons/com.sun.star.frame.theDesktop").getCurrentFrame()
        except Exception:
            frame = None
    if frame is None:
        return
    try:
        controller = frame.getController()
    except Exception:
        controller = None
    if controller is not None:
        _register_controller(ctx, controller)


def ensure_registered_model(ctx, model):
    try:
        controller = model.getCurrentController()
    except Exception:
        controller = None
    if controller is None:
        try:
            controller = ctx.getByName(
                "/singletons/com.sun.star.frame.theDesktop"
            ).getCurrentFrame().getController()
        except Exception:
            controller = None
    if controller is not None:
        _register_controller(ctx, controller)


class ContextMenuJob(unohelper.Base, XJob):
    def __init__(self, ctx):
        self.ctx = uno.getComponentContext()

    def execute(self, args):
        frame = None
        model = None
        for arg in args:
            if arg.Name != "Environment":
                continue
            try:
                for item in arg.Value:
                    if item.Name == "Frame":
                        frame = item.Value
                    elif item.Name == "Model":
                        model = item.Value
            except Exception:
                pass
        if model is not None:
            ensure_registered_model(self.ctx, model)
        if frame is not None:
            ensure_registered(self.ctx, frame)
        if frame is None and model is None:
            ensure_registered(self.ctx, None)
        # Make the HaiLPER deck the active sidebar deck so menu actions open it.
        try:
            import cp_dialog
            cp_dialog._set_last_active_deck(self.ctx)
        except Exception:
            pass
        return None


g_ImplementationHelper = unohelper.ImplementationHelper()
g_ImplementationHelper.addImplementation(
    ContextMenuJob, IMPL_FACTORY, (IMPL_FACTORY, "com.sun.star.task.Job")
)
