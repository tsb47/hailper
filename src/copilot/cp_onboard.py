"""First-run guided walkthrough for HaiLPER.

A small modal, paged tour shown once after the panel is first opened. It can be
replayed from the panel menu or Settings. The only state it persists is the
``onboarded`` flag in the config.
"""

import cp_config
import cp_ui as ui


DLG_W = 440
DLG_H = 300
PAD = 10
LINE_H = 14
BTN_H = 22
MAP_PIXEL = 7

TITLE_FONT = 9.0
BODY_FONT = 7.0


PAGES = [
    {
        "title": "Welcome to HaiLPER",
        "body": (
            "HaiLPER is your AI writing assistant, docked in the LibreOffice "
            "sidebar.\n\n"
            "It can summarise, rewrite, translate, proofread and continue your "
            "text, answer questions about the document, and research the web."
        ),
    },
    {
        "title": "1. Connect a provider",
        "body": (
            "Open Settings and pick a provider (Ollama, OpenAI, Anthropic, "
            "Gemini, DeepSeek and many more), then paste your API key.\n\n"
            "Keys are stored in your operating system's keyring, never in a "
            "plain-text file. Local models via Ollama need no key."
        ),
        "settings": True,
    },
    {
        "title": "2. Choose a Persona and an Action",
        "body": (
            "Persona sets the tone and expertise; Action sets what to do "
            "(Summarise, Rewrite, Translate, Proofread, Continue...).\n\n"
            "Type your instruction in the box and press Send. With nothing "
            "selected, HaiLPER works on the whole document."
        ),
    },
    {
        "title": "3. Work with a selection",
        "body": (
            "Select some text first and HaiLPER focuses on exactly that.\n\n"
            "Use Insert formatted to place the answer into the document with "
            "real Writer styles. Use the Undo / Retry button to roll back the "
            "last change."
        ),
    },
    {
        "title": "4. Right-click anywhere",
        "body": (
            "Right-click a selection to find the HaiLPER submenu. It adapts to "
            "what you picked - summarise a link, draft a reply to an email, "
            "explain a short phrase, rewrite, translate and more.\n\n"
            "Your own custom actions appear there too."
        ),
    },
    {
        "title": "5. Agent mode and the web",
        "body": (
            "Enable Agent mode from the menu to let HaiLPER work in steps, "
            "reading and editing the document as needed.\n\n"
            "Web search and page fetching let it look things up, with results "
            "clearly marked as untrusted before they reach the model."
        ),
    },
    {
        "title": "You're all set",
        "body": (
            "Everything is available from the sidebar. Reopen this tour any "
            "time from the menu, or from Settings.\n\n"
            "Tip: the small line at the bottom shows token usage for the last "
            "request."
        ),
        "last": True,
    },
]


def should_onboard(config):
    """True when the guided tour has not been completed yet."""
    return cp_config.should_onboard(config)


class _Bridge(object):
    def __init__(self, ctx, frame, config):
        self.ctx = ctx
        self.frame = frame
        self.config = config
        self.index = 0
        self.model = None
        self.dialog = None

    def build(self):
        ctx = self.ctx
        self.model = ui.smgr(ctx).createInstanceWithContext(
            "com.sun.star.awt.UnoControlDialogModel", ctx)
        self.model.setPropertyValue("Title", "Welcome to HaiLPER")
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
            PositionX=PAD, PositionY=PAD, Width=content_w - 60, Height=16,
            Label="", FontHeight=TITLE_FONT)
        add("com.sun.star.awt.UnoControlFixedText", "page_label",
            PositionX=PAD + content_w - 56, PositionY=PAD + 2, Width=56,
            Height=LINE_H, Label="", Align=2, FontHeight=BODY_FONT)
        add("com.sun.star.awt.UnoControlFixedText", "body",
            PositionX=PAD, PositionY=PAD + 20, Width=content_w, Height=140,
            Label="", MultiLine=True, FontHeight=BODY_FONT)
        add("com.sun.star.awt.UnoControlButton", "settings_btn",
            PositionX=PAD, PositionY=PAD + 168, Width=120, Height=BTN_H,
            Label="Open Settings\u2026")
        add("com.sun.star.awt.UnoControlCheckBox", "dont_show",
            PositionX=PAD, PositionY=PAD + 196, Width=content_w, Height=12,
            Label="Don't show this walkthrough again", State=1,
            FontHeight=BODY_FONT)
        add("com.sun.star.awt.UnoControlButton", "skip",
            PositionX=PAD, PositionY=DLG_H - BTN_H - PAD, Width=70,
            Height=BTN_H, Label="Skip")
        add("com.sun.star.awt.UnoControlButton", "back",
            PositionX=PAD + content_w - 2 * 80 - 6, PositionY=DLG_H - BTN_H - PAD,
            Width=80, Height=BTN_H, Label="Back")
        add("com.sun.star.awt.UnoControlButton", "next",
            PositionX=PAD + content_w - 80, PositionY=DLG_H - BTN_H - PAD,
            Width=80, Height=BTN_H, Label="Next", DefaultButton=True)

        self.dialog = ui.smgr(ctx).createInstanceWithContext(
            "com.sun.star.awt.UnoControlDialog", ctx)
        self.dialog.setModel(self.model)
        toolkit = ui.smgr(ctx).createInstanceWithContext(
            "com.sun.star.awt.Toolkit", ctx)
        try:
            parent = self.frame.getContainerWindow()
        except Exception:
            parent = None
        self.dialog.createPeer(toolkit, parent)

        self.dialog.getControl("next").addActionListener(
            ui.ActionListener(lambda event: self.on_next()))
        self.dialog.getControl("back").addActionListener(
            ui.ActionListener(lambda event: self.on_back()))
        self.dialog.getControl("skip").addActionListener(
            ui.ActionListener(lambda event: self.on_skip()))
        self.dialog.getControl("settings_btn").addActionListener(
            ui.ActionListener(lambda event: self.on_settings()))

        self._render()

    def _render(self):
        page = PAGES[self.index]
        self.dialog.getControl("title").setText(page["title"])
        self.dialog.getControl("body").setText(page["body"])
        self.dialog.getControl("page_label").setText(
            "%d / %d" % (self.index + 1, len(PAGES)))
        is_first = self.index == 0
        is_last = self.index == len(PAGES) - 1
        self._set_visible("settings_btn", bool(page.get("settings")))
        self._set_visible("dont_show", is_last)
        self._set_visible("back", not is_first)
        self._set_label("next", "Finish" if is_last else "Next")
        self._set_visible("skip", not is_last)
        if page.get("settings"):
            self._set_label("skip", "Skip")

    def _set_visible(self, name, visible):
        try:
            self.dialog.getControl(name).setVisible(visible)
        except Exception:
            pass

    def _set_label(self, name, label):
        try:
            self.dialog.getControl(name).setLabel(label)
        except Exception:
            pass

    def on_settings(self):
        try:
            import cp_options
            cp_options.show(self.ctx, self.frame, self.config)
        except Exception as error:
            ui.log("walkthrough settings failed: %r" % error)

    def on_next(self):
        if self.index >= len(PAGES) - 1:
            self._finish()
        else:
            self.index += 1
            self._render()

    def on_back(self):
        if self.index > 0:
            self.index -= 1
            self._render()

    def on_skip(self):
        self._finish()

    def _finish(self):
        try:
            self.dialog.endExecute()
        except Exception:
            pass
        try:
            self.dialog.dispose()
        except Exception:
            pass

    def run(self):
        try:
            self.dialog.execute()
        except Exception as error:
            ui.log("walkthrough execute failed: %r" % error)


def show(ctx, frame, config, force=False):
    """Show the guided tour. Marks the config as onboarded unless forced."""
    bridge = _Bridge(ctx, frame, config)
    try:
        bridge.build()
    except Exception as error:
        ui.log("walkthrough build failed: %r" % error)
        return
    ui.log("walkthrough shown force=%s" % force)
    bridge.run()
    ui.log("walkthrough closed")
    if force:
        return
    try:
        config["onboarded"] = True
        import cp_config
        cp_config.save(config)
    except Exception as error:
        ui.log("walkthrough save failed: %r" % error)
