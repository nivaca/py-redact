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

### Fedora

The RPM is signed with the author's key, `RPM-GPG-KEY-py-redact`, which is
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

- Drag on the page to draw a box. Drag a box to move it, or its edges and
  corners to resize it. Ctrl+click adds a box to the selection; Shift+drag
  draws a new box over others.
- *Select text* (T) marks text instead: drag over it, and a box is made over
  each of its lines. *Draw boxes* (B) goes back to drawing.
- Right-click a box for its pages (its own page only, all, odd, even, from
  it to the end, or a list such as `2-10, 15, LAST`), its colour, and to make
  its colour the one of new boxes. Right-click the page for the colour of new
  boxes.
- A new box is always on its own page only, whatever the box before it was
  repeated on, and has the colour of new boxes.
- *Settings ▸ Settings…* keeps, in the configuration file: the colour of new
  boxes; what happens to images under a box (blank that part, remove the
  whole image, or leave them) and to drawings (remove those wholly under a
  box, those it touches, or none); and whether to also remove metadata,
  hidden text, attachments and scripts. Text under a box is always removed.
- *View ▸ Show the result* (Ctrl+R) shows the page as it will be in the
  redacted copy.
- Closing the window, or opening another file, with boxes not yet saved to a
  redacted copy asks first.

The interface is in English and Spanish (*Settings ▸ Language*).

## Tests

```bash
uv run pytest
```

## Licence

GPL-3.0-or-later. By Nicolas Vaughan.
