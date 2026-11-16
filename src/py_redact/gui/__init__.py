"""The window of py-redact (PySide6 / Qt 6). Start it with ``py-redact [file.pdf]``."""

from __future__ import annotations

import sys
from pathlib import Path


def app_icon():
    from PySide6.QtGui import QIcon

    icon = QIcon()
    hicolor = Path(__file__).resolve().parent.parent / "icons" / "linux" / "hicolor"
    for png in sorted(hicolor.glob("*/apps/py-redact.png")):
        icon.addFile(str(png))
    return icon


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] in ("--version", "-V"):
        from .. import __version__

        print(f"py-redact {__version__}")
        return 0
    if argv and argv[0] in ("--help", "-h"):
        print("Usage: py-redact [file.pdf]")
        return 0
    from .. import interface

    interface.use_configured()
    from PySide6.QtWidgets import QApplication

    from .window import _WINDOWS, MainWindow, install_qt_translations

    app = QApplication.instance() or QApplication([sys.argv[0]] + argv)
    app.setApplicationName("py-redact")
    app.setOrganizationName("py-redact")
    app.setDesktopFileName("py-redact")
    app.setWindowIcon(app_icon())
    install_qt_translations()
    win = MainWindow()
    _WINDOWS.append(win)
    files = [a for a in argv if a.lower().endswith(".pdf")]
    if files:
        win.open_path(Path(files[0]))
    win.show()
    return app.exec()
