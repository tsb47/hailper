"""UNO entry point: routes Addons.xcu menu/toolbar commands to the dialogs."""

import os
import sys
import time
from urllib.parse import unquote

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import uno
import unohelper

from com.sun.star.frame import XDispatch, XDispatchProvider
from com.sun.star.lang import XInitialization, XServiceInfo


IMPL_NAME = "io.github.rokusaburo.hailper.CommandHandler"
PROTOCOL = "io.github.rokusaburo.hailper:"
SERVICE_NAMES = (
    "io.github.rokusaburo.hailper.CommandHandler",
    "com.sun.star.frame.ProtocolHandler",
)


def _log(message):
    try:
        path = os.path.join(
            os.path.expanduser("~"), ".config", "hailper", "hailper.log"
        )
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "a", encoding="utf-8") as handle:
            handle.write("%s %s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), message))
    except Exception:
        pass


def _is_document(component):
    if component is None:
        return False
    for service in (
        "com.sun.star.text.TextDocument",
        "com.sun.star.sheet.SpreadsheetDocument",
        "com.sun.star.presentation.PresentationDocument",
        "com.sun.star.drawing.DrawingDocument",
    ):
        try:
            if component.supportsService(service):
                return True
        except Exception:
            pass
    return False


def _model_of_frame(frame):
    if frame is None:
        return None
    try:
        controller = frame.getController()
        if controller is not None:
            model = controller.getModel()
            if _is_document(model):
                return model
    except Exception:
        pass
    return None


def _parse_url(url):
    """Return (action, params) for a command URL.

    Accepts both the custom protocol form
    ``io.github.rokusaburo.hailper:summarize?style=...`` and the legacy
    ``service:...?action=summarize`` form. UNO may fill Protocol/Path or only
    Complete, so handle both.
    """
    path = getattr(url, "Path", "") or ""
    complete = getattr(url, "Complete", "") or ""
    raw = path
    if not raw and complete.startswith(PROTOCOL):
        raw = complete[len(PROTOCOL):]
    query = ""
    if "?" in raw:
        raw, query = raw.split("?", 1)
    elif "?" in complete:
        query = complete.split("?", 1)[1]
    params = {}
    for pair in query.split("&"):
        if "=" in pair:
            key, value = pair.split("=", 1)
            params[unquote(key)] = unquote(value)
        elif pair.startswith("action="):
            pass
    action = raw
    if not action and "action=" in complete:
        for pair in query.split("&"):
            if pair.startswith("action="):
                action = pair[len("action="):]
                break
    return (action or "chat"), params


class CommandHandler(
    unohelper.Base,
    XDispatch,
    XDispatchProvider,
    XInitialization,
    XServiceInfo,
):
    def __init__(self, ctx):
        self.ctx = ctx
        self.frame = None

    # ------------------------------------------------------------- lifecycle
    def initialize(self, args):
        for arg in args:
            name = getattr(arg, "Name", "") or ""
            value = getattr(arg, "Value", None)
            if name == "Frame":
                self.frame = value
            elif not name and value is not None:
                # Some paths pass the frame as an unnamed argument.
                self.frame = value

    # ------------------------------------------------------------- dispatch
    def queryDispatch(self, url, target_frame_name, search_flags):
        complete = getattr(url, "Complete", "") or ""
        protocol = getattr(url, "Protocol", "") or ""
        if protocol == PROTOCOL or complete.startswith(PROTOCOL):
            return self
        if IMPL_NAME in complete:
            return self
        return None

    def queryDispatches(self, requests):
        return tuple(
            self.queryDispatch(r.URL, r.TargetFrameName, r.SearchFlags)
            for r in requests
        )

    def dispatch(self, url, args):
        action, params = _parse_url(url)
        _log("dispatch action=%r params=%r url=%r"
             % (action, params, getattr(url, "Complete", "?")))
        try:
            self._run(action, params)
        except Exception as error:  # noqa: BLE001
            _log("dispatch FAILED: %s: %s" % (type(error).__name__, error))
            self._error("HaiLPER error", "%s: %s" % (type(error).__name__, error))

    def addStatusListener(self, listener, url):
        pass

    def removeStatusListener(self, listener, url):
        pass

    # ------------------------------------------------------------- XServiceInfo
    def getImplementationName(self):
        return IMPL_NAME

    def supportsService(self, name):
        return name in SERVICE_NAMES

    def getSupportedServiceNames(self):
        return SERVICE_NAMES

    # ------------------------------------------------------------- internals
    def _run(self, action, params=None):
        params = params or {}
        import cp_config

        if action == "options":
            import cp_options
            cp_options.show(self.ctx, self.frame, cp_config.load())
            return

        if action == "chat" and self._current_document() is None:
            self._error("HaiLPER", "Open a document first.")
            return

        document = self._current_document()
        if document is None:
            self._error("HaiLPER", "Open a document first.")
            return

        import cp_document
        import cp_dialog

        kind = cp_document.detect_kind(document)
        # Capture the current selection now, before the panel takes focus, so
        # the model reads exactly what the user had selected.
        try:
            doc_ctx = cp_document.DocumentContext(self.ctx, document)
            if doc_ctx.selected_text.strip():
                params.setdefault("captured_text", doc_ctx.selected_text)
        except Exception:
            pass
        _log("run action=%s kind=%s captured=%s"
             % (action, kind, bool(params.get("captured_text"))))
        config = cp_config.load()
        if kind == cp_document.UNKNOWN:
            self._error(
                "HaiLPER",
                "This document type is not supported yet. Try Writer, Calc or Impress.",
            )
            return
        cp_dialog.sidebar_show(self.ctx, self.frame, action, config, params)

    def _current_document(self):
        if self.frame is not None:
            document = _model_of_frame(self.frame)
            if document is not None:
                return document
        try:
            desktop = self.ctx.getByName(
                "/singletons/com.sun.star.frame.theDesktop"
            )
        except Exception as error:
            _log("_current_document: no desktop: %r" % error)
            return None
        document = _model_of_frame(desktop.getCurrentFrame())
        if document is not None:
            return document
        try:
            components = desktop.getComponents()
            if components is not None:
                enumeration = components.createEnumeration()
                while enumeration.hasMoreElements():
                    component = enumeration.nextElement()
                    if _is_document(component):
                        return component
        except Exception:
            pass
        try:
            return desktop.getCurrentComponent()
        except Exception:
            return None

    def _error(self, title, message):
        try:
            toolkit = self.ctx.getServiceManager().createInstanceWithContext(
                "com.sun.star.awt.Toolkit", self.ctx
            )
            parent = None
            try:
                parent = self.frame.getContainerWindow()
            except Exception:
                parent = None
            rectangle = uno.createUnoStruct("com.sun.star.awt.Rectangle")
            rectangle.X = 0
            rectangle.Y = 0
            rectangle.Width = 300
            rectangle.Height = 200
            box = toolkit.createMessageBox(
                parent, rectangle, "errorbox", "OK", title, message
            )
            box.execute()
        except Exception:
            pass


def _create_handler(ctx):
    return CommandHandler(ctx)


g_ImplementationHelper = unohelper.ImplementationHelper()
g_ImplementationHelper.addImplementation(
    _create_handler, IMPL_NAME, SERVICE_NAMES
)
