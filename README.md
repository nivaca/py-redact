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

## Running it

```bash
uv sync
uv run py-redact [file.pdf]
```

It needs Python 3.15, PyMuPDF (which does the redaction) and PySide6.

## Using it

- Drag on the page to draw a box. Drag a box to move it, or its edges and
  corners to resize it. Ctrl+click adds a box to the selection; Shift+drag
  draws a new box over others.
- The panel on the right gives the colour and the pages of the selected
  boxes. With no box selected, it gives those of the boxes you draw next.
- *View ▸ Show the result* (Ctrl+R) shows the page as it will be in the
  redacted copy.
- *File ▸ Also remove metadata, hidden text, attachments and scripts* cleans
  the rest of the document as well when the copy is saved.

The interface is in English and Spanish (*Settings ▸ Language*).

## Tests

```bash
uv run pytest
```

## Licence

GPL-3.0-or-later. By Nicolas Vaughan.
