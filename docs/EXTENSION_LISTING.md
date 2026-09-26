# LibreOffice Extensions site — listing copy

Ready-to-paste fields for the entry on <https://extensions.libreoffice.org>.
Upload artifact: `submission/HaiLPER-1.8.0.oxt`
(sha256 `0e1edec0787bfdccf4e0fac90ffddbb7f920193aee9fe0c58282d3a5e8a6b628`,
the exact GitHub `v1.8.0` release asset).

## Entry (main, English)

**Title**
```
HaiLPER
```

**Summary / short description** (one or two sentences, shown in lists)
```
An AI writing assistant docked in the LibreOffice sidebar. Chat, summarise,
rewrite, translate, proofread and continue your documents, with changes applied
as tracked changes. Works with local Ollama / LM Studio and 50+ cloud providers.
```

**Description** (full)
```
HaiLPER puts an AI assistant in the LibreOffice sidebar so you can work on the
document without leaving it.

WHAT IT DOES
- Chat about the open document, or ask it to summarise, explain, rewrite,
  translate, proofread or continue writing.
- Select any text first and every action focuses on exactly that selection;
  with nothing selected it works on the whole document.
- Insert the result as formatted text using real Writer styles, or as comments,
  tracked changes, a new document, or a side-by-side diff to accept/reject.
- A context-aware right-click menu adapts to what you select: summarise a link,
  draft a reply to an email address, explain a short phrase, rewrite, translate
  and more.
- Agent mode lets it work in steps, reading and editing the document with tools
  (read, search, insert, replace, format, tables, sections).
- Optional web search and page fetching, with untrusted content clearly marked
  before it reaches the model.
- Personas and custom actions, starter prompts, saved conversations, and a
  token/cost usage line.

PROVIDERS
- Local and private: Ollama, LM Studio, llama.cpp and any OpenAI-compatible
  server.
- Cloud: OpenAI, Anthropic Claude, Google Gemini, DeepSeek, Groq, Mistral, xAI,
  OpenRouter, Azure OpenAI and many more (50+ presets). Models are fetched
  automatically where supported.

PRIVACY
- No telemetry, ever. Requests go only to the provider you configure, and
  document text is sent only when an action needs it.
- API keys are stored in your operating system's keyring (Secret Service), never
  in a plain-text file, and are redacted from diagnostics.

A short guided walkthrough appears the first time you open the panel.

Requires LibreOffice 7.6 or newer on Linux. Works in Writer, Calc, Impress and
Draw.
```

**Homepage**
```
https://github.com/tsb47/hailper
```

**Source repository**
```
https://github.com/tsb47/hailper
```

**Issue tracker / support**
```
https://github.com/tsb47/hailper/issues
```

**License**
```
MPL-2.0 (Mozilla Public License 2.0)
```

**Logo**
```
src/icons/robot-48.png
```
(the site scales it; replace with a 256×256 version if you have one)

**Tags** (pick these on the site)
```
AI/LLM, Writer, Calc, Impress, Draw, Documents, Extensions
```

## Release (add after saving the entry)

**Version**
```
1.8.0
```

**File**
```
submission/HaiLPER-1.8.0.oxt
```

**Release notes**
```
Added
- First-run guided walkthrough when the sidebar is first opened, replayable
  from the panel menu and from Settings.
- Settings gear button in the panel header next to the Persona and Action
  dropdowns.

Fixed
- The right-click HaiLPER submenu now reliably appears and always reflects the
  current selection.
- The right-click interceptor is also registered when the sidebar opens.

Changed
- Removed the duplicate Settings entry from the right-click document menu.
- Context menu shows the most relevant action for URLs and email addresses.
```

**Compatibility**
```
LibreOffice 7.6 and newer. Platform: Linux. Applications: Writer, Calc,
Impress, Draw.
```

## Optional translations
Add translations after the English entry is saved. Only fields marked with the
translation icon should be translated. The site translates tags itself.
