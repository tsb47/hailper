# Publishing HaiLPER

Distribution target: the **official LibreOffice Extensions site**
(<https://extensions.libreoffice.org>). GitHub is used only to build and host the
release artifact and source.

## What the site needs
- The packaged extension: `dist/HaiLPER-<version>.oxt` (built by `./build.sh`).
- A **description** (summary + longer body) and **screenshots** (1470×960 or
  similar) — see `docs/screenshots/` (add real captures before submitting).
- **License**: MPL-2.0 (`LICENSE`).
- **Publisher**: Rokusaburo (https://github.com/tsb47).
- Compatibility: LibreOffice **7.6+**, Linux. Declared in `description.xml`.

## Release steps
1. Bump `<version>` in `src/description.xml` and add a `CHANGELOG.md` entry.
2. `./build.sh` → `dist/HaiLPER-<version>.oxt`.
3. `./install.sh` and smoke-test in LibreOffice (panel opens, a chat reply, a
   tool call, formatted insert, undo).
4. Commit and tag: `git tag v<version> && git push origin v<version>`; CI builds
   the `.oxt` and attaches it to a GitHub Release.
5. On extensions.libreoffice.org: sign in → *Add extension* → upload the `.oxt`,
   fill in the name/description/icon/screenshots, select categories (Writer,
   Calc, Impress/Draw → *AI*/*Editing*), set the license to MPL-2.0, and submit
   for review.

## Description.xml checklist
- `identifier` `io.github.rokusaburo.hailper`, `display-name` HaiLPER,
  `publisher` Rokusaburo, `icon` robot-48.png — all present.
- Consider adding localized `<name>`/`<description>` for extra `xml:lang`s.
- Consider `<update-information>` so the site/Office can surface new versions.

## Privacy statement (include in the listing)
- No telemetry. Requests go only to the provider you configure; document text is
  sent only when an action needs it. API keys are stored in the OS keyring
  (Secret Service), never in plain text, and are redacted from diagnostics.
