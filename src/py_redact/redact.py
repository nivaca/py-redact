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


IMAGES = {"pixels": pymupdf.PDF_REDACT_IMAGE_PIXELS, "whole": pymupdf.PDF_REDACT_IMAGE_REMOVE,
          "none": pymupdf.PDF_REDACT_IMAGE_NONE}
DRAWINGS = {"covered": pymupdf.PDF_REDACT_LINE_ART_REMOVE_IF_COVERED,
            "touched": pymupdf.PDF_REDACT_LINE_ART_REMOVE_IF_TOUCHED, "none": pymupdf.PDF_REDACT_LINE_ART_NONE}


def redact_page(page: pymupdf.Page, boxes: list[Box], images: str = "pixels", drawings: str = "covered") -> int:
    """Redact BOXES (those on this page) on PAGE. IMAGES: what to do with the
    images under a box ('pixels': blank the part under it; 'whole': remove the
    image; 'none': leave it); DRAWINGS: which drawings go ('covered': those
    wholly under a box; 'touched': those it touches; 'none'). Returns how many
    boxes were applied."""
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
    page.apply_redactions(images=IMAGES[images], graphics=DRAWINGS[drawings],
                          text=pymupdf.PDF_REDACT_TEXT_REMOVE)
    return len(areas)


def redact(doc: pymupdf.Document, boxes: list[Box], clean: bool = False, images: str = "pixels",
           drawings: str = "covered") -> int:
    """Redact BOXES in DOC (in memory). With CLEAN, also remove the metadata,
    hidden text, attached files, scripts and links of the document. Returns how
    many boxes were applied, counting each page a box is repeated on."""
    count = doc.page_count
    done = 0
    for number in range(count):
        here = boxes_on(boxes, number, count)
        if here:
            done += redact_page(doc[number], here, images, drawings)
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
                   clean: bool = False, images: str = "pixels", drawings: str = "covered") -> int:
    """SOURCE with BOXES redacted, saved as TARGET (safely: TARGET may be
    SOURCE). Returns how many boxes were applied (see redact)."""
    doc = open_pdf(source, password)
    fd, tmp = tempfile.mkstemp(suffix=".pdf", dir=target.parent)
    os.close(fd)
    try:
        done = redact(doc, boxes, clean, images, drawings)
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


def preview_page(doc: pymupdf.Document, number: int, boxes: list[Box], images: str = "pixels",
                 drawings: str = "covered") -> pymupdf.Document:
    """A new one-page document: page NUMBER of DOC with BOXES (those on it) redacted."""
    one = pymupdf.open()
    one.insert_pdf(doc, from_page=number, to_page=number)
    here = boxes_on(boxes, number, doc.page_count)
    redact_page(one[0], here, images, drawings)
    return one


def _shown(page: pymupdf.Page, rect) -> pymupdf.Rect:
    return (pymupdf.Rect(rect) * page.rotation_matrix).normalize()


def words(page: pymupdf.Page) -> list[tuple[Rect, int, int]]:
    """The words of PAGE in reading order: (their rectangle as the page is
    shown, block number, line number)."""
    out = []
    for x0, y0, x1, y1, _text, block, line, _n in page.get_text("words", sort=False):
        r = _shown(page, (x0, y0, x1, y1))
        out.append(((r.x0, r.y0, r.x1, r.y1), block, line))
    return out


def nearest_word(found: list[tuple[Rect, int, int]], x: float, y: float) -> int | None:
    """The index of the word at (X, Y), or else of the nearest one; None if there are none."""
    if not found:
        return None

    def distance(i):
        x0, y0, x1, y1 = found[i][0]
        dx = max(x0 - x, 0, x - x1)
        dy = max(y0 - y, 0, y - y1)
        return dx * dx + 4 * dy * dy  # (the line it is on matters more)

    return min(range(len(found)), key=distance)


def text_rects(found: list[tuple[Rect, int, int]], first: int, last: int, pad: float = 1.0) -> list[Rect]:
    """The rectangles that cover the words FIRST to LAST (in either order) of
    FOUND: one for each line, a little larger than the words (PAD points)."""
    if first > last:
        first, last = last, first
    lines: dict[tuple[int, int], list[float]] = {}
    for (x0, y0, x1, y1), block, line in found[first:last + 1]:
        r = lines.setdefault((block, line), [x0, y0, x1, y1])
        r[0], r[1], r[2], r[3] = min(r[0], x0), min(r[1], y0), max(r[2], x1), max(r[3], y1)
    return [(round(x0 - pad, 2), round(y0 - pad, 2), round(x1 + pad, 2), round(y1 + pad, 2))
            for x0, y0, x1, y1 in lines.values()]
