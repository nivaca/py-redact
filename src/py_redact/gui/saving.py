"""Saving the redacted copy from the main window, with the checks after saving
(the text under the boxes, the bookmarks), PDF/A or PDF/X, and saving without
the hidden information."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QFileDialog, QMessageBox

from .. import conform
from ..interface import ntr, tr
from ..pagesel import check
from ..redact import RedactError, bookmark_leaks, check_redacted, remove_bookmarks, sanitize, write_redacted
from . import background
from .renderer import renderer
from .background import Cancelled


class SavingMixin:
    """(Mixed into MainWindow: it uses its attributes.)"""

    def save_dialog(self, standard: str = "") -> bool:
        """Save the redacted copy, as a plain PDF or, this once, as STANDARD ('a-2b', 'x-4'...)."""
        if self.path is None:
            return False
        if not self.boxes and self.meta is None:
            self.status(tr("There is nothing to save: no boxes, and the metadata is the document's own"),
                        error=True)
            return False
        bad = [b for b in self.boxes if b.repeat.strip() and check(b.repeat)]
        if bad:
            self.status(tr("A box has pages that can't be read: {error}", error=check(bad[0].repeat)), error=True)
            return False
        default = Path(self.last_dir()) / f"{self.path.stem}-redacted.pdf"
        title = tr("Save the redacted copy") if not standard \
            else tr("Save the redacted copy as {standard}", standard=conform.label(standard))
        name, _ = QFileDialog.getSaveFileName(self, title, str(default), tr("PDF files (*.pdf)"))
        if not name:
            return False
        target = Path(name)
        if target.suffix.lower() != ".pdf":
            target = target.with_suffix(".pdf")
        return self.save_to(target, standard)

    def save_to(self, target: Path, standard: str = "") -> bool:
        """Write the redacted copy as TARGET: a plain PDF or, if given, STANDARD."""
        replacing = target.resolve() == self.path.resolve()
        if replacing and QMessageBox.warning(
                self, tr("Replace the original"),
                tr("The redacted copy will take the place of {name}, and what is under the boxes will be lost "
                   "for good. Go on?", name=self.path.name),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Cancel) != QMessageBox.StandardButton.Yes:
            return False
        if replacing:  # (the file is about to change under the open document, and the processes that draw it)
            self.doc.close()
            self.doc = None
            renderer().shutdown(wait=True)
        # (in a process of its own, which can be stopped: see background.py; until
        # the copy is complete, it is written as PART, next to it)
        part = target.with_name(f".{target.name}.part")
        try:
            done = background.run(self, tr("Writing the redacted copy…"), write_redacted, self.path, self.boxes,
                                  target, self.password, self.prefs.clean, self.prefs.images, self.prefs.drawings,
                                  self.meta, part, cancel=True)
        except (RedactError, Cancelled) as e:
            part.unlink(missing_ok=True)
            if replacing:
                self._load(self.path, self.password)
                self.refresh()
            if isinstance(e, Cancelled):
                self.status(tr("Saving was stopped: nothing was written"))
            else:
                self.status(str(e), error=True)
            return False
        # (before PDF/A or PDF/X: changing the copy afterwards could undo its conformance)
        bookmarks = "" if replacing else self.check_bookmarks(target)
        check_ = ""
        if standard and not conform.available():
            self.warn(conform.label(standard), tr("The redacted copy was saved as a plain PDF: {command} is not "
                                                  "installed (or not where Settings say)", command=conform.COMMAND))
            standard = ""
        if standard:
            try:  # (another program: in a thread, which waits for it)
                check_ = background.run(self, tr("Making {standard} with {command}…", standard=conform.label(standard),
                                                 command=conform.COMMAND),
                                        conform.convert, target, target, standard, self.password, thread=True)
            except conform.ConformError as e:
                self.warn(conform.label(standard),
                          tr("The redacted copy was saved as a plain PDF, but it could not be made "
                             "{standard}:\n\n{error}", standard=conform.label(standard), error=e))
                standard = ""
        self.settings.setValue("last_dir", str(target.parent))
        self.add_recent(target)
        leaks = [] if replacing else self.check_copy(target)
        self.saved = list(self.boxes)
        self.saved_meta = self.meta
        if replacing:  # (the boxes are in the file now)
            page = self.page
            self._load(self.path, self.password)
            self.boxes, self.saved, self.undo_stack, self.redo_stack, self.selected = [], [], [], [], []
            self.meta = self.saved_meta = None  # (the metadata is in the file now too)
            self.refresh()
            self.show_page(page)
        self._update_title()
        message = ntr("Saved {path} ({count} area redacted)", "Saved {path} ({count} areas redacted)", done,
                      path=target)
        if standard:
            message += " — " + conform.label(standard) + (f" ({check_})" if check_ else "")
            if self.password:
                message += " — " + tr("PDF/A and PDF/X can't be protected: the copy has no password")
        if leaks:
            self.warn(tr("Check the redacted copy"),
                                tr("Some text can still be read under the boxes of {name}:", name=target.name)
                                + "\n\n" + "\n".join(tr("Page {page}: {context}", page=p + 1, context=t)
                                                     for p, t in leaks[:10]))
        elif not replacing:
            message += " — " + tr("checked: nothing under the boxes can be read")
        if bookmarks:
            message += " — " + bookmarks
        self.status(message)
        return True

    def check_bookmarks(self, target: Path) -> str:
        """Look for bookmarks of TARGET that give away what was redacted, and
        take them out if the user wants. Returns what was done, for the status bar."""
        try:
            leaks = background.run(self, tr("Checking the bookmarks of the copy…"), bookmark_leaks, self.path, target,
                                   self.boxes, self.password)
        except RedactError as e:
            self.status(str(e), error=True)
            return ""
        if not leaks:
            return ""
        choice = self.ask_bookmarks(target.name, leaks)
        if not choice:
            return ntr("{count} bookmark that gives away what was redacted was kept",
                       "{count} bookmarks that give away what was redacted were kept", len(leaks))
        try:
            background.run(self, tr("Removing the bookmarks…"), remove_bookmarks, target,
                           None if choice == "all" else {i for i, _, _ in leaks}, self.password)
        except RedactError as e:
            self.status(str(e), error=True)
            return ""
        return tr("all the bookmarks were removed") if choice == "all" \
            else ntr("{count} bookmark was removed", "{count} bookmarks were removed", len(leaks))

    def ask_bookmarks(self, name: str, leaks: list[tuple[int, str, str]]) -> str:
        """What to do with bookmarks that give away what was redacted: 'these'
        (remove them), 'all' (remove all the bookmarks) or '' (keep them)."""
        box = QMessageBox(QMessageBox.Icon.Warning, tr("Check the redacted copy"),
                          ntr("A bookmark of {name} may give away what was redacted:",
                              "{count} bookmarks of {name} may give away what was redacted:", len(leaks),
                              name=name)
                          + "\n\n" + "\n".join(f"• “{title}”: {why}" for _, title, why in leaks[:12]),
                          QMessageBox.StandardButton.NoButton, self)
        these = box.addButton(ntr("Remove it", "Remove them", len(leaks)), QMessageBox.ButtonRole.AcceptRole)
        everything = box.addButton(tr("Remove all the bookmarks"), QMessageBox.ButtonRole.DestructiveRole)
        box.addButton(tr("Keep them"), QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(these)
        box.exec()
        clicked = box.clickedButton()
        return "these" if clicked is these else "all" if clicked is everything else ""

    def check_copy(self, target: Path) -> list[tuple[int, str]]:
        """What can still be read under the boxes in TARGET (see redact.check_redacted)."""
        try:
            return background.run(self, tr("Checking that nothing under the boxes can be read…"), check_redacted,
                                  self.path, target, self.boxes, self.password)
        except RedactError as e:
            self.status(str(e), error=True)
            return []

    def sanitize_dialog(self, kinds: set[str] | None = None) -> bool:
        if self.path is None:
            return False
        default = Path(self.last_dir()) / f"{self.path.stem}-sanitized.pdf"
        name, _ = QFileDialog.getSaveFileName(self, tr("Sanitize the document"), str(default),
                                              tr("PDF files (*.pdf)"))
        if not name:
            return False
        target = Path(name)
        if target.resolve() == self.path.resolve():
            self.status(tr("Choose another name: the document stays open"), error=True)
            return False
        try:
            background.run(self, tr("Writing the sanitized copy…"), sanitize, self.path, target, self.password, kinds)
        except RedactError as e:
            self.status(str(e), error=True)
            return False
        self.status(tr("Saved {path}, sanitized", path=target))
        return True

    def _show_output(self):
        """The Save as menu: PDF/A and PDF/X greyed out if pdf2iso isn't there."""
        have = conform.available()
        for value, act in self.output_actions.items():
            act.setEnabled(self.can_save() and (have or not value))
            if value:
                act.setEnabled(have)
                act.setToolTip("" if have else tr("Needs {command}: install it, or say where it is in Settings",
                                                  command=conform.COMMAND))
        self._toolbar_tips()
