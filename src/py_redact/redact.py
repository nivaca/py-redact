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
from typing import NamedTuple

import pymupdf

from .interface import tr
from .pagesel import parse_pages

Rect = tuple[float, float, float, float]  # x0, y0, x1, y1


@dataclasses.dataclass(frozen=True)
class Box:
    page: int  # 0-based: the page where it was drawn
    rect: Rect
    color: str = "#000000"  # of the fill; '' for none (what is under it is removed, and nothing is painted)
    repeat: str = ""  # '' for its own page only; else the pages it goes on
    text: str = ""  # written over the box once it is redacted ("REDACTED", "[name]"...)
    text_color: str = "#ffffff"
    font_size: float = 0  # 0: as large as fits, up to 12 points
    align: str = "center"  # of the text: 'left', 'center' or 'right'
    repeat_text: bool = False  # the text again and again, all along the box
    note: str = ""  # shown when the mouse is over the box; never written in the PDF
    locked: bool = False  # can't be moved, resized or deleted

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


ALIGN = {"left": pymupdf.TEXT_ALIGN_LEFT, "center": pymupdf.TEXT_ALIGN_CENTER, "right": pymupdf.TEXT_ALIGN_RIGHT}
FONT = "helv"
MAX_FONT = 12.0


def overlay(box: Box, area: pymupdf.Rect) -> tuple[str, float]:
    """The text to write over AREA, and its size: as large as fits on one line
    (or the box's own size), and, with repeat_text, repeated to fill the line."""
    text = " ".join(box.text.split())
    if not text or area.width < 2 or area.height < 2:
        return "", 0
    size = box.font_size or min(MAX_FONT, area.height * 0.75)
    width = pymupdf.get_text_length(text, fontname=FONT, fontsize=size)
    room = area.width - 2
    if not box.font_size and width > room:
        size = max(size * room / width, 3)
    if box.repeat_text:
        unit = text + " "
        n = max(int(room // pymupdf.get_text_length(unit, fontname=FONT, fontsize=size)), 1)
        text = (unit * n).strip()
    return text, round(size, 2)


def boxes_on(boxes: list[Box], page: int, count: int) -> list[Box]:
    return [b for b in boxes if b.on(page, count)]


def boxes_by_page(boxes: list[Box], count: int) -> dict[int, list[Box]]:
    """BOXES by the pages they are on, in a document of COUNT pages (in their
    order on each page): each repeated box's pages are read once, not once a page."""
    out: dict[int, list[Box]] = {}
    for box in boxes:
        for number in box.pages(count):
            out.setdefault(number, []).append(box)
    return out


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
        text, size = overlay(box, area)
        page.add_redact_annot(area, text=text or None, fontname=FONT, fontsize=size or 11, align=ALIGN[box.align],
                              fill=rgb(box.color) if box.color else False,
                              text_color=rgb(box.text_color), cross_out=False)
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
    done = 0
    for number, here in sorted(boxes_by_page(boxes, doc.page_count).items()):
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
                   clean: bool = False, images: str = "pixels", drawings: str = "covered", meta=None,
                   part: Path | None = None) -> int:
    """SOURCE with BOXES redacted, saved as TARGET (safely: TARGET may be
    SOURCE). META (a metadata.Metadata), if given, becomes the metadata of
    TARGET, after any cleaning. PART, if given, is the file written first and
    then renamed TARGET (else a new temporary file next to it), so that the
    caller can remove it if the writing is stopped halfway. Returns how many
    boxes were applied (see redact)."""
    doc = open_pdf(source, password)
    if part is None:
        fd, tmp = tempfile.mkstemp(suffix=".pdf", dir=target.parent)
        os.close(fd)
    else:
        tmp = str(part)
    try:
        done = redact(doc, boxes, clean, images, drawings)
        if meta is not None:
            from . import metadata

            metadata.write(doc, meta)
        # (garbage=4 drops the objects nothing uses any more: the fonts and images
        # that only the redacted parts used, which would otherwise stay in the file)
        doc.save(tmp, garbage=4, deflate=True, clean=True,
                 encryption=pymupdf.PDF_ENCRYPT_KEEP if doc.needs_pass else pymupdf.PDF_ENCRYPT_NONE)
        doc.close()
        os.replace(tmp, target)
    except BaseException as e:
        if not doc.is_closed:  # (it may fail after closing: the renaming, on Windows)
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


def _turner(page: pymupdf.Page):
    """A function that gives a rectangle of PAGE as the page is shown, in
    plain numbers (as _shown, but quick enough for every character of a book)."""
    m = page.rotation_matrix
    a, b, c, d, e, f = m.a, m.b, m.c, m.d, m.e, m.f
    if (a, b, c, d, e, f) == (1, 0, 0, 1, 0, 0):
        return lambda r: (min(r[0], r[2]), min(r[1], r[3]), max(r[0], r[2]), max(r[1], r[3]))

    def turn(r):  # (pages turn by quarters: two opposite corners stay opposite)
        x0, y0, x1, y1 = r
        u0, u1 = a * x0 + c * y0 + e, a * x1 + c * y1 + e
        v0, v1 = b * x0 + d * y0 + f, b * x1 + d * y1 + f
        return min(u0, u1), min(v0, v1), max(u0, u1), max(v0, v1)

    return turn


class Word(NamedTuple):
    rect: Rect  # as the page is shown
    block: int
    line: int
    text: str


def words(page: pymupdf.Page) -> list[Word]:
    """The words of PAGE in reading order, with their rectangles as the page
    is shown: the one reading of a page's words, for selecting text and for
    telling what is under a box (see under)."""
    turn = _turner(page)
    return [Word(turn((x0, y0, x1, y1)), block, line, w)
            for x0, y0, x1, y1, w, block, line, _n in page.get_text("words", sort=False)]


def nearest_word(found: list[Word], x: float, y: float) -> int | None:
    """The index of the word at (X, Y), or else of the nearest one; None if there are none."""
    if not found:
        return None

    def distance(i):
        x0, y0, x1, y1 = found[i][0]
        dx = max(x0 - x, 0, x - x1)
        dy = max(y0 - y, 0, y - y1)
        return dx * dx + 4 * dy * dy  # (the line it is on matters more)

    return min(range(len(found)), key=distance)


def text_rects(found: list[Word], first: int, last: int, pad: float = 1.0) -> list[Rect]:
    """The rectangles that cover the words FIRST to LAST (in either order) of
    FOUND: one for each line, a little larger than the words (PAD points)."""
    if first > last:
        first, last = last, first
    lines: dict[tuple[int, int], list[float]] = {}
    for (x0, y0, x1, y1), block, line, _text in found[first:last + 1]:
        r = lines.setdefault((block, line), [x0, y0, x1, y1])
        r[0], r[1], r[2], r[3] = min(r[0], x0), min(r[1], y0), max(r[2], x1), max(r[3], y1)
    return [(round(x0 - pad, 2), round(y0 - pad, 2), round(x1 + pad, 2), round(y1 + pad, 2))
            for x0, y0, x1, y1 in lines.values()]


@dataclasses.dataclass(frozen=True)
class Match:
    page: int  # 0-based
    rects: tuple[Rect, ...]  # one for each line of the text found (as the page is shown)
    text: str  # what was found
    context: str  # with some words around it


def page_chars(page: pymupdf.Page) -> tuple[str, list]:
    """The text of PAGE as find_text reads it, and for each of its characters
    (block, line, rectangle as the page is shown), or None for a space put
    between two lines. Runs of spaces are one space."""
    text, where = [], []
    turn = _turner(page)
    raw = page.get_text("rawdict", flags=pymupdf.TEXTFLAGS_SEARCH & ~pymupdf.TEXT_PRESERVE_IMAGES)
    for b, block in enumerate(raw.get("blocks", [])):
        for n, line in enumerate(block.get("lines", [])):
            if text and text[-1] != " ":
                text.append(" ")
                where.append(None)
            for span in line.get("spans", []):
                for ch in span.get("chars", []):
                    c = ch["c"]
                    if c.isspace():
                        if text and text[-1] == " ":
                            continue
                        c = " "
                    text.append(c)
                    where.append((b, n, turn(ch["bbox"])))
    return "".join(text), where


def _compile(query: str, case: bool, whole_words: bool, regex: bool):
    import re

    pattern = query if regex else r"\s+".join(re.escape(w) for w in query.split())
    if whole_words:
        pattern = rf"(?<!\w)(?:{pattern})(?!\w)"
    return re.compile(pattern, 0 if case else re.IGNORECASE)


def _matches_on(number: int, text: str, where: list, found_re, keep_start: int, keep_end: int) -> list[Match]:
    """The places of PAGE_CHARS' TEXT (of page NUMBER) where FOUND_RE is."""
    out = []
    for m in found_re.finditer(text):
        start, end = m.span()
        if end <= start:
            continue
        real = [i for i in range(start, end) if where[i] is not None and not text[i].isspace()]
        chosen = real[keep_start:len(real) - keep_end if keep_end else None]
        if not chosen:
            continue
        lines: dict[tuple[int, int], tuple] = {}  # (an empty rectangle, as of a space, adds nothing)
        for i in range(chosen[0], chosen[-1] + 1):
            if where[i] is None:
                continue
            b, n, r = where[i]
            old = lines.get((b, n))
            if old is None or not (old[2] > old[0] and old[3] > old[1]):
                lines[(b, n)] = r
            elif r[2] > r[0] and r[3] > r[1]:
                lines[(b, n)] = (min(old[0], r[0]), min(old[1], r[1]), max(old[2], r[2]), max(old[3], r[3]))
        rects = tuple((round(x0 - 0.5, 2), round(y0 - 0.5, 2), round(x1 + 0.5, 2), round(y1 + 0.5, 2))
                      for x0, y0, x1, y1 in lines.values())
        before = text[max(start - 40, 0):start].split(" ", 1)[-1] if start > 40 else text[:start]
        after = text[end:end + 40].rsplit(" ", 1)[0] if len(text) > end + 40 else text[end:]
        snippet = m.group(0).strip()
        context = " ".join(p for p in (before.strip(), f"[{snippet}]", after.strip()) if p)
        out.append(Match(number, rects, snippet, context))
    return out


def find_text(doc: pymupdf.Document, query: str, pages: list[int] | None = None, case: bool = False,
              whole_words: bool = False, regex: bool = False, keep_start: int = 0, keep_end: int = 0,
              texts: dict | None = None) -> list[Match]:
    """Where QUERY is on PAGES (0-based; all if None) of DOC. The text of a page
    is read with single spaces between its words and lines, so a phrase is found
    across line breaks and however it is spaced. With REGEX, QUERY is a regular
    expression (raises re.error if it is wrong). KEEP_START and KEEP_END leave
    that many characters of each place found out of its boxes (the last four
    digits of a card number stay visible, for instance). TEXTS: see find_all."""
    return find_all(doc, [(query, regex)], pages, case, whole_words, keep_start, keep_end, texts=texts)


def find_all(doc: pymupdf.Document, queries: list[tuple[str, bool]], pages: list[int] | None = None,
             case: bool = False, whole_words: bool = False, keep_start: int = 0, keep_end: int = 0,
             progress=None, texts: dict | None = None) -> list[Match]:
    """Where any of QUERIES ((text, whether it is a regular expression)) is (see
    find_text), in page order; a place found by two of them is given once. Each
    page is read once, whatever the number of QUERIES. PROGRESS, if given, is
    called after each page with (pages done, pages in all); if it returns False,
    the search stops there, with what it found so far. TEXTS, if given, keeps
    the text of each page read (by its number), for the next search in the
    same document: the caller empties it when the document changes."""
    compiled = [_compile(q, case, whole_words, regex) for q, regex in queries if q.strip()]
    if not compiled:
        return []
    numbers = list(range(doc.page_count) if pages is None else pages)
    seen, out = set(), []
    for done, number in enumerate(numbers, 1):
        if texts is None:
            text, where = page_chars(doc[number])
        else:
            if number not in texts:
                texts[number] = page_chars(doc[number])
            text, where = texts[number]
        found = []
        for found_re in compiled:
            for m in _matches_on(number, text, where, found_re, keep_start, keep_end):
                if (m.page, m.rects) not in seen:
                    seen.add((m.page, m.rects))
                    found.append(m)
        out += sorted(found, key=lambda m: (m.rects[0][1], m.rects[0][0]))
        if progress is not None and progress(done, len(numbers)) is False:
            break
    return out


def under(found: list[Word], rect: Rect) -> list[str]:
    """The words of FOUND (see words) wholly or mostly under RECT (as the page
    is shown), in reading order. (In plain numbers: thousands of boxes on
    hundreds of pages.)"""
    ax0, ay0, ax1, ay1 = normalized(rect)
    out = []
    for (x0, y0, x1, y1), _block, _line, w in found:
        if x1 <= ax0 or x0 >= ax1 or y1 <= ay0 or y0 >= ay1:
            continue
        whole = (x1 - x0) * (y1 - y0)
        if x1 > x0 and y1 > y0 and (min(x1, ax1) - max(x0, ax0)) * (min(y1, ay1) - max(y0, ay0)) >= 0.5 * whole:
            out.append(w)
    return out


def text_under(page: pymupdf.Page, rect: Rect) -> str:
    """The words of PAGE wholly or mostly under RECT (as the page is shown), in reading order."""
    return " ".join(under(words(page), rect))


def check_redacted(source: Path, target: Path, boxes: list[Box], password: str = "") -> list[tuple[int, str]]:
    """What can still be read under the boxes in TARGET, the redacted copy of
    SOURCE: [(page, text)], empty if nothing. A word counts if it was under a
    box in SOURCE and is still under it in TARGET (the text written over a box
    doesn't count)."""
    leaks = []
    before, after = open_pdf(source, password), open_pdf(target, password)
    try:
        count = min(before.page_count, after.page_count)
        # (each page's words are read once, in both copies, for all its boxes)
        for number, here in sorted(boxes_by_page(boxes, before.page_count).items()):
            if number >= count:
                continue
            page = before[number]
            old, new = words(page), words(after[number])
            for box in here:
                area = page_rect(page, box.rect)
                if area is None:
                    continue
                shown = tuple((area * page.rotation_matrix).normalize())
                hidden = set(under(old, shown))
                written = set(overlay(box, area)[0].split())
                left = [w for w in under(new, shown) if w in hidden and w not in written]
                if left:
                    leaks.append((number, " ".join(left)))
    finally:
        before.close()
        after.close()
    return leaks


def image_at(page: pymupdf.Page, x: float, y: float) -> Rect | None:
    """The rectangle (as the page is shown) of the image at (X, Y), if there is one."""
    for info in page.get_image_info():
        r = _shown(page, info["bbox"])
        if r.contains(pymupdf.Point(x, y)):
            return (round(r.x0, 2), round(r.y0, 2), round(r.x1, 2), round(r.y1, 2))
    return None


def sanitize(source: Path, target: Path, password: str = "", kinds: set[str] | None = None) -> None:
    """SOURCE without the KINDS of hidden information (see hidden.py; all if
    None), and nothing else changed, saved as TARGET."""
    from . import hidden

    kinds = {k for k, _, _ in hidden.KINDS} if kinds is None else kinds
    doc = open_pdf(source, password)
    fd, tmp = tempfile.mkstemp(suffix=".pdf", dir=target.parent)
    os.close(fd)
    try:
        hidden.remove(doc, kinds)
        doc.save(tmp, garbage=4 if "unused" in kinds else 1, deflate=True, clean="unused" in kinds,
                 encryption=pymupdf.PDF_ENCRYPT_KEEP if doc.needs_pass else pymupdf.PDF_ENCRYPT_NONE)
        doc.close()
        os.replace(tmp, target)
    except BaseException as e:
        if not doc.is_closed:  # (it may fail after closing: the renaming, on Windows)
            doc.close()
        Path(tmp).unlink(missing_ok=True)
        if isinstance(e, (OSError, RuntimeError)):
            raise RedactError(tr("{path} cannot be written: {error}", path=target, error=e)) from None
        raise


# Words too common to say anything about what was redacted (English and Spanish)
COMMON_WORDS = frozenset("""
a an and are as at be but by for from has have in is it its of on or that the this to was were will with
al con de del el en es la las lo los o para por que se sin su sus un una uno y
""".split())


def _plain_words(text: str) -> list[str]:
    import re

    return [w for w in re.findall(r"\w+", text.casefold()) if len(w) >= 3 and w not in COMMON_WORDS]


def bookmark_leaks(source: Path, target: Path, boxes: list[Box], password: str = "") -> list[tuple[int, str, str]]:
    """The bookmarks of TARGET (the redacted copy of SOURCE) that may give
    away what was redacted: [(their index in the outline, their title, why)].
    A bookmark is named if it points to no page of the document, or if its
    title tells what was under the boxes in SOURCE: it has a word that was
    under a box and nowhere else in SOURCE, or more than half of its words
    were under boxes ("Creating watermarks", over a redacted heading)."""
    after = open_pdf(target, password)
    try:
        toc = after.get_toc(simple=False)
        pages = after.page_count
    finally:
        after.close()
    if not toc:  # (no bookmarks: no need to read the text)
        return []
    under_boxes: set[str] = set()
    elsewhere: set[str] = set()  # (the words of SOURCE outside the boxes)
    before = open_pdf(source, password)
    try:
        by_page = boxes_by_page(boxes, before.page_count)
        for number in range(before.page_count):
            page = before[number]
            found = words(page)  # (read once, for its boxes and for the whole page)
            hidden_counts: dict[str, int] = {}  # (the words under the boxes of the page, with how many times)
            for box in by_page.get(number, []):
                area = page_rect(page, box.rect)
                if area is not None:
                    shown = tuple((area * page.rotation_matrix).normalize())
                    for w in _plain_words(" ".join(under(found, shown))):
                        hidden_counts[w] = hidden_counts.get(w, 0) + 1
            under_boxes |= hidden_counts.keys()
            # (a word of the page is also elsewhere if it is there more times than under the boxes)
            counts: dict[str, int] = {}
            for w in _plain_words(" ".join(w.text for w in found)):
                counts[w] = counts.get(w, 0) + 1
            elsewhere |= {w for w, n in counts.items() if n > hidden_counts.get(w, 0)}
    finally:
        before.close()
    out = []
    for i, (_level, title, page, *_rest) in enumerate(toc):
        title = " ".join(title.split())
        all_words = list(dict.fromkeys(_plain_words(title)))
        hidden = [w for w in all_words if w in under_boxes]
        telling = any(w not in elsewhere for w in hidden) or (all_words and len(hidden) * 2 > len(all_words))
        if hidden and telling:
            out.append((i, title, tr("it has words that were under the boxes: {words}", words=", ".join(hidden))))
        elif not 1 <= page <= pages:
            out.append((i, title, tr("it points to no page of the document")))
    return out


def remove_bookmarks(path: Path, which: set[int] | None = None, password: str = "") -> None:
    """Take out of PATH the bookmarks WHICH (their indices in the outline;
    all if None), and the bookmarks under them, saving it again (safely)."""
    doc = open_pdf(path, password)
    fd, tmp = tempfile.mkstemp(suffix=".pdf", dir=path.parent)
    os.close(fd)
    try:
        if which is None:
            doc.set_toc([])
        else:
            toc, keep, cut_level = doc.get_toc(simple=False), [], None
            for i, item in enumerate(toc):
                level = item[0]
                if cut_level is not None and level > cut_level:
                    continue  # (under a bookmark taken out)
                cut_level = level if i in which else None
                if i not in which:
                    keep.append(item)
            # (levels must go down one at a time: a bookmark whose parent went is raised)
            fixed, last = [], 0
            for item in keep:
                item = [min(item[0], last + 1)] + list(item[1:])
                fixed.append(item)
                last = item[0]
            doc.set_toc(fixed)
        doc.save(tmp, garbage=4, deflate=True,
                 encryption=pymupdf.PDF_ENCRYPT_KEEP if doc.needs_pass else pymupdf.PDF_ENCRYPT_NONE)
        doc.close()
        os.replace(tmp, path)
    except BaseException as e:
        if not doc.is_closed:  # (it may fail after closing: the renaming, on Windows)
            doc.close()
        Path(tmp).unlink(missing_ok=True)
        if isinstance(e, (OSError, RuntimeError, ValueError)):
            raise RedactError(tr("{path} cannot be written: {error}", path=path, error=e)) from None
        raise
