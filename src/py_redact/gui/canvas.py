"""The page being redacted, and its boxes: drawn by dragging on the page,
moved by dragging them, resized by dragging their edges and corners."""

from __future__ import annotations

import pymupdf
from PySide6.QtCore import QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QBrush, QColor, QCursor, QImage, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QGraphicsPixmapItem, QGraphicsRectItem, QGraphicsScene, QGraphicsView

from ..interface import tr
from ..redact import Box, Rect, image_at, nearest_word, normalized, text_rects, words

SCENE_MARGIN = 12  # points around the page
MIN_SIZE = 2.0  # points: a smaller drag is a click
GRIP = 6  # pixels from an edge where dragging resizes
MAX_PIXELS = 40_000_000  # the largest rendering of a page
CACHED_PAGES = 6  # renderings kept, so that a change of the boxes or a page turned back needn't render again
SELECTED = QColor(42, 127, 255)
OUTLINE = QColor(208, 48, 48)  # (marks not yet applied: red)
NEAR_TEXT = 3.0  # points: a drag that starts this close to a word selects text


def page_image(page: pymupdf.Page, scale: float) -> QImage:
    pix = page.get_pixmap(matrix=pymupdf.Matrix(scale, scale), alpha=False)
    return QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format.Format_RGB888).copy()


class BoxItem(QGraphicsRectItem):
    """A box not yet applied: see-through, with a red outline (blue when
    selected), dashed if it goes on other pages; its text shown as it will be."""

    def __init__(self, index: int, box: Box, own: bool, selected: bool, outline: QColor = OUTLINE,
                 opacity: int = 60):
        super().__init__(QRectF(QPointF(box.rect[0], box.rect[1]), QPointF(box.rect[2], box.rect[3])))
        self.index = index
        self.box = box
        self.own = own
        self.chosen = selected
        self.outline = QColor(outline)
        self.preview = False  # (the mouse is over it: shown as it will be)
        self.setAcceptHoverEvents(True)
        if box.color:
            fill = QColor(box.color)
            fill.setAlpha(round(255 * opacity / 100))
            self.setBrush(QBrush(fill))
        else:  # (no colour: only the content goes)
            hatch = QColor(self.outline)
            hatch.setAlpha(110)
            self.setBrush(QBrush(hatch, Qt.BrushStyle.BDiagPattern))
        pen = QPen(SELECTED if selected else self.outline, 2 if selected else 1.5)
        pen.setCosmetic(True)
        if not own or box.repeat.strip():
            pen.setStyle(Qt.PenStyle.DashLine)
        self.setPen(pen)
        self.setZValue(2 if selected else 1)
        if box.repeat.strip():
            tip = tr("Drawn on page {page}, repeated on: {pages}", page=box.page + 1, pages=box.repeat)
        else:
            tip = tr("Only on this page")
        if box.locked:
            tip += " — " + tr("locked")
        if box.note:
            tip = f"<b>{box.note}</b><br>{tip}"
        self.setToolTip(tip)

    def hoverEnterEvent(self, event):
        self.preview = True
        self.update()
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        self.preview = False
        self.update()
        super().hoverLeaveEvent(event)

    def paint(self, painter, option, widget=None):
        from ..redact import overlay

        r = self.rect()
        if self.preview:  # (as it will be once applied: opaque, or the bare page for no colour)
            painter.fillRect(r, QColor(self.box.color) if self.box.color else QColor("white"))
            painter.setPen(self.pen())
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(r)
        else:
            super().paint(painter, option, widget)
        text, size = overlay(self.box, pymupdf.Rect(r.left(), r.top(), r.right(), r.bottom()))
        if text:
            font = painter.font()
            font.setFamily("Helvetica")
            font.setPointSizeF(size)
            painter.setFont(font)
            painter.setPen(QColor(self.box.text_color))
            flags = {"left": Qt.AlignmentFlag.AlignLeft, "right": Qt.AlignmentFlag.AlignRight}.get(
                self.box.align, Qt.AlignmentFlag.AlignHCenter) | Qt.AlignmentFlag.AlignVCenter
            painter.drawText(r.adjusted(1, 0, -1, 0), flags, text)
        scale = painter.worldTransform().m11() or 1
        if self.box.locked:  # (a small padlock in the corner)
            side = 9 / scale
            x, y = r.right() - side - 2 / scale, r.top() + 2 / scale
            painter.setPen(QPen(OUTLINE, 1.2 / scale))
            painter.setBrush(QColor(255, 255, 255, 220))
            painter.drawRect(QRectF(x, y + side * 0.45, side, side * 0.55))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawArc(QRectF(x + side * 0.2, y, side * 0.6, side * 0.9), 0, 180 * 16)
        elif self.chosen:  # (the corners, of a fixed size on the screen)
            side = 7 / scale
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(SELECTED)
            for corner in (r.topLeft(), r.topRight(), r.bottomLeft(), r.bottomRight()):
                painter.drawRect(QRectF(corner.x() - side / 2, corner.y() - side / 2, side, side))


class PageCanvas(QGraphicsView):
    """A page and its boxes. The boxes are identified by their index in the
    window's list; what the user does is reported with the signals."""

    drawn = Signal(tuple)  # Rect: a new box
    edited = Signal(int, tuple)  # index, Rect: a box moved or resized
    picked = Signal(list, bool)  # indices clicked; whether to add them to the selection
    zoom_changed = Signal(float)
    text_chosen = Signal(list)  # [Rect]: the lines of the text selected
    double_clicked = Signal(int, tuple)  # index of the box (-1: none), (x, y) on the page
    image_chosen = Signal(tuple)  # Rect of an image double-clicked
    menu_asked = Signal(int, object, object)  # index of the box (-1: none), place on the screen, on the page

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setScene(QGraphicsScene(self))
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        self.setDragMode(QGraphicsView.DragMode.NoDrag)
        self.setMouseTracking(True)
        self.setBackgroundBrush(self.palette().dark())
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.page: pymupdf.Page | None = None
        self.page_size = QRectF()
        self.editable = True
        self.fit = "page"  # 'page', 'width' or '' (a zoom of its own)
        # 'text': dragging over text selects it, and elsewhere draws a box (Ctrl+drag always draws one);
        # 'box': dragging draws a box; 'hand': dragging scrolls. Boxes are moved in 'text' and 'box'.
        self.mode = "text"
        self.mark_outline, self.mark_opacity = OUTLINE, 60  # (how boxes not yet applied look: Settings)
        self._words: list | None = None  # (of the page, when first needed)
        self.pixmap_item: QGraphicsPixmapItem | None = None
        self.sheet: QGraphicsRectItem | None = None
        self.items_: list[BoxItem] = []
        self._drag: dict | None = None
        self._rendered = 0.0
        self.render_timer = QTimer(self, singleShot=True, interval=120)
        self.render_timer.timeout.connect(self._render)
        from collections import OrderedDict

        self._cache: OrderedDict = OrderedDict()  # (document, page number, scale) -> QPixmap
        self._ahead: list[pymupdf.Page] = []  # pages to render while the window is idle
        self.ahead_timer = QTimer(self, singleShot=True, interval=60)
        self.ahead_timer.timeout.connect(self._render_ahead)
        # (path, password, stamp) of the document on disk, if the pages can be rendered in
        # another process (see renderer.py); and a picture to show until the page arrives
        self.source = None
        self.placeholder: QImage | None = None
        self._wanted: tuple | None = None  # the key of the rendering awaited for the page shown

    # ----------------------------------------------------------------- page and boxes

    def show_page(self, page: pymupdf.Page | None, boxes: list[tuple[int, Box, bool]], selected: list[int],
                  editable: bool = True, keep_view: bool = False):
        """PAGE, with BOXES: (index, box, whether it was drawn on this page)."""
        same = keep_view and page is not None and self.page is not None and QRectF(*page.rect) == self.page_size
        self.scene().clear()
        self.items_, self.pixmap_item, self.sheet, self._drag = [], None, None, None
        if page is not self.page:
            self._words = None
            self._wanted = None
        self.page = page
        self.editable = editable
        if page is None:
            self.page_size = QRectF()
            return
        self.page_size = QRectF(*page.rect)
        self.scene().setSceneRect(self.page_size.adjusted(-SCENE_MARGIN, -SCENE_MARGIN, SCENE_MARGIN, SCENE_MARGIN))
        self.sheet = self.scene().addRect(self.page_size, QPen(Qt.PenStyle.NoPen), QBrush(Qt.GlobalColor.white))
        self.pixmap_item = QGraphicsPixmapItem()
        self.pixmap_item.setTransformationMode(Qt.TransformationMode.SmoothTransformation)
        self.scene().addItem(self.pixmap_item)
        self._rendered = 0.0
        if editable:
            for index, box, own in boxes:
                item = BoxItem(index, box, own, index in selected, self.mark_outline, self.mark_opacity)
                self.scene().addItem(item)
                self.items_.append(item)
        if not same:
            self.apply_fit()
        self._render()

    def zoom(self) -> float:
        return self.transform().m11()

    def _scale_for(self, page: pymupdf.Page) -> float:
        """The scale to render PAGE at, for the zoom and the screen."""
        scale = self.zoom() * self.devicePixelRatioF()
        w, h = page.rect.width * scale, page.rect.height * scale
        if w * h > MAX_PIXELS:
            scale *= (MAX_PIXELS / (w * h)) ** 0.5
        return round(scale, 3)

    def _pixmap(self, page: pymupdf.Page, scale: float) -> QPixmap:
        """PAGE rendered at SCALE, from the cache if it is there."""
        key = (id(page.parent), page.number, scale)
        pixmap = self._cache.get(key)
        if pixmap is None:
            pixmap = QPixmap.fromImage(page_image(page, scale))
            self._cache[key] = pixmap
            while len(self._cache) > CACHED_PAGES:
                self._cache.popitem(last=False)
        else:
            self._cache.move_to_end(key)
        return pixmap

    def clear_cache(self):
        """Forget the renderings (another document was opened, or this one changed on disk)."""
        self._cache.clear()
        self._ahead = []

    def _remote(self):
        """The renderer of other processes, if pages are rendered there."""
        from .renderer import renderer

        r = renderer()
        return r if self.source is not None and r.available() else None

    def render_ahead(self, pages: list[pymupdf.Page]):
        """Render PAGES (the next and previous ones) when the window is idle, so that
        turning to them is at once."""
        remote = self._remote()
        if remote is None:
            self._ahead = list(pages)
            self.ahead_timer.start()
            return
        self._ahead = list(pages)
        shown = self.page.number if self.page is not None else -1
        remote.drop("view", keep=lambda path, number: number == shown)
        self._request_ahead(remote)

    def _request_ahead(self, remote):
        """Ask the other process for the pages to render ahead (at the zoom of now)."""
        for page in self._ahead:
            try:
                scale = self._scale_for(page)
            except (RuntimeError, ValueError):  # (the document was closed meanwhile)
                self._ahead = []
                return
            key = (id(page.parent), page.number, scale)
            if key not in self._cache:
                remote.request("view", self.source, page.number, scale,
                               lambda image, key=key: self._arrived(key, image))

    def _render_ahead(self):
        if not self._ahead:
            return
        page = self._ahead.pop(0)
        try:
            self._pixmap(page, self._scale_for(page))
        except (RuntimeError, ValueError):  # (the document was closed meanwhile)
            self._ahead = []
            return
        if self._ahead:
            self.ahead_timer.start()

    def _keep(self, key: tuple, image: QImage) -> QPixmap:
        pixmap = QPixmap.fromImage(image)
        self._cache[key] = pixmap
        while len(self._cache) > CACHED_PAGES:
            self._cache.popitem(last=False)
        return pixmap

    def _arrived(self, key: tuple, image: QImage | None):
        """A rendering from another process (None: it couldn't be made there)."""
        if image is not None:
            pixmap = self._keep(key, image)
        elif key == self._wanted and self.page is not None:
            pixmap = self._pixmap(self.page, key[2])  # (rendered here, then)
        else:
            return
        if key == self._wanted and self.pixmap_item is not None:
            self._wanted = None
            self.pixmap_item.setPixmap(pixmap)
            self.pixmap_item.setScale(1 / key[2])

    def _render(self):
        if self.page is None or self.pixmap_item is None:
            return
        scale = self._scale_for(self.page)
        if abs(scale - self._rendered) < 1e-3:
            return
        self._rendered = scale
        if not self.editable:  # (the result shown is a page of a document of its own, made each time: not kept)
            self.pixmap_item.setPixmap(QPixmap.fromImage(page_image(self.page, scale)))
            self.pixmap_item.setScale(1 / scale)
            return
        key = (id(self.page.parent), self.page.number, scale)
        remote = self._remote()
        if key in self._cache or remote is None:
            self._wanted = None
            self.pixmap_item.setPixmap(self._pixmap(self.page, scale))
            self.pixmap_item.setScale(1 / scale)
            return
        # (meanwhile, the page as it was, at another zoom, or its thumbnail made larger)
        if self.pixmap_item.pixmap().isNull():
            old = next((k for k in reversed(self._cache) if k[:2] == key[:2]), None)
            if old is not None:
                self.pixmap_item.setPixmap(self._cache[old])
                self.pixmap_item.setScale(1 / old[2])
            elif self.placeholder is not None and not self.placeholder.isNull():
                self.pixmap_item.setPixmap(QPixmap.fromImage(self.placeholder))
                self.pixmap_item.setScale(self.page_size.width() / self.placeholder.width())
        self._wanted = key
        remote.drop("view")  # (the pages next to one left behind, or at an older zoom)
        remote.request("view", self.source, self.page.number, scale, lambda image: self._arrived(key, image),
                       first=True)
        self._request_ahead(remote)

    # ----------------------------------------------------------------- zoom

    def set_zoom(self, factor: float, fit: str = ""):
        factor = max(0.05, min(factor, 16))
        self.fit = fit
        self.resetTransform()
        self.scale(factor, factor)
        self.render_timer.start()
        self.zoom_changed.emit(factor)

    def apply_fit(self):
        if self.page_size.isEmpty() or not self.fit:
            return
        room = self.viewport().size()
        margin = 2 * SCENE_MARGIN + 4  # (points around the page, and a few pixels)
        by_width = (room.width() - 4) / (self.page_size.width() + margin)
        by_height = (room.height() - 4) / (self.page_size.height() + margin)
        self.set_zoom(by_width if self.fit == "width" else min(by_width, by_height), self.fit)

    def zoom_by(self, factor: float):
        self.set_zoom(self.zoom() * factor)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.apply_fit()

    def wheelEvent(self, event):
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
            factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
            z = max(0.05, min(self.zoom() * factor, 16))
            self.scale(z / self.zoom(), z / self.zoom())
            self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
            self.fit = ""
            self.render_timer.start()
            self.zoom_changed.emit(z)
            event.accept()
        else:
            super().wheelEvent(event)

    # ----------------------------------------------------------------- the mouse

    def _hit(self, pos) -> tuple[BoxItem | None, str]:
        """The box at POS (view coordinates), and the edges grabbed ('' to move
        it; else some of 'l', 't', 'r', 'b')."""
        point = self.mapToScene(pos)
        grip = GRIP / (self.zoom() or 1)
        found = None
        for item in sorted(self.items_, key=lambda i: -i.zValue()):
            if item.rect().adjusted(-grip, -grip, grip, grip).contains(point):
                found = item
                break
        if found is None:
            return None, ""
        r = found.rect()
        edges = ""
        if abs(point.x() - r.left()) <= grip:
            edges += "l"
        elif abs(point.x() - r.right()) <= grip:
            edges += "r"
        if abs(point.y() - r.top()) <= grip:
            edges += "t"
        elif abs(point.y() - r.bottom()) <= grip:
            edges += "b"
        if not edges and not r.contains(point):
            return None, ""
        return found, edges

    @staticmethod
    def _cursor(edges: str) -> Qt.CursorShape:
        if edges in ("lt", "rb"):
            return Qt.CursorShape.SizeFDiagCursor
        if edges in ("rt", "lb"):
            return Qt.CursorShape.SizeBDiagCursor
        if edges in ("l", "r"):
            return Qt.CursorShape.SizeHorCursor
        if edges in ("t", "b"):
            return Qt.CursorShape.SizeVerCursor
        return Qt.CursorShape.SizeAllCursor

    def _clamp(self, point: QPointF) -> QPointF:
        r = self.page_size
        return QPointF(min(max(point.x(), r.left()), r.right()), min(max(point.y(), r.top()), r.bottom()))

    def contextMenuEvent(self, event):
        if not self.editable or self.page is None:
            return
        item, _ = self._hit(event.pos())
        if item is not None and not item.chosen:
            self.picked.emit([item.index], False)
        self.menu_asked.emit(item.index if item else -1, event.globalPos(), self.mapToScene(event.pos()))
        event.accept()

    def page_words(self) -> list:
        if self._words is None:
            self._words = words(self.page) if self.page is not None else []
        return self._words

    def _text_selection(self, start: QPointF, end: QPointF) -> list[Rect]:
        found = self.page_words()
        a = nearest_word(found, start.x(), start.y())
        b = nearest_word(found, end.x(), end.y())
        return [] if a is None else text_rects(found, a, b)

    def _show_text(self, rects: list[Rect]):
        for item in self._drag["marks"]:
            self.scene().removeItem(item)
        color = QColor(SELECTED)
        color.setAlpha(90)
        self._drag["marks"] = [self.scene().addRect(QRectF(QPointF(r[0], r[1]), QPointF(r[2], r[3])),
                                                    QPen(Qt.PenStyle.NoPen), QBrush(color)) for r in rects]
        for item in self._drag["marks"]:
            item.setZValue(3)
        self._drag["rects"] = rects

    def near_text(self, point: QPointF) -> bool:
        """Whether POINT (on the page) is on a word, or very close to one."""
        for (x0, y0, x1, y1), _, _ in self.page_words():
            if x0 - NEAR_TEXT <= point.x() <= x1 + NEAR_TEXT and y0 - NEAR_TEXT <= point.y() <= y1 + NEAR_TEXT:
                return True
        return False

    def set_mode(self, mode: str):
        self.mode = mode
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag if mode == "hand"
                         else QGraphicsView.DragMode.NoDrag)
        self.viewport().unsetCursor()

    def mouseDoubleClickEvent(self, event):
        if not self.editable or self.page is None or self.mode == "hand" \
                or event.button() != Qt.MouseButton.LeftButton:
            super().mouseDoubleClickEvent(event)
            return
        point = self.mapToScene(event.position().toPoint())
        item, _ = self._hit(event.position().toPoint())
        self._drag = None
        self.double_clicked.emit(item.index if item else -1, (point.x(), point.y()))
        event.accept()

    def mousePressEvent(self, event):
        if self.mode == "hand":
            super().mousePressEvent(event)
            return
        ctrl = bool(event.modifiers() & Qt.KeyboardModifier.ControlModifier)
        point = self.mapToScene(event.position().toPoint()) if self.page is not None else QPointF()
        if (self.editable and self.page is not None and self.mode == "text"
                and event.button() == Qt.MouseButton.LeftButton
                and (event.modifiers() & Qt.KeyboardModifier.ShiftModifier
                     or (self._hit(event.position().toPoint())[0] is None and not ctrl
                         and self.near_text(point)))):
            start = self.mapToScene(event.position().toPoint())
            self.picked.emit([], False)
            self._drag = {"kind": "text", "start": start, "marks": [], "rects": []}
            if not self.page_words():
                self._drag = None
            event.accept()
            return
        if not self.editable or self.page is None or event.button() != Qt.MouseButton.LeftButton:
            super().mousePressEvent(event)
            return
        add = bool(event.modifiers() & Qt.KeyboardModifier.ControlModifier)
        item, edges = (None, "") if event.modifiers() & Qt.KeyboardModifier.ShiftModifier \
            else self._hit(event.position().toPoint())
        start = self.mapToScene(event.position().toPoint())
        if item is None:
            if not add or self.mode == "text":
                self.picked.emit([], False)
            start = self._clamp(start)
            rect = QGraphicsRectItem(QRectF(start, start))
            pen = QPen(SELECTED, 1, Qt.PenStyle.DashLine)
            pen.setCosmetic(True)
            rect.setPen(pen)
            rect.setZValue(3)
            self.scene().addItem(rect)
            self._drag = {"kind": "draw", "start": start, "item": rect}
        else:
            if not item.chosen or add:
                self.picked.emit([item.index], add)
                item = next((i for i in self.items_ if i.index == item.index), None)
                if item is None or add:
                    self._drag = None
                    return
            if item.box.locked:  # (selected, but it stays where it is)
                self._drag = None
                event.accept()
                return
            self._drag = {"kind": "edit", "start": start, "item": item, "edges": edges,
                          "rect": QRectF(item.rect()), "moved": False}
        event.accept()

    def mouseMoveEvent(self, event):
        drag = self._drag
        if drag is None:
            if self.editable and self.page is not None and self.mode != "hand":
                item, edges = self._hit(event.position().toPoint())
                point = self.mapToScene(event.position().toPoint())
                text_here = self.mode == "text" and not event.modifiers() & Qt.KeyboardModifier.ControlModifier \
                    and self.near_text(point)
                empty = Qt.CursorShape.IBeamCursor if text_here else Qt.CursorShape.CrossCursor
                if item is not None and item.box.locked:
                    shape = Qt.CursorShape.ArrowCursor
                else:
                    shape = self._cursor(edges) if item else empty
                self.viewport().setCursor(QCursor(shape))
            super().mouseMoveEvent(event)
            return
        point = self.mapToScene(event.position().toPoint())
        if drag["kind"] == "text":
            self._show_text(self._text_selection(drag["start"], point))
        elif drag["kind"] == "draw":
            drag["item"].setRect(QRectF(drag["start"], self._clamp(point)).normalized())
        else:
            r = QRectF(drag["rect"])
            delta = point - drag["start"]
            if not drag["edges"]:
                r.translate(delta)
                # (kept on the page)
                dx = max(self.page_size.left() - r.left(), 0) + min(self.page_size.right() - r.right(), 0)
                dy = max(self.page_size.top() - r.top(), 0) + min(self.page_size.bottom() - r.bottom(), 0)
                r.translate(dx, dy)
            else:
                p = self._clamp(point)
                if "l" in drag["edges"]:
                    r.setLeft(p.x())
                if "r" in drag["edges"]:
                    r.setRight(p.x())
                if "t" in drag["edges"]:
                    r.setTop(p.y())
                if "b" in drag["edges"]:
                    r.setBottom(p.y())
                r = r.normalized()
            drag["item"].setRect(r)
            drag["moved"] = True
        event.accept()

    def mouseReleaseEvent(self, event):
        drag, self._drag = self._drag, None
        if drag is None or event.button() != Qt.MouseButton.LeftButton:
            super().mouseReleaseEvent(event)
            return
        if drag["kind"] == "text":
            point = self.mapToScene(event.position().toPoint())
            moved = (point - drag["start"]).manhattanLength() * self.zoom() > 3
            rects = self._text_selection(drag["start"], point) if moved else []
            for item in drag["marks"]:
                self.scene().removeItem(item)
            if rects:
                self.text_chosen.emit(rects)
            event.accept()
            return
        r = drag["item"].rect().normalized()
        if drag["kind"] == "draw":
            self.scene().removeItem(drag["item"])
            if r.width() >= MIN_SIZE and r.height() >= MIN_SIZE:
                self.drawn.emit(self._rect(r))
        elif drag["moved"] and r.width() >= MIN_SIZE and r.height() >= MIN_SIZE:
            self.edited.emit(drag["item"].index, self._rect(r))
        elif drag["moved"]:
            drag["item"].setRect(drag["rect"])
        event.accept()

    @staticmethod
    def _rect(r: QRectF) -> Rect:
        return normalized((round(r.left(), 2), round(r.top(), 2), round(r.right(), 2), round(r.bottom(), 2)))

    def word_at(self, point: QPointF) -> str:
        """The word under POINT (on the page), or ''."""
        if self.page is None:
            return ""
        for w in self.page.get_text("words", sort=False):
            r = pymupdf.Rect(w[:4]) * self.page.rotation_matrix
            if r.normalize().contains(pymupdf.Point(point.x(), point.y())):
                return w[4]
        return ""

    def flash(self, rects: list[Rect]):
        """Show RECTS for a moment (a place found), and bring them into view."""
        if not rects:
            return
        color = QColor(255, 200, 0, 150)
        pen = QPen(QColor(230, 120, 0), 2)
        pen.setCosmetic(True)
        items = []
        for r in rects:
            item = self.scene().addRect(QRectF(QPointF(r[0], r[1]), QPointF(r[2], r[3])), pen, QBrush(color))
            item.setZValue(4)
            items.append(item)
        self.ensureVisible(items[0], 60, 60)

        def remove():
            for item in items:
                try:
                    if item.scene() is not None:
                        item.scene().removeItem(item)
                except RuntimeError:  # (the page was shown again meanwhile: the item is gone)
                    pass

        QTimer.singleShot(1500, remove)

    def image_rect(self, point: tuple[float, float]) -> Rect | None:
        return image_at(self.page, *point) if self.page is not None else None
