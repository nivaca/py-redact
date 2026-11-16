"""The properties of the boxes selected: their fill, the text written over
them, a note, whether they are locked; and, if asked, the same for new boxes."""

from __future__ import annotations

import dataclasses

from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCheckBox, QColorDialog, QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox, QFormLayout, QGroupBox, QLineEdit,
    QPushButton, QVBoxLayout,
)

from ..interface import N_, ntr, tr
from ..redact import Box

ALIGNS = [("left", N_("Left")), ("center", N_("Centre")), ("right", N_("Right"))]
SAME = object()  # (a property that differs among the boxes: left as each has it)


class ColorButton(QPushButton):
    """A button that shows a colour and lets the user choose another; NONE
    allows 'no colour' ('')."""

    def __init__(self, color, swatch, color_name, none: bool = False, parent=None):
        super().__init__(parent)
        self._swatch, self._name, self.none = swatch, color_name, none
        self.color = color
        self.clicked.connect(self._choose)
        self._show()

    def _show(self):
        if self.color is SAME:
            self.setText(tr("(several)"))
            self.setIcon(self._swatch("#808080"))
        else:
            self.setText(self._name(self.color))
            self.setIcon(self._swatch(self.color))

    def _choose(self):
        from PySide6.QtWidgets import QMenu

        menu = QMenu(self)
        if self.none:
            menu.addAction(self._swatch(""), tr("No colour"), lambda: self.set_color(""))
        menu.addAction(tr("Choose…"), self._dialog)
        menu.exec(self.mapToGlobal(self.rect().bottomLeft()))

    def _dialog(self):
        start = QColor(self.color) if isinstance(self.color, str) and self.color else QColor("#000000")
        chosen = QColorDialog.getColor(start, self, tr("Colour"))
        if chosen.isValid():
            self.set_color(chosen.name())

    def set_color(self, color: str):
        self.color = color
        self._show()


class PropertiesDialog(QDialog):
    def __init__(self, boxes: list[Box], swatch, color_name, parent=None):
        super().__init__(parent)
        self.setWindowTitle(ntr("Properties of the box", "Properties of the {count} boxes", len(boxes)))
        self.boxes = boxes

        def common(name):
            values = {getattr(b, name) for b in boxes}
            return values.pop() if len(values) == 1 else SAME

        self.fill = ColorButton(common("color"), swatch, color_name, none=True)
        self.fill.setToolTip(tr("With no colour, what is under the box is removed and nothing is painted there"))
        text = common("text")
        self.text = QLineEdit("" if text is SAME else text)
        self.text.setPlaceholderText(tr("(several)") if text is SAME else tr("REDACTED, [name]…"))
        self.text_color = ColorButton(common("text_color"), swatch, color_name)
        self.font_size = QDoubleSpinBox()
        self.font_size.setRange(0, 72)
        self.font_size.setDecimals(1)
        self.font_size.setSpecialValueText(tr("As large as fits"))
        self.font_size.setSuffix(" pt")
        size = common("font_size")
        self.font_size.setValue(0 if size is SAME else size)
        self._size_given = size is not SAME
        self.align = QComboBox()
        for value, name in ALIGNS:
            self.align.addItem(tr(name), value)
        align = common("align")
        self.align.setCurrentIndex(-1 if align is SAME else [v for v, _ in ALIGNS].index(align))
        self.repeat_text = self._check(tr("Repeat the text all along the box"), common("repeat_text"))
        note = common("note")
        self.note = QLineEdit("" if note is SAME else note)
        self.note.setPlaceholderText(tr("(several)") if note is SAME else tr("Shown when the mouse is over the box"))
        self.locked = self._check(tr("Locked: can't be moved, resized or deleted"), common("locked"))
        self.as_default = QCheckBox(tr("Save as default for new boxes"))
        self.as_default.setToolTip(tr("The fill and the text, with its colour, size and alignment"))

        redaction = QGroupBox(tr("Once redacted"))
        form = QFormLayout(redaction)
        form.addRow(tr("Fill:"), self.fill)
        form.addRow(tr("Text:"), self.text)
        form.addRow(tr("Text colour:"), self.text_color)
        form.addRow(tr("Font size:"), self.font_size)
        form.addRow(tr("Alignment:"), self.align)
        form.addRow("", self.repeat_text)
        general = QGroupBox(tr("Box"))
        form = QFormLayout(general)
        form.addRow(tr("Note:"), self.note)
        form.addRow("", self.locked)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        lay = QVBoxLayout(self)
        lay.addWidget(redaction)
        lay.addWidget(general)
        lay.addWidget(self.as_default)
        lay.addWidget(buttons)
        self._text_given = text is not SAME
        self.resize(420, self.sizeHint().height())

    @staticmethod
    def _check(text: str, value) -> QCheckBox:
        box = QCheckBox(text)
        if value is SAME:
            box.setTristate(True)
            box.setCheckState(box.checkState().PartiallyChecked)
        else:
            box.setChecked(bool(value))
        return box

    def changes(self) -> dict:
        """What to change in each box (what the user left as '(several)' isn't changed)."""
        out = {}
        if self.fill.color is not SAME:
            out["color"] = self.fill.color
        if self._text_given or self.text.text():
            out["text"] = " ".join(self.text.text().split())
        if self.text_color.color is not SAME:
            out["text_color"] = self.text_color.color
        if self._size_given or self.font_size.value():
            out["font_size"] = self.font_size.value()
        if self.align.currentIndex() >= 0:
            out["align"] = self.align.currentData()
        for name in ("repeat_text", "locked"):
            box = getattr(self, name)
            if box.checkState() != box.checkState().PartiallyChecked:
                out[name] = box.isChecked()
        if self.note.text() or len({b.note for b in self.boxes}) == 1:
            out["note"] = self.note.text().strip()
        return out

    def apply(self, box: Box) -> Box:
        return dataclasses.replace(box, **self.changes())
