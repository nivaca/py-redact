"""Long work away from the window. Writing the redacted copy of a book and
checking it take seconds, and PyMuPDF keeps Python's lock all that time, so
a thread wouldn't let the window answer: the work is done in a process of
its own (see worker.py), while the window goes on drawing itself and shows
what is being done. The conversion to PDF/A or PDF/X, another program,
waits in a thread instead.

run() waits for the work and returns what it returns (or raises what it
raises), so that the steps of saving stay one after the other (see
saving.py); meanwhile the window can't be changed. If no process can be
started, the work is done in the window's own, as before.
"""

from __future__ import annotations

import multiprocessing
import threading

from PySide6.QtCore import QEventLoop, Qt, QTimer
from PySide6.QtWidgets import QProgressDialog

from .. import interface, worker
from ..interface import tr

ENABLED = True  # (the tests turn it off: they want the work done at once)
SHOW_AFTER = 400  # milliseconds: quick work shows no dialog
POLL = 20  # milliseconds between looks at the work


class Cancelled(Exception):
    """The user stopped the work."""


def run(parent, text: str, func, *args, cancel: bool = False, thread: bool = False):
    """FUNC(*ARGS) in a process of its own (or, with THREAD, in a thread),
    showing TEXT, if it takes a while, in a dialog over PARENT, with a Cancel
    button if CANCEL (which raises Cancelled; only for work that can be
    stopped halfway without harm)."""
    if not ENABLED:
        return func(*args)
    if thread:
        answer: list = []

        def work():
            try:
                answer.append((True, func(*args)))
            except BaseException as e:  # noqa: BLE001
                answer.append((False, e))

        t = threading.Thread(target=work, daemon=True)
        t.start()
        done, stop = (lambda: not t.is_alive()), None
        receive = lambda: answer[0]  # noqa: E731
    else:
        context = multiprocessing.get_context("spawn")
        try:
            here, there = context.Pipe(duplex=False)
            process = context.Process(target=worker.run_and_send, args=(there, interface.code(), func, args),
                                      daemon=True)
            process.start()
        except Exception:  # (no process: do it here)
            return func(*args)
        there.close()
        done = lambda: here.poll() or not process.is_alive()  # noqa: E731

        def receive():
            if here.poll():
                try:
                    return here.recv()
                except EOFError:
                    pass
            return (False, RuntimeError(tr("The work stopped before it was done")))

        def stop():
            process.terminate()
            process.join()

    ok, value = _wait(parent, text, done, receive, stop if cancel else None)
    if not thread:
        process.join()
        here.close()
    if ok:
        return value
    raise value


def _wait(parent, text: str, done, receive, stop):
    """Let the window draw itself until DONE(), with a dialog after SHOW_AFTER;
    then RECEIVE(). Until the dialog shows, clicks and keys wait (they would
    change the boxes being saved); then the dialog keeps them from the window."""
    loop = QEventLoop()
    dialog = QProgressDialog(text, tr("Cancel"), 0, 0, parent)
    dialog.setWindowTitle("py-redact")
    dialog.setWindowModality(Qt.WindowModality.WindowModal)
    dialog.setAutoReset(False)
    dialog.setAutoClose(False)
    if stop is None:
        dialog.setCancelButton(None)
    dialog.hide()
    cancelled = []

    def cancel():
        cancelled.append(True)
        stop()

    dialog.canceled.connect(cancel)
    timer = QTimer()  # (it wakes the loop below, to look at the work again)
    timer.start(POLL)
    shower = QTimer()
    shower.setSingleShot(True)
    shower.timeout.connect(dialog.show)
    shower.start(SHOW_AFTER)
    while not cancelled and not done():
        flags = QEventLoop.ProcessEventsFlag.AllEvents if dialog.isVisible() \
            else QEventLoop.ProcessEventsFlag.ExcludeUserInputEvents
        loop.processEvents(flags | QEventLoop.ProcessEventsFlag.WaitForMoreEvents)
    timer.stop()
    shower.stop()
    dialog.canceled.disconnect(cancel)
    dialog.close()
    dialog.deleteLater()
    if cancelled:
        return False, Cancelled()
    return receive()
