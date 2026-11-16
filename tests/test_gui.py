"""The window, driven as the user would: drawing, moving and resizing boxes with the mouse."""

from __future__ import annotations

import shutil

import pymupdf
import pytest
from PySide6.QtCore import QEvent, QPointF, Qt  # noqa: F401
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication, QMessageBox

from py_redact import settings
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
    assert w.canvas.mode == "text"  # (the tool on startup)
    w.set_tool("box")
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
    drag(window, (60, 105), (300, 126))
    # (a new box takes neither the pages nor the colour of the one before: only the default colour)
    assert (window.boxes[1].color, window.boxes[1].repeat) == ("#000000", "")
    window.set_repeat("2-")
    window.result_box.setChecked(True)
    window.result_box.setChecked(False)
    out = tmp_path / "out.pdf"
    assert window.save_to(out)
    assert not window.is_modified()
    pages = [p.get_text() for p in pymupdf.open(out)]
    assert "HEADER1" in pages[0] and not any("HEADER" in t or "Person" in t for t in pages[1:])


def test_default_colour_is_kept(window):
    drag(window, (60, 40), (300, 66))
    window.set_color("#ff0000")
    window.set_default_color(window.boxes[0].color)  # (Make red the colour of new boxes)
    window.pick([], False)
    drag(window, (60, 105), (300, 126))
    assert window.boxes[1].color == "#ff0000"
    assert settings.load().color == "#ff0000"
    window.pick([], False)
    window.set_color("#ffffff")  # (nothing selected: the default)
    assert settings.load().color == "#ffffff" and [b.color for b in window.boxes] == ["#ff0000", "#ff0000"]


def test_text_tool_still_moves_boxes(window):
    drag(window, (60, 40), (300, 66))
    window.set_tool("text")
    drag(window, (150, 50), (170, 60))  # (on a box: moves it, selects no text)
    assert len(window.boxes) == 1 and close(window.boxes[0].rect, (80, 50, 320, 76))


def test_find_and_redact(window, tmp_path):
    window.find_dialog("person")
    finder = window.finder
    assert len(finder.matches) == 5 and "5" in finder.summary.text()
    finder.results.setCurrentRow(2)  # (shows the place)
    assert window.page == 2
    finder.results.item(0).setCheckState(Qt.CheckState.Unchecked)
    finder.mark.emit(finder.ticked())
    assert sorted(b.page for b in window.boxes) == [1, 2, 3, 4]
    finder.mark.emit(finder.ticked(all_=True))  # (not twice over the same place)
    assert sorted(b.page for b in window.boxes) == [0, 1, 2, 3, 4]
    out = tmp_path / "out.pdf"
    assert window.save_to(out)
    assert not any("Person" in p.get_text() for p in pymupdf.open(out))


def test_find_options(window):
    window.find_dialog()
    f = window.finder
    f.query.setText("PERSON")
    f.case.setChecked(True)
    f.search()
    assert f.matches == []
    f.case.setChecked(False)
    f.scope.setCurrentIndex(3)
    f.pages.setText("2-3")
    f.search()
    assert [m.page for m in f.matches] == [1, 2]
    f.regex.setChecked(True)
    f.query.setText(r"Person[13]")
    f.scope.setCurrentIndex(0)
    f.search()
    assert [m.page for m in f.matches] == [0, 2]
    f.query.setText("(unclosed")
    f.search()
    assert f.matches == [] and f.summary.text()


def menu_texts(window, monkeypatch, index, point):
    seen = []

    def fake_exec(menu, *_):
        def walk(m, depth=0):
            for act in m.actions():
                seen.append(("  " * depth) + act.text())
                if act.menu():
                    walk(act.menu(), depth + 1)
        walk(menu)

    monkeypatch.setattr(window, "show_menu", fake_exec)
    window.box_menu(index, None, QPointF(*point))
    return seen


def test_menus_fit_where_they_are(window, monkeypatch):
    texts = menu_texts(window, monkeypatch, -1, (80, 116))  # (on the word "Name:")
    assert texts[0] == "“Name:”" and "Redact it on every page…" in texts
    assert not any("Select the" in t for t in texts)  # (no boxes on the page)
    drag(window, (70, 108), (200, 125))
    texts = menu_texts(window, monkeypatch, 0, (100, 116))
    assert texts[0] == "Apply the redaction…" and texts[2].startswith("Box drawn on page 1")
    assert any(t.startswith("Redact “Name: Person1”") for t in texts) and "Properties…" in texts
    assert not any("Up to page" in t for t in texts)  # (it is on page 1)
    window.mark_matches(window._find("Name", [0]))  # (inside the box: still marked)
    window._edit_menu()
    assert window.a_select_all.isEnabled() and window.a_undo.text() == "Undo (2)"


def test_select_text(window):
    window.set_tool("text")
    window.set_tool("text")
    drag(window, (75, 115), (150, 118))  # (over "Name: Person1")
    assert len(window.boxes) == 1 and window.boxes[0].page == 0
    x0, y0, x1, y1 = window.boxes[0].rect
    assert x0 < 73 and x1 > 150 and y0 < 112 and y1 > 120
    window.set_tool("box")
    out = window.path.with_name("t.pdf")
    assert window.save_to(out)
    text = pymupdf.open(out)[0].get_text()
    assert "Person1" not in text and "HEADER1" in text and "Body text stays" in text


def test_select_text_over_lines(window):
    window.set_tool("text")
    drag(window, (75, 55), (110, 300))  # (from the header to the body: three lines)
    assert len(window.boxes) == 3


def test_quitting_asks_until_saved(window, tmp_path, monkeypatch):
    asked = []
    monkeypatch.setattr(window, "ask_unsaved", lambda: asked.append(1) or QMessageBox.StandardButton.Cancel)
    drag(window, (60, 40), (300, 66))
    assert not window.close() and asked == [1] and window.isVisible()
    assert window.save_to(tmp_path / "out.pdf")
    assert window.close() and asked == [1]


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


@pytest.mark.skipif(not shutil.which("py-pdfconform"), reason="py-pdfconform not installed")
@pytest.mark.parametrize("standard", ["a-2b", "x-4"])
def test_save_as_pdfa_or_pdfx(window, tmp_path, standard):
    drag(window, (60, 105), (300, 126))
    window.output_actions[standard].trigger()
    assert window.output() == standard and settings.load().output == standard
    assert "PDF/" in window.a_save.text()
    out = tmp_path / "out.pdf"
    assert window.save_to(out)
    doc = pymupdf.open(out)
    raw = out.read_bytes()
    assert (b"pdfaid:part" in raw or b"pdfaid" in raw) if standard.startswith("a") else b"GTS_PDFX" in raw
    assert "Person1" not in doc[0].get_text() and "PDF/" in window.statusBar().currentMessage()


def test_pdfa_greyed_without_py_pdfconform(app, sample, tmp_path, monkeypatch):
    from py_redact import conform

    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(conform, "command", lambda: None)
    settings.save(settings.Settings(output="a-2b"))  # (chosen when it was there)
    w = MainWindow()
    assert not w.output_actions["a-2b"].isEnabled() and w.output_actions[""].isChecked()
    assert w.output() == "" and w.a_save.text() == "Save the redacted copy…"
    w.close()


def test_toolbar_has_icons(window):
    buttons = [a for a in window.toolbar.actions() if not a.isSeparator()]
    assert buttons and all(not a.icon().isNull() for a in buttons)
    assert window.toolbar.toolButtonStyle() == Qt.ToolButtonStyle.ToolButtonIconOnly
    window.a_labels.trigger()
    assert window.toolbar.toolButtonStyle() == Qt.ToolButtonStyle.ToolButtonTextUnderIcon


def double_click(w, point):
    c = w.canvas
    pos = c.mapFromScene(*point)
    c.mouseDoubleClickEvent(QMouseEvent(QEvent.Type.MouseButtonDblClick, QPointF(pos),
                                        QPointF(c.viewport().mapToGlobal(pos)), Qt.MouseButton.LeftButton,
                                        Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier))
    QApplication.processEvents()


def test_one_tool_for_text_and_areas(window):
    window.set_tool("text")
    drag(window, (300, 400), (400, 500))  # (no text there: a box)
    assert len(window.boxes) == 1 and close(window.boxes[0].rect, (300, 400, 400, 500))
    drag(window, (75, 115), (150, 118))  # (over text: the text)
    assert len(window.boxes) == 2 and window.boxes[1].rect[3] < 125
    drag(window, (80, 296), (150, 330), Qt.KeyboardModifier.ControlModifier)  # (Ctrl: a box, even over text)
    assert len(window.boxes) == 3 and close(window.boxes[2].rect, (80, 296, 150, 330))


def test_double_click_a_word(window):
    window.set_tool("text")
    double_click(window, (120, 116))  # ("Person1")
    assert len(window.boxes) == 1
    x0, y0, x1, y1 = window.boxes[0].rect
    assert x0 > 100 and x1 < 160


def test_locked_boxes_stay(window):
    drag(window, (60, 40), (300, 66))
    window.set_locked(True)
    drag(window, (150, 50), (170, 60))
    assert close(window.boxes[0].rect, (60, 40, 300, 66))
    window.delete_selected()
    window.delete_all = lambda: None
    assert len(window.boxes) == 1
    window.set_locked(False)
    window.delete_selected()
    assert window.boxes == []


def test_properties_and_default(window, tmp_path, monkeypatch):
    from py_redact.gui import props

    drag(window, (60, 105), (300, 126))

    def fake_exec(dialog):
        dialog.fill.set_color("")
        dialog.text.setText("  [name]  ")
        dialog.text_color.set_color("#ff0000")
        dialog.note.setText("from the register")
        dialog.as_default.setChecked(True)
        return props.QDialog.DialogCode.Accepted

    monkeypatch.setattr(props.PropertiesDialog, "exec", fake_exec)
    window.properties_dialog()
    box = window.boxes[0]
    assert (box.color, box.text, box.text_color, box.note) == ("", "[name]", "#ff0000", "from the register")
    assert settings.load().text == "[name]" and settings.load().color == ""
    window.pick([], False)
    drag(window, (60, 40), (300, 66))
    assert (window.boxes[1].text, window.boxes[1].color, window.boxes[1].note) == ("[name]", "", "")
    out = tmp_path / "out.pdf"
    assert window.save_to(out)
    assert "checked" in window.statusBar().currentMessage()
    assert "Person1" not in pymupdf.open(out)[0].get_text()


def test_hand_tool_draws_nothing(window):
    window.set_tool("hand")
    drag(window, (300, 400), (400, 500))
    assert window.boxes == [] and window.a_tool_hand.isChecked()


def test_sanitize(window, tmp_path, monkeypatch):
    from py_redact.gui import window as w

    out = tmp_path / "clean.pdf"
    monkeypatch.setattr(w.QFileDialog, "getSaveFileName", lambda *a, **k: (str(out), ""))
    assert window.sanitize_dialog()
    assert "Person1" in pymupdf.open(out)[0].get_text()
