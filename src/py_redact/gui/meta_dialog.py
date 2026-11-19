"""The metadata dialog: every field of the document's metadata, each with a
button to remove it (it is then left empty, and the copy won't have it);
fields of its own can be added. What is chosen is given to the copy when it
is saved."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QFormLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit, QMessageBox,
    QPlainTextEdit, QPushButton, QScrollArea, QToolButton, QVBoxLayout, QWidget,
)

from .. import metadata as M
from ..interface import tr


def remove_button(tip: str, slot) -> QToolButton:
    from .window import icon

    b = QToolButton()
    b.setIcon(icon("edit-clear"))
    b.setText("✕")
    b.setToolTip(tip)
    b.setAutoRaise(True)
    b.clicked.connect(slot)
    return b


class MetadataDialog(QDialog):
    def __init__(self, current: M.Metadata, original: M.Metadata, parent=None):
        """CURRENT: the metadata the copy will have; ORIGINAL: the document's own."""
        super().__init__(parent)
        self.setWindowTitle(tr("Metadata"))
        self.original = original
        self.fields: dict[str, QLineEdit | QComboBox] = {}
        self.custom_rows: list[tuple[QLineEdit, QLineEdit, QWidget]] = []
        self.shown_dates: dict[str, tuple[str, str]] = {}  # key -> (as shown, as the PDF writes it)

        standard = QGroupBox(tr("Document information"))
        form = QFormLayout(standard)
        for key, name in M.STANDARD:
            row = QHBoxLayout()
            if key == "Trapped":
                field = QComboBox()
                field.addItem("", "")
                for value in M.TRAPPED:
                    field.addItem(value, value)
                field.setToolTip(tr("Whether the document has been trapped for printing"))
            else:
                field = QLineEdit()
                if key in M.DATES:
                    field.setPlaceholderText("2026-11-17 07:57:28 -05:00")
            self.fields[key] = field
            row.addWidget(field, 1)
            if key in M.DATES:
                now = QPushButton(tr("Now"))
                now.setToolTip(tr("This moment"))
                now.clicked.connect(lambda _=False, f=field: f.setText(M.now()))
                row.addWidget(now)
            row.addWidget(remove_button(tr("Remove it"), lambda _=False, k=key: self._clear(k)))
            form.addRow(tr(name) + ":", row)
        self.language = QLineEdit()
        self.language.setPlaceholderText("es-CO, en-US…")
        self.language.setToolTip(tr("The language of the document's text, as a language tag"))
        row = QHBoxLayout()
        row.addWidget(self.language, 1)
        row.addWidget(remove_button(tr("Remove it"), lambda: self.language.clear()))
        form.addRow(tr("Language:"), row)

        self.custom_box = QGroupBox(tr("Other fields"))
        self.custom_layout = QVBoxLayout(self.custom_box)
        self.custom_note = QLabel(tr("(none)"))
        self.custom_note.setStyleSheet("color: palette(placeholder-text);")
        self.custom_layout.addWidget(self.custom_note)
        add = QPushButton(tr("Add a field"))
        add.clicked.connect(lambda: self._add_custom("", ""))
        self.custom_layout.addWidget(add, 0, Qt.AlignmentFlag.AlignLeft)

        xmp_box = QGroupBox(tr("XMP metadata"))
        lay = QVBoxLayout(xmp_box)
        self.xmp = QPlainTextEdit()
        self.xmp.setPlaceholderText(tr("(none)"))
        self.xmp.setToolTip(tr("Metadata as XML, which may repeat the fields above and add others"))
        self.xmp.setMinimumHeight(110)
        lay.addWidget(self.xmp)
        b = QPushButton(tr("Remove the XMP metadata"))
        b.clicked.connect(lambda: self.xmp.clear())
        lay.addWidget(b, 0, Qt.AlignmentFlag.AlignLeft)

        body = QWidget()
        lay = QVBoxLayout(body)
        lay.addWidget(standard)
        lay.addWidget(self.custom_box)
        lay.addWidget(xmp_box)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(body)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        remove_all = buttons.addButton(tr("Remove all"), QDialogButtonBox.ButtonRole.ResetRole)
        remove_all.setToolTip(tr("Leave every field empty: the copy will have no metadata"))
        remove_all.clicked.connect(lambda: self.show_metadata(M.Metadata()))
        restore = buttons.addButton(tr("The document's own"), QDialogButtonBox.ButtonRole.ResetRole)
        restore.setToolTip(tr("Show again the metadata the document has"))
        restore.clicked.connect(lambda: self.show_metadata(self.original))
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        note = QLabel(tr("The redacted copy gets this metadata when it is saved; the document open is not "
                         "changed. A PDF/A or PDF/X copy may get a producer and XMP of its own."))
        note.setWordWrap(True)
        note.setStyleSheet("color: palette(placeholder-text);")
        outer = QVBoxLayout(self)
        outer.addWidget(scroll, 1)
        outer.addWidget(note)
        outer.addWidget(buttons)
        self.resize(640, 720)
        self.show_metadata(current)

    # ----------------------------------------------------------------- showing

    def _clear(self, key: str):
        field = self.fields[key]
        if isinstance(field, QComboBox):
            field.setCurrentIndex(0)
        else:
            field.clear()

    def _add_custom(self, key: str, value: str):
        row = QWidget()
        lay = QHBoxLayout(row)
        lay.setContentsMargins(0, 0, 0, 0)
        k, v = QLineEdit(key), QLineEdit(value)
        k.setPlaceholderText(tr("Name"))
        v.setPlaceholderText(tr("Value"))
        lay.addWidget(k, 1)
        lay.addWidget(v, 2)
        entry = (k, v, row)
        lay.addWidget(remove_button(tr("Remove it"), lambda: self._remove_custom(entry)))
        self.custom_rows.append(entry)
        self.custom_layout.insertWidget(self.custom_layout.count() - 1, row)
        self.custom_note.setVisible(False)
        if not key:
            k.setFocus()

    def _remove_custom(self, entry):
        self.custom_rows.remove(entry)
        entry[2].deleteLater()
        self.custom_note.setVisible(not self.custom_rows)

    def show_metadata(self, meta: M.Metadata):
        for key, field in self.fields.items():
            value = meta.get(key)
            if isinstance(field, QComboBox):
                i = field.findData(value)
                field.setCurrentIndex(i if i >= 0 else 0)
            elif key in M.DATES and value:
                shown = M.text_date(value)
                self.shown_dates[key] = (shown, value)
                field.setText(shown)
            else:
                field.setText(value)
        self.language.setText(meta.language)
        for entry in list(self.custom_rows):
            self._remove_custom(entry)
        for key, value in meta.custom():
            self._add_custom(key, value)
        self.custom_note.setVisible(not self.custom_rows)
        self.xmp.setPlainText(meta.xmp)

    # ----------------------------------------------------------------- the result

    def problems(self) -> list[str]:
        """What can't be kept as it is written."""
        out = []
        for key in M.DATES:
            text = self.fields[key].text().strip()
            if text and M.pdf_date(text) is None:
                name = tr(dict(M.STANDARD)[key])
                out.append(tr("{field}: {text} is not a date (2026-11-17 07:57:28 -05:00)", field=name, text=text))
        standard = {k for k, _ in M.STANDARD}
        seen = set()
        for k, v, _ in self.custom_rows:
            key = k.text().strip()
            if not key and not v.text().strip():
                continue
            if not M.KEY.fullmatch(key):
                out.append(tr("{name} can't be the name of a field: letters, digits, '.', '-' and '_', "
                              "starting with a letter", name=key or "''"))
            elif key in standard or key in seen:
                out.append(tr("There is a field called {name} already", name=key))
            seen.add(key)
        if self.xmp.toPlainText().strip():
            import xml.etree.ElementTree as ET

            try:
                ET.fromstring(self._xmp_body())
            except ET.ParseError as e:
                out.append(tr("The XMP metadata is not well-formed XML: {error}", error=e))
        return out

    def _xmp_body(self) -> str:
        """The XMP without its <?xpacket?> instructions, for checking it."""
        import re

        return re.sub(r"<\?xpacket[^>]*\?>", "", self.xmp.toPlainText()).strip()

    def metadata(self) -> M.Metadata:
        info = []
        for key, _ in M.STANDARD:
            field = self.fields[key]
            if isinstance(field, QComboBox):
                value = field.currentData() or ""
            else:
                value = " ".join(field.text().split())
                if key in M.DATES and value:
                    shown, raw = self.shown_dates.get(key, ("", ""))
                    # (a date left as it was keeps the very form it had: D:…Z is not D:…+00'00')
                    value = raw if value == shown else (M.pdf_date(value) or value)
            if value:
                info.append((key, value))
        for k, v, _ in self.custom_rows:
            if k.text().strip() and v.text().strip():
                info.append((k.text().strip(), " ".join(v.text().split())))
        return M.Metadata(tuple(info), self.language.text().strip(), self.xmp.toPlainText().strip())

    def accept(self):
        problems = self.problems()
        if problems:
            QMessageBox.warning(self, tr("Metadata"), "\n".join(problems))
            return
        super().accept()
