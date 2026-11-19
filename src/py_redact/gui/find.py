"""Find and redact: look for a word or phrase, several of them, or patterns
(phone numbers, e-mail addresses...) on some pages, see where they are, and
put boxes over all or some of the places found, whole or leaving some
characters visible."""

from __future__ import annotations

import re

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDialog, QFileDialog, QFormLayout, QHBoxLayout, QLabel, QLineEdit, QListWidget,
    QListWidgetItem, QPlainTextEdit, QPushButton, QSpinBox, QStackedWidget, QVBoxLayout, QWidget,
)

from ..interface import N_, ntr, tr
from ..pagesel import check, parse_pages
from .. import patterns
from ..redact import Match, find_all

# where to look: (value, its name); '*' is a list typed by the user
MODES = [("one", N_("A word or phrase")), ("many", N_("Several words or phrases")), ("patterns", N_("Patterns"))]
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
        self.searching = False  # (a search is going on: Find is then Stop)
        self.stop_asked = False
        self.mode = QComboBox()
        for value, name in MODES:
            self.mode.addItem(tr(name), value)
        self.query = QLineEdit()
        self.query.setPlaceholderText(tr("Text to find"))
        self.query.returnPressed.connect(self.search)
        self.terms = QPlainTextEdit()
        self.terms.setPlaceholderText(tr("One word or phrase on each line"))
        self.terms.setTabChangesFocus(True)
        read = QPushButton(tr("Read from a file…"))
        read.setToolTip(tr("A text file with one word or phrase on each line"))
        read.clicked.connect(self.read_terms)
        self.pattern_list = QListWidget()
        for key, name, _ in patterns.PATTERNS:
            item = QListWidgetItem(tr(name))
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked)
            item.setData(Qt.ItemDataRole.UserRole, key)
            self.pattern_list.addItem(item)
        self.language = QComboBox()
        for value, name in patterns.LANGUAGES:
            self.language.addItem(tr(name), value)
        self.language.setCurrentIndex([v for v, _ in patterns.LANGUAGES].index(window.prefs.pattern_language))
        self.language.setToolTip(tr("The forms of the patterns: of phone numbers, dates, identity numbers"))
        self.language.currentIndexChanged.connect(self._language_changed)
        self.partial = QCheckBox(tr("Leave some characters visible:"))
        self.partial.setToolTip(tr("For instance the last four digits of a card number, so that it can still be "
                                   "told apart"))
        self.keep_start, self.keep_end = QSpinBox(), QSpinBox()
        for box, text in ((self.keep_start, tr("the first ")), (self.keep_end, tr("the last "))):
            box.setRange(0, 99)
            box.setPrefix(text)
            box.setEnabled(False)
            self.partial.toggled.connect(box.setEnabled)
        self.keep_end.setValue(4)
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
        find.clicked.connect(self._find_or_stop)
        self.find_button = find

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

        one = QWidget()
        lay = QVBoxLayout(one)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self.query)
        options = QHBoxLayout()
        for w in (self.case, self.whole, self.regex):
            options.addWidget(w)
        options.addStretch(1)
        lay.addLayout(options)
        many = QWidget()
        lay = QVBoxLayout(many)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self.terms)
        lay.addWidget(read, 0, Qt.AlignmentFlag.AlignLeft)
        pats = QWidget()
        lay = QVBoxLayout(pats)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self.pattern_list)
        row = QHBoxLayout()
        row.addWidget(QLabel(tr("Forms:")))
        row.addWidget(self.language, 1)
        lay.addLayout(row)
        self.pages_of_modes = QStackedWidget()
        for w in (one, many, pats):
            self.pages_of_modes.addWidget(w)
        self.terms.setMaximumHeight(110)
        self.pattern_list.setMaximumHeight(140)
        self.mode.currentIndexChanged.connect(self.pages_of_modes.setCurrentIndex)
        self.mode.currentIndexChanged.connect(lambda i: self.pages_of_modes.setMaximumHeight(
            [self.query.sizeHint().height() * 2 + 8, 150, 180][i]))
        self.pages_of_modes.setMaximumHeight(self.query.sizeHint().height() * 2 + 8)

        form = QFormLayout()
        row = QHBoxLayout()
        row.addWidget(self.mode, 1)
        row.addWidget(find)
        form.addRow(tr("Find:"), row)
        form.addRow("", self.pages_of_modes)
        partial = QHBoxLayout()
        partial.addWidget(self.partial)
        partial.addWidget(self.keep_start)
        partial.addWidget(self.keep_end)
        partial.addStretch(1)
        where = QHBoxLayout()
        where.addWidget(self.scope)
        where.addWidget(self.pages, 1)
        form.addRow(tr("On:"), where)
        form.addRow("", partial)
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
        self.resize(600, 560)
        self._enable()

    def start(self, text: str = "", scope: str = "all"):
        """Show the dialog, with TEXT to find (and found at once, if given)."""
        if text:
            self.mode.setCurrentIndex(0)
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

    def _find_or_stop(self):
        if self.searching:
            self.stop_asked = True
        else:
            self.search()

    def _progress(self, done: int, total: int) -> bool:
        """Show how far a search has gone, let the window answer, and say whether to go on."""
        self.summary.setText(tr("Looking on page {done} of {total}…", done=done, total=total))
        QApplication.processEvents()
        return not self.stop_asked

    def closeEvent(self, event):
        self.stop_asked = True
        super().closeEvent(event)

    def search(self):
        if self.searching:
            return
        self.results.clear()
        self.matches = []
        doc = self.window.doc
        queries = self.queries()
        if doc is None or not queries:
            self.summary.setText("")
            self._enable()
            return
        keep = (self.keep_start.value(), self.keep_end.value()) if self.partial.isChecked() else (0, 0)
        self.searching, self.stop_asked = True, False
        self.find_button.setText(tr("Stop"))
        self.b_all.setEnabled(False)
        self.b_ticked.setEnabled(False)
        try:
            self.matches = find_all(doc, queries, self.page_list(), self.case.isChecked(),
                                    self.whole.isChecked() and self.mode.currentData() != "patterns", *keep,
                                    progress=self._progress, texts=self.window.texts)
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
        if self.stop_asked:
            self.summary.setText(self.summary.text() + " " + tr("(stopped before the end)"))
        self._enable()

    def queries(self) -> list[tuple[str, bool]]:
        """What to look for: [(text, whether it is a regular expression)]."""
        mode = self.mode.currentData()
        if mode == "one":
            text = self.query.text()
            return [(text, self.regex.isChecked())] if text.strip() else []
        if mode == "many":
            return [(line.strip(), False) for line in self.terms.toPlainText().splitlines() if line.strip()]
        language = self.language.currentData()
        return [(patterns.regex(self.pattern_list.item(r).data(Qt.ItemDataRole.UserRole), language), True)
                for r in range(self.pattern_list.count())
                if self.pattern_list.item(r).checkState() == Qt.CheckState.Checked]

    def read_terms(self):
        name, _ = QFileDialog.getOpenFileName(self, tr("Words or phrases to find"), self.window.last_dir(),
                                              tr("Text files (*.txt);;All files (*)"))
        if not name:
            return
        try:
            with open(name, encoding="utf-8-sig") as f:
                lines = [line.strip() for line in f if line.strip()]
        except (OSError, UnicodeDecodeError) as e:
            self.summary.setText(str(e))
            return
        old = [line for line in self.terms.toPlainText().splitlines() if line.strip()]
        self.terms.setPlainText("\n".join(old + [x for x in lines if x not in old]))
        self.summary.setText(ntr("{count} word or phrase read", "{count} words or phrases read", len(lines)))

    def _language_changed(self):
        import dataclasses

        self.window.set_prefs(dataclasses.replace(self.window.prefs, pattern_language=self.language.currentData()))

    def ticked(self, all_: bool = False) -> list[Match]:
        return [self.matches[self.results.item(r).data(Qt.ItemDataRole.UserRole)]
                for r in range(self.results.count())
                if all_ or self.results.item(r).checkState() == Qt.CheckState.Checked]

    def _chosen(self, item, _previous=None):
        if item is not None:
            self.show_match.emit(self.matches[item.data(Qt.ItemDataRole.UserRole)])

    def _enable(self):
        self.searching = False
        self.find_button.setText(tr("Find"))
        self.b_all.setEnabled(bool(self.matches))
        self.b_ticked.setEnabled(bool(self.matches))
