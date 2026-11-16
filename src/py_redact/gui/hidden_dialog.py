"""Remove hidden information: what the document holds besides its pages,
kind by kind, with how much of each it has; the kinds ticked are removed in a
copy of the document."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QListWidget, QListWidgetItem, QVBoxLayout

from .. import hidden
from ..interface import ntr, tr


class HiddenDialog(QDialog):
    def __init__(self, found: dict[str, int], parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("Remove hidden information"))
        self.list = QListWidget()
        for key, name, what in hidden.KINDS:
            n = found.get(key, 0)
            if n < 0:
                count = tr("(found when the copy is written)")
            elif n == 0:
                count = tr("(none)")
            else:
                count = ntr("({count} found)", "({count} found)", n)
            item = QListWidgetItem(f"{tr(name)}  {count}")
            item.setToolTip(tr(what))
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked if n != 0 else Qt.CheckState.Unchecked)
            if n == 0:
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEnabled)
            item.setData(Qt.ItemDataRole.UserRole, key)
            self.list.addItem(item)
        note = QLabel(tr("A copy is saved without what is ticked; the document open is not changed, and its "
                         "boxes are not applied."))
        note.setWordWrap(True)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
        self.b_remove = buttons.addButton(tr("Remove and save a copy…"), QDialogButtonBox.ButtonRole.AcceptRole)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        self.list.itemChanged.connect(lambda _: self.b_remove.setEnabled(bool(self.kinds())))
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel(tr("What this document holds besides what its pages show:")))
        lay.addWidget(self.list, 1)
        lay.addWidget(note)
        lay.addWidget(buttons)
        self.resize(520, 400)
        self.b_remove.setEnabled(bool(self.kinds()))

    def kinds(self) -> set[str]:
        return {self.list.item(r).data(Qt.ItemDataRole.UserRole) for r in range(self.list.count())
                if self.list.item(r).checkState() == Qt.CheckState.Checked}
