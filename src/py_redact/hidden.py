"""Hidden information, as Acrobat's "Remove hidden information" finds it:
what a PDF holds besides what its pages show. inspect() says what a document
has of each kind; remove() takes out the kinds chosen.
"""

from __future__ import annotations

import pymupdf

from .interface import N_

# (key, name shown, what it is)
KINDS = [
    ("metadata", N_("Metadata"), N_("Title, author, subject, keywords, the program that made it (and the XMP)")),
    ("attachments", N_("Attached files"), N_("Files attached to the document or to its pages")),
    ("bookmarks", N_("Bookmarks"), N_("The outline, which may show headings of removed pages")),
    ("comments", N_("Comments and markups"), N_("Notes, highlights and other annotations (links are below)")),
    ("forms", N_("Form fields"), N_("Fields and their values; they are flattened: what they show stays, as "
                                    "part of the page")),
    ("hidden_text", N_("Hidden text"), N_("Text that is not drawn (invisible), such as an OCR layer")),
    ("links", N_("Links, actions and JavaScript"), N_("Links to pages and web addresses, actions and scripts")),
    ("thumbnails", N_("Page thumbnails"), N_("Small pictures of the pages, made before any redaction")),
    ("unused", N_("Deleted or unused content"), N_("Objects that nothing uses any more, as earlier versions of "
                                                   "the document leave them")),
]
DEFAULT = ("metadata", "attachments", "comments", "hidden_text", "links", "thumbnails", "unused")


def _hidden_text_spans(page: pymupdf.Page) -> int:
    """How many pieces of text of PAGE are not drawn (text render mode 3)."""
    n = 0
    for trace in page.get_texttrace():
        if trace.get("type") == 3 or trace.get("opacity", 1) == 0:
            n += 1
    return n


def inspect(doc: pymupdf.Document) -> dict[str, int]:
    """{kind: how many} of what DOC holds (0: none; -1: some, not counted)."""
    found = {k: 0 for k, _, _ in KINDS}
    meta = {k: v for k, v in (doc.metadata or {}).items() if v and k not in ("format", "encryption")}
    found["metadata"] = len(meta) + (1 if doc.get_xml_metadata().strip() else 0)
    found["attachments"] = doc.embfile_count()
    found["bookmarks"] = len(doc.get_toc(simple=True))
    for page in doc:
        for annot in page.annots() or []:
            if annot.type[0] == pymupdf.PDF_ANNOT_FILE_ATTACHMENT:
                found["attachments"] += 1
            elif annot.type[0] not in (pymupdf.PDF_ANNOT_LINK, pymupdf.PDF_ANNOT_REDACT, pymupdf.PDF_ANNOT_WIDGET):
                found["comments"] += 1
        found["forms"] += len(list(page.widgets() or []))
        found["links"] += len(page.get_links())
        found["hidden_text"] += _hidden_text_spans(page)
        if page.get_contents() and "/Thumb" in doc.xref_object(page.xref):
            found["thumbnails"] += 1
    try:
        if doc.xref_get_key(doc.pdf_catalog(), "Names/JavaScript")[0] != "null" \
                or doc.xref_get_key(doc.pdf_catalog(), "OpenAction")[0] != "null":
            found["links"] += 1
    except (RuntimeError, ValueError):
        pass
    found["unused"] = -1  # (known only once the file is written again)
    return found


def remove(doc: pymupdf.Document, kinds: set[str]) -> None:
    """Take out of DOC (in memory) the KINDS of hidden information. The
    'unused' objects go when DOC is saved with garbage collection, as
    write_redacted always does."""
    if "forms" in kinds:  # (flattened first: its looks stay on the page)
        doc.bake(annots=False, widgets=True)
    if "comments" in kinds:
        for page in doc:
            for annot in list(page.annots() or []):
                if annot.type[0] not in (pymupdf.PDF_ANNOT_LINK, pymupdf.PDF_ANNOT_REDACT,
                                         pymupdf.PDF_ANNOT_FILE_ATTACHMENT):
                    page.delete_annot(annot)
    doc.scrub(attached_files="attachments" in kinds, clean_pages=False, embedded_files="attachments" in kinds,
              hidden_text="hidden_text" in kinds, javascript="links" in kinds, metadata="metadata" in kinds,
              redactions=False, remove_links="links" in kinds, reset_fields=False, reset_responses=False,
              thumbnails="thumbnails" in kinds, xml_metadata="metadata" in kinds)
    if "metadata" in kinds:
        doc.set_metadata({})
    if "bookmarks" in kinds:
        doc.set_toc([])
