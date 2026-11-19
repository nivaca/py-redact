"""Rendering pages in a process of its own (see gui/renderer.py): MuPDF keeps
Python's lock while it renders, and a scanned page can take a fifth of a
second, so rendering in the window's process would stop the window meanwhile.

Nothing here uses Qt: the process imports only this and PyMuPDF.
"""

from __future__ import annotations

import pymupdf

KEPT = 3  # documents kept open (one per window, usually)
_docs: dict[str, tuple[tuple, pymupdf.Document]] = {}  # path -> (stamp, the document)


def _document(path: str, password: str, stamp: tuple) -> pymupdf.Document:
    """The document at PATH, opened again if it changed (another STAMP)."""
    held = _docs.pop(path, None)
    if held is not None and held[0] == stamp:
        _docs[path] = held  # (the last used, last)
        return held[1]
    if held is not None:
        held[1].close()
    doc = pymupdf.open(path)
    if doc.needs_pass:
        doc.authenticate(password)
    _docs[path] = (stamp, doc)
    while len(_docs) > KEPT:
        _docs.pop(next(iter(_docs)))[1].close()
    return doc


def render(path: str, password: str, stamp: tuple, number: int, scale: float) -> tuple[int, int, int, bytes]:
    """Page NUMBER of the document at PATH rendered at SCALE: its width,
    height, bytes per line and RGB pixels."""
    pix = _document(path, password, stamp)[number].get_pixmap(matrix=pymupdf.Matrix(scale, scale), alpha=False)
    return pix.width, pix.height, pix.stride, bytes(pix.samples)
