"""The redaction itself (redact.py) and the lists of pages (pagesel.py)."""

from __future__ import annotations

import pymupdf
import pytest

from py_redact.pagesel import PageError, check, parse_pages
from py_redact.redact import (
    Box, PasswordError, RedactError, nearest_word, open_pdf, preview_page, rgb, text_rects, words, write_redacted,
)

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


def test_text_rects(sample):
    page = pymupdf.open(sample)[0]
    found = words(page)
    a, b = nearest_word(found, 75, 115), nearest_word(found, 150, 118)
    assert len(text_rects(found, a, b)) == 1 and len(text_rects(found, 0, len(found) - 1)) == 3


@pytest.mark.parametrize("images", ["pixels", "whole", "none"])
def test_image_modes(tmp_path, images):
    doc = pymupdf.open()
    page = doc.new_page()
    pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 20, 20), False)
    pix.set_rect(pix.irect, (255, 0, 0))
    page.insert_image(pymupdf.Rect(100, 100, 300, 300), pixmap=pix)
    path, out = tmp_path / "in.pdf", tmp_path / "out.pdf"
    doc.save(path)
    write_redacted(path, [Box(0, (100, 100, 150, 150), "#00ff00")], out, images=images)
    page = pymupdf.open(out)[0]
    assert len(page.get_images()) == (0 if images == "whole" else 1)
    assert page.get_pixmap().pixel(250, 250) == ((255, 255, 255) if images == "whole" else (255, 0, 0))


def test_settings_survive_a_bad_file():
    from py_redact import config, settings

    path = config.config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('[parameters]\nredact_color = "red"\nredact_images = "whole"\nredact_clean = "yes"\n')
    assert settings.load() == settings.Settings(images="whole")
    path.write_text("not toml [")
    assert settings.load() == settings.DEFAULTS
    settings.save(settings.Settings(color="#ff0000", clean=True))
    assert settings.load() == settings.Settings(color="#ff0000", clean=True)


def test_find_text(tmp_path):
    from py_redact.redact import find_text, text_under

    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 100), "John Doe signed. JOHN", fontsize=12)
    page.insert_text((72, 120), "Doe again, johnny", fontsize=12)
    found = find_text(doc, "john  doe")
    assert [len(m.rects) for m in found] == [1, 2]  # (the second goes across a line break)
    assert len(find_text(doc, "john", whole_words=True)) == 2 and len(find_text(doc, "john")) == 3
    assert len(find_text(doc, "John", case=True)) == 1 and find_text(doc, "  ") == []
    assert text_under(page, found[0].rects[0]) == "John Doe"


def test_conform_missing(sample, tmp_path, monkeypatch):
    from py_redact import conform

    monkeypatch.setattr(conform, "command", lambda path=None: None)
    with pytest.raises(conform.ConformError):
        conform.convert(sample, tmp_path / "x.pdf", "a-2b")


def test_overlay_text_and_no_fill(sample, tmp_path):
    from py_redact.redact import check_redacted, overlay

    boxes = [Box(0, NAME, "", text="X"), Box(1, NAME, "#000000", text="[name]", repeat_text=True, align="left")]
    out = tmp_path / "out.pdf"
    write_redacted(sample, boxes, out)
    assert check_redacted(sample, out, boxes) == []
    assert check_redacted(sample, sample, boxes)  # (an unredacted file: its words are found)
    pix = pymupdf.open(out)[0].get_pixmap()
    assert pix.pixel(65, 110) == (255, 255, 255)  # (no fill: nothing painted)
    text, size = overlay(boxes[1], pymupdf.Rect(NAME))
    assert text.count("[name]") > 3 and 3 <= size <= 12


def test_image_at(tmp_path):
    from py_redact.redact import image_at

    doc = pymupdf.open()
    page = doc.new_page()
    pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 10, 10), False)
    page.insert_image(pymupdf.Rect(100, 100, 200, 150), pixmap=pix)
    assert image_at(page, 150, 120) == (100, 100, 200, 150) and image_at(page, 10, 10) is None


def test_patterns():
    import re

    from py_redact import patterns

    text = ("Call (555) 123-4567, +57 601 555 1234 or 612 345 678; a.b@x.co.uk; 4111 1111 1111 1111; "
            "SSN 123-45-6789; 3/14/2024 and 14 de marzo de 2024; DNI 12345678Z; IBAN ES91 2100 0418 4502 0005 1332")
    found = {(k, lang): re.findall(patterns.regex(k, lang), text) for k, _, _ in patterns.PATTERNS
             for lang in ("en", "es")}
    assert found[("email", "en")] == ["a.b@x.co.uk"]
    assert "(555) 123-4567" in found[("phone", "en")]
    assert found[("phone", "es")] == ["+57 601 555 1234", "612 345 678"]
    assert "4111 1111 1111 1111" in found[("card", "en")]
    assert found[("id", "en")] == ["123-45-6789"] and "12345678Z" in found[("id", "es")]
    assert "14 de marzo de 2024" in found[("date", "es")] and "3/14/2024" in found[("date", "en")]
    assert found[("iban", "en")] == ["ES91 2100 0418 4502 0005 1332"]


def test_partial_and_several(tmp_path):
    from py_redact import patterns
    from py_redact.redact import find_all, find_text

    doc = pymupdf.open()
    doc.new_page().insert_text((72, 100), "Card 4111 1111 1111 1234 and mail a.b@x.org", fontsize=11)
    whole = find_text(doc, patterns.regex("card"), regex=True)[0].rects[0]
    part = find_text(doc, patterns.regex("card"), regex=True, keep_end=4)[0].rects[0]
    assert part[0] == whole[0] and part[2] < whole[2] - 15
    found = find_all(doc, [("card", False), ("mail", False), (patterns.regex("email"), True)])
    assert [m.text for m in found] == ["Card", "mail", "a.b@x.org"]
    path, out = tmp_path / "in.pdf", tmp_path / "out.pdf"
    doc.save(path)
    m = find_text(doc, patterns.regex("card"), regex=True, keep_end=4)[0]
    write_redacted(path, [Box(0, r) for r in m.rects], out)
    assert "1234" in texts(out)[0] and "4111" not in texts(out)[0]


def test_codes(tmp_path):
    from py_redact import codes

    assert codes.toggle("(b)(6)", "(b)(7)(C)") == "(b)(6), (b)(7)(C)"
    assert codes.toggle("(b)(6), (b)(7)(C)", "(b)(6)") == "(b)(7)(C)"
    sets = {"Mine": ["Personal data", "Health"]}
    assert codes.parse(codes.dump(sets)) == sets
    codes.save_user_sets(sets)
    assert codes.all_sets()["Mine"] == ["Personal data", "Health"] and "U.S. FOIA" in codes.all_sets()
    codes.path().write_text("<broken")
    assert codes.user_sets() == {}
    with pytest.raises(codes.CodesError):
        codes.parse("<other/>")


def test_hidden_information(tmp_path):
    from py_redact import hidden
    from py_redact.redact import sanitize

    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), "seen")
    page.insert_text((72, 100), "ocr layer", render_mode=3)
    doc.set_metadata({"author": "Me"})
    doc.embfile_add("a.txt", b"x")
    doc.set_toc([[1, "Chapter", 1]])
    page.add_text_annot((100, 100), "a note")
    page.insert_link({"kind": pymupdf.LINK_URI, "from": pymupdf.Rect(0, 0, 50, 50), "uri": "https://example.org"})
    path = tmp_path / "in.pdf"
    doc.save(path)
    found = hidden.inspect(pymupdf.open(path))
    assert all(found[k] >= 1 for k in ("metadata", "attachments", "bookmarks", "comments", "hidden_text", "links"))
    out = tmp_path / "out.pdf"
    sanitize(path, out, kinds={"bookmarks", "hidden_text"})
    after = hidden.inspect(pymupdf.open(out))
    assert after["bookmarks"] == 0 and after["hidden_text"] == 0 and after["comments"] == 1
    sanitize(path, out)
    assert not any(v > 0 for v in hidden.inspect(pymupdf.open(out)).values())
    assert pymupdf.open(out)[0].get_text() == "seen\n"


def test_finding_pdfconform(tmp_path, monkeypatch):
    from py_redact import conform, settings

    home = tmp_path / "home"
    (home / "bin").mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("PATH", "/usr/bin:/bin")  # (as a session started from the desktop menu may have it)
    assert conform.find() is None and not conform.available()
    script = home / "bin" / "pdf2iso"
    script.write_text("#!/bin/sh\n")
    script.chmod(0o755)
    assert conform.find() == script and conform.command() == [str(script)]
    other = tmp_path / "elsewhere.py"  # (a script that can't be run by itself: run with python3)
    other.write_text("print()\n")
    settings.save(settings.Settings(pdfconform=str(other)))
    cmd = conform.command()
    assert cmd[-1] == str(other) and cmd[0].endswith("python3")
    settings.save(settings.Settings(pdfconform=str(tmp_path / "missing")))
    assert conform.command() is None


def test_finding_the_old_name(tmp_path, monkeypatch):
    """Before version 2.0, pdf2iso was called py-pdfconform: that name is
    still found, but pdf2iso comes first."""
    from py_redact import conform

    home = tmp_path / "home"
    (home / "bin").mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("PATH", "/usr/bin:/bin")
    old = home / "bin" / "py-pdfconform.py"
    old.write_text("#!/bin/sh\n")
    old.chmod(0o755)
    assert conform.find() == old
    new = home / "bin" / "pdf2iso"
    new.write_text("#!/bin/sh\n")
    new.chmod(0o755)
    assert conform.find() == new


def test_bookmark_leaks_and_removal(tmp_path):
    from py_redact.redact import bookmark_leaks, remove_bookmarks

    doc = pymupdf.open()
    for text in ("Creating headers", "Creating watermarks"):
        doc.new_page().insert_text((72, 100), text, fontsize=14)
    doc.set_toc([[1, "Chapter 4", 1], [2, "Creating headers", 1], [2, "Creating watermarks", 2],
                 [3, "Watermark sizes", 2], [1, "The end", 1]])
    path, out = tmp_path / "in.pdf", tmp_path / "out.pdf"
    doc.save(path)
    boxes = [Box(1, (60, 80, 300, 110))]
    write_redacted(path, boxes, out)
    leaks = bookmark_leaks(path, out, boxes)
    assert [(i, t) for i, t, _ in leaks] == [(2, "Creating watermarks")] and "watermarks" in leaks[0][2]
    remove_bookmarks(out, {i for i, _, _ in leaks})
    assert pymupdf.open(out).get_toc() == [[1, "Chapter 4", 1], [2, "Creating headers", 1], [1, "The end", 1]]
    remove_bookmarks(out)
    assert pymupdf.open(out).get_toc() == []


def test_bookmark_to_no_page(tmp_path):
    from py_redact.redact import bookmark_leaks

    doc = pymupdf.open()
    doc.new_page().insert_text((72, 100), "Only page", fontsize=14)
    doc.set_toc([[1, "Gone chapter", -1], [1, "Here", 1]])
    path = tmp_path / "in.pdf"
    doc.save(path)
    assert [t for _, t, _ in bookmark_leaks(path, path, [])] == ["Gone chapter"]


def test_page_labels_are_hidden_information(tmp_path):
    from py_redact import hidden
    from py_redact.redact import sanitize

    doc = pymupdf.open()
    for _ in range(3):
        doc.new_page()
    doc.set_page_labels([{"startpage": 0, "prefix": "", "style": "D", "firstpagenum": 82}])
    path, out = tmp_path / "in.pdf", tmp_path / "out.pdf"
    doc.save(path)
    assert hidden.inspect(pymupdf.open(path))["page_labels"] == 1
    sanitize(path, out, kinds={"page_labels"})
    copy = pymupdf.open(out)
    assert hidden.inspect(copy)["page_labels"] == 0 and copy[0].get_label() == ""
