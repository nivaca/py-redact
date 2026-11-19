"""Pages rendered in other processes, so that the window answers while they
are rendered (see rendering.py). There are two lanes, each with a process
of its own: 'view' for the page shown and the pages next to it, 'thumbs' for
the thumbnails; so a page asked for never waits behind the thumbnails.

Each lane renders one page at a time and keeps its own queue, so a request
can go before the others (the page just asked for) and those no longer
wanted can be dropped (the pages next to one left behind). If the processes
can't be started, or die, available() is False and the window renders in
its own process, as before.
"""

from __future__ import annotations

import multiprocessing
from concurrent.futures import ProcessPoolExecutor
from typing import Callable

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QImage

from .. import rendering

ENABLED = True  # (the tests turn it off: they want the page drawn at once)

Source = tuple[str, str, tuple]  # path, password, stamp (the file's time and size)


class Lane:
    def __init__(self):
        self.pool: ProcessPoolExecutor | None = None
        self.busy: tuple | None = None  # the key being rendered
        self.waiting: list[tuple] = []  # (key, arguments), in order
        self.callbacks: dict[tuple, list[Callable]] = {}


class Renderer(QObject):
    _arrived = Signal(object)  # (lane, key, future): from the executor's thread to the window's

    def __init__(self):
        super().__init__()
        self.lanes: dict[str, Lane] = {}
        self.broken = False
        self._arrived.connect(self._deliver)

    def available(self) -> bool:
        return ENABLED and not self.broken

    def request(self, lane: str, source: Source, number: int, scale: float, callback: Callable,
                first: bool = False) -> None:
        """Render page NUMBER of SOURCE at SCALE, and give CALLBACK the QImage (or
        None if it couldn't be rendered there). FIRST: before those waiting."""
        ln = self.lanes.setdefault(lane, Lane())
        key = (source[0], source[2], number, scale)
        ln.callbacks.setdefault(key, []).append(callback)
        if key == ln.busy:
            return
        entry = next((e for e in ln.waiting if e[0] == key), None)
        if entry is not None:
            ln.waiting.remove(entry)
        else:
            entry = (key, (source[0], source[1], source[2], number, scale))
        if first:
            ln.waiting.insert(0, entry)
        else:
            ln.waiting.append(entry)
        self._next(lane)

    def drop(self, lane: str, keep: Callable[[str, int], bool] = lambda path, number: False) -> None:
        """Forget the requests waiting in LANE, but those whose (path, page) KEEP wants."""
        ln = self.lanes.get(lane)
        if ln is None:
            return
        for entry in [e for e in ln.waiting if not keep(e[0][0], e[0][2])]:
            ln.waiting.remove(entry)
            ln.callbacks.pop(entry[0], None)

    def busy(self, lane: str) -> bool:
        ln = self.lanes.get(lane)
        return ln is not None and (ln.busy is not None or bool(ln.waiting))

    def _next(self, lane: str) -> None:
        ln = self.lanes[lane]
        if ln.busy is not None or not ln.waiting:
            return
        key, args = ln.waiting.pop(0)
        try:
            if ln.pool is None:
                ln.pool = ProcessPoolExecutor(max_workers=1, mp_context=multiprocessing.get_context("spawn"))
            future = ln.pool.submit(rendering.render, *args)
        except Exception:  # (no process could be started: render in the window's)
            self._fail()
            return
        ln.busy = key
        future.add_done_callback(lambda f: self._arrived.emit((lane, key, f)))

    def _deliver(self, item: tuple) -> None:
        lane, key, future = item
        ln = self.lanes[lane]
        ln.busy = None
        image = None
        try:
            width, height, stride, data = future.result()
            image = QImage(data, width, height, stride, QImage.Format.Format_RGB888).copy()
        except Exception as e:
            from concurrent.futures.process import BrokenProcessPool

            if isinstance(e, BrokenProcessPool):
                self._fail()
                return
        for callback in ln.callbacks.pop(key, []):
            _call(callback, image)
        self._next(lane)

    def _fail(self) -> None:
        """The processes can't render: tell all who wait (they render themselves)."""
        self.broken = True
        lanes, self.lanes = self.lanes, {}
        for ln in lanes.values():
            if ln.pool is not None:
                ln.pool.shutdown(wait=False, cancel_futures=True)
            for callbacks in ln.callbacks.values():
                for callback in callbacks:
                    _call(callback, None)

    def shutdown(self, wait: bool = False) -> None:
        """Stop the processes (they are started again when a page is asked for).
        WAIT: until they are gone, and the files they had open are closed (on
        Windows, an open file can't be replaced)."""
        for ln in self.lanes.values():
            if ln.pool is not None:
                ln.pool.shutdown(wait=wait, cancel_futures=True)
        self.lanes = {}


def _call(callback: Callable, image: QImage | None) -> None:
    try:
        callback(image)
    except RuntimeError:  # (its window was closed meanwhile)
        pass


_RENDERER: Renderer | None = None


def renderer() -> Renderer:
    """The one renderer of the application, for all its windows."""
    global _RENDERER
    if _RENDERER is None:
        _RENDERER = Renderer()
        from PySide6.QtCore import QCoreApplication

        app = QCoreApplication.instance()
        if app is not None:
            app.aboutToQuit.connect(_RENDERER.shutdown)
    return _RENDERER

