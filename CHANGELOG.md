# Changelog

All notable changes to py-redact. The releases, with their wheels,
AppImages and RPMs, are on
[Codeberg](https://codeberg.org/nivaca/py-redact/releases) and
[GitHub](https://github.com/nivaca/py-redact/releases).

## Unreleased

- `tools/zenodo.py`: the description of the deposit is now the whole
  README of the tag, in HTML. The draft also gets the contributor (the
  project leader), the languages, the copyright, the repository on GitHub,
  the programming language and the development status, these last through
  Zenodo's records API (its deposit API doesn't take them). The token can
  be kept in the desktop keyring (`secret-tool store --label="Zenodo
  token" service zenodo`) instead of `$ZENODO_TOKEN`; `tools/zenodo.py
  check-token` says whether there is one.

- `tools/zenodo.py` prepares the deposit of a release for Zenodo. `collect`
  puts in `dist/zenodo/` the tree of the tag as
  `py-redact-VERSION-source.tar.gz`, with its signature, a signed
  `SHA256SUMS` of the deposit and the public key, and checks every signature
  with only that key (`--packages` adds the files of the release). `upload`
  sends it to Zenodo as a draft, a new version of the deposit if there is
  one already, and never publishes it. `tools/release.py` now collects the
  deposit after the tag and uploads it as a draft, unless `--no-zenodo`. The
  metadata are in `.zenodo.json`.
- `tools/zenodo.py`: the description of the deposit leaves out the line
  that points to the README in other languages and the Screenshots section,
  whose images Zenodo does not show.

## 1.0.11 — 2026-11-22

- **Every release signed**: besides the RPM, each file published (the
  wheel, the source, the ZIP, the AppImage) comes with its signature
  (`.asc`), with `SHA256SUMS` and its signature, and with the public key;
  the tag of the version is signed too. Each signature is checked with the
  published key before anything is published. The README says how to check
  a download.

## 1.0.10 — 2026-11-21

- `docs/SOFTWARE.md` and `docs/SOFTWARE_es.md`: the free and open-source
  software py-redact uses, to run, to save PDF/A and PDF/X, to build the
  packages and to develop it, with their licences.

## 1.0.9 — 2026-11-19

- On macOS the application is called py-redact in the menu bar (its name
  is set in the bundle information).
- The AppImage leaves out the parts of Qt and Python the program does not
  use (88 to 73 MB), with a check that no Qt library left needs one left
  out.
- Copr builds for Fedora 44 too.
- CI opens the program on the screen of the three systems
  (`.github/smoke.py`) and keeps the pictures.

## 1.0.8 — 2026-11-19

Versions 1.0.2 to 1.0.7 were not released on their own; their changes
are in this one.

- **Saving no longer stops the window.** The copy is written, checked and
  sanitized in a process of its own (`worker.py`, `gui/background.py`),
  with a dialog after 0.4 s and a Cancel button; the copy is written as a
  `.part` file and renamed when complete. On 300 pages with 5,100 boxes
  the longest stop of the window went from 5.2 s to 0.1 s.
- **Faster checks after saving**: each page is read once for all its
  boxes (140 s to 2 s on 300 pages with 5,100 boxes; the bookmark check
  85 s to 1 s, and skipped when the copy has no bookmarks).
- Searching is ten times faster (15 s to 1.5 s on 300 pages), and the
  window keeps the text of each page until another document is opened.
- The installers run on Windows, macOS and Linux in GitHub Actions
  (`.github/workflows/installers.yml`), with the tests against the
  program installed. This found two faults, now fixed: `install.sh`
  stopped halfway on macOS, and on Windows saving over the original
  failed.
- The AppImage installs PyMuPDF and PySide6 in the versions of `uv.lock`
  (PyMuPDF 1.28.2, PySide6 6.12.0).
- `gui/window.py` is split into `gui/menus.py`, `gui/saving.py`,
  `gui/thumbnails.py` and `gui/common.py`, and the words of a page are
  read in one way only.

## 1.0.1 — 2026-11-19

- A new icon, in colour: a blue page with two lines blacked out and a red
  marker, with a plainer drawing for 32 pixels and less;
  `tools/icons.py` draws every PNG from the two SVGs.

## 1.0.0 — 2026-11-19

- **Pages are rendered in processes of their own**, as MuPDF keeps
  Python's lock while it renders: clicking a thumbnail answers at once,
  showing the thumbnail made larger until the page arrives. Requests for
  pages left behind are dropped, and the thumbnails have their own
  process.
- **Installers for Linux, macOS and Windows** (`install/`): py-redact from
  its source, in an environment of its own, with Python 3.14 or later and
  an entry in the menu of the system. On Windows pdf2iso is run through
  Python.
- The RPM build replaces the older RPMs in `dist/` with the new one.

## 0.4.9 — 2026-11-19

- A quicker window: a page is rendered once and kept, so a change of the
  boxes does not render it again; the next and previous pages are
  rendered while the window is idle, and only the thumbnails whose boxes
  changed are drawn again.

## 0.4.8 — 2026-11-18

- The window answers with large documents: thousands of boxes are
  selected in the list at once (one row at a time took minutes),
  thumbnails are drawn one at a time, those in view first, and Find and
  redact reads each page once for all its terms, shows its progress and
  can be stopped.
- The RPM build copies the RPM to `dist/`.

## 0.4.7 — 2026-11-18

- File > Metadata: every field of the metadata (document information,
  other fields, language, XMP), each with a button to remove it. The
  redacted copy gets it when saved, even with no boxes.

## 0.4.6 — 2026-11-17

- PDF/A and PDF/X are made by pdf2iso, the new name of py-pdfconform; the
  old name is still looked for.
- The contact email is now nicolasvaughan@proton.me.

## 0.4.5 — 2026-11-17

- The bookmarks of the redacted copy are checked after saving: those that
  name what was under the boxes, or point to no page, can be removed, or
  all of them.
- Page labels are a kind of hidden information that can be removed.

## 0.4.4 — 2026-11-17

- The documentation, the RPM changelog and the comments of the code no
  longer name other redaction programs. The program is the same.

## 0.4.3 — 2026-11-16

- Save always writes a plain PDF. File > Save as writes a plain PDF,
  PDF/A or PDF/X this once, as soon as it is chosen, and remembers
  nothing: the kind of PDF is no longer a setting.
- Python 3.14 or later is needed (it was 3.15); the AppImage carries
  Python 3.14.

## 0.4.2 — 2026-11-16

- File > Save as saves at once in the kind of PDF chosen (PDF, PDF/A,
  PDF/X); before, it only chose it, and Save had to be chosen after.

## 0.4.1 — 2026-11-16

- Settings > py-pdfconform shows where the script is and which one will be
  used. It is also looked for in `~/bin` and `~/.local/bin` and with the
  `.py` extension: started from the desktop menu, it was often not on the
  PATH, and PDF/A and PDF/X were always greyed out.
- The README, in English and Spanish, is complete: what is needed,
  installing, updating and uninstalling, what is where, and the history of
  the versions.

## 0.4.0 — 2026-11-16

- **Find and redact several words or phrases** at once, typed or read from
  a file, and patterns (e-mail, phone, card, date, identity, IBAN, in U.S.
  or Spanish forms), leaving some characters visible if wanted.
- **Redaction codes**: the U.S. FOIA and Privacy Act sets, and the user's
  own, with an editor that imports and exports them.
- File > Remove hidden information, kind by kind.
- Boxes are shown under the mouse as they will be; the outline colour and
  opacity of boxes not yet applied can be set.
- Documentation in English and Spanish (README, `docs/DESCRIPTION.md`,
  `docs/DESCRIPCIÓN_es.md`) with screenshots made by
  `tools/screenshots.py`. Settings has the shortcut Ctrl+,.

## 0.3.0 — 2026-11-16

- **One tool for text and areas** (Ctrl+drag for a box); double-click a
  word or an image to redact it; a hand tool.
- Box properties: no fill, a text over the box with its colour, size,
  alignment and repetition, a note, locked, and save as default.
  See-through marks with a red outline; Apply all redactions in the
  right-click menu.
- The copy is checked after saving; File > Sanitize the document.
- Save the redacted copy as PDF/A (1b, 2b, 3b) or PDF/X-4, made by
  py-pdfconform when it is on the PATH.
- Icons in the toolbar, from the desktop's theme or the program's own,
  with tooltips that give the shortcut.

## 0.2.0 — 2026-11-16

- **Find and redact**: a text or a regular expression, on some or all
  pages, across line breaks.
- The text tool is the one on startup and still moves boxes; right-click
  menus offer what fits where they are clicked (a word, a box with text
  under it, the page); a Tools menu.
- The Copr project is now nivaca/py-redact.

## 0.1.0 — 2026-11-16

- First version: a window for redacting PDF documents. Whatever lies under
  each box is removed from the copy, and the place is filled with a colour
  of choice; boxes can repeat on other pages.
- Selecting text makes boxes over its lines; a right-click menu of a box
  (pages, colour, make its colour the default); a settings dialog kept in
  `config.toml` (colour of new boxes, images, drawings, cleaning).
- The AppImage, the signed RPM, a ZIP of the source, and
  `tools/release.py` to publish them on GitHub and Codeberg;
  `py-redact --version`.
