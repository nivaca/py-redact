from __future__ import annotations

import os

import pymupdf
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(autouse=True)
def own_config(tmp_path, monkeypatch):
    """A configuration folder of its own, so the tests don't read or change the user's."""
    monkeypatch.setenv("PY_REDACT_CONFIG", str(tmp_path / "config"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    from py_redact import interface

    interface.use(None)


@pytest.fixture
def sample(tmp_path):
    """A PDF of 5 pages: a header on each, a name on each, and a body of text."""
    path = tmp_path / "sample.pdf"
    doc = pymupdf.open()
    for i in range(5):
        page = doc.new_page()  # (595 × 842 points)
        page.insert_text((72, 60), f"HEADER{i + 1}", fontsize=14)
        page.insert_text((72, 120), f"Name: Person{i + 1}", fontsize=12)
        page.insert_text((72, 300), "Body text stays", fontsize=12)
    doc.save(path)
    return path
