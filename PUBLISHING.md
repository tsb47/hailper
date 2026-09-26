# Publishing HaiLPER

Distribution target: the **official LibreOffice Extensions site**
(<https://extensions.libreoffice.org>). GitHub is used only to build and host the
release artifact and source.

## What the site needs
- The packaged extension. **Upload the CI-built GitHub release asset**, not a
  local rebuild: zips are not byte-reproducible, so `./build.sh` produces a
  different checksum each time. For 1.8.0 the release asset is in
  `submission/HaiLPER-1.8.0.oxt`
  (sha256 `0e1edec0787bfdccf4e0fac90ffddbb7f920193aee9fe0c58282d3a5e8a6b628`).
- A **title**, **summary** and **full description** — ready to paste in
  `docs/EXTENSION_LISTING.md`.
- A **logo** (`src/icons/robot-48.png`) and, optionally, **screenshots**
  (1470×960 or similar). Screenshots are optional; site screenshots
  (`docs/screenshots/`) are not required to publish.
- **License**: MPL-2.0 (`LICENSE`).
- **Publisher**: Rokusaburo (https://github.com/tsb47).
- Compatibility: LibreOffice **7.6+**, Linux; Writer/Calc/Impress/Draw. Declared
  in `description.xml`.

## Release steps
1. Bump `<version>` in `src/description.xml` and add a `CHANGELOG.md` entry.
2. `./build.sh` → `dist/HaiLPER-<version>.oxt`.
3. `./install.sh` and smoke-test in LibreOffice (panel opens, a chat reply, a
   tool call, formatted insert, undo).
4. Commit and tag: `git tag v<version> && git push origin v<version>`; CI builds
   the `.oxt` and attaches it to a GitHub Release. Download that asset into
   `submission/` for the site.

## Uploading to extensions.libreoffice.org
The site has **no upload API** — it is a web form tied to your TDF account, so
this step is done manually by the publisher.

1. Create a TDF single-sign-on account at <https://user.documentfoundation.org>
   (see the tutorial at
   <https://extensions.libreoffice.org/en/home/using-this-site-as-an-extension-maintainer/create-account>).
2. Sign in at <https://extensions.libreoffice.org/admin>.
   Make sure **English** is selected as the entry language (it is the fallback).
3. Click **Add Extension**, fill in the title, summary and description from
   `docs/EXTENSION_LISTING.md`, add the logo (and screenshots if you have them),
   pick the tags (**AI/LLM**, **Writer**, **Calc**, **Impress**, **Draw**,
   **Documents**) and set the homepage/source URLs. Save with **Create** first —
   files can only be added after the entry exists.
4. In the entry's **Releases** section click **Add Extension Release**, upload
   `submission/HaiLPER-<version>.oxt`, set the version and paste the release
   notes, then **Create**.
5. Set the license to MPL-2.0 and **publish**. A moderator reviews the request
   before it goes live.

Optional: add translations (only fields with the translation icon) after the
English entry is saved. Tags are translated by the site's moderators.

## Description.xml checklist
- `identifier` `io.github.rokusaburo.hailper`, `display-name` HaiLPER,
  `publisher` Rokusaburo, `icon` robot-48.png — all present.
- Consider adding localized `<name>`/`<description>` for extra `xml:lang`s.
- Consider `<update-information>` so the site/Office can surface new versions.

## Privacy statement (include in the listing)
- No telemetry. Requests go only to the provider you configure; document text is
  sent only when an action needs it. API keys are stored in the OS keyring
  (Secret Service), never in plain text, and are redacted from diagnostics.
