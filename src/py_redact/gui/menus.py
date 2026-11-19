"""The menus of the main window: the menu bar, the recent files, the menu of a box
and its submenus."""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path

from PySide6.QtCore import QSize
from PySide6.QtGui import QAction, QActionGroup, QIcon, QKeySequence
from PySide6.QtWidgets import QMenu, QToolBar

from .. import codes, conform, interface
from ..interface import N_, ntr, tr
from ..redact import Box, under
from .find import FindDialog
from .common import RECENT, REPEATS, SWATCHES, color_name, icon, swatch


class MenusMixin:
    """(Mixed into MainWindow: it uses its attributes.)"""

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
        self.a_save = self._action(m, tr("Save the redacted copy…"), lambda: self.save_dialog(),
                                   QKeySequence.StandardKey.Save,
                                   tr("Write a copy of the document with what is under the boxes removed, as a plain PDF (File > Save "
                                      "as: PDF/A or PDF/X)"))
        self.a_clean = QAction(tr("Also remove metadata, hidden text, attachments and scripts"), self,
                               checkable=True)
        self.a_clean.setChecked(self.prefs.clean)
        self.a_clean.toggled.connect(lambda on: self.set_prefs(dataclasses.replace(self.prefs, clean=on)))
        self.a_clean.setToolTip(tr("Remove as well what the document holds besides its pages: its title, "
                                   "author and other metadata, text that isn't shown, attached files, "
                                   "JavaScript and links"))
        m.addAction(self.a_clean)
        self.a_meta = self._action(m, tr("Metadata…"), self.metadata_dialog, "Ctrl+Shift+M",
                                   tr("See and change the title, author, dates and the rest of the metadata the "
                                      "redacted copy will have, or remove them"))
        self.a_hidden = self._action(m, tr("Remove hidden information…"), self.hidden_dialog,
                                     tip=tr("See what the document holds besides its pages (metadata, attachments, "
                                            "bookmarks, comments, hidden text…), and save a copy without what you "
                                            "choose"))
        self.a_sanitize = self._action(m, tr("Sanitize the document…"), self.sanitize_dialog,
                                       tip=tr("Save a copy without metadata, hidden text, attachments, scripts and "
                                              "links, and with nothing else changed (the boxes aren't applied)"))
        # Save as: the redacted copy, this once, as a plain PDF, PDF/A or PDF/X (Save is always a plain PDF)
        self.m_output = m.addMenu(tr("Save as"))
        self.m_output.setToolTipsVisible(True)
        self.output_actions = {}
        for value, name in [("", N_("PDF"))] + conform.STANDARDS:
            act = QAction(tr(name) + "…", self)
            act.triggered.connect(lambda _=False, v=value: self.save_dialog(v))
            self.m_output.addAction(act)
            self.output_actions[value] = act
        self._show_output()
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

        self.m_edit = m
        m.aboutToShow.connect(self._edit_menu)

        m = self.menuBar().addMenu(tr("&Tools"))
        tools = QActionGroup(self)
        self.a_tool_text = self._action(m, tr("Redact (text or area)"), lambda: self.set_tool("text"), "T",
                                        tr("Over text, dragging selects it and a box is made over each of its lines; "
                                           "elsewhere it draws a box (Ctrl+drag always draws one). Double-click a "
                                           "word or an image to mark only that"))
        self.a_tool_box = self._action(m, tr("Draw boxes"), lambda: self.set_tool("box"), "B",
                                       tr("Dragging on the page always draws a box, even over text"))
        self.a_tool_hand = self._action(m, tr("Hand"), lambda: self.set_tool("hand"), "H",
                                        tr("Dragging moves the page in the window"))
        for act in (self.a_tool_box, self.a_tool_text, self.a_tool_hand):
            act.setCheckable(True)
            tools.addAction(act)
        self.a_tool_text.setChecked(True)
        m.addSeparator()
        self.a_find = self._action(m, tr("Find and redact…"), lambda: self.find_dialog(),
                                   QKeySequence.StandardKey.Find,
                                   tr("Find a text, or a regular expression, on some or all pages, and put boxes "
                                      "over it"))
        m.setToolTipsVisible(True)
        self.finder: FindDialog | None = None

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
        self._action(m, tr("Settings…"), self.settings_dialog, [QKeySequence("Ctrl+,")])
        self.a_labels = QAction(tr("Labels in the toolbar"), self, checkable=True)
        self.a_labels.toggled.connect(self.show_labels)
        m.addAction(self.a_labels)
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

        for act, name in ((self.a_open, "document-open"), (self.a_save, "document-save-as"),
                          (self.a_tool_text, "edit-select-text"), (self.a_tool_box, "draw-rectangle"),
                          (self.a_tool_hand, "transform-browse"),
                          (self.a_find, "edit-find"), (self.a_undo, "edit-undo"), (self.a_redo, "edit-redo"),
                          (self.a_delete, "edit-delete"), (self.a_prev, "go-previous"), (self.a_next, "go-next"),
                          (self.a_fit, "zoom-fit-best"), (self.a_fit_width, "zoom-fit-width"),
                          (self.a_zoom_out, "zoom-out"), (self.a_zoom_in, "zoom-in"), (self.a_result, "view-preview")):
            act.setIcon(icon(name))
        bar = QToolBar(tr("Tools"))
        self.toolbar = bar
        bar.setObjectName("tools")
        bar.setIconSize(QSize(22, 22))
        for act in (self.a_open, self.a_save, None, self.a_tool_text, self.a_tool_box, self.a_tool_hand, self.a_find, None, self.a_undo,
                    self.a_redo, self.a_delete, None, self.a_prev,
                    self.a_next, None, self.a_fit, self.a_fit_width, self.a_zoom_out, self.a_zoom_in):
            if act is None:
                bar.addSeparator()
            else:
                bar.addAction(act)
        self.addToolBar(bar)
        self.show_labels(self.settings.value("toolbar_labels", "false") == "true")
        self._toolbar_tips()

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

    def _colors_menu(self, menu: QMenu, title: str, current: str | None, choose, icon=True) -> QMenu:
        """A menu of colours (CURRENT ticked), each given to CHOOSE."""
        sub = menu.addMenu(swatch(current) if icon and current else QIcon(), title)
        group = QActionGroup(sub)
        for value, name in SWATCHES:
            act = sub.addAction(swatch(value), tr(name), lambda v=value: choose(v))
            act.setCheckable(True)
            act.setChecked(value == current)
            group.addAction(act)
        sub.addSeparator()
        other = sub.addAction(tr("Other colour…"), self.choose_color)
        if current and current not in [v for v, _ in SWATCHES]:
            other.setText(tr("Other colour ({color})…", color=current))
            other.setIcon(swatch(current))
        return sub

    def box_menu(self, index: int, where, point=None):
        """The right-click menu: of the boxes selected (INDEX: the one clicked), or
        of the page (INDEX -1), with what makes sense where it was clicked."""
        menu = QMenu(self)
        menu.setToolTipsVisible(True)
        if self.boxes:
            act = menu.addAction(icon("document-save-as"), ntr("Apply the redaction…", "Apply all {count} redactions…",
                                                                len(self.boxes)), self.save_dialog)
            act.setToolTip(tr("Save the redacted copy: what is under the boxes is removed for good"))
            menu.addSeparator()
        if index >= 0 and self.selected:
            chosen = [self.boxes[i] for i in self.selected]
            if len(chosen) == 1:
                box = chosen[0]
                menu.addSection(tr("Box drawn on page {page} — {pages}", page=box.page + 1,
                                   pages=self._covers(box).lower() if box.repeat.strip() else tr("only there")))
            else:
                menu.addSection(ntr("{count} box", "{count} boxes", len(chosen)))
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
            if page < self.count:
                pages.addAction(tr("From page {page} to the end", page=page), lambda: self.set_repeat(f"{page}-"))
            if page > 1:
                pages.addAction(tr("Up to page {page}", page=page), lambda: self.set_repeat(f"1-{page}"))
            custom = {r for r in repeats if r not in ("", "all", "odd", "even")}
            act = pages.addAction(tr("These pages ({pages})…", pages=chosen[0].repeat) if len(repeats) == 1 and custom
                                  else tr("These pages…"), self.ask_pages)
            act.setCheckable(True)
            act.setChecked(len(repeats) == 1 and bool(custom))
            group.addAction(act)
            colors = {b.color for b in chosen}
            color = colors.pop() if len(colors) == 1 else None
            self._colors_menu(menu, tr("Colour"), color, lambda v: self._change_selected(color=v))
            if color and color != self.prefs.color:
                menu.addAction(swatch(color), tr("Make {color} the colour of new boxes", color=color_name(color)),
                               lambda: self.set_default_color(color))
            if len(chosen) == 1 and chosen[0].on(self.page, self.count):
                words_ = " ".join(under(self.canvas.page_words(), chosen[0].rect))
                if words_:
                    menu.addSeparator()
                    short = words_ if len(words_) <= 30 else words_[:28] + "…"
                    act = menu.addAction(tr("Redact “{text}” wherever it is…", text=short),
                                         lambda: self.find_dialog(words_))
                    act.setToolTip(tr("Find the text under this box on every page, and mark it"))
            self._codes_menu(menu, chosen)
            menu.addSeparator()
            menu.addAction(tr("Properties…"), self.properties_dialog)
            all_locked = all(b.locked for b in chosen)
            menu.addAction(tr("Unlock") if all_locked else tr("Lock"), lambda: self.set_locked(not all_locked))
            act = menu.addAction(icon("edit-delete"), ntr("Delete the box", "Delete the {count} boxes", len(chosen)),
                                 self.delete_selected)
            act.setEnabled(not all_locked)
        else:
            word = self.canvas.word_at(point) if point is not None and self.canvas.editable else ""
            if word:
                menu.addSection(f"“{word}”")
                menu.addAction(tr("Redact it on this page"), lambda: self.mark_matches(
                    self._find(word, [self.page])))
                menu.addAction(tr("Redact it on every page…"), lambda: self.find_dialog(word))
                menu.addSeparator()
            menu.addAction(self.a_find)
            menu.addAction(self.a_tool_text)
            menu.addAction(self.a_tool_box)
            menu.addSeparator()
            self._colors_menu(menu, tr("Colour of new boxes"), self.prefs.color, self.set_default_color)
            here = [i for i, b in enumerate(self.boxes) if b.on(self.page, self.count)]
            if here:
                menu.addSeparator()
                menu.addAction(ntr("Select the box of this page", "Select the {count} boxes of this page",
                                   len(here)), self.select_page)
                if any(b.page == self.page for b in self.boxes):
                    menu.addAction(self.a_clear_page)
            menu.addSeparator()
            menu.addAction(self.a_result)
            menu.addAction(tr("Settings…"), self.settings_dialog)
        self.show_menu(menu, where)

    def show_menu(self, menu: QMenu, where):
        menu.exec(where)

    def _codes_menu(self, menu: QMenu, chosen: list[Box]):
        """Redaction codes: each set, with its codes ticked if all the boxes have them."""
        sub = menu.addMenu(tr("Redaction code"))
        sub.setToolTipsVisible(True)
        for name, entries in codes.all_sets().items():
            group = sub.addMenu(name)
            for code in entries:
                act = group.addAction(code, lambda c=code: self.toggle_code(c))
                act.setCheckable(True)
                act.setChecked(all(code in codes.codes_of(b.text) for b in chosen))
        sub.addSeparator()
        if any(b.text for b in chosen):
            sub.addAction(tr("No code (no text)"), lambda: self._change_selected(text=""))
        sub.addAction(tr("Edit the codes…"), self.codes_dialog)

    def _edit_menu(self):
        """The Edit menu, as things are when it opens."""
        n = len(self.selected)
        self.a_delete.setText(ntr("Delete the selected box", "Delete the {count} selected boxes", n) if n
                              else tr("Delete the selected boxes"))
        has_here = self.doc is not None and any(b.on(self.page, self.count) for b in self.boxes)
        self.a_select_all.setEnabled(has_here)
        self.a_clear_page.setEnabled(self.doc is not None and any(b.page == self.page for b in self.boxes))
        self.a_undo.setText(tr("Undo") if not self.undo_stack else tr("Undo ({count})", count=len(self.undo_stack)))
