"""Find and redact: look for a text (or a regular expression) on some pages,
see where it is, and put boxes over all or some of the places found."""

from __future__ import annotations

import re

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QFormLayout, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem,
    QPushButton, QVBoxLayout,
)

from ..interface import N_, ntr, tr
from ..pagesel import check, parse_pages
from ..redact import Match, find_text

# where to look: (value, its name); '*' is a list typed by the user
SCOPES = [("all", N_("All pages")), ("page", N_("This page")), ("from", N_("From this page to the end")),
          ("*", N_("These pages:"))]


class FindDialog(QDialog):
    """Not modal: the window stays usable while it is open. It asks the window
    (through the signals) to show a place found, and to mark the places chosen."""

    show_match = Signal(object)  # Match
    mark = Signal(list)  # [Match]

    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.setWindowTitle(tr("Find and redact"))
        self.matches: list[Match] = []
        self.query = QLineEdit()
        self.query.setPlaceholderText(tr("Text to find"))
        self.query.returnPressed.connect(self.search)
        self.case = QCheckBox(tr("Match case"))
        self.whole = QCheckBox(tr("Whole words"))
        self.regex = QCheckBox(tr("Regular expression"))
        self.regex.setToolTip(tr("For instance \\d+-\\d+ for numbers such as 555-1234, or [\\w.]+@[\\w.]+ for "
                                 "e-mail addresses"))
        self.scope = QComboBox()
        for value, name in SCOPES:
            self.scope.addItem(tr(name), value)
        self.scope.currentIndexChanged.connect(self._scope_changed)
        self.pages = QLineEdit()
        self.pages.setPlaceholderText(tr("1-5, 8, 10-"))
        self.pages.setEnabled(False)
        find = QPushButton(tr("Find"))
        find.setDefault(True)
        find.clicked.connect(self.search)

        self.results = QListWidget()
        self.results.currentItemChanged.connect(self._chosen)
        self.results.itemDoubleClicked.connect(
            lambda item: self.mark.emit([self.matches[item.data(Qt.ItemDataRole.UserRole)]]))
        self.summary = QLabel("")
        self.b_all = QPushButton(tr("Mark them all"))
        self.b_all.setToolTip(tr("A box over every place found"))
        self.b_all.clicked.connect(lambda: self.mark.emit(self.ticked(all_=True)))
        self.b_ticked = QPushButton(tr("Mark the ticked ones"))
        self.b_ticked.clicked.connect(lambda: self.mark.emit(self.ticked()))
        close = QPushButton(tr("Close"))
        close.clicked.connect(self.close)

        form = QFormLayout()
        row = QHBoxLayout()
        row.addWidget(self.query, 1)
        row.addWidget(find)
        form.addRow(tr("Find:"), row)
        options = QHBoxLayout()
        for w in (self.case, self.whole, self.regex):
            options.addWidget(w)
        options.addStretch(1)
        form.addRow("", options)
        where = QHBoxLayout()
        where.addWidget(self.scope)
        where.addWidget(self.pages, 1)
        form.addRow(tr("On:"), where)
        buttons = QHBoxLayout()
        buttons.addWidget(self.b_all)
        buttons.addWidget(self.b_ticked)
        buttons.addStretch(1)
        buttons.addWidget(close)
        lay = QVBoxLayout(self)
        lay.addLayout(form)
        lay.addWidget(self.results, 1)
        lay.addWidget(self.summary)
        lay.addLayout(buttons)
        self.resize(560, 460)
        self._enable()

    def start(self, text: str = "", scope: str = "all"):
        """Show the dialog, with TEXT to find (and found at once, if given)."""
        if text:
            self.query.setText(text)
        self.scope.setCurrentIndex([v for v, _ in SCOPES].index(scope))
        self.show()
        self.raise_()
        self.activateWindow()
        self.query.setFocus()
        self.query.selectAll()
        if text:
            self.search()

    def _scope_changed(self):
        typed = self.scope.currentData() == "*"
        self.pages.setEnabled(typed)
        if typed:
            self.pages.setFocus()

    def page_list(self) -> list[int] | None:
        count, page = self.window.count, self.window.page
        scope = self.scope.currentData()
        if scope == "page":
            return [page]
        if scope == "from":
            return list(range(page, count))
        if scope == "*":
            error = check(self.pages.text())
            if error:
                raise ValueError(error)
            return parse_pages(self.pages.text(), count)
        return None

    def search(self):
        self.results.clear()
        self.matches = []
        doc = self.window.doc
        if doc is None or not self.query.text().strip():
            self.summary.setText("")
            self._enable()
            return
        try:
            self.matches = find_text(doc, self.query.text(), self.page_list(), self.case.isChecked(),
                                     self.whole.isChecked(), self.regex.isChecked())
        except re.error as e:
            self.summary.setText(tr("That regular expression can't be read: {error}", error=e))
            self._enable()
            return
        except ValueError as e:
            self.summary.setText(str(e))
            self._enable()
            return
        for i, m in enumerate(self.matches):
            item = QListWidgetItem(tr("Page {page}: {context}", page=m.page + 1, context=m.context))
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked)
            item.setData(Qt.ItemDataRole.UserRole, i)
            self.results.addItem(item)
        pages = len({m.page for m in self.matches})
        self.summary.setText(ntr("Found once", "Found {count} times", len(self.matches))
                             + (ntr(", on {count} page", ", on {count} pages", pages) if self.matches else "")
                             if self.matches else tr("Not found"))
        self._enable()

    def ticked(self, all_: bool = False) -> list[Match]:
        return [self.matches[self.results.item(r).data(Qt.ItemDataRole.UserRole)]
                for r in range(self.results.count())
                if all_ or self.results.item(r).checkState() == Qt.CheckState.Checked]

    def _chosen(self, item, _previous=None):
        if item is not None:
            self.show_match.emit(self.matches[item.data(Qt.ItemDataRole.UserRole)])

    def _enable(self):
        self.b_all.setEnabled(bool(self.matches))
        self.b_ticked.setEnabled(bool(self.matches))
