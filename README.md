# py-redact

py-redact redacts PDF documents. You draw boxes on the pages, and in the
redacted copy whatever lies under each box is removed for good: the text, the
parts of images under it, the drawings it covers, and any annotation or form
field that touches it. The box is then filled with a colour of your choice,
black, white, grey or any other.

A box belongs to the page where it was drawn, but it can also go on other
pages: all of them, the odd or the even ones, or a list such as `2-10, 15,
LAST`. This is meant for what repeats in the same place on many pages, like a
header, a footer or a stamp. On a page of a different size the box keeps its
position, cut to the page.

The original file is not changed: the redaction is saved as a copy
(`NAME-redacted.pdf` by default). Protected files keep their protection.

## Installation

There are three ways: the AppImage (nothing to install), the RPM for Fedora,
or from the source. All of them are in the
[releases](https://github.com/nivaca/py-redact/releases).

### AppImage (any Linux)

Download `py-redact-VERSION-x86_64.AppImage`, make it executable, and run it.
It holds its own Python, Qt and PyMuPDF, and runs on Linux with glibc 2.34 or
later (Ubuntu 22.04, Debian 12, Fedora 35 and later).

```bash
chmod +x py-redact-*-x86_64.AppImage
./py-redact-*-x86_64.AppImage [file.pdf]
```

### Fedora (Copr)

```bash
sudo dnf copr enable nivaca/py-redact
sudo dnf install py-redact
```

Updates then come with `sudo dnf upgrade`. The packages are built and signed
by [Copr](https://copr.fedorainfracloud.org/coprs/nivaca/py-redact/).

Each release also has the RPM itself. It is signed with the author's key, `RPM-GPG-KEY-py-redact`, which is
attached to each release and is also in the repository
([`packaging/RPM-GPG-KEY-py-redact`](packaging/RPM-GPG-KEY-py-redact)). Its
fingerprint is `8187 0643 CA22 1AF9 0C30 554E BE68 32CD 3599 4948`:

```bash
sudo rpm --import RPM-GPG-KEY-py-redact
sudo dnf install ./py-redact-*.noarch.rpm
```

It installs `py-redact` and a menu entry (also offered for opening PDF files),
using Fedora's own Python, PyMuPDF and PySide6. It needs Fedora 45 or later.

### From the source

```bash
uv sync
uv run py-redact [file.pdf]
```

It needs Python 3.15, PyMuPDF (which does the redaction) and PySide6.

## Using it

- The window starts with *Redact* (T), which works as Xodo's redaction tool:
  dragging over text selects it, and a box is made over each of its lines;
  dragging anywhere else draws a box; Ctrl+drag always draws a box, even
  over text. Double-click a word to mark only that word, or an image to mark
  all of it. *Draw boxes* (B) always draws boxes, and *Hand* (H) moves the
  page in the window. Drag a box to move it, or its edges and corners to
  resize it.
- Until they are applied, boxes are see-through with a red outline (blue
  when selected; dashed when they go on other pages).
- Double-click a box, or right-click it and choose *Properties…*, for what it
  will look like once redacted: its fill (any colour, or *No colour*, which
  removes what is under it and paints nothing), a text written over it
  (`REDACTED`, `[name]`) with its colour, size and alignment, repeated all
  along the box if wanted; a note, shown when the mouse is over the box; and
  *Locked*, so that it can't be moved, resized or deleted. Holding the mouse
  over a box shows it as it will be once applied.
- Right-click a box ▸ *Redaction code* writes over it why it was redacted:
  the codes of the U.S. FOIA or Privacy Act exemptions, or your own, several
  on a box if needed (`(b)(6), (b)(7)(C)`). *Edit the codes…* makes and
  changes your own code sets, and imports and exports them as XML files. *Save as default
  for new boxes* makes new boxes look the same.
- *Tools ▸ Find and redact…* (Ctrl+F) looks for a word or phrase (matching
  case, as whole words, or as a regular expression), for several words or
  phrases at once (typed one on each line, or read from a text file), or for
  patterns: e-mail addresses, phone numbers, credit card numbers, dates,
  identity numbers and bank accounts (IBAN), in their U.S. or Spanish forms.
  It looks on all pages, this page, from this page to the end, or a list of
  pages, and lists every place found with the words around it; clicking one
  shows it. *Mark them all* or *Mark the ticked ones* puts boxes over them,
  whole or leaving some characters visible (the last four digits of a card
  number, for instance). A phrase is found across line breaks.
- Right-click a box for its pages (its own page only, all, odd, even, from
  it to the end, up to it, or a list such as `2-10, 15, LAST`), its colour,
  to make its colour the one of new boxes, and to redact the text under it
  wherever else it is. Right-click a word to redact it on this page or on
  every page; right-click elsewhere on the page for the tools, the colour of
  new boxes and the boxes of the page.
- A new box is always on its own page only, whatever the box before it was
  repeated on, and has the colour of new boxes.
- *Settings ▸ Settings…* keeps, in the configuration file: the colour of new
  boxes; what happens to images under a box (blank that part, remove the
  whole image, or leave them) and to drawings (remove those wholly under a
  box, those it touches, or none); and whether to also remove metadata,
  hidden text, attachments and scripts. Text under a box is always removed.
- *File ▸ Save as* chooses the kind of redacted copy: a plain PDF, PDF/A-1b,
  PDF/A-2b, PDF/A-3b (for archiving) or PDF/X-4 (for printing). PDF/A and
  PDF/X are made by the author's
  [py-pdfconform](https://github.com/nivaca/py-pdfconform), which must be
  installed and on the PATH; without it, those choices are greyed out. They
  can't be password-protected, so the copy of a protected document comes out
  without its password.
- *View ▸ Show the result* (Ctrl+R) shows the page as it will be in the
  redacted copy.
- *Apply all redactions…*, at the top of the right-click menu, saves the
  redacted copy. The copy is then checked: if any word that was under a box
  can still be read there, a warning says where.
- *File ▸ Remove hidden information…* shows what the document holds besides
  its pages (metadata, attached files, bookmarks, comments, form fields,
  hidden text, links and scripts, thumbnails, unused objects) and how much of
  each, and saves a copy without what you tick. *File ▸ Sanitize the
  document…* removes all of it at once.
- Closing the window, or opening another file, with boxes not yet saved to a
  redacted copy asks first.

The interface is in English and Spanish (*Settings ▸ Language*).

## Tests

```bash
uv run pytest
```

## Licence

GPL-3.0-or-later. By Nicolas Vaughan.
