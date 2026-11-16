"""The window, driven as the user would: drawing, moving and resizing boxes with the mouse."""

from __future__ import annotations

import pymupdf
import pytest
from PySide6.QtCore import QEvent, QPointF, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication

from py_redact.gui.window import MainWindow


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def window(app, sample, tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))  # (QSettings)
    w = MainWindow()
    w.resize(1200, 800)
    w.show()
    app.processEvents()
    assert w.open_path(sample)
    app.processEvents()
    yield w
    w.boxes = w.saved = []
    w.close()


def drag(w, start, end, mods=Qt.KeyboardModifier.NoModifier):
    """Drag with the mouse on the page, from START to END (in points)."""
    c = w.canvas
    a, b = c.mapFromScene(*start), c.mapFromScene(*end)
    for kind, pos, button, handler in ((QEvent.Type.MouseButtonPress, a, Qt.MouseButton.LeftButton, c.mousePressEvent),
                                       (QEvent.Type.MouseMove, b, Qt.MouseButton.NoButton, c.mouseMoveEvent),
                                       (QEvent.Type.MouseButtonRelease, b, Qt.MouseButton.LeftButton,
                                        c.mouseReleaseEvent)):
        handler(QMouseEvent(kind, QPointF(pos), QPointF(c.viewport().mapToGlobal(pos)), button,
                            Qt.MouseButton.LeftButton, mods))
    QApplication.processEvents()


def close(a, b, tolerance=2.0):
    return all(abs(x - y) <= tolerance for x, y in zip(a, b))


def test_draw_move_resize(window):
    drag(window, (60, 40), (300, 66))
    assert len(window.boxes) == 1 and window.selected == [0]
    assert close(window.boxes[0].rect, (60, 40, 300, 66))
    drag(window, (150, 50), (170, 60))  # (inside: moves it)
    assert close(window.boxes[0].rect, (80, 50, 320, 76))
    drag(window, (320, 76), (400, 100))  # (its corner: resizes it)
    assert close(window.boxes[0].rect, (80, 50, 400, 100))
    window.undo()
    window.undo()
    assert close(window.boxes[0].rect, (60, 40, 300, 66))
    window.redo()
    assert close(window.boxes[0].rect, (80, 50, 320, 76))


def test_tiny_drag_draws_nothing(window):
    drag(window, (60, 40), (61, 41))
    assert window.boxes == []


def test_colour_and_repeat_then_save(window, tmp_path):
    drag(window, (60, 40), (300, 66))
    window.set_color("#ffffff")
    window.set_repeat("2-")
    assert (window.boxes[0].color, window.boxes[0].repeat) == ("#ffffff", "2-")
    assert window.pages.item(3).text().endswith("● 1")
    window.set_repeat("nonsense")
    assert window.boxes[0].repeat == "2-"
    window.pick([], False)
    drag(window, (60, 105), (300, 126))  # (new boxes take the last colour and pages)
    assert (window.boxes[1].color, window.boxes[1].repeat) == ("#ffffff", "2-")
    window.result_box.setChecked(True)
    window.result_box.setChecked(False)
    out = tmp_path / "out.pdf"
    assert window.save_to(out)
    assert not window.is_modified()
    pages = [p.get_text() for p in pymupdf.open(out)]
    assert "HEADER1" in pages[0] and not any("HEADER" in t or "Person" in t for t in pages[1:])


def test_boxes_follow_the_page(window):
    drag(window, (60, 40), (300, 66))
    window.show_page(2)
    assert window.canvas.items_ == [] and window.selected == []
    window.pick([], False)
    window.show_page(0)
    window.select_page()
    window.set_repeat("all")
    window.show_page(2)
    assert [i.index for i in window.canvas.items_] == [0]
    window.select_page()
    window.delete_selected()
    assert window.boxes == []
