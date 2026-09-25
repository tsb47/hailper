# Changelog

All notable changes to HaiLPER are documented here.
The format is based on [Keep a Changelog](https://keepachangelog.com/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [1.7.1] - 2026-09-23

### Changed

- **Context-aware right-click menu.** It now adapts to the selection: a URL
  offers **Summarize linked page**, an email address **Draft a reply**, a short
  phrase **Explain / define**, plus **Look up on the web** and quick rewrite
  presets (**Shorten**, **Make formal**, **Simplify**) alongside **Rewrite as ▸**.
  Calc shows formula/range actions; Impress shows slide/notes actions.
- The document (no-selection) menu adds **Show context…** and **Settings…**.
- **Your custom actions** now appear in the right-click submenu.

## [1.7.0] - 2026-09-23

### Added

- **Context tools** for the model: `search_document`, `read_context`,
  `get_section` and `get_metadata`; `read_document` now returns the section
  around the cursor by default (add `"full": true` for the whole document).
- **Rolling conversation summary**: older turns are compressed by one background
  model call and recalled on later requests, and saved with the conversation.
- **Show context…** in the ⋯ menu, to see exactly what is sent to the model.

### Changed

- **Summarize** sends the whole (budget-trimmed) document; other actions use the
  selection/section context.

## [1.6.0] - 2026-09-23

### Added

- **Context awareness**: each request now carries a structured bundle — document
  metadata (kind/title/words/read-only/tracked-changes), the **current section
  heading**, the selection, the **paragraphs around the cursor**, the outline,
  and the **top-K most relevant paragraphs** (BM25-ranked against your message).
- **Token budgeting**: context and chat history are packed to ~55% of the
  model's context window (`context.budget_ratio`), older turns are trimmed, and
  for large documents the message body falls back to the **current section**
  instead of dumping the whole file. New settings under `context`.

## [1.5.0] - 2026-09-23

### Changed

- **Web tools run off the UI thread** so the panel stays responsive while the
  model searches; the results are threaded back into the tool loop (with a
  "Searching the web…" status). Stop still cancels.

### Added

- **Integration tests in CI**: a job installs headless LibreOffice and
  `python3-uno`, starts a UNO socket, and runs `tests/test_integration.py`
  (formatted insert + the document tools) against a real LibreOffice.

## [1.4.4] - 2026-09-23

### Changed

- Providers now retry transient failures (HTTP 429/5xx and network errors) up
  to 3 times with exponential backoff, for both normal and streaming requests.

## [1.4.3] - 2026-09-23

### Security

- **SSRF protection** for web tools: `fetch_url`/`web_search` only fetch public
  http(s) URLs; loopback, private, link-local, reserved and credential-bearing
  URLs are refused, and redirects to them are blocked.
- **Prompt-injection boundary**: tool and web results are wrapped as
  `<<<UNTRUSTED … >>>` data, and the model is told never to follow instructions
  found in document or web content.
- **Copy diagnostics** (⋯ menu) produces a support report with API keys/tokens
  redacted. No telemetry is ever sent.

## [1.4.2] - 2026-09-23

### Fixed

- **Web search returns real, current results.** The old DuckDuckGo HTML
  endpoint is bot-blocked (HTTP 202), so searches fell back to generic
  Wikipedia pages. It now uses **DuckDuckGo Lite**, with the HTML endpoint and
  Wikipedia as fallbacks.

### Changed

- When web tools are available the model is told it has **live internet
  access** and today's date, and is instructed to search rather than claim it
  cannot. The chat tool loop allows an extra step so it can search, open a
  result and then answer.

## [1.4.1] - 2026-09-22

### Fixed

- `cp_tools` no longer imports the UNO document layer at module load, so the
  unit tests (and any non-LibreOffice import) work without UNO installed.

## [1.4.0] - 2026-09-22

### Added

- **Native tool calling.** HaiLPER now sends real function/tool definitions to
  the model (OpenAI-compatible incl. DeepSeek, Azure, Ollama, Anthropic and
  Gemini) so it can call tools instead of emitting JSON in prose:
  `read_document`, `get_outline`, `replace_text`, `insert_text`, `format_text`
  and `insert_table`. Tool calls are executed on the document and their results
  fed back, looping (up to 3 steps in normal use, `max_steps` in Agent mode).
  Permissions gate the tools; providers without tool support fall back to the
  prompted-JSON directives.
- **Web research tools**: `web_search` and `fetch_url` let the model look things
  up online. Works with no API key (DuckDuckGo with a Wikipedia fallback;
  optional SearXNG via `web.base_url`), gated by a new *Allow HaiLPER to search
  the web* setting.

## [1.3.4] - 2026-09-22

### Changed

- **Scope is automatic**: the current selection when there is one, otherwise the
  whole document. The Scope control and the "Using …" line were removed.
- **Starter cards** hide as soon as you start typing and are more compact.
- Interface **font size reduced by 2 pt** across the panel for a denser layout.

## [1.3.3] - 2026-09-22

### Changed

- **Compact panel**: the **Persona** and **Action** dropdowns now sit side by
  side (Persona first, as the main selector); the separate labels and the
  "Conversation:" header are gone. The token / context line is small, light grey
  and pinned to the very bottom. The **⋯** button now opens a small menu (model
  picker, starter prompts, history, new chat, agent mode) instead of a popup
  menu that could fail to appear.

### Fixed

- **Insert / Insert formatted**: the first block no longer glues onto existing
  text, and standalone `**bold**` subheading lines no longer merge into the
  following paragraph. Plain Insert now inserts clean text with Markdown
  markers removed.

## [1.3.2] - 2026-09-22

### Added

- **Undo / Retry button** in the status area: after inserting, adopting or
  formatting it offers **Undo** (one click reverts the change; formatted inserts
  undo as a single step); after an error it offers **Retry**.

## [1.3.1] - 2026-09-22

### Changed

- Errors are shown with a warning marker and an actionable hint (auth → open
  Settings, timeout → raise the timeout).

## [1.3.0] - 2026-09-22

### Added

- **Markdown rendering** in the transcript (headings, bullets, ordered lists,
  aligned tables, code fences, quotes) and **Insert formatted**, which applies
  the same Markdown to the document as real Writer formatting (Heading styles,
  lists, bold/italic, monospace, tables). Insert formatted is the default
  primary action for Chat and Summarize.
- **Contextual UX**: labelled Action/Persona dropdowns, per-action instruction
  placeholders, an explicit **Scope (Selection/Document)** control with a
  "Using: …" indicator, and clickable **starter chips** under the transcript on
  the empty state.
- The header switches (model, starters, history, agent) are collapsed into a
  single **⋯ menu** with New chat.

### Fixed

- Tool-directive JSON (and stray `{…}` fragments) no longer leak into the
  transcript.
- Clearer usage line: `last N tok (in A / out B) · ctx · cost — session N tok`,
  with a provider · model caption.

## [1.2.1] - 2026-09-22

### Fixed

- Starting a new chat now begins a fresh saved conversation instead of
  appending to the previous one.
- Made the starter-prompt menu's parent window more robust across UI backends.

## [1.2.0] - 2026-09-22

### Added

- **Action dropdown** replacing the icon row: one selector for all built-in and
  custom actions.
- **Personas** (General, Editor, Reviewer, Researcher) that set the system
  prompt, model, temperature and which actions are available; switchable from
  the panel.
- **Custom actions** defined in `~/.config/hailper/actions.json` and shown in
  the dropdown and right-click menu.
- **Token / cost meter**: per-request tokens, estimated cost (built-in price
  table with overrides) and context-window usage, for cloud and local models.
- **Document outline awareness**: the model receives the heading outline, and
  an action/format target of `section` can be used.
- **Agent mode**: an explicit, multi-step loop where the model uses the
  edit/format/document tools until the task is done (toggle in the panel).
- **Starter prompts** per persona and **conversation persistence** under
  `~/.config/hailper/conversations/` with a History picker.
- Panel header buttons: model picker, starters, history and agent toggle.

### Notes

- Local models show token counts and `local · free`; unknown cloud pricing
  shows `$0.00` rather than guessing.

## [1.1.1] - 2026-09-21

### Security

- **API keys are stored in the OS keyring** (Secret Service, via libsecret)
  instead of plaintext in `config.json`. Any existing plaintext key is migrated
  automatically on first load and removed from the file.
- The Settings dialog **never loads the real key into the input field**, so it
  can no longer be copied out of the masked box; a **Clear** button deletes the
  stored key. The key label shows where the key lives (`keyring` / `file`).
- If no OS keyring is available, keys are kept **in memory for the session only**
  (never written to disk) unless you leave them unremembered.

## [1.1.0] - 2026-09-21

### Added

- **Formatting, styling and layout (Writer).** With *Allow HaiLPER to change
  formatting, styles and layout* enabled, the model can apply character
  formatting (bold, italic, underline, strikeout, font, size, colour,
  highlight), paragraph formatting (paragraph/character style, alignment,
  space before/after, indents, line spacing, keep-together), page layout
  (page style, margins, orientation) and insert tables, via a
  `{"format": [...]}` directive. Document-wide and page-layout changes are
  confirmed before applying, and each batch is a single undo step. The model
  is given the document's available style names so it only uses real styles.

## [1.0.2] - 2026-09-21

### Changed

- The conversation transcript now expands to fill the available height so the
  action buttons stay pinned on screen (with a safety allowance for the deck
  chrome).
- The model picker is hidden by default and shown by a small gear button at the
  top-right of the conversation header, leaving more room for the transcript.

## [1.0.1] - 2026-09-21

### Added

- **Model switcher in the sidebar**: the model field is now a dropdown so you
  can change the active model without opening Settings (the choice is saved).

### Fixed

- **Compact UI.** Reduced the sidebar panel and Settings dialog padding, row
  spacing, control heights and font size so action buttons no longer fall off
  the bottom of the panel and the Settings window fits on screen.
- Log file path now follows the config directory
  (`~/.config/hailper/hailper.log`).

## [1.0.0] - 2026-09-21

### Added

- Docked **HaiLPER** sidebar deck (not a pop-up) with a scrolling conversation
  transcript and background generation.
- Actions: **Chat, Summarize, Rewrite / Improve, Continue Writing, Translate,
  Proofread / Review, Explain, Ask About Selection**.
- Inline proofread review (Adopt / Reject / Previous / Next / Adopt all / Finish).
- Draft review for Rewrite / Translate / Continue (Adopt / Reject / Refine / Copy).
- Right-click **HaiLPER** submenu in Writer, Calc and Impress, with document-level
  actions when there is no selection.
- **Track changes** (Writer): Rewrite and Proofread can be applied as tracked
  changes so reviewers can accept or reject them. Controlled by
  *Apply Rewrite / Proofread as tracked changes* in Settings (on by default);
  the Rewrite button shows **Suggest (tracked)** and the draft review shows
  **Adopt (tracked)**. *Adopt all* is grouped into a single undo step.
- **Streaming responses** for OpenAI-compatible, Ollama, Anthropic and Gemini
  providers (toggle in Settings; proofread stays buffered so the JSON is parsed
  once complete).
- 51 AI provider presets: local (Ollama, LM Studio, llama.cpp, Atomic Chat,
  LLM Gateway) and cloud (OpenAI, Anthropic Claude, Google Gemini, Azure OpenAI,
  DeepSeek, Groq, Mistral, Cerebras, Together, Fireworks, Perplexity, Cohere,
  OpenRouter, xAI, Qwen, Moonshot, MiniMax, Z.AI, NVIDIA, Hugging Face, and more).
- Settings dialog with per-provider API key, model and base URL, plus temperature,
  max tokens, timeout and system prompt; automatic model-list fetching, **Test
  connection** and **Load models** buttons, and a **Remember API key** option
  (off = session-only, never written to disk).
- Permission gates for direct document editing and on-request document access.

### Notes

- Linux only in this release.
- Requires LibreOffice 7.6 or newer.
