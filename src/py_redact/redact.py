"""Boxes to redact, and their redaction.

A box is a rectangle on a page, in points, measured from the top left corner
of the page as it is shown (that is, with the page's rotation applied). It
belongs to the page where it was drawn, and may be repeated on other pages:
``repeat`` is then a list of pages (see pagesel.py: ``all``, ``odd``,
``2-10, 15``...). A repeated box keeps its position, cut to the size of each
page.

Redacting a box removes, for good, everything under it: text, the parts of
images under it, and the drawings it covers; annotations and form fields that
touch it are removed too. The box is then filled with its colour.
"""

from __future__ import annotations

import dataclasses
import os
import tempfile
from pathlib import Path

import pymupdf

from .interface import tr
from .pagesel import parse_pages

Rect = tuple[float, float, float, float]  # x0, y0, x1, y1


@dataclasses.dataclass(frozen=True)
class Box:
    page: int  # 0-based: the page where it was drawn
    rect: Rect
    color: str = "#000000"
    repeat: str = ""  # '' for its own page only; else the pages it goes on

    def pages(self, count: int) -> list[int]:
        """The pages (0-based) it covers, in a document of COUNT pages."""
        if not self.repeat.strip():
            return [self.page] if self.page < count else []
        return parse_pages(self.repeat, count)

    def on(self, page: int, count: int) -> bool:
        return page in self.pages(count)


class RedactError(Exception):
    """A document that cannot be redacted or written."""


class PasswordError(RedactError):
    """A document whose password is missing or wrong."""


def normalized(rect: Rect) -> Rect:
    x0, y0, x1, y1 = rect
    return min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)


def rgb(color: str) -> tuple[float, float, float]:
    """'#rrggbb' as PyMuPDF's (r, g, b), each from 0 to 1."""
    c = color.lstrip("#")
    if len(c) != 6:
        raise ValueError(color)
    return tuple(int(c[i:i + 2], 16) / 255 for i in (0, 2, 4))


def boxes_on(boxes: list[Box], page: int, count: int) -> list[Box]:
    return [b for b in boxes if b.on(page, count)]


def page_rect(page: pymupdf.Page, rect: Rect) -> pymupdf.Rect | None:
    """RECT (as the page is shown) in the page's own coordinates, cut to the
    page; None if nothing of it is on the page."""
    shown = pymupdf.Rect(normalized(rect)) & page.rect
    if shown.is_empty:
        return None
    return (shown * page.derotation_matrix).normalize()


def redact_page(page: pymupdf.Page, boxes: list[Box]) -> int:
    """Redact BOXES (those on this page) on PAGE. Returns how many were applied."""
    areas = []
    for box in boxes:
        area = page_rect(page, box.rect)
        if area is None:
            continue
        areas.append(area)
        page.add_redact_annot(area, fill=rgb(box.color), cross_out=False)
    if not areas:
        return 0
    # (annotations and form fields over the boxes would keep what they say)
    for annot in list(page.annots() or []):
        if annot.type[0] != pymupdf.PDF_ANNOT_REDACT and any(annot.rect.intersects(a) for a in areas):
            page.delete_annot(annot)
    for widget in list(page.widgets() or []):
        if any(widget.rect.intersects(a) for a in areas):
            page.delete_widget(widget)
    page.apply_redactions(images=pymupdf.PDF_REDACT_IMAGE_PIXELS,
                          graphics=pymupdf.PDF_REDACT_LINE_ART_REMOVE_IF_COVERED,
                          text=pymupdf.PDF_REDACT_TEXT_REMOVE)
    return len(areas)


def redact(doc: pymupdf.Document, boxes: list[Box], clean: bool = False) -> int:
    """Redact BOXES in DOC (in memory). With CLEAN, also remove the metadata,
    hidden text, attached files, scripts and links of the document. Returns how
    many boxes were applied, counting each page a box is repeated on."""
    count = doc.page_count
    done = 0
    for number in range(count):
        here = boxes_on(boxes, number, count)
        if here:
            done += redact_page(doc[number], here)
    if clean:
        doc.scrub()
        doc.set_metadata({})
    return done


def open_pdf(path: Path, password: str = "") -> pymupdf.Document:
    """The PDF at PATH, opened with PASSWORD if it needs one (raises RedactError)."""
    try:
        doc = pymupdf.open(path)
    except (pymupdf.FileNotFoundError, pymupdf.FileDataError, RuntimeError) as e:
        raise RedactError(tr("{path} cannot be read as a PDF: {error}", path=path, error=e)) from None
    if not doc.is_pdf:
        doc.close()
        raise RedactError(tr("{path} is not a PDF", path=path))
    if doc.needs_pass and not doc.authenticate(password):
        doc.close()
        raise PasswordError(tr("{path} is protected by a password", path=path))
    return doc


def write_redacted(source: Path, boxes: list[Box], target: Path, password: str = "",
                   clean: bool = False) -> int:
    """SOURCE with BOXES redacted, saved as TARGET (safely: TARGET may be
    SOURCE). Returns how many boxes were applied (see redact)."""
    doc = open_pdf(source, password)
    fd, tmp = tempfile.mkstemp(suffix=".pdf", dir=target.parent)
    os.close(fd)
    try:
        done = redact(doc, boxes, clean)
        # (garbage=4 drops the objects nothing uses any more: the fonts and images
        # that only the redacted parts used, which would otherwise stay in the file)
        doc.save(tmp, garbage=4, deflate=True, clean=True,
                 encryption=pymupdf.PDF_ENCRYPT_KEEP if doc.needs_pass else pymupdf.PDF_ENCRYPT_NONE)
        doc.close()
        os.replace(tmp, target)
    except BaseException as e:
        doc.close()
        Path(tmp).unlink(missing_ok=True)
        if isinstance(e, (OSError, RuntimeError)):
            raise RedactError(tr("{path} cannot be written: {error}", path=target, error=e)) from None
        raise
    return done


def preview_page(doc: pymupdf.Document, number: int, boxes: list[Box]) -> pymupdf.Document:
    """A new one-page document: page NUMBER of DOC with BOXES (those on it) redacted."""
    one = pymupdf.open()
    one.insert_pdf(doc, from_page=number, to_page=number)
    here = boxes_on(boxes, number, doc.page_count)
    redact_page(one[0], here)
    return one
