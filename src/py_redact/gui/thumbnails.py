"""The list of pages of the main window, with their thumbnails (drawn in another
process when it can: see renderer.py) and their labels."""

from __future__ import annotations


from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QColor, QIcon, QImage, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QListWidgetItem

from .canvas import page_image
from .renderer import renderer
from .common import THUMB


class ThumbnailsMixin:
    """(Mixed into MainWindow: it uses its attributes.)"""

    def _fill_pages(self):
        self.pages.clear()
        blank = QPixmap(THUMB)
        blank.fill(QColor(0, 0, 0, 0))
        for n in range(self.count):
            item = QListWidgetItem(QIcon(blank), str(n + 1))
            item.setTextAlignment(Qt.AlignmentFlag.AlignHCenter)
            self.pages.addItem(item)
        self.page_spin.blockSignals(True)
        self.page_spin.setMaximum(max(self.count, 1))
        self.page_spin.setSuffix(f" / {self.count}")
        self.page_spin.blockSignals(False)
        self.thumb_timer.start()

    def _draw_thumbnails(self):
        """Draw one thumbnail at each turn of the event loop, those in view first,
        so that the window answers between them (a scanned page can take a
        fifth of a second)."""
        if self.doc is None:
            self.thumb_timer.stop()
            return
        top = self.pages.indexAt(QPoint(10, 10)).row()
        start = max(top, 0)
        n = next((m for m in [*range(start, self.count), *range(0, start)] if m not in self._thumbs), None)
        if n is None:
            self.thumb_timer.stop()
            return
        page = self.doc[n]
        scale = min(THUMB.width() / page.rect.width, THUMB.height() / page.rect.height)
        remote = renderer()
        if self.canvas.source is not None and remote.available():
            # (in another process: the timer waits until it is drawn, then goes on with the next)
            self.thumb_timer.stop()
            source = self.canvas.source
            remote.request("thumbs", source, n, round(scale, 4),
                           lambda image: self._thumb_arrived(source, n, scale, image))
            return
        self._thumbs[n] = page_image(page, scale)
        self._thumb(n)

    def _thumb_arrived(self, source, n: int, scale: float, image: QImage | None):
        if self.doc is None or source != self.canvas.source:
            return  # (of a document no longer open)
        self._thumbs[n] = image if image is not None else page_image(self.doc[n], scale)
        self._thumb(n)
        self.thumb_timer.start()

    def _thumb(self, n: int):
        """The thumbnail of page N, with its boxes (drawn again only if they changed)."""
        image = self._thumbs.get(n)
        if image is None or n >= self.pages.count():
            return
        boxes = self._by_page[n] if n < len(self._by_page) else []
        shown = tuple((b.rect, b.color) for b in boxes)
        if self._thumb_shown.get(n) == shown:
            return
        self._thumb_shown[n] = shown
        pixmap = QPixmap(THUMB)
        pixmap.fill(QColor(0, 0, 0, 0))
        p = QPainter(pixmap)
        x, y = (THUMB.width() - image.width()) // 2, THUMB.height() - image.height()
        p.drawImage(x, y, image)
        page = self.doc[n]
        scale = image.width() / page.rect.width
        for box in boxes:
            x0, y0, x1, y1 = (v * scale for v in box.rect)
            p.fillRect(int(x + x0), int(y + y0), max(int(x1 - x0), 1), max(int(y1 - y0), 1), QColor(box.color))
            p.setPen(QColor(128, 128, 128))
            p.drawRect(int(x + x0), int(y + y0), max(int(x1 - x0), 1), max(int(y1 - y0), 1))
        p.setPen(QPen(QColor(128, 128, 128)))
        p.drawRect(x, y, image.width() - 1, image.height() - 1)
        p.end()
        self.pages.item(n).setIcon(QIcon(pixmap))

    def _label_pages(self):
        if self.doc is None:
            return
        self._by_page = [[] for _ in range(self.count)]
        for box in self.boxes:
            for n in box.pages(self.count):
                self._by_page[n].append(box)
        for n in range(min(self.count, self.pages.count())):
            item = self.pages.item(n)
            count = len(self._by_page[n])
            text = f"{n + 1}  ● {count}" if count else str(n + 1)
            if item.text() != text:
                item.setText(text)
            self._thumb(n)
