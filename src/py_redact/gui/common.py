"""What the main window and its parts share: constants, icons, colour swatches."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSize
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QApplication

from .. import interface
from ..interface import N_, tr

RECENT = 10  # documents in File ▸ Open recent
AUTHOR = '<a href="https://nicolasvaughan.org">Nicolas Vaughan</a>'
THUMB = QSize(84, 112)  # the largest thumbnail of a page
SWATCHES = [("#000000", N_("Black")), ("#ffffff", N_("White")), ("#808080", N_("Grey")), ("", N_("No colour"))]
# the choices of "Pages": (what is kept in Box.repeat, its name); '*' is a list typed by the user
REPEATS = [("", N_("Only the page where it was drawn")), ("all", N_("All pages")), ("odd", N_("Odd pages")),
           ("even", N_("Even pages")), ("*", N_("These pages:"))]

def install_qt_translations():
    """Qt's own texts (file dialogs, standard buttons) in the language in use."""
    from PySide6.QtCore import QLibraryInfo, QLocale, QTranslator

    app = QApplication.instance()
    for old in getattr(app, "_py_redact_translators", []):
        app.removeTranslator(old)
    app._py_redact_translators = []
    code = interface.code()
    QLocale.setDefault(QLocale(code))
    if code == "en":
        return
    folder = QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)
    for name in ("qtbase", "qt"):
        t = QTranslator(app)
        if t.load(f"{name}_{code}", folder):
            app.installTranslator(t)
            app._py_redact_translators.append(t)
            break


ACTIONS = Path(__file__).resolve().parent.parent / "icons" / "actions"


def icon(name: str) -> QIcon:
    """The icon NAME (a freedesktop name: document-open...) of the desktop's icon
    theme, so that it looks like the rest of the desktop; or else the program's own."""
    own = ACTIONS / f"{name}.svg"
    return QIcon.fromTheme(name, QIcon(str(own)) if own.is_file() else QIcon())


def swatch(color: str, size: int = 16) -> QIcon:
    """A square of COLOR; for no colour (''), an empty square crossed out."""
    pixmap = QPixmap(size, size)
    pixmap.fill(QColor(color) if color else QColor(0, 0, 0, 0))
    p = QPainter(pixmap)
    if not color:
        p.setPen(QColor(208, 48, 48))
        p.drawLine(1, size - 2, size - 2, 1)
    p.setPen(QColor(128, 128, 128))
    p.drawRect(0, 0, size - 1, size - 1)
    p.end()
    return QIcon(pixmap)


def color_name(color: str) -> str:
    for value, name in SWATCHES:
        if value == color.lower():
            return tr(name)
    return color.lower()


def mm(points: float) -> str:
    return f"{points / 72 * 25.4:.0f}"
