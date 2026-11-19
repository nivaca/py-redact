"""py-redact on a real screen (not Qt's offscreen platform), run by
.github/workflows/installers.yml on GitHub's machines with the Python of an
installed py-redact:

    python .github/smoke.py FOLDER

It opens a PDF of five pages in the window, waits until the pages and the
thumbnails come from the processes that draw them, draws a box, saves the
redacted copy (in the process that writes and checks it), checks that what
was under the box is gone, and takes pictures of the screen into FOLDER:
window.png, and menu.png with the menu of the box open. It fails (exit 1)
if any of it doesn't happen within a minute.

Its settings go to FOLDER, not the user's: the configuration file, and, on
Linux, the window's own (recent files, size). On macOS and Windows those of
the window go where they always do (GitHub's machines are thrown away).
"""

from __future__ import annotations

import sys
import time
from pathlib import Path


def main() -> int:
    out = Path(sys.argv[1]).resolve()
    out.mkdir(parents=True, exist_ok=True)
    import os

    os.environ["PY_REDACT_CONFIG"] = str(out / "config")
    import pymupdf

    sample = out / "sample.pdf"
    doc = pymupdf.open()
    for i in range(5):
        page = doc.new_page()
        page.insert_text((72, 60), f"HEADER{i + 1}", fontsize=14)
        page.insert_text((72, 120), f"Name: Person{i + 1}", fontsize=12)
        page.insert_text((72, 300), "Body text stays", fontsize=12)
    doc.save(sample)

    from PySide6.QtCore import QSettings, QTimer

    QSettings.setPath(QSettings.Format.NativeFormat, QSettings.Scope.UserScope, str(out / "settings"))
    from PySide6.QtWidgets import QApplication

    from py_redact.gui import app_icon, macos_name
    from py_redact.gui.window import MainWindow
    from py_redact.redact import Box

    macos_name()
    app = QApplication([sys.argv[0]])
    app.setWindowIcon(app_icon())
    print("platform:", app.platformName(), flush=True)
    w = MainWindow()
    w.warn = lambda title, text: print("warning:", title, text, flush=True)
    w.resize(1100, 760)
    w.show()
    w.raise_()
    w.activateWindow()

    def wait(what, condition, seconds=60):
        end = time.monotonic() + seconds
        while not condition():
            if time.monotonic() > end:
                raise SystemExit(f"timed out: {what}")
            app.processEvents()
            time.sleep(0.02)
        print("ok:", what, flush=True)

    def picture(name):
        for _ in range(20):
            app.processEvents()
            time.sleep(0.02)
        screen = w.screen() or app.primaryScreen()
        shot = screen.grabWindow(0)
        if shot.isNull() or not shot.save(str(out / name)):
            shot = w.grab()  # (where the screen can't be read: the window alone)
            shot.save(str(out / name))
        print("picture:", out / name, shot.width(), "x", shot.height(), flush=True)

    assert w.open_path(sample)
    canvas = w.canvas
    wait("the page, drawn in another process", lambda: canvas._wanted is None and not canvas.pixmap_item.pixmap().isNull())
    wait("the thumbnails", lambda: len(w._thumbs) == 5)
    w.change([Box(0, (60, 100, 300, 128), text="REDACTED")])
    picture("window.png")

    target = out / "redacted.pdf"
    assert w.save_to(target), w.statusBar().currentMessage()
    print("status:", w.statusBar().currentMessage(), flush=True)
    with pymupdf.open(target) as d:
        text = d[0].get_text()
    assert "Person1" not in text and "Body text stays" in text, text
    print("ok: the copy is redacted", flush=True)

    # (the menu of the box, open on the screen for a moment)
    QTimer.singleShot(800, lambda: (picture("menu.png"), app.activePopupWidget() and app.activePopupWidget().close()))
    point = canvas.mapToGlobal(canvas.mapFromScene(180, 114))
    w.box_menu(0, point)
    w.boxes = w.saved = []
    w.close()
    from py_redact.gui.renderer import renderer

    renderer().shutdown()
    return 0


if __name__ == "__main__":  # (guarded: the processes that draw the pages import it again)
    raise SystemExit(main())
