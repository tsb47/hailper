# HaiLPER for LibreOffice

An AI writing assistant embedded directly in LibreOffice as a **docked sidebar
panel**, so you can keep editing while the model is generating. It reads and
analyses the active document, rewrites or improves a selection, continues
writing, translates, proofreads (with a step-through review), and inserts
AI-generated text, comments, or new content.

It is a Python UNO extension packaged as a `.oxt`, so it runs inside
LibreOffice and talks to your chosen AI provider over HTTPS. No third-party
Python packages are required.

## Features

- **Docked sidebar panel** – an **HaiLPER** deck next to Properties/Styles,
  not a pop-up window. Generation runs in the background.
- **Chat with AI** – multi-turn conversation that can see your document.
- **Summarize** – overview plus key points; can go straight into a new document.
- **Rewrite / Improve** – clearer, more formal, friendlier, more persuasive,
  simpler, expanded, or grammar-only.
- **Continue Writing** – continues naturally from the selection/cursor.
- **Translate** – into 14 common languages.
- **Proofread / Review** – suggestions are returned as structured data and a
  step-through window lets you **Fix** or **Ignore** each one.
- **Ask About Selection** – free-form instruction applied to the selection.
- **Conversation panel** – a scrolling transcript with labelled, separated
  turns and a tinted message box so input and output are easy to distinguish.
- **Inline proofread review** – step through suggestions in the sidebar and
  adopt or reject each one.
- **Direct document editing / reading** – permission-gated; the model can read
  the document on request and apply edits it proposes.
- **Formatting, styles and layout** (Writer) – permission-gated; the model can
  apply character and paragraph formatting, existing styles, page margins and
  orientation, and insert tables, via a structured `{"format": [...]}`
  directive. Each batch is one undo step and document-wide/page changes are
  confirmed first.
- **Action dropdown + personas** – one selector for every action, and personas
  (General, Editor, Reviewer, Researcher) that set the system prompt, model,
  temperature and which actions are available.
- **Custom actions** – save your own prompts in
  `~/.config/hailper/actions.json`; they appear in the dropdown and the
  right-click menu.
- **Token / cost meter** – per-request tokens, estimated cost (with editable
  price overrides) and context-window usage, for cloud and local models.
- **Document outline awareness** – the model is given the heading outline, and
  formatting/actions can target a section by heading.
- **Agent mode** – an explicit multi-step loop where the model uses the edit,
  format and document tools until the task is done.
- **Starter prompts** and **saved conversations** (History picker).
- **Per-action options** – format/length, style/length, language/register,
  proofread categories/severity (remembered per action).
- **Rewrite diff** – compare original vs suggested and Accept/Reject.
- **Right-click menu** – an **HaiLPER** submenu on any selection (auto-runs).
- Apply with **Insert**, **Replace**, **Append**, **Comment**, **New document**,
  **Diff**, or **Copy**, depending on the action.

Works in **Writer** (full support), **Calc** (read/insert into cells) and
**Impress/Draw** (read/insert text boxes).

## Supported providers

**51 presets**, all selectable in **HaiLPER → Settings** (each with its own API
key, model and base URL; models are fetched automatically where supported).

- **Local:** Ollama, LM Studio, llama.cpp, Atomic Chat, LLM Gateway.
- **Native APIs:** OpenAI, Anthropic Claude, Google Gemini, Azure OpenAI,
  Azure Cognitive Services.
- **OpenAI-compatible cloud:** DeepSeek, Qwen (DashScope), xAI Grok, Groq,
  Mistral, Cerebras, Together AI, Fireworks AI, Perplexity, Cohere, DeepInfra,
  Baseten, NVIDIA NIM, Moonshot (Kimi), MiniMax, Z.AI (GLM), Hugging Face,
  Nebius, Scaleway, OVHcloud, Vercel AI Gateway, DigitalOcean, Cortecs,
  GMI Cloud, IO.NET, Venice AI, ZenMux, Poolside, STACKIT, 302.AI, Eden AI,
  Cloudflare Workers AI, Cloudflare AI Gateway, FrogBot, Helicone, SCX.ai,
  Modal, Ollama Cloud, OpenCode Zen, OpenRouter, and **Custom
  OpenAI-compatible** for anything else.

> OAuth/SigV4-only providers that OpenCode lists (Amazon Bedrock, Google Vertex
> AI, GitHub Copilot, GitLab Duo, SAP AI Core, Snowflake Cortex) are not preset;
> use **Custom** if you have a reachable OpenAI-compatible endpoint.

## Install

```sh
./build.sh
./install.sh          # removes the old copy, then installs
```

`unopkg` refuses to add the same version twice, so `install.sh` removes first.
You can also use **Tools → Extensions → Add…** and pick
`dist/HaiLPER-<version>.oxt`. Restart LibreOffice afterwards.

Requires **LibreOffice 7.6+** on **Linux** (this release).

## Using the sidebar

After restarting, open the sidebar (**View → Sidebar**, or `Ctrl+F5`) and
select the **HaiLPER** deck. The panel docks on the right and stays put while
you work.

Every menu/toolbar/NotebookBar action routes to it:

- **HaiLPER** menu (Standard UI) or the **Extension** tab (Tabbed UI).
- Actions such as Summarize, Rewrite, Translate, Proofread, and Chat.

If the sidebar is not showing when you run an action, the extension dispatches
`.uno:Sidebar` to open it and `.uno:SidebarDeck.io.github.rokusaburo.hailper.deck`
to activate the HaiLPER deck; the panel is then created and the requested
action runs. The sidebar can be opened/closed normally and the deck remembered.

## Conversation flow

The panel is a running conversation. Every action (whether triggered from the
menu, the toolbar, the **Extension** tab, the right-click menu, or the panel's
own **Action** dropdown) appends a turn to the transcript, and you can keep
chatting with the document in context. Use **New chat** to start over.

Choose an action in the **Action** dropdown (Chat, Summarize, Rewrite,
Translate, Proofread, Continue, Explain, plus any custom actions) and a
**Persona** below it, or run an action from the menu / right-click menu. The
**⋯ menu** in the conversation header holds the **model picker**, **starter
prompts**, **saved conversations**, **New chat** and the **agent-mode** toggle.
A **Scope** control chooses Selection or Document, a "Using: …" line shows what
will be read, and a usage line shows tokens, cost and context-window use.
Answers are rendered as Markdown in the transcript; **Insert formatted** applies
that Markdown to the document as real Writer styles. After a change the status
area offers **Undo** (formatted inserts undo in one step), and after an error it
offers **Retry**.

The transcript scrolls on its own and auto-scrolls to the newest message, and
`You` / `HaiLPER` turns are labelled and separated.

Actions that produce a replacement — **Rewrite**, **Translate** and
**Continue** — open a review of the draft with **Adopt**, **Reject**,
**Refine** and **Copy**. **Adopt** writes it into the document (replacing the
selection, or inserting at the cursor for Continue); **Refine** asks what to
change and regenerates the draft. **Summarize** just outputs into the chat, with
**New document**, Insert, Append, Comment and Copy as options.

## Contextual actions

Each action shows its own buttons and one or two dropdowns for the choices that
matter. The last choice per action is remembered.

| Action | Choices | Primary button | Other buttons |
| --- | --- | --- | --- |
| Chat | — | Insert reply | Copy, Comment, New chat, Close |
| Summarize | Format, Length | **New document** | Insert, Append, Comment, Copy |
| Rewrite / Improve | Style, Length | **Replace selection** | Diff, Insert, Append, Copy |
| Continue Writing | Length | **Insert at cursor** | Append to end, Comment, Copy |
| Translate | Language, Register | **Replace selection** | New document, Insert, Append, Copy |
| Proofread | Check, Level | **Review suggestions** | Fix all safe, Report, Insert, Comment |
| Ask About Selection | — | **Replace selection** | Insert, Append, Comment, Copy |

- **Regenerate / Stop** — the Send button becomes **Stop** while a request is
  running and **Send** again afterwards.
- **Diff** (Rewrite) opens a compare window with **Accept**, **Copy**, **Close**.
- **Proofread** runs on the document (or selection) and switches the panel into
  an inline review, one suggestion at a time (Original → Suggested, with the
  reason). Choose **Adopt** to write that fix into the document, **Reject** to
  skip it, **Previous** / **Next** to move around, **Adopt all** to accept every
  suggestion at once, or **Finish** to return to the conversation. Adopting a
  suggestion searches for the original text and replaces it.
- Insert/Replace/Append/Comment respect the document's **Record Changes** state;
  nothing is forced.

## Right-click menu

Right-clicking always shows an **HaiLPER** submenu (items auto-run; they appear
in Writer, Calc and Impress). With a **selection** it offers the actions below;
with **no selection** it offers document-level actions (Summarize document,
Translate, Explain document, Continue writing, Ask…, Add to chat).

- **Writer:** Rewrite as ▸ · Summarize · Translate to ▸ · Proofread · Continue
  writing · Explain · Ask AI… · Add to chat
- **Calc:** Summarize range · Rewrite · Translate to ▸ · Fix spelling · Explain
  formula · Ask AI… · Add to chat
- **Impress:** Rewrite text · Summarize slide · Translate to ▸ · Speaker notes ·
  Ask AI… · Add to chat
- **Translate to** lists the top five languages plus **More…**, which opens the
  panel with the full language list.

The interceptor is registered automatically when a document is opened (via
`Jobs.xcu`), so no setup is needed. It appears exactly **once** and is
de-duplicated even if it gets registered more than once. The current selection
is captured at the moment you click, so the model reads exactly what you had
selected. **Add to chat** seeds the panel's prompt with the selection instead of
running immediately.

## Configure

Open **HaiLPER → Settings**. Choose a provider, paste the API key (not needed
for Ollama), confirm the model/base URL, and tune temperature, max tokens,
timeout and the system prompt. Two permissions control what the model may do:

- **Allow HaiLPER to edit the document directly** (on by default) — the model
  can change the document by returning an edit directive:
  `{"edit": {"find": "old text", "text": "new text"}}` (replace a passage),
  `{"edit": {"action": "insert", "text": "..."}}` (at the cursor) or
  `{"edit": {"action": "append", "text": "..."}}` (at the end).
- **Allow HaiLPER to request document contents** (on by default) — in chat the
  model can reply `{"request": "document"}` and HaiLPER will send the document
  and re-ask, so the full text is only used when it is actually needed.
- **Allow HaiLPER to change formatting, styles and layout** (on by default) —
  lets the model apply character/paragraph formatting, existing styles, page
  layout and tables. It is given the document's available style names and is
  told to only format when you ask.
- **Apply Rewrite / Proofread as tracked changes** (Writer, on by default) —
  edits arrive as accept/reject tracked changes instead of silent replacements;
  the buttons read **Suggest (tracked)** / **Adopt (tracked)**. *Adopt all*
  becomes a single undo step.
- **Remember API key on this computer** — API keys are stored in the **OS
  keyring** (Secret Service / libsecret), not in the config file. Turn this off
  to keep the key in memory for the session only. The key field never shows the
  stored key (so it can't be copied out); use **Clear** to delete it.
- **Stream responses as they are generated** — tokens appear in the transcript
  while the model is still writing (Proofread stays buffered so its JSON is
  parsed once complete).

Use **Test connection** to send a one-word round trip and **Load models** to
populate the model list from the provider.

Settings are stored in `~/.config/hailper/config.json` (mode `0600`); API keys
are **not** written there — they go to the OS keyring. If no keyring backend is
available, a key is kept in memory for the current session only. Existing
plaintext keys are migrated into the keyring automatically, and the config from
the previous `~/.config/libreoffice-copilot/` location is migrated on first run.

Provider hints: DeepSeek `https://api.deepseek.com/v1`; Qwen
`https://dashscope-intl.aliyuncs.com/compatible-mode/v1`; Grok
`https://api.x.ai/v1`; Claude `https://api.anthropic.com/v1`; Gemini
`https://generativelanguage.googleapis.com/v1beta`; custom OpenAI-compatible
servers (LM Studio, vLLM, …).

## Troubleshooting

- **No HaiLPER deck in the sidebar.** Restart LibreOffice after installing,
  then open the sidebar. Check the **Extension** tab too (Tabbed UI).
- **Clicking a menu action does nothing.** Every dispatch is appended to
  `~/.config/hailper/hailper.log`; if a click produces no new line,
  the UI entry is not reaching the handler. If the sidebar is open on a
  different deck, the extension shows a note asking you to open the HaiLPER
  deck once.
- **"already been added" on reinstall.** Use `./install.sh` (it removes first).

## Development

```
src/
  META-INF/manifest.xml     component + data registration
  description.xml           extension metadata
  Addons.xcu                menu bar / toolbar / NotebookBar entries
  ProtocolHandler.xcu       maps io.github.rokusaburo.hailper:* to the handler
  Sidebar.xcu               HaiLPER deck and panel
  Factory.xcu               registers the sidebar panel factory
  Jobs.xcu                  always-on context-menu registration
  copilot_panel.xdl         empty container dialog for the panel
  copilot/
    command.py              UNO entry point / ProtocolHandler
    cp_sidebar.py           sidebar XUIElementFactory + panel
    cp_contextmenu.py       XContextMenuInterceptor + job
    cp_config.py            settings load/save
    cp_providers.py         HTTP clients for every provider
    cp_document.py          read/write Writer, Calc, Impress via UNO
    cp_prompts.py           prompt templates + choices per action
    cp_format.py            formatting / style / layout operations
    cp_dialog.py            panel controller (layout, choices, apply)
    cp_diff.py              compare window (Accept/Reject)
    cp_options.py           settings dialog
    cp_ui.py                small shared UNO helpers
build.sh / install.sh
tests/                    unit tests (no LibreOffice needed)
```

Run the tests with `python3 -m unittest discover -s tests -v`; CI runs them
and builds `dist/HaiLPER-<version>.oxt` on every push and tag.

### Notes learned while building this

1. **Child control models must be created through the dialog model's
   `XMultiServiceFactory`** (`dialog_model.createInstance("...Model")`).
   Creating them with the global service manager yields models without the
   `UnoControlDialogElement` geometry properties and `setModel()` fails with
   `UnknownPropertyException: PositionX`.
2. `StringItemList` is `[]string`; set it with
   `uno.invoke(model, "setPropertyValue", ("StringItemList", uno.Any("[]string", values)))`.
3. `com.sun.star.awt.AsyncCallback` exposes **`addCallback(callback, data)`**,
   which asynchronously calls `callback.notify(data)` on the main thread. The
   payload must be a UNO type (a `sequence<NamedValue>` is used here).
4. The sidebar panel is a `ContainerWindowProvider` window hosting a
   `UnoControlDialogModel`; the factory is registered in `Factory.xcu` with
   type `toolpanel` and the component declares the `com.sun.star.task.Job`
   service (the same trick LibreAssist uses). Do **not** add a
   `TopWindowListener` to the sidebar container window — it crashes.
5. UI entries use a **custom protocol** (`io.github.rokusaburo.hailper:*`)
   registered in `ProtocolHandler.xcu`. Parse `url.Complete` as a fallback,
   because UNO may leave `Protocol`/`Path` empty.
6. Wayland does not let applications position top-level windows, which is why
   the panel is a real sidebar deck rather than a floating window.
7. **Changing a control model's position after `createPeer` does not move the
   control.** Reflow must be done with the control's `XWindow.setPosSize` in
   pixels; measure the scale from a known control's pixel width vs its model
   width.
8. `Jobs.xcu` extension jobs fire on **`onDocumentOpened`/`onCreate`**, not on
   `onLoad`/`onNew` in this build. The `Environment` argument carries **`Model`**
   (not `Frame`), so resolve the controller from the model.
9. **Right-click menus** use `XContextMenuInterceptor`: get the menu from
   `event.ActionTriggerContainer`, create `ActionTrigger` / `ActionTriggerContainer`
   / `ActionTriggerSeparator` via its `XMultiServiceFactory`, nest via the
   trigger's `SubContainer`, and return `CONTINUE_MODIFIED`. Only add items when
   `event.Selection` has content.
10. `queryInterface` in pyuno needs a UNO `Type`
    (`uno.getTypeByName("...")`), not the interface class.

## License

Mozilla Public License 2.0 (MPL-2.0). See `LICENSE`.
