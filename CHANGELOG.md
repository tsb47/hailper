# Changelog

All notable changes to HaiLPER are documented here.
The format is based on [Keep a Changelog](https://keepachangelog.com/),
and this project adheres to [Semantic Versioning](https://semver.org/).

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
