"""LibreOffice Sidebar panel for HaiLPER.

Registers an XUIElementFactory (see Factory.xcu) that creates a docked sidebar
panel. The panel content is the same UI as the floating panel, hosted in a
ContainerWindowProvider window so it lives inside the sidebar.

Shared state (the live bridge and any pending action) lives in cp_dialog so the
sidebar component and the command handler see the same objects even though
LibreOffice loads the component file under its own module name.
"""

import os
import sys
import traceback

import uno
import unohelper

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from com.sun.star.lang import XComponent
from com.sun.star.ui import XUIElement
from com.sun.star.ui import XUIElementFactory
from com.sun.star.ui import XSidebarPanel
from com.sun.star.ui import XToolPanel
from com.sun.star.ui import LayoutSize
from com.sun.star.ui.UIElementType import TOOLPANEL as UET_TOOLPANEL

import cp_config
import cp_dialog
import cp_ui as ui


IMPL = "io.github.rokusaburo.hailper.SidebarFactory"
DECK_ID = "io.github.rokusaburo.hailper.deck"
PANEL_ID = "io.github.rokusaburo.hailper.panel"
FACTORY_NAME = "CopilotFactory"
PANEL_URL = "private:resource/toolpanel/%s/%s" % (FACTORY_NAME, PANEL_ID)
XDL_URL = ("vnd.sun.star.extension://io.github.rokusaburo.hailper/"
           "copilot_panel.xdl")


class CopilotPanel(
    unohelper.Base, XSidebarPanel, XUIElement, XToolPanel, XComponent
):
    def __init__(self, ctx, frame, parent_window, url, sidebar=None):
        self.ctx = ctx
        self.frame = frame
        self.parent_window = parent_window
        self.url = url
        self.sidebar = sidebar
        self.window = None
        self.bridge = None

    def _request_layout(self):
        if self.sidebar is not None:
            try:
                self.sidebar.requestLayout()
            except Exception:
                pass

    # ------------------------------------------------------ XUIElement
    def getRealInterface(self):
        if self.window is None:
            provider = self.ctx.ServiceManager.createInstanceWithContext(
                "com.sun.star.awt.ContainerWindowProvider", self.ctx
            )
            self.window = provider.createContainerWindow(
                XDL_URL, "", self.parent_window, None
            )
            action = cp_dialog._sidebar_pending.get("action", "chat")
            config = cp_dialog._sidebar_pending.get("config") or cp_config.load()
            params = cp_dialog._sidebar_pending.get("params") or {}
            cp_dialog._sidebar_pending.clear()
            self.bridge = cp_dialog._Bridge(self.ctx, self.frame, action, config)
            try:
                self.bridge.available_px = self.parent_window.getPosSize().Height
            except Exception:
                self.bridge.available_px = 0
            self.bridge.build_into(self.window, None, is_sidebar=True)
            self.bridge.on_layout = self._request_layout
            cp_dialog._sidebar_bridge = self.bridge
            cp_dialog._sidebar_visible = True
            cp_dialog._sidebar_ever_seen = True
            cp_dialog._apply_sidebar_action(
                self.bridge, self.frame, action, config, params)
            # Force a full layout pass and make sure the content window is
            # actually shown; without this the panel can come up blank.
            try:
                self.bridge._relayout(controls_ready=True)
            except Exception:
                ui.log("relayout FAILED:\n" + traceback.format_exc())
            for ensure in ("setVisible", "Visible"):
                try:
                    if ensure == "setVisible":
                        self.window.setVisible(True)
                    else:
                        self.window.Visible = True
                except Exception:
                    pass
            try:
                self.window.getControl("instruction").setFocus()
            except Exception:
                pass
            try:
                import cp_contextmenu
                cp_contextmenu.ensure_registered(self.ctx, self.frame)
            except Exception:
                pass
            try:
                cp_dialog.maybe_show_walkthrough(self.ctx, self.frame, config)
            except Exception:
                pass
            self._request_layout()
            ui.log("CopilotPanel: built")
        return self

    @property
    def Frame(self):
        return self.frame

    @property
    def ResourceURL(self):
        return self.url

    @property
    def Type(self):
        return UET_TOOLPANEL

    # ------------------------------------------------------ XToolPanel
    @property
    def Window(self):
        return self.window

    def getWindow(self):
        return self.window

    def createAccessible(self, parent):
        return None

    # ------------------------------------------------------ XSidebarPanel
    def _content_extent(self):
        """Return (width, height) of the built controls in pixels."""
        try:
            dialog = self.bridge.dialog
            bottom = dialog.getControl("btn_%d" % (cp_dialog.SLOTS - 1))
            pos = bottom.getPosSize()
            height = pos.Y + pos.Height + 10
            result = dialog.getControl("result")
            rpos = result.getPosSize()
            width = rpos.X + rpos.Width + 12
            return width, height
        except Exception:
            return 420, 760

    def getHeightForWidth(self, width):
        _w, height = self._content_extent()
        return LayoutSize(height, height, height)

    def getMinimalWidth(self):
        width, _h = self._content_extent()
        return width

    # ------------------------------------------------------ XComponent
    def dispose(self):
        if self.bridge is not None:
            self.bridge.alive = False
        if cp_dialog._sidebar_bridge is self.bridge:
            cp_dialog._sidebar_bridge = None
        cp_dialog._sidebar_visible = False
        ui.log("CopilotPanel: disposed")

    def addEventListener(self, listener):
        pass

    def removeEventListener(self, listener):
        pass


class ElementFactory(unohelper.Base, XUIElementFactory):
    def __init__(self, ctx):
        self.ctx = uno.getComponentContext()

    def createUIElement(self, resource_url, args):
        ui.log("createUIElement url=%r" % resource_url)
        if resource_url != PANEL_URL:
            return None
        frame = None
        parent_window = None
        sidebar = None
        for arg in args:
            if arg.Name == "Frame":
                frame = arg.Value
            elif arg.Name == "ParentWindow":
                parent_window = arg.Value
            elif arg.Name == "Sidebar":
                sidebar = arg.Value
        try:
            panel = CopilotPanel(self.ctx, frame, parent_window, resource_url, sidebar)
            panel.getRealInterface()
            return panel
        except Exception:
            import traceback
            ui.log("sidebar panel FAILED:\n" + traceback.format_exc())
            raise


def show(ctx, frame, action, config, params=None):
    return cp_dialog.sidebar_show(ctx, frame, action, config, params)


g_ImplementationHelper = unohelper.ImplementationHelper()
g_ImplementationHelper.addImplementation(
    ElementFactory, IMPL, (IMPL, "com.sun.star.task.Job")
)
