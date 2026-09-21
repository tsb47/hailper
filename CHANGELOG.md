# Changelog

All notable changes to HaiLPER are documented here.
The format is based on [Keep a Changelog](https://keepachangelog.com/),
and this project adheres to [Semantic Versioning](https://semver.org/).

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
