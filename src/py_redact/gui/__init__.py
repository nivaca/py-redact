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


def macos_name(name: str = "py-redact") -> None:
    """On macOS, call the application NAME in the menu bar. It runs as Python
    (the installer's application starts the Python of its environment), and
    macOS names the menu after the bundle of the program that runs, which is
    Python's; so NAME is put in that bundle's information, in this process
    only, before Qt reads it. Done through the Objective-C runtime, with
    ctypes; if anything is missing, the name stays as it was."""
    if sys.platform != "darwin":
        return
    try:
        import ctypes
        import ctypes.util

        objc = ctypes.cdll.LoadLibrary(ctypes.util.find_library("objc"))
        ctypes.cdll.LoadLibrary(ctypes.util.find_library("Foundation"))
        objc.objc_getClass.restype = objc.sel_registerName.restype = ctypes.c_void_p
        objc.objc_getClass.argtypes = objc.sel_registerName.argtypes = [ctypes.c_char_p]
        address = ctypes.cast(objc.objc_msgSend, ctypes.c_void_p).value
        p = ctypes.c_void_p
        send = ctypes.CFUNCTYPE(p, p, p)(address)
        send_text = ctypes.CFUNCTYPE(p, p, p, ctypes.c_char_p)(address)
        send_pair = ctypes.CFUNCTYPE(None, p, p, p, p)(address)
        sel = objc.sel_registerName
        string = objc.objc_getClass(b"NSString")
        info = send(send(objc.objc_getClass(b"NSBundle"), sel(b"mainBundle")), sel(b"infoDictionary"))
        if info:
            for key in (b"CFBundleName", b"CFBundleDisplayName"):
                send_pair(info, sel(b"setObject:forKey:"),
                          send_text(string, sel(b"stringWithUTF8String:"), name.encode()),
                          send_text(string, sel(b"stringWithUTF8String:"), key))
    except Exception:  # (the name stays Python's)
        pass


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

    macos_name()
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
