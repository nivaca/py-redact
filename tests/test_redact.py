"""The redaction itself (redact.py) and the lists of pages (pagesel.py)."""

from __future__ import annotations

import pymupdf
import pytest

from py_redact.pagesel import PageError, check, parse_pages
from py_redact.redact import Box, PasswordError, RedactError, open_pdf, preview_page, rgb, write_redacted

HEADER = (60, 40, 300, 66)
NAME = (60, 105, 300, 126)


def texts(path, password=""):
    doc = pymupdf.open(path)
    if password:
        doc.authenticate(password)
    return [page.get_text() for page in doc]


@pytest.mark.parametrize("spec, pages", [
    ("", [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]), ("all", list(range(10))), ("odd", [0, 2, 4, 6, 8]),
    ("even", [1, 3, 5, 7, 9]), ("3", [2]), ("2-4, 9", [1, 2, 3, 8]), ("8-", [7, 8, 9]), ("4..2", [1, 2, 3]),
    ("LAST", [9]), ("LAST-1", [8]), ("LAST-2-LAST", [7, 8, 9]), ("1 3; 12", [0, 2]),
])
def test_pages(spec, pages):
    assert parse_pages(spec, 10) == pages


def test_bad_pages():
    with pytest.raises(PageError):
        parse_pages("1-x", 10)
    assert check("abc") and not check("1-3, 7-")


def test_box_pages():
    assert Box(2, HEADER).pages(5) == [2]
    assert Box(2, HEADER, repeat="all").pages(5) == [0, 1, 2, 3, 4]
    assert Box(7, HEADER).pages(5) == []
    assert rgb("#ff8000") == (1.0, 128 / 255, 0.0)


def test_one_page(sample, tmp_path):
    out = tmp_path / "out.pdf"
    assert write_redacted(sample, [Box(1, NAME)], out) == 1
    pages = texts(out)
    assert "Person2" not in pages[1] and "HEADER2" in pages[1] and "Body text stays" in pages[1]
    assert all(f"Person{i + 1}" in pages[i] for i in (0, 2, 3, 4))


def test_repeated(sample, tmp_path):
    out = tmp_path / "out.pdf"
    assert write_redacted(sample, [Box(0, HEADER, repeat="all"), Box(0, NAME, repeat="even")], out) == 7
    pages = texts(out)
    assert not any("HEADER" in t for t in pages)
    assert ["Person" in t for t in pages] == [True, False, True, False, True]
    assert all("Body text stays" in t for t in pages)


@pytest.mark.parametrize("color", ["#000000", "#ffffff", "#ff0000"])
def test_colour(sample, tmp_path, color):
    out = tmp_path / "out.pdf"
    write_redacted(sample, [Box(0, (100, 400, 200, 500), color)], out)
    pix = pymupdf.open(out)[0].get_pixmap()
    assert pix.pixel(150, 450) == tuple(round(c * 255) for c in rgb(color))


def test_rotated_page(sample, tmp_path):
    doc = pymupdf.open(sample)
    doc[0].set_rotation(90)
    rotated = tmp_path / "rotated.pdf"
    doc.save(rotated)
    page = pymupdf.open(rotated)[0]
    shown = page.search_for("HEADER1")[0] * page.rotation_matrix  # (as the page is shown)
    out = tmp_path / "out.pdf"
    write_redacted(rotated, [Box(0, tuple(shown))], out)
    assert "HEADER1" not in texts(out)[0] and "Person1" in texts(out)[0]


def test_box_beyond_a_smaller_page(tmp_path):
    doc = pymupdf.open()
    doc.new_page(width=600, height=800).insert_text((500, 700), "corner", fontsize=12)
    doc.new_page(width=300, height=400).insert_text((50, 50), "small", fontsize=12)
    path, out = tmp_path / "in.pdf", tmp_path / "out.pdf"
    doc.save(path)
    assert write_redacted(path, [Box(0, (450, 650, 600, 800), repeat="all")], out) == 1
    assert texts(out) == ["", "small\n"]


def test_annotations_over_a_box_go(sample, tmp_path):
    doc = pymupdf.open(sample)
    doc[0].add_text_annot((80, 115), "a note with the name")
    doc[0].add_text_annot((80, 500), "another note")
    path, out = tmp_path / "in.pdf", tmp_path / "out.pdf"
    doc.save(path)
    write_redacted(path, [Box(0, NAME)], out)
    assert [a.info["content"] for a in pymupdf.open(out)[0].annots()] == ["another note"]


def test_clean(sample, tmp_path):
    doc = pymupdf.open(sample)
    doc.set_metadata({"author": "Somebody", "title": "Secret"})
    path, out = tmp_path / "in.pdf", tmp_path / "out.pdf"
    doc.save(path)
    write_redacted(path, [Box(0, NAME)], out, clean=True)
    meta = pymupdf.open(out).metadata
    assert not meta.get("author") and not meta.get("title")


def test_protected(sample, tmp_path):
    doc = pymupdf.open(sample)
    path, out = tmp_path / "in.pdf", tmp_path / "out.pdf"
    doc.save(path, encryption=pymupdf.PDF_ENCRYPT_AES_256, user_pw="u", owner_pw="o")
    with pytest.raises(PasswordError):
        open_pdf(path)
    write_redacted(path, [Box(0, NAME)], out, password="u")
    assert pymupdf.open(out).needs_pass
    assert "Person1" not in texts(out, "u")[0]


def test_in_place(sample):
    write_redacted(sample, [Box(0, NAME)], sample)
    assert "Person1" not in texts(sample)[0]


def test_not_a_pdf(tmp_path):
    path = tmp_path / "x.pdf"
    path.write_text("nothing")
    with pytest.raises(RedactError):
        open_pdf(path)


def test_preview_leaves_the_document(sample):
    doc = pymupdf.open(sample)
    one = preview_page(doc, 3, [Box(0, NAME, repeat="all")])
    assert "Person4" not in one[0].get_text() and "Person4" in doc[3].get_text()
