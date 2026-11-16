#!/usr/bin/env python3
"""Make the screenshots of the README, in English and in Spanish:

    uv run python tools/screenshots.py [-o FOLDER]

It writes, in docs/img/ (or FOLDER), for each language (en, es):

* window_LANG.png: the window, with a letter whose header goes on every page,
  a name with a text over it, and a phone number found by a pattern;
* find_LANG.png: Find and redact, looking for patterns;
* properties_LANG.png: the properties of a box.

The window is drawn off the screen (Qt's offscreen platform), with a
configuration folder of its own, so the user's settings are not touched.
The letter is made each time, with made-up names and numbers.
"""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

LETTER = {
    "en": ("MUNICIPAL ARCHIVE, case 2026-0417",
           ["Bogotá, 3 March 2026", "", "Dear Ms Laura Restrepo,",
            "We have received your request about the property at 14 Calle Real.",
            "Please call us at (555) 312-4478 or write to l.restrepo@example.org,",
            "quoting your identity number 123-45-6789.",
            "", "The documents you asked for will be ready within two weeks."]),
    "es": ("ARCHIVO MUNICIPAL, expediente 2026-0417",
           ["Bogotá, 3 de marzo de 2026", "", "Estimada señora Laura Restrepo:",
            "Hemos recibido su solicitud sobre el predio de la Calle Real 14.",
            "Llámenos al 601 312 4478 o escriba a l.restrepo@example.org,",
            "citando su cédula 1.020.345.678.",
            "", "Los documentos que pidió estarán listos en dos semanas."]),
}
NAME = {"en": "Laura Restrepo", "es": "Laura Restrepo"}
CODE = {"en": "(b)(6)", "es": "(b)(6)"}


def make_letter(path: Path, language: str):
    import pymupdf

    header, lines = LETTER[language]
    doc = pymupdf.open()
    for n in range(3):
        page = doc.new_page()
        page.insert_text((72, 60), header, fontsize=11)
        y = 120
        for line in (lines if n == 0 else lines[3:] * 2):
            page.insert_text((72, y), line, fontsize=12)
            y += 22
    doc.save(path)


def shoot(folder: Path, language: str):
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication

    from py_redact import interface
    from py_redact.redact import Box

    interface.use(language)
    from py_redact.gui.props import PropertiesDialog
    from py_redact.gui.window import MainWindow, color_name, install_qt_translations, swatch

    app = QApplication.instance() or QApplication([])
    install_qt_translations()
    with tempfile.TemporaryDirectory() as tmp:
        letter = Path(tmp) / ("letter.pdf" if language == "en" else "carta.pdf")
        make_letter(letter, language)
        w = MainWindow()
        w.resize(1400, 900)
        w.show()
        w.open_path(letter)
        page = w.doc[0]
        header = page.search_for(LETTER[language][0])[0]
        name = page.search_for(NAME[language])[0]
        w.change([Box(0, (header.x0 - 2, header.y0 - 2, header.x1 + 2, header.y1 + 2), repeat="all"),
                  Box(0, (name.x0 - 1, name.y0 - 1, name.x1 + 1, name.y1 + 1), text=CODE[language])])
        w.find_dialog()
        f = w.finder
        f.mode.setCurrentIndex(2)
        for r in range(f.pattern_list.count()):
            if f.pattern_list.item(r).data(Qt.ItemDataRole.UserRole) in ("phone", "email"):
                f.pattern_list.item(r).setCheckState(f.pattern_list.item(r).checkState().Checked)
        f.language.setCurrentIndex(0 if language == "en" else 1)
        f.search()
        f.mark.emit(f.ticked(all_=True))
        w.pick([1], False)
        f.move(2000, 2000)
        app.processEvents()
        w.grab().save(str(folder / f"window_{language}.png"))
        f.move(0, 0)
        f.results.setCurrentRow(-1)
        app.processEvents()
        f.grab().save(str(folder / f"find_{language}.png"))
        f.close()
        d = PropertiesDialog([w.boxes[1]], swatch, color_name, w)
        d.show()
        app.processEvents()
        d.grab().save(str(folder / f"properties_{language}.png"))
        d.close()
        w.boxes = w.saved = []
        w.close()


def main(argv=None):
    parser = argparse.ArgumentParser(prog="tools/screenshots.py", description="Make the README's screenshots.")
    parser.add_argument("-o", "--output", type=Path, default=ROOT / "docs" / "img")
    args = parser.parse_args(argv)
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    with tempfile.TemporaryDirectory() as config:
        os.environ["PY_REDACT_CONFIG"] = config
        os.environ["XDG_CONFIG_HOME"] = config
        args.output.mkdir(parents=True, exist_ok=True)
        for language in ("en", "es"):
            shoot(args.output, language)
    for p in sorted(args.output.glob("*.png")):
        print(p.relative_to(ROOT) if p.is_relative_to(ROOT) else p)


if __name__ == "__main__":
    main()
