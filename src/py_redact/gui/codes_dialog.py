"""The editor of redaction codes: the user's code sets and their codes, which
can be exported to a file and imported from one (see codes.py). The sets that
come with the program can be copied, not changed."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QFileDialog, QHBoxLayout, QInputDialog, QLabel, QListWidget, QMessageBox,
    QPushButton, QVBoxLayout,
)

from .. import codes
from ..interface import tr


class CodesDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("Redaction codes"))
        self.sets = codes.user_sets()
        self.set_list = QListWidget()
        self.set_list.currentRowChanged.connect(self._show_codes)
        self.code_list = QListWidget()
        self.code_list.currentRowChanged.connect(lambda _: self._enable())
        self.b_add_set = self._button(tr("Add set…"), self.add_set)
        self.b_copy_set = self._button(tr("Copy set…"), self.copy_set)
        self.b_rename_set = self._button(tr("Rename set…"), self.rename_set)
        self.b_remove_set = self._button(tr("Remove set"), self.remove_set)
        self.b_import = self._button(tr("Import set…"), self.import_set)
        self.b_export = self._button(tr("Export set…"), self.export_set)
        self.b_add_code = self._button(tr("Add code…"), self.add_code)
        self.b_rename_code = self._button(tr("Rename code…"), self.rename_code)
        self.b_remove_code = self._button(tr("Remove code"), self.remove_code)
        self.note = QLabel(tr("The sets that come with the program can be copied, then changed."))
        self.note.setStyleSheet("color: palette(placeholder-text);")
        self.note.setWordWrap(True)

        left = QVBoxLayout()
        left.addWidget(QLabel("<b>" + tr("Code sets") + "</b>"))
        left.addWidget(self.set_list, 1)
        for b in (self.b_add_set, self.b_copy_set, self.b_rename_set, self.b_remove_set, self.b_import,
                  self.b_export):
            left.addWidget(b)
        right = QVBoxLayout()
        right.addWidget(QLabel("<b>" + tr("Codes") + "</b>"))
        right.addWidget(self.code_list, 1)
        for b in (self.b_add_code, self.b_rename_code, self.b_remove_code):
            right.addWidget(b)
        right.addStretch(0)
        columns = QHBoxLayout()
        columns.addLayout(left, 1)
        columns.addLayout(right, 1)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        lay = QVBoxLayout(self)
        lay.addLayout(columns, 1)
        lay.addWidget(self.note)
        lay.addWidget(buttons)
        self.resize(560, 440)
        self._fill_sets()

    def _button(self, text, slot) -> QPushButton:
        b = QPushButton(text)
        b.clicked.connect(slot)
        return b

    # ----------------------------------------------------------------- showing

    def all_sets(self) -> dict[str, list[str]]:
        return {**codes.BUILT_IN, **self.sets}

    def current_set(self) -> str | None:
        item = self.set_list.currentItem()
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    def is_own(self, name: str | None) -> bool:
        return name is not None and name in self.sets

    def _fill_sets(self, select: str | None = None):
        self.set_list.blockSignals(True)
        self.set_list.clear()
        for name in self.all_sets():
            label = name if self.is_own(name) else tr("{name} (built in)", name=name)
            self.set_list.addItem(label)
            self.set_list.item(self.set_list.count() - 1).setData(Qt.ItemDataRole.UserRole, name)
        names = list(self.all_sets())
        self.set_list.setCurrentRow(names.index(select) if select in names else 0)
        self.set_list.blockSignals(False)
        self._show_codes()

    def _show_codes(self, *_):
        self.code_list.clear()
        name = self.current_set()
        if name is not None:
            self.code_list.addItems(self.all_sets()[name])
        self._enable()

    def _enable(self):
        own = self.is_own(self.current_set())
        has_set = self.current_set() is not None
        for b in (self.b_rename_set, self.b_remove_set, self.b_add_code):
            b.setEnabled(own)
        for b in (self.b_copy_set, self.b_export):
            b.setEnabled(has_set)
        has_code = own and self.code_list.currentRow() >= 0
        self.b_rename_code.setEnabled(has_code)
        self.b_remove_code.setEnabled(has_code)

    # ----------------------------------------------------------------- changes

    def _ask(self, title: str, label: str, text: str = "") -> str | None:
        value, ok = QInputDialog.getText(self, title, label, text=text)
        value = " ".join(value.split())
        return value if ok and value else None

    def _new_set_name(self, title: str, text: str = "") -> str | None:
        name = self._ask(title, tr("Name of the set:"), text)
        if name is not None and name in self.all_sets():
            QMessageBox.warning(self, title, tr("There is a set called {name} already", name=name))
            return None
        return name

    def add_set(self):
        name = self._new_set_name(tr("Add set"))
        if name:
            self.sets[name] = []
            self._fill_sets(name)

    def copy_set(self):
        source = self.current_set()
        name = self._new_set_name(tr("Copy set"), tr("{name} (copy)", name=source))
        if name:
            self.sets[name] = list(self.all_sets()[source])
            self._fill_sets(name)

    def rename_set(self):
        old = self.current_set()
        name = self._new_set_name(tr("Rename set"), old)
        if name:
            self.sets = {(name if k == old else k): v for k, v in self.sets.items()}
            self._fill_sets(name)

    def remove_set(self):
        name = self.current_set()
        if self.is_own(name):
            del self.sets[name]
            self._fill_sets()

    def add_code(self):
        name = self.current_set()
        code = self._ask(tr("Add code"), tr("The text written over the box:"))
        if code and code not in self.sets[name]:
            self.sets[name].append(code)
            self._show_codes()
            self.code_list.setCurrentRow(self.code_list.count() - 1)

    def rename_code(self):
        name, row = self.current_set(), self.code_list.currentRow()
        code = self._ask(tr("Rename code"), tr("The text written over the box:"), self.sets[name][row])
        if code:
            self.sets[name][row] = code
            self._show_codes()
            self.code_list.setCurrentRow(row)

    def remove_code(self):
        name, row = self.current_set(), self.code_list.currentRow()
        del self.sets[name][row]
        self._show_codes()

    def import_set(self):
        file, _ = QFileDialog.getOpenFileName(self, tr("Import set"), str(Path.home()),
                                              tr("Code sets (*.xml);;All files (*)"))
        if not file:
            return
        try:
            found = codes.parse(Path(file))
        except codes.CodesError as e:
            QMessageBox.warning(self, tr("Import set"), tr("{path} cannot be read: {error}", path=file, error=e))
            return
        self.sets.update(found)
        self._fill_sets(next(iter(found), None))

    def export_set(self):
        name = self.current_set()
        file, _ = QFileDialog.getSaveFileName(self, tr("Export set"), str(Path.home() / f"{name}.xml"),
                                              tr("Code sets (*.xml);;All files (*)"))
        if not file:
            return
        try:
            Path(file).write_text(codes.dump({name: self.all_sets()[name]}), encoding="utf-8")
        except OSError as e:
            QMessageBox.warning(self, tr("Export set"), tr("{path} cannot be written: {error}", path=file, error=e))

    def accept(self):
        try:
            codes.save_user_sets(self.sets)
        except OSError as e:
            QMessageBox.warning(self, tr("Redaction codes"), str(e))
            return
        super().accept()
