"""The metadata of a PDF: the fields of its Info dictionary (title, author,
subject, keywords, creator, producer, dates, trapped, and any others a
program put there), its language (/Lang of the catalog) and its XMP metadata
(an XML packet). read() takes them from a document and write() gives a
document exactly these, removing what isn't there.

Dates are kept as PDF writes them (D:20261117125728Z, or with an offset,
D:20261117075728-05'00'); text_date() and pdf_date() turn them into
2026-11-17 07:57:28 -05:00 and back.
"""

from __future__ import annotations

import dataclasses
import re
from datetime import datetime, timedelta, timezone

import pymupdf

from .interface import N_

# (the key in the Info dictionary, the name shown) of the fields every PDF may have
STANDARD = [("Title", N_("Title")), ("Author", N_("Author")), ("Subject", N_("Subject")),
            ("Keywords", N_("Keywords")), ("Creator", N_("Creator")), ("Producer", N_("Producer")),
            ("CreationDate", N_("Created")), ("ModDate", N_("Modified")), ("Trapped", N_("Trapped"))]
DATES = ("CreationDate", "ModDate")
TRAPPED = ("True", "False", "Unknown")
KEY = re.compile(r"[A-Za-z][A-Za-z0-9_.-]*")  # (a key a custom field may have)


@dataclasses.dataclass(frozen=True)
class Metadata:
    info: tuple[tuple[str, str], ...] = ()  # (key, value): the standard fields, then the others
    language: str = ""
    xmp: str = ""

    def get(self, key: str) -> str:
        return dict(self.info).get(key, "")

    def custom(self) -> list[tuple[str, str]]:
        standard = {k for k, _ in STANDARD}
        return [(k, v) for k, v in self.info if k not in standard]

    def is_empty(self) -> bool:
        return not (any(v for _, v in self.info) or self.language or self.xmp.strip())


def _info_xref(doc: pymupdf.Document) -> int:
    kind, value = doc.xref_get_key(-1, "Info")
    if kind == "xref":
        return int(value.split()[0])
    return 0


def read(doc: pymupdf.Document) -> Metadata:
    info = []
    xref = _info_xref(doc)
    if xref:
        for key in doc.xref_get_keys(xref):
            kind, value = doc.xref_get_key(xref, key)
            if kind == "name":
                value = value.lstrip("/")
            elif kind not in ("string", "text"):
                continue  # (a dictionary or an array: not something to show as a field)
            info.append((key, value))
    order = {k: i for i, (k, _) in enumerate(STANDARD)}
    info.sort(key=lambda kv: order.get(kv[0], len(order)))
    kind, lang = doc.xref_get_key(doc.pdf_catalog(), "Lang")
    return Metadata(tuple(info), lang if kind == "string" else "", doc.get_xml_metadata())


def write(doc: pymupdf.Document, meta: Metadata) -> None:
    """Give DOC (in memory) exactly META: fields that META hasn't, or has
    empty, are removed, and so are the language and the XMP if empty."""
    wanted = {k: v for k, v in meta.info if v.strip()}
    xref = _info_xref(doc)
    if not xref and wanted:
        doc.set_metadata({"title": " "})  # (makes the Info dictionary; the title is set below)
        xref = _info_xref(doc)
    if xref:
        for key in doc.xref_get_keys(xref):
            if key not in wanted:
                doc.xref_set_key(xref, key, "null")
        for key, value in wanted.items():
            if key == "Trapped":
                doc.xref_set_key(xref, key, "/" + value)
            else:
                doc.xref_set_key(xref, key, pymupdf.get_pdf_str(value))
    doc.xref_set_key(doc.pdf_catalog(), "Lang",
                     pymupdf.get_pdf_str(meta.language) if meta.language.strip() else "null")
    if meta.xmp.strip():
        doc.set_xml_metadata(meta.xmp)
    else:
        doc.del_xml_metadata()


_PDF_DATE = re.compile(r"D?:?(\d{4})(\d{2})?(\d{2})?(\d{2})?(\d{2})?(\d{2})?(Z|[+-]\d{2}'?\d{2}'?)?")
_TEXT_DATE = re.compile(r"(\d{4})-(\d{2})-(\d{2})(?:[ T](\d{2}):(\d{2})(?::(\d{2}))?)?\s*(Z|UTC|[+-]\d{2}:?\d{2})?")


def text_date(pdf: str) -> str:
    """A PDF date (D:20261117075728-05'00') as 2026-11-17 07:57:28 -05:00; the
    same text if it can't be read."""
    m = _PDF_DATE.fullmatch(pdf.strip())
    if not m:
        return pdf
    y, mo, d, h, mi, s, tz = m.groups()
    text = f"{y}-{mo or '01'}-{d or '01'} {h or '00'}:{mi or '00'}:{s or '00'}"
    if tz == "Z":
        text += " +00:00"
    elif tz:
        digits = tz.replace("'", "")
        text += f" {digits[:3]}:{digits[3:5]}"
    return text


def pdf_date(text: str) -> str | None:
    """2026-11-17 07:57:28 -05:00 (or 2026-11-17, or with Z) as a PDF date; None
    if it isn't a date."""
    m = _TEXT_DATE.fullmatch(text.strip())
    if not m:
        return None
    y, mo, d, h, mi, s, tz = m.groups()
    try:
        datetime(int(y), int(mo), int(d), int(h or 0), int(mi or 0), int(s or 0))
    except ValueError:
        return None
    out = f"D:{y}{mo}{d}{h or '00'}{mi or '00'}{s or '00'}"
    if tz in ("Z", "UTC"):
        out += "Z"
    elif tz:
        digits = tz.replace(":", "")
        out += f"{digits[:3]}'{digits[3:5]}'"
    return out


def now() -> str:
    """This moment, as text_date writes dates."""
    local = datetime.now(timezone.utc).astimezone()
    offset = local.utcoffset() or timedelta(0)
    sign = "-" if offset < timedelta(0) else "+"
    minutes = abs(int(offset.total_seconds())) // 60
    return local.strftime("%Y-%m-%d %H:%M:%S") + f" {sign}{minutes // 60:02d}:{minutes % 60:02d}"
