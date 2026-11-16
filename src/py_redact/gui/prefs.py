"""The settings dialog: the default colour of new boxes, and how boxes are redacted."""

from __future__ import annotations

from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCheckBox, QColorDialog, QComboBox, QDialog, QDialogButtonBox, QFormLayout, QHBoxLayout, QLabel, QPushButton,
    QVBoxLayout,
)

from ..interface import N_, tr
from .. import conform
from ..settings import DEFAULTS, Settings

IMAGES = [("pixels", N_("Blank the part under the box")), ("whole", N_("Remove the whole image")),
          ("none", N_("Leave the images as they are"))]
DRAWINGS = [("covered", N_("Remove those wholly under a box")), ("touched", N_("Remove those a box touches")),
            ("none", N_("Leave the drawings as they are"))]


class SettingsDialog(QDialog):
    def __init__(self, settings: Settings, swatch, color_name, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("Settings"))
        self._swatch, self._color_name = swatch, color_name
        self.color = settings.color
        self.color_button = QPushButton()
        self.color_button.clicked.connect(self._choose)
        self.images = QComboBox()
        for value, name in IMAGES:
            self.images.addItem(tr(name), value)
        self.drawings = QComboBox()
        for value, name in DRAWINGS:
            self.drawings.addItem(tr(name), value)
        self.output = QComboBox()
        self.output.addItem(tr("PDF"), "")
        for value, name in conform.STANDARDS:
            self.output.addItem(tr(name), value)
            if not conform.available():
                self.output.model().item(self.output.count() - 1).setEnabled(False)
        if not conform.available():
            self.output.setToolTip(tr("PDF/A and PDF/X need {command}, which is not installed (or not on the PATH)",
                                      command=conform.COMMAND))
        self.clean = QCheckBox(tr("Also remove metadata, hidden text, attachments and scripts"))
        form = QFormLayout()
        form.addRow(tr("Colour of new boxes:"), self.color_button)
        form.addRow(tr("Images under a box:"), self.images)
        form.addRow(tr("Drawings under a box:"), self.drawings)
        form.addRow("", self.clean)
        form.addRow(tr("Save as:"), self.output)
        note = QLabel(tr("Text under a box is always removed."))
        note.setStyleSheet("color: palette(placeholder-text);")
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
                                   | QDialogButtonBox.StandardButton.RestoreDefaults)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        buttons.button(QDialogButtonBox.StandardButton.RestoreDefaults).clicked.connect(lambda: self.show_settings(
            DEFAULTS))
        lay = QVBoxLayout(self)
        lay.addLayout(form)
        lay.addWidget(note)
        bottom = QHBoxLayout()
        bottom.addWidget(buttons)
        lay.addLayout(bottom)
        self.show_settings(settings)

    def show_settings(self, settings: Settings):
        self.color = settings.color
        self._show_color()
        self.images.setCurrentIndex([v for v, _ in IMAGES].index(settings.images))
        self.drawings.setCurrentIndex([v for v, _ in DRAWINGS].index(settings.drawings))
        self.clean.setChecked(settings.clean)
        values = [self.output.itemData(i) for i in range(self.output.count())]
        self.output.setCurrentIndex(values.index(settings.output) if conform.available() else 0)

    def _show_color(self):
        self.color_button.setIcon(self._swatch(self.color))
        self.color_button.setText(self._color_name(self.color))

    def _choose(self):
        chosen = QColorDialog.getColor(QColor(self.color), self, tr("The colour of the boxes"))
        if chosen.isValid():
            self.color = chosen.name()
            self._show_color()

    def settings(self) -> Settings:
        return Settings(color=self.color, clean=self.clean.isChecked(), images=self.images.currentData(),
                        drawings=self.drawings.currentData(), output=self.output.currentData())
