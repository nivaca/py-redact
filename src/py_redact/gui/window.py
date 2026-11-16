"""The main window: the pages of a PDF, the page being redacted with its
boxes, and the list of boxes with their colour and the pages they go on."""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path

import pymupdf
from PySide6.QtCore import QByteArray, QSettings, QSize, Qt, QTimer
from PySide6.QtGui import QAction, QActionGroup, QColor, QIcon, QImage, QKeySequence, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView, QApplication, QCheckBox, QColorDialog, QComboBox, QDialog, QFileDialog, QFormLayout, QHBoxLayout,
    QHeaderView, QInputDialog, QLabel, QLineEdit, QListView, QListWidget, QListWidgetItem, QMainWindow, QMenu,
    QMessageBox, QPushButton, QSpinBox, QSplitter, QTableWidget, QTableWidgetItem, QToolBar, QToolButton,
    QVBoxLayout, QWidget,
)

from .. import __version__, config, interface, settings
from ..interface import N_, ntr, tr
from ..pagesel import check
from ..redact import Box, PasswordError, RedactError, Rect, boxes_on, open_pdf, preview_page, write_redacted
from .canvas import PageCanvas, page_image
from .prefs import SettingsDialog

RECENT = 10  # documents in File ▸ Open recent
AUTHOR = '<a href="https://nicolasvaughan.org">Nicolas Vaughan</a>'
THUMB = QSize(84, 112)  # the largest thumbnail of a page
SWATCHES = [("#000000", N_("Black")), ("#ffffff", N_("White")), ("#808080", N_("Grey"))]
# the choices of "Pages": (what is kept in Box.repeat, its name); '*' is a list typed by the user
REPEATS = [("", N_("Only the page where it was drawn")), ("all", N_("All pages")), ("odd", N_("Odd pages")),
           ("even", N_("Even pages")), ("*", N_("These pages:"))]

_WINDOWS: list = []  # (windows built again in another language must stay referenced)


def install_qt_translations():
    """Qt's own texts (file dialogs, standard buttons) in the language in use."""
    from PySide6.QtCore import QLibraryInfo, QLocale, QTranslator

    app = QApplication.instance()
    for old in getattr(app, "_py_redact_translators", []):
        app.removeTranslator(old)
    app._py_redact_translators = []
    code = interface.code()
    QLocale.setDefault(QLocale(code))
    if code == "en":
        return
    folder = QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)
    for name in ("qtbase", "qt"):
        t = QTranslator(app)
        if t.load(f"{name}_{code}", folder):
            app.installTranslator(t)
            app._py_redact_translators.append(t)
            break


def swatch(color: str, size: int = 16) -> QIcon:
    pixmap = QPixmap(size, size)
    pixmap.fill(QColor(color))
    p = QPainter(pixmap)
    p.setPen(QColor(128, 128, 128))
    p.drawRect(0, 0, size - 1, size - 1)
    p.end()
    return QIcon(pixmap)


def color_name(color: str) -> str:
    for value, name in SWATCHES:
        if value == color.lower():
            return tr(name)
    return color.lower()


def mm(points: float) -> str:
    return f"{points / 72 * 25.4:.0f}"


class MainWindow(QMainWindow):
    def __init__(self, state: dict | None = None):
        """STATE (from export_state) carries the document over when the window is
        built again, for instance in another language."""
        super().__init__()
        self.setAcceptDrops(True)
        self.settings = QSettings("py-redact", "py-redact")
        self.path: Path | None = None
        self.password = ""
        self.doc: pymupdf.Document | None = None
        self.count = 0
        self.page = 0  # (0-based) the page shown
        self.boxes: list[Box] = []
        self.saved: list[Box] = []  # the boxes when the redacted copy was last saved
        self.undo_stack: list[list[Box]] = []
        self.redo_stack: list[list[Box]] = []
        self.selected: list[int] = []  # indices in self.boxes
        self.prefs = settings.load()  # (the default colour of new boxes, and how boxes are redacted)
        self._preview_doc: pymupdf.Document | None = None
        self._thumbs: dict[int, QImage] = {}  # page -> its picture, without the boxes
        self._rows: list[int] = []  # row of the table -> index of its box
        self._build()
        self._build_menus()
        self._restore()
        self.refresh()
        if state:
            self.adopt_state(state)

    # ----------------------------------------------------------------- construction

    def _build(self):
        self.pages = QListWidget()
        self.pages.setViewMode(QListView.ViewMode.IconMode)
        self.pages.setFlow(QListView.Flow.TopToBottom)
        self.pages.setWrapping(False)
        self.pages.setMovement(QListView.Movement.Static)
        self.pages.setIconSize(THUMB)
        self.pages.setGridSize(QSize(THUMB.width() + 28, THUMB.height() + 30))
        self.pages.setUniformItemSizes(True)
        self.pages.setMinimumWidth(THUMB.width() + 50)
        self.pages.setToolTip(tr("The pages; the number after ● is how many boxes a page has"))
        self.pages.currentRowChanged.connect(lambda row: self.show_page(row) if row >= 0 else None)
        self.thumb_timer = QTimer(self, interval=0)
        self.thumb_timer.timeout.connect(self._draw_thumbnails)

        self.canvas = PageCanvas()
        self.canvas.drawn.connect(self.add_box)
        self.canvas.edited.connect(self.move_box)
        self.canvas.picked.connect(self.pick)
        self.canvas.text_chosen.connect(self.add_text_boxes)
        self.canvas.menu_asked.connect(self.box_menu)
        self.canvas.zoom_changed.connect(lambda z: self.zoom_label.setText(f"{z * 100:.0f} %"))
        self.page_spin = QSpinBox()
        self.page_spin.setMinimum(1)
        self.page_spin.setPrefix(tr("Page "))
        self.page_spin.valueChanged.connect(lambda v: self.show_page(v - 1))
        self.zoom_label = QLabel("")
        self.result_box = QCheckBox(tr("Show the result"))
        self.result_box.setToolTip(tr("The page as it will be in the redacted copy (the boxes can't be changed "
                                      "while it is shown)"))
        self.result_box.toggled.connect(lambda _: self.show_page(self.page))
        top = QHBoxLayout()
        top.addWidget(self.page_spin)
        top.addStretch(1)
        top.addWidget(self.result_box)
        top.addWidget(self.zoom_label)
        center = QWidget()
        lay = QVBoxLayout(center)
        lay.setContentsMargins(4, 4, 4, 4)
        lay.addLayout(top)
        lay.addWidget(self.canvas, 1)
        hint = QLabel(tr("Drag on the page to draw a box (B), or over text to mark it (T). Drag a box to move it, or "
                         "its edges to resize it; right-click it for its pages and colour."))
        hint.setWordWrap(True)
        hint.setStyleSheet("color: palette(placeholder-text);")
        lay.addWidget(hint)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels([tr("Page"), tr("Goes on"), tr("Colour"), tr("Size (mm)")])
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.itemSelectionChanged.connect(self._table_selected)

        self.panel_title = QLabel()
        self.color_button = QToolButton()
        self.color_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.color_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        menu = QMenu(self.color_button)
        for value, name in SWATCHES:
            menu.addAction(swatch(value), tr(name), lambda v=value: self.set_color(v))
        menu.addSeparator()
        menu.addAction(tr("Other colour…"), self.choose_color)
        self.color_button.setMenu(menu)
        self.repeat_combo = QComboBox()
        for value, name in REPEATS:
            self.repeat_combo.addItem(tr(name), value)
        self.repeat_combo.activated.connect(self._repeat_chosen)
        self.repeat_edit = QLineEdit()
        self.repeat_edit.setPlaceholderText(tr("1-5, 8, 10-"))
        self.repeat_edit.setToolTip(tr("Pages and ranges, separated by commas: 3, 5-9, 12- (to the end), LAST, "
                                       "LAST-1"))
        self.repeat_edit.editingFinished.connect(self._repeat_typed)
        self.b_delete = QPushButton(tr("Delete"))
        self.b_delete.clicked.connect(self.delete_selected)
        form = QFormLayout()
        form.addRow(tr("Colour:"), self.color_button)
        form.addRow(tr("Pages:"), self.repeat_combo)
        form.addRow("", self.repeat_edit)
        right = QWidget()
        lay = QVBoxLayout(right)
        lay.setContentsMargins(4, 4, 4, 4)
        lay.addWidget(QLabel("<b>" + tr("Boxes") + "</b>"))
        lay.addWidget(self.table, 1)
        lay.addWidget(self.panel_title)
        lay.addLayout(form)
        lay.addWidget(self.b_delete, 0, Qt.AlignmentFlag.AlignRight)

        self.splitter = QSplitter()
        self.splitter.addWidget(self.pages)
        self.splitter.addWidget(center)
        self.splitter.addWidget(right)
        self.splitter.setStretchFactor(0, 0)
        self.splitter.setStretchFactor(1, 3)
        self.splitter.setStretchFactor(2, 1)
        self.splitter.setSizes([150, 750, 300])
        self.setCentralWidget(self.splitter)

    def _action(self, menu: QMenu | None, text: str, triggered, shortcut=None, tip: str = "") -> QAction:
        act = QAction(text, self, triggered=triggered)
        if shortcut is not None:
            act.setShortcuts(shortcut if isinstance(shortcut, list) else [QKeySequence(shortcut)])
        if tip:
            act.setToolTip(tip)
            act.setStatusTip(tip)
        if menu is not None:
            menu.addAction(act)
        return act

    def _build_menus(self):
        m = self.menuBar().addMenu(tr("&File"))
        m.setToolTipsVisible(True)
        self.a_open = self._action(m, tr("Open…"), self.open_dialog, QKeySequence.StandardKey.Open)
        self.m_recent = m.addMenu(tr("Open recent"))
        self._recent_menu()
        self.a_save = self._action(m, tr("Save the redacted copy…"), self.save_dialog,
                                   QKeySequence.StandardKey.Save,
                                   tr("Write a copy of the document with what is under the boxes removed"))
        self.a_clean = QAction(tr("Also remove metadata, hidden text, attachments and scripts"), self,
                               checkable=True)
        self.a_clean.setChecked(self.prefs.clean)
        self.a_clean.toggled.connect(lambda on: self.set_prefs(dataclasses.replace(self.prefs, clean=on)))
        self.a_clean.setToolTip(tr("Remove as well what the document holds besides its pages: its title, "
                                   "author and other metadata, text that isn't shown, attached files, "
                                   "JavaScript and links"))
        m.addAction(self.a_clean)
        m.addSeparator()
        self._action(m, tr("Quit"), self.close, QKeySequence.StandardKey.Quit)

        m = self.menuBar().addMenu(tr("&Edit"))
        self.a_undo = self._action(m, tr("Undo"), self.undo, QKeySequence.StandardKey.Undo)
        self.a_redo = self._action(m, tr("Redo"), self.redo, QKeySequence.StandardKey.Redo)
        m.addSeparator()
        self.a_delete = self._action(m, tr("Delete the selected boxes"), self.delete_selected,
                                     [QKeySequence(QKeySequence.StandardKey.Delete), QKeySequence("Backspace")])
        self.a_select_all = self._action(m, tr("Select the boxes of this page"), self.select_page,
                                         QKeySequence.StandardKey.SelectAll)
        self._action(m, tr("Select none"), lambda: self.pick([], False), "Escape")
        m.addSeparator()
        self.a_clear_page = self._action(m, tr("Delete the boxes drawn on this page"), self.delete_page)
        self.a_clear_all = self._action(m, tr("Delete all the boxes"), self.delete_all)

        m.addSeparator()
        tools = QActionGroup(self)
        self.a_tool_box = self._action(m, tr("Draw boxes"), lambda: self.set_tool("box"), "B",
                                       tr("Dragging on the page draws a box"))
        self.a_tool_text = self._action(m, tr("Select text"), lambda: self.set_tool("text"), "T",
                                        tr("Dragging over text selects it, and a box is made over each of its "
                                           "lines"))
        for act in (self.a_tool_box, self.a_tool_text):
            act.setCheckable(True)
            tools.addAction(act)
        self.a_tool_box.setChecked(True)

        m = self.menuBar().addMenu(tr("&View"))
        self.a_result = self._action(m, tr("Show the result"), self.result_box.toggle, "Ctrl+R")
        m.addSeparator()
        self.a_prev = self._action(m, tr("Previous page"), lambda: self.show_page(self.page - 1),
                                   [QKeySequence("PgUp")])
        self.a_next = self._action(m, tr("Next page"), lambda: self.show_page(self.page + 1),
                                   [QKeySequence("PgDown")])
        self.a_first = self._action(m, tr("First page"), lambda: self.show_page(0), "Ctrl+Home")
        self.a_last = self._action(m, tr("Last page"), lambda: self.show_page(self.count - 1), "Ctrl+End")
        m.addSeparator()
        self.a_fit = self._action(m, tr("Fit the page"), lambda: self._fit("page"), "Ctrl+0")
        self.a_fit_width = self._action(m, tr("Fit the width"), lambda: self._fit("width"), "Ctrl+9")
        self.a_zoom_in = self._action(m, tr("Zoom in"), lambda: self.canvas.zoom_by(1.25),
                                      [QKeySequence(QKeySequence.StandardKey.ZoomIn), QKeySequence("Ctrl+=")])
        self.a_zoom_out = self._action(m, tr("Zoom out"), lambda: self.canvas.zoom_by(1 / 1.25),
                                       QKeySequence.StandardKey.ZoomOut)

        m = self.menuBar().addMenu(tr("&Settings"))
        self._action(m, tr("Settings…"), self.settings_dialog, QKeySequence.StandardKey.Preferences)
        lang = m.addMenu(tr("Language"))
        group = QActionGroup(self)
        for code, name in interface.names().items():
            act = QAction(name, self, checkable=True)
            act.setChecked(code == interface.code())
            act.triggered.connect(lambda _=False, c=code: self.change_language(c))
            group.addAction(act)
            lang.addAction(act)
        m = self.menuBar().addMenu(tr("&Help"))
        self._action(m, tr("About"), self.about)

        bar = QToolBar(tr("Tools"))
        bar.setObjectName("tools")
        bar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        for act in (self.a_open, self.a_save, None, self.a_tool_box, self.a_tool_text, None, self.a_undo,
                    self.a_redo, self.a_delete, None, self.a_prev,
                    self.a_next, None, self.a_fit, self.a_fit_width, self.a_zoom_out, self.a_zoom_in):
            if act is None:
                bar.addSeparator()
            else:
                bar.addAction(act)
        self.addToolBar(bar)

    # ----------------------------------------------------------------- settings

    def _restore(self):
        geo = self.settings.value("geometry")
        if isinstance(geo, QByteArray):
            self.restoreGeometry(geo)
        else:
            self.resize(1280, 860)
        split = self.settings.value("splitter")
        if isinstance(split, QByteArray):
            self.splitter.restoreState(split)

    def save_settings(self):
        self.settings.setValue("geometry", self.saveGeometry())
        self.settings.setValue("splitter", self.splitter.saveState())
        self.settings.sync()

    def closeEvent(self, event):
        if not self.maybe_discard():
            event.ignore()
            return
        self.save_settings()
        super().closeEvent(event)

    def export_state(self) -> dict:
        """What a new window needs to carry on with the same document."""
        return {"path": self.path, "password": self.password, "boxes": self.boxes, "saved": self.saved,
                "undo": self.undo_stack, "redo": self.redo_stack, "page": self.page,
                "tool": self.canvas.mode}

    def adopt_state(self, state: dict):
        self.set_tool(state["tool"])
        if state["path"] is None or not self._load(state["path"], state["password"]):
            self.refresh()
            return
        self.boxes, self.saved = list(state["boxes"]), list(state["saved"])
        self.undo_stack, self.redo_stack = list(state["undo"]), list(state["redo"])
        self.refresh()
        self.show_page(state["page"])

    def last_dir(self) -> str:
        return self.settings.value("last_dir", str(Path.home()))

    # ----------------------------------------------------------------- language

    def change_language(self, code: str):
        """Use CODE for the interface, keep it in the configuration file, and
        build the window again in that language."""
        if code == interface.code():
            return
        if not interface.use(code):
            QMessageBox.warning(self, tr("Language"),
                                tr("The language of the interface could not be changed: {error}",
                                   error=interface.error()))
            interface.use(config.get("interface"))
            return
        try:
            config.set("interface", code)
        except OSError as e:
            self.status(tr("Could not keep the setting: {error}", error=e), error=True)
        install_qt_translations()
        self.save_settings()
        new = MainWindow(self.export_state())
        new.restoreGeometry(self.saveGeometry())
        new.show()
        _WINDOWS.append(new)
        self.boxes = self.saved = []  # (nothing to ask about: the new window has it)
        self.hide()
        self.deleteLater()
        if self in _WINDOWS:
            _WINDOWS.remove(self)

    # ----------------------------------------------------------------- documents

    def open_dialog(self):
        name, _ = QFileDialog.getOpenFileName(self, tr("Open PDF"), self.last_dir(), tr("PDF files (*.pdf)"))
        if name:
            self.open_path(Path(name))

    def open_path(self, path: Path) -> bool:
        if not path.is_file():
            self.status(tr("{path} not found", path=path), error=True)
            return False
        if not self.maybe_discard():
            return False
        password = ""
        while True:
            try:
                open_pdf(path, password).close()
                break
            except PasswordError:
                password = self.ask_password(path, again=bool(password))
                if password is None:
                    self.status(tr("{path} is protected by a password", path=path), error=True)
                    return False
            except RedactError as e:
                self.status(str(e), error=True)
                return False
        if not self._load(path, password):
            return False
        self.settings.setValue("last_dir", str(path.parent))
        self.add_recent(path)
        self.boxes, self.saved, self.undo_stack, self.redo_stack, self.selected = [], [], [], [], []
        self.refresh()
        self.show_page(0)
        self.status(ntr("Opened {path} ({count} page)", "Opened {path} ({count} pages)", self.count, path=path))
        return True

    def ask_password(self, path: Path, again: bool = False) -> str | None:
        text = tr("That password is not right. The password of {name}:", name=path.name) if again \
            else tr("{name} is protected. Its password:", name=path.name)
        password, ok = QInputDialog.getText(self, tr("Password"), text, QLineEdit.EchoMode.Password)
        return password if ok and password else None

    def _load(self, path: Path, password: str) -> bool:
        try:
            doc = open_pdf(path, password)
        except RedactError as e:
            self.status(str(e), error=True)
            return False
        if self.doc is not None:
            self.doc.close()
        self.doc, self.path, self.password, self.count = doc, path, password, doc.page_count
        self.page = 0
        self._thumbs = {}
        self._fill_pages()
        return True

    def save_dialog(self) -> bool:
        if self.path is None:
            return False
        if not self.boxes:
            self.status(tr("There are no boxes to redact"), error=True)
            return False
        bad = [b for b in self.boxes if b.repeat.strip() and check(b.repeat)]
        if bad:
            self.status(tr("A box has pages that can't be read: {error}", error=check(bad[0].repeat)), error=True)
            return False
        default = Path(self.last_dir()) / f"{self.path.stem}-redacted.pdf"
        name, _ = QFileDialog.getSaveFileName(self, tr("Save the redacted copy"), str(default),
                                              tr("PDF files (*.pdf)"))
        if not name:
            return False
        target = Path(name)
        if target.suffix.lower() != ".pdf":
            target = target.with_suffix(".pdf")
        return self.save_to(target)

    def save_to(self, target: Path) -> bool:
        replacing = target.resolve() == self.path.resolve()
        if replacing and QMessageBox.warning(
                self, tr("Replace the original"),
                tr("The redacted copy will take the place of {name}, and what is under the boxes will be lost "
                   "for good. Go on?", name=self.path.name),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Cancel) != QMessageBox.StandardButton.Yes:
            return False
        if replacing:  # (the file is about to change under the open document)
            self.doc.close()
            self.doc = None
        try:
            done = write_redacted(self.path, self.boxes, target, self.password, self.prefs.clean,
                                  self.prefs.images, self.prefs.drawings)
        except RedactError as e:
            if replacing:
                self._load(self.path, self.password)
                self.refresh()
            self.status(str(e), error=True)
            return False
        self.settings.setValue("last_dir", str(target.parent))
        self.add_recent(target)
        self.saved = list(self.boxes)
        if replacing:  # (the boxes are in the file now)
            page = self.page
            self._load(self.path, self.password)
            self.boxes, self.saved, self.undo_stack, self.redo_stack, self.selected = [], [], [], [], []
            self.refresh()
            self.show_page(page)
        self._update_title()
        self.status(ntr("Saved {path} ({count} area redacted)", "Saved {path} ({count} areas redacted)", done,
                        path=target))
        return True

    # ----------------------------------------------------------------- recent files

    def recent_files(self) -> list[Path]:
        try:
            names = json.loads(self.settings.value("recent", "[]"))
        except (TypeError, ValueError):
            names = []
        return [Path(n) for n in names if isinstance(n, str)][:RECENT]

    def _set_recent(self, paths: list[Path]):
        self.settings.setValue("recent", json.dumps([str(p) for p in paths[:RECENT]]))
        self._recent_menu()

    def add_recent(self, path: Path):
        path = path.resolve()
        self._set_recent([path] + [p for p in self.recent_files() if p != path])

    def clear_recent(self):
        self._set_recent([])

    def _recent_menu(self):
        m = self.m_recent
        m.clear()
        paths = self.recent_files()
        for i, path in enumerate(paths, 1):
            key = f"&{i}" if i < 10 else "1&0"
            act = m.addAction(f"{key} " + path.name.replace("&", "&&"), lambda p=path: self.open_path(p))
            act.setToolTip(str(path))
            act.setStatusTip(str(path))
        if paths:
            m.addSeparator()
        m.addAction(tr("Clear the list"), self.clear_recent).setEnabled(bool(paths))
        m.setToolTipsVisible(True)

    # ----------------------------------------------------------------- changing the boxes

    def change(self, boxes: list[Box], selected: list[int] | None = None):
        """Make BOXES the boxes (so that it can be undone), selecting SELECTED."""
        if boxes == self.boxes:
            return
        self.undo_stack.append(self.boxes)
        self.redo_stack.clear()
        self.boxes = boxes
        self.selected = [i for i in (selected or []) if i < len(boxes)]
        self.refresh()

    def add_box(self, rect: Rect):
        """A new box, of the default colour, only on the page shown (it never takes the pages of another)."""
        box = Box(self.page, rect, self.prefs.color)
        self.change(self.boxes + [box], [len(self.boxes)])

    def add_text_boxes(self, rects: list[Rect]):
        """A box over each line of the text selected."""
        new = [Box(self.page, r, self.prefs.color) for r in rects]
        self.change(self.boxes + new, list(range(len(self.boxes), len(self.boxes) + len(new))))
        self.status(ntr("{count} line of text marked", "{count} lines of text marked", len(new)))

    def set_tool(self, tool: str):
        self.canvas.mode = tool
        (self.a_tool_text if tool == "text" else self.a_tool_box).setChecked(True)
        self.canvas.viewport().unsetCursor()

    def move_box(self, index: int, rect: Rect):
        boxes = list(self.boxes)
        boxes[index] = dataclasses.replace(boxes[index], rect=rect)
        self.change(boxes, self.selected if index in self.selected else [index])

    def _change_selected(self, **changes):
        boxes = list(self.boxes)
        for i in self.selected:
            boxes[i] = dataclasses.replace(boxes[i], **changes)
        self.change(boxes, self.selected)

    def _remove(self, keep) -> None:
        """Remove the boxes for which KEEP(box) is false."""
        boxes = [b for b in self.boxes if keep(b)]
        if len(boxes) != len(self.boxes):
            self.change(boxes, [])

    def delete_selected(self):
        chosen = set(self.selected)
        self.change([b for i, b in enumerate(self.boxes) if i not in chosen], [])

    def delete_page(self):
        self._remove(lambda b: b.page != self.page)

    def delete_all(self):
        if self.boxes and QMessageBox.question(
                self, tr("Delete all the boxes"),
                ntr("Delete the {count} box of the document?", "Delete the {count} boxes of the document?",
                    len(self.boxes))) == QMessageBox.StandardButton.Yes:
            self._remove(lambda b: False)

    def set_color(self, color: str):
        """The colour of the selected boxes; with none selected, the default colour of new boxes."""
        if self.selected:
            self._change_selected(color=color)
        else:
            self.set_default_color(color)

    def set_default_color(self, color: str):
        self.set_prefs(dataclasses.replace(self.prefs, color=color))
        self.status(tr("New boxes will be {color}", color=color_name(color)))

    def choose_color(self):
        current = self.boxes[self.selected[0]].color if self.selected else self.prefs.color
        chosen = QColorDialog.getColor(QColor(current), self, tr("The colour of the boxes"))
        if chosen.isValid():
            self.set_color(chosen.name())

    # ----------------------------------------------------------------- settings

    def set_prefs(self, prefs: settings.Settings):
        """Use PREFS, and keep them in the configuration file."""
        changed = (prefs.images, prefs.drawings) != (self.prefs.images, self.prefs.drawings)
        self.prefs = prefs
        try:
            settings.save(prefs)
        except (OSError, ValueError) as e:
            self.status(tr("Could not keep the setting: {error}", error=e), error=True)
        self.a_clean.blockSignals(True)
        self.a_clean.setChecked(prefs.clean)
        self.a_clean.blockSignals(False)
        self._show_panel()
        if changed and self.result_box.isChecked():
            self.show_page(self.page, keep_view=True)

    def settings_dialog(self):
        dialog = SettingsDialog(self.prefs, swatch, color_name, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.set_prefs(dialog.settings())

    # ----------------------------------------------------------------- the menu of a box

    def box_menu(self, index: int, where):
        """The menu of the boxes selected (INDEX: the one clicked), or of the page if INDEX is -1."""
        menu = QMenu(self)
        if index >= 0 and self.selected:
            chosen = [self.boxes[i] for i in self.selected]
            repeats = {b.repeat.strip().lower() for b in chosen}
            pages = menu.addMenu(tr("Pages"))
            group = QActionGroup(pages)
            for value, name in REPEATS[:4]:
                act = pages.addAction(tr(name), lambda v=value: self.set_repeat(v))
                act.setCheckable(True)
                act.setChecked(repeats == {value})
                group.addAction(act)
            pages.addSeparator()
            page = chosen[0].page + 1
            pages.addAction(tr("From page {page} to the end", page=page), lambda: self.set_repeat(f"{page}-"))
            pages.addAction(tr("Up to page {page}", page=page), lambda: self.set_repeat(f"1-{page}"))
            act = pages.addAction(tr("These pages…"), self.ask_pages)
            act.setCheckable(True)
            act.setChecked(len(repeats) == 1 and repeats.pop() not in ("", "all", "odd", "even"))
            group.addAction(act)
            colors = menu.addMenu(tr("Colour"))
            for value, name in SWATCHES:
                colors.addAction(swatch(value), tr(name), lambda v=value: self._change_selected(color=v))
            colors.addSeparator()
            colors.addAction(tr("Other colour…"), self.choose_color)
            color = chosen[0].color
            act = menu.addAction(swatch(color), tr("Make {color} the colour of new boxes", color=color_name(color)),
                                 lambda: self.set_default_color(color))
            act.setEnabled(color != self.prefs.color)
            menu.addSeparator()
            menu.addAction(ntr("Delete the box", "Delete the {count} boxes", len(chosen)), self.delete_selected)
        else:
            colors = menu.addMenu(swatch(self.prefs.color), tr("Colour of new boxes"))
            for value, name in SWATCHES:
                colors.addAction(swatch(value), tr(name), lambda v=value: self.set_default_color(v))
            colors.addSeparator()
            colors.addAction(tr("Other colour…"), self.choose_color)
            menu.addAction(self.a_tool_box)
            menu.addAction(self.a_tool_text)
            menu.addSeparator()
            menu.addAction(tr("Settings…"), self.settings_dialog)
        menu.exec(where)

    def ask_pages(self):
        if not self.selected:
            return
        current = self.boxes[self.selected[0]].repeat
        if current.lower() in ("", "all", "odd", "even"):
            current = f"{self.boxes[self.selected[0]].page + 1}-"
        while True:
            text, ok = QInputDialog.getText(self, tr("Pages"),
                                            tr("Pages and ranges, separated by commas: 3, 5-9, 12- (to the end), "
                                               "LAST, LAST-1"), QLineEdit.EchoMode.Normal, current)
            if not ok or not text.strip():
                return
            error = check(text)
            if not error:
                self.set_repeat(text.strip())
                return
            QMessageBox.warning(self, tr("Pages"), error)
            current = text

    def set_repeat(self, repeat: str):
        error = check(repeat) if repeat.strip() else ""
        if error:
            self.status(error, error=True)
            self._show_panel()
            return
        if self.selected:
            self._change_selected(repeat=repeat)
        else:
            self._show_panel()

    def _repeat_chosen(self, row: int):
        value = self.repeat_combo.itemData(row)
        if value == "*":
            if not self.selected:
                return
            current = self.boxes[self.selected[0]].repeat
            if current.lower() in ("", "all", "odd", "even"):
                current = f"{self.page + 1}-"
            self.repeat_edit.setText(current)
            self.set_repeat(current)
            self.repeat_edit.setFocus()
            self.repeat_edit.selectAll()
        else:
            self.set_repeat(value)

    def _repeat_typed(self):
        if self.repeat_combo.currentData() == "*" and self.repeat_edit.isEnabled():
            text = self.repeat_edit.text().strip()
            if text:
                self.set_repeat(text)

    def undo(self):
        if self.undo_stack:
            self.redo_stack.append(self.boxes)
            self.boxes = self.undo_stack.pop()
            self.selected = []
            self.refresh()

    def redo(self):
        if self.redo_stack:
            self.undo_stack.append(self.boxes)
            self.boxes = self.redo_stack.pop()
            self.selected = []
            self.refresh()

    # ----------------------------------------------------------------- selection

    def pick(self, indices: list[int], add: bool):
        if add:
            chosen = list(self.selected)
            for i in indices:
                if i in chosen:
                    chosen.remove(i)
                else:
                    chosen.append(i)
        else:
            chosen = list(indices)
        if chosen != self.selected:
            self.selected = chosen
            self.refresh(pages=False)

    def select_page(self):
        self.pick([i for i, b in enumerate(self.boxes) if b.on(self.page, self.count)], False)

    def _table_selected(self):
        rows = sorted({i.row() for i in self.table.selectedIndexes()})
        chosen = [self._rows[r] for r in rows if r < len(self._rows)]
        if chosen == self.selected:
            return
        self.selected = chosen
        if chosen and not any(self.boxes[i].on(self.page, self.count) for i in chosen):
            self.show_page(self.boxes[chosen[0]].page)
        else:
            self.refresh(pages=False, table=False)

    # ----------------------------------------------------------------- showing

    def refresh(self, pages: bool = True, table: bool = True):
        """Show the boxes again, after a change."""
        if table:
            self._fill_table()
        if pages:
            self._label_pages()
        self.show_page(self.page, keep_view=True)
        self._show_panel()
        self._enable()
        self._update_title()

    def show_page(self, page: int, keep_view: bool = False):
        if self.doc is None:
            self.canvas.show_page(None, [], [])
            return
        page = max(0, min(page, self.count - 1))
        keep_view = keep_view or page == self.page
        if page != self.page:
            self.selected = [i for i in self.selected if self.boxes[i].on(page, self.count)]
            self.page = page
            self._show_panel()
            self._select_rows()
            self._enable()
        if self._preview_doc is not None:
            self._preview_doc.close()
            self._preview_doc = None
        if self.result_box.isChecked():
            self._preview_doc = preview_page(self.doc, page, self.boxes, self.prefs.images, self.prefs.drawings)
            self.canvas.show_page(self._preview_doc[0], [], [], editable=False, keep_view=keep_view)
        else:
            here = [(i, b, b.page == page) for i, b in enumerate(self.boxes) if b.on(page, self.count)]
            self.canvas.show_page(self.doc[page], here, self.selected, keep_view=keep_view)
        self.page_spin.blockSignals(True)
        self.page_spin.setValue(page + 1)
        self.page_spin.blockSignals(False)
        self.pages.blockSignals(True)
        self.pages.setCurrentRow(page)
        self.pages.blockSignals(False)

    def _fit(self, how: str):
        self.canvas.fit = how
        self.canvas.apply_fit()

    def _fill_pages(self):
        self.pages.clear()
        blank = QPixmap(THUMB)
        blank.fill(QColor(0, 0, 0, 0))
        for n in range(self.count):
            item = QListWidgetItem(QIcon(blank), str(n + 1))
            item.setTextAlignment(Qt.AlignmentFlag.AlignHCenter)
            self.pages.addItem(item)
        self.page_spin.blockSignals(True)
        self.page_spin.setMaximum(max(self.count, 1))
        self.page_spin.setSuffix(f" / {self.count}")
        self.page_spin.blockSignals(False)
        self.thumb_timer.start()

    def _draw_thumbnails(self):
        """Draw a few thumbnails at each turn of the event loop."""
        if self.doc is None:
            self.thumb_timer.stop()
            return
        todo = [n for n in range(self.count) if n not in self._thumbs][:6]
        if not todo:
            self.thumb_timer.stop()
            return
        for n in todo:
            page = self.doc[n]
            scale = min(THUMB.width() / page.rect.width, THUMB.height() / page.rect.height)
            self._thumbs[n] = page_image(page, scale)
            self._thumb(n)

    def _thumb(self, n: int):
        """The thumbnail of page N, with its boxes."""
        image = self._thumbs.get(n)
        if image is None or n >= self.pages.count():
            return
        pixmap = QPixmap(THUMB)
        pixmap.fill(QColor(0, 0, 0, 0))
        p = QPainter(pixmap)
        x, y = (THUMB.width() - image.width()) // 2, THUMB.height() - image.height()
        p.drawImage(x, y, image)
        page = self.doc[n]
        scale = image.width() / page.rect.width
        for box in boxes_on(self.boxes, n, self.count):
            x0, y0, x1, y1 = (v * scale for v in box.rect)
            p.fillRect(int(x + x0), int(y + y0), max(int(x1 - x0), 1), max(int(y1 - y0), 1), QColor(box.color))
            p.setPen(QColor(128, 128, 128))
            p.drawRect(int(x + x0), int(y + y0), max(int(x1 - x0), 1), max(int(y1 - y0), 1))
        p.setPen(QPen(QColor(128, 128, 128)))
        p.drawRect(x, y, image.width() - 1, image.height() - 1)
        p.end()
        self.pages.item(n).setIcon(QIcon(pixmap))

    def _label_pages(self):
        if self.doc is None:
            return
        counts = [0] * self.count
        for box in self.boxes:
            for n in box.pages(self.count):
                counts[n] += 1
        for n in range(min(self.count, self.pages.count())):
            self.pages.item(n).setText(f"{n + 1}  ● {counts[n]}" if counts[n] else str(n + 1))
            self._thumb(n)

    def _covers(self, box: Box) -> str:
        for value, name in REPEATS[1:4]:
            if box.repeat.strip().lower() == value:
                return tr(name)
        if not box.repeat.strip():
            return tr("Its page")
        return box.repeat

    def _fill_table(self):
        order = sorted(range(len(self.boxes)), key=lambda i: (self.boxes[i].page, self.boxes[i].rect[1],
                                                              self.boxes[i].rect[0]))
        self._rows = order
        self.table.blockSignals(True)
        self.table.setRowCount(len(order))
        for row, i in enumerate(order):
            box = self.boxes[i]
            x0, y0, x1, y1 = box.rect
            cells = [QTableWidgetItem(str(box.page + 1)), QTableWidgetItem(self._covers(box)),
                     QTableWidgetItem(swatch(box.color), color_name(box.color)),
                     QTableWidgetItem(f"{mm(x1 - x0)} × {mm(y1 - y0)}")]
            cells[3].setToolTip(tr("{width} × {height} mm, {left} mm from the left and {top} mm from the top",
                                   width=mm(x1 - x0), height=mm(y1 - y0), left=mm(x0), top=mm(y0)))
            for col, cell in enumerate(cells):
                self.table.setItem(row, col, cell)
        self.table.resizeColumnToContents(0)
        self.table.blockSignals(False)
        self._select_rows()

    def _select_rows(self):
        self.table.blockSignals(True)
        self.table.clearSelection()
        mode = self.table.selectionMode()
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.MultiSelection)
        for row, i in enumerate(self._rows):
            if i in self.selected:
                self.table.selectRow(row)
        self.table.setSelectionMode(mode)
        self.table.blockSignals(False)

    def _show_panel(self):
        """The colour and pages of the selected boxes, or of new boxes if none is selected."""
        chosen = [self.boxes[i] for i in self.selected if i < len(self.boxes)]
        if chosen:
            self.panel_title.setText("<b>" + ntr("{count} box selected", "{count} boxes selected",
                                                 len(chosen)) + "</b>")
            colors = {b.color for b in chosen}
            repeats = {b.repeat.strip() for b in chosen}
        else:
            self.panel_title.setText("<b>" + tr("New boxes") + "</b>")
            colors, repeats = {self.prefs.color}, {""}
        color = colors.pop() if len(colors) == 1 else None
        self.color_button.setIcon(swatch(color) if color else QIcon())
        self.color_button.setText(color_name(color) if color else tr("(several)"))
        repeat = repeats.pop() if len(repeats) == 1 else None
        values = [v for v, _ in REPEATS]
        key = repeat.lower() if repeat is not None else None
        row = values.index(key) if key in values else (values.index("*") if repeat else -1)
        self.repeat_combo.blockSignals(True)
        self.repeat_combo.setCurrentIndex(row)
        self.repeat_combo.blockSignals(False)
        typed = row == values.index("*")
        self.repeat_edit.setEnabled(typed)
        self.repeat_edit.setText(repeat if typed else "")
        # (new boxes are always only on their own page: their pages are given once they are there)
        self.repeat_combo.setEnabled(self.doc is not None and bool(chosen))
        self.repeat_edit.setEnabled(typed and bool(chosen))

    def _enable(self):
        has = self.doc is not None
        for w in (self.a_save, self.a_select_all, self.a_clear_page, self.a_result, self.a_first, self.a_last,
                  self.a_fit, self.a_fit_width, self.a_zoom_in, self.a_zoom_out, self.page_spin, self.result_box,
                  self.color_button):
            w.setEnabled(has)
        self.a_save.setEnabled(has and bool(self.boxes))
        self.a_clear_all.setEnabled(bool(self.boxes))
        self.a_delete.setEnabled(bool(self.selected))
        self.b_delete.setEnabled(bool(self.selected))
        self.a_prev.setEnabled(has and self.page > 0)
        self.a_next.setEnabled(has and self.page < self.count - 1)
        self.a_undo.setEnabled(bool(self.undo_stack))
        self.a_redo.setEnabled(bool(self.redo_stack))

    # ----------------------------------------------------------------- unsaved changes

    def is_modified(self) -> bool:
        return bool(self.boxes) and self.boxes != self.saved

    def _update_title(self):
        name = f"{self.path.name}[*] — py-redact" if self.path else "py-redact"
        self.setWindowTitle(name)
        self.setWindowModified(self.is_modified())

    def ask_unsaved(self) -> QMessageBox.StandardButton:
        box = QMessageBox(QMessageBox.Icon.Warning, tr("Unsaved boxes"),
                          tr("The boxes haven't been applied to a redacted copy. Save one before going on?"),
                          QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard
                          | QMessageBox.StandardButton.Cancel, self)
        box.setDefaultButton(QMessageBox.StandardButton.Save)
        return QMessageBox.StandardButton(box.exec())

    def maybe_discard(self) -> bool:
        """True if it is all right to go on (nothing unsaved, saved now, or discarded)."""
        if not self.is_modified():
            return True
        answer = self.ask_unsaved()
        if answer == QMessageBox.StandardButton.Save:
            return self.save_dialog()
        return answer == QMessageBox.StandardButton.Discard

    # ----------------------------------------------------------------- drag and drop

    def dragEnterEvent(self, event):
        if any(u.toLocalFile().lower().endswith(".pdf") for u in event.mimeData().urls()):
            event.acceptProposedAction()

    def dropEvent(self, event):
        for u in event.mimeData().urls():
            if u.toLocalFile().lower().endswith(".pdf"):
                self.open_path(Path(u.toLocalFile()))
                break

    # ----------------------------------------------------------------- messages

    def status(self, text: str, error: bool = False):
        self.statusBar().setStyleSheet("color: #c0392b;" if error else "")
        self.statusBar().showMessage(text, 0 if error else 8000)

    def about(self):
        QMessageBox.about(self, tr("About py-redact"),
                          tr("<b>py-redact {version}</b><p>Redacts PDF documents: what lies under the boxes "
                             "drawn on their pages is removed for good, and the boxes are filled with a "
                             "colour.</p><p>By {author}.</p><p>Licensed under the GNU General Public License, "
                             "version 3 or later.</p>", version=__version__, author=AUTHOR))
