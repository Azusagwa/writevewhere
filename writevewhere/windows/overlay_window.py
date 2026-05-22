from __future__ import annotations

from math import atan2, cos, sin
from typing import Protocol

from PySide6.QtCore import QEvent, QPoint, QPointF, QCoreApplication, QRect, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QGuiApplication, QKeyEvent, QMouseEvent, QPainter, QPen, QPixmap, QPolygonF
from PySide6.QtWidgets import QWidget

from writevewhere.core import DrawMode, Point, Stroke, StrokeShape, StrokeStore
from writevewhere.system.screenshot import save_screenshot
from writevewhere.system import set_click_through
from writevewhere.windows.screenshot_window import PinnedScreenshotWindow, ScreenshotToolbar


MIN_SCREENSHOT_SELECTION_SIZE = 8
SCREENSHOT_SELECTION_HANDLE_MARGIN = 8
SCREENSHOT_REPAINT_MARGIN = 12


class _ControlWindowLike(Protocol):
    def ensure_on_top(self) -> None:
        ...

    def sync_overlay_mode(self, mode: DrawMode) -> None:
        ...


class OverlayWindow(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.store = StrokeStore()
        self.mode = DrawMode.PASSTHROUGH
        self.pen_color = "#ff3333"
        self.pen_width = 5
        self.eraser_width = 22
        self.current_stroke: Stroke | None = None
        self.control_window: _ControlWindowLike | None = None
        self._forwarding_control_events = False
        self._forwarding_screenshot_toolbar_events = False
        self._forwarding_pinned_screenshot: PinnedScreenshotWindow | None = None
        self.mouse_event_count = 0
        self.last_mouse_event: str | None = None
        self.screenshot_selection_rect: QRect | None = None
        self._screenshot_start: QPoint | None = None
        self._screenshot_edit_mode: str | None = None
        self._screenshot_edit_start: QPoint | None = None
        self._screenshot_edit_rect: QRect | None = None
        self._screenshot_pixmap: QPixmap | None = None
        self._screenshot_toolbar: ScreenshotToolbar | None = None
        self._pinned_screenshots: list[PinnedScreenshotWindow] = []

        self.setWindowTitle("Writevewhere Overlay")
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setMouseTracking(True)
        self._fit_virtual_desktop()
        self.set_mode(DrawMode.PASSTHROUGH)

    def set_control_window(self, control_window: _ControlWindowLike) -> None:
        self.control_window = control_window

    def _fit_virtual_desktop(self) -> None:
        geometry = QRect()
        for screen in QGuiApplication.screens():
            geometry = geometry.united(screen.geometry())
        self.setGeometry(geometry)

    def set_mode(self, mode: DrawMode | str) -> None:
        self.mode = DrawMode(mode)
        set_click_through(self, self.mode == DrawMode.PASSTHROUGH)
        if self.mode == DrawMode.PASSTHROUGH:
            self.current_stroke = None
            self._cancel_screenshot()
        self.show()
        self.raise_()
        if self.mode in (DrawMode.DRAW, DrawMode.ERASE, DrawMode.SCREENSHOT, DrawMode.BOX, DrawMode.ELLIPSE, DrawMode.ARROW):
            self.setFocus(Qt.FocusReason.ActiveWindowFocusReason)
        else:
            self.releaseMouse()
        if self.control_window is not None:
            self.control_window.ensure_on_top()
            sync_mode = getattr(self.control_window, "sync_overlay_mode", None)
            if callable(sync_mode):
                sync_mode(self.mode)

    def set_pen_color(self, color: str) -> None:
        self.pen_color = color
        self.update()

    def set_pen_width(self, width: int) -> None:
        self.pen_width = max(1, int(width))

    def set_eraser_width(self, width: int) -> None:
        self.eraser_width = max(4, int(width))

    def clear(self) -> None:
        self.store.clear()
        self.current_stroke = None
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        if self.mode in (DrawMode.DRAW, DrawMode.ERASE, DrawMode.SCREENSHOT, DrawMode.BOX, DrawMode.ELLIPSE, DrawMode.ARROW):
            painter.fillRect(self.rect(), QColor(0, 0, 0, 1))
        for stroke in self.store.strokes:
            self._paint_stroke(painter, stroke)
        if self.current_stroke is not None:
            self._paint_stroke(painter, self.current_stroke)
        if self.screenshot_selection_rect is not None:
            self._paint_screenshot_selection(painter, self.screenshot_selection_rect)
        painter.end()

    def _paint_stroke(self, painter: QPainter, stroke: Stroke) -> None:
        if not stroke.points:
            return
        pen = QPen(QColor(stroke.color), stroke.width)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        if stroke.shape == StrokeShape.BOX:
            self._paint_box(painter, stroke)
            return
        if stroke.shape == StrokeShape.ELLIPSE:
            self._paint_ellipse(painter, stroke)
            return
        if stroke.shape == StrokeShape.ARROW:
            self._paint_arrow(painter, stroke)
            return
        if len(stroke.points) == 1:
            point = stroke.points[0]
            painter.drawPoint(QPointF(point.x, point.y))
            return
        for start, end in zip(stroke.points, stroke.points[1:]):
            painter.drawLine(QPointF(start.x, start.y), QPointF(end.x, end.y))

    def _paint_box(self, painter: QPainter, stroke: Stroke) -> None:
        if len(stroke.points) < 2:
            return
        painter.drawRect(_rect_from_points(stroke.points[0], stroke.points[1]))

    def _paint_ellipse(self, painter: QPainter, stroke: Stroke) -> None:
        if len(stroke.points) < 2:
            return
        painter.drawEllipse(_rect_from_points(stroke.points[0], stroke.points[1]))

    def _paint_arrow(self, painter: QPainter, stroke: Stroke) -> None:
        if len(stroke.points) < 2:
            return
        start, end = stroke.points[0], stroke.points[1]
        angle = atan2(end.y - start.y, end.x - start.x)
        distance = start.distance_to(end)
        if distance == 0:
            return

        unit_x = cos(angle)
        unit_y = sin(angle)
        normal_x = -unit_y
        normal_y = unit_x
        head_length = min(max(stroke.width * 5, 18), distance)
        head_width = max(stroke.width * 3, 12)
        base_x = end.x - head_length * unit_x
        base_y = end.y - head_length * unit_y

        painter.drawLine(QPointF(start.x, start.y), QPointF(end.x, end.y))

        head = QPolygonF(
            [
                QPointF(end.x, end.y),
                QPointF(base_x + normal_x * head_width / 2, base_y + normal_y * head_width / 2),
                QPointF(base_x - normal_x * head_width / 2, base_y - normal_y * head_width / 2),
            ]
        )
        painter.setBrush(QBrush(QColor(stroke.color)))
        painter.drawPolygon(head)
        painter.setBrush(Qt.BrushStyle.NoBrush)

    def _paint_screenshot_selection(self, painter: QPainter, rect: QRect) -> None:
        painter.setPen(QPen(QColor(255, 79, 79, 230), 2, Qt.PenStyle.DashLine))
        painter.setBrush(QColor(255, 79, 79, 38))
        painter.drawRect(rect)

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if self._forward_mouse_event_to_pinned_screenshot(event):
            return
        if self._forward_mouse_event_to_screenshot_toolbar(event):
            return
        if self._handle_screenshot_editor_event(event):
            return
        if self._forward_mouse_event_to_control(event):
            return
        self._handle_mouse_press(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if self._forward_mouse_event_to_pinned_screenshot(event):
            return
        if self._forward_mouse_event_to_screenshot_toolbar(event):
            return
        if self._handle_screenshot_editor_event(event):
            return
        if self._forward_mouse_event_to_control(event):
            return
        self._handle_mouse_move(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if self._forward_mouse_event_to_pinned_screenshot(event):
            return
        if self._forward_mouse_event_to_screenshot_toolbar(event):
            return
        if self._handle_screenshot_editor_event(event):
            return
        if self._forward_mouse_event_to_control(event):
            return
        self._handle_mouse_release(event)

    def handle_control_passthrough_mouse_event(self, event: QMouseEvent) -> None:
        global_pos = event.globalPosition().toPoint()
        local_pos = QPointF(self.mapFromGlobal(global_pos))
        forwarded = QMouseEvent(
            event.type(),
            local_pos,
            local_pos,
            QPointF(global_pos),
            event.button(),
            event.buttons(),
            event.modifiers(),
        )
        if event.type() == QEvent.Type.MouseButtonPress:
            self._handle_mouse_press(forwarded)
        elif event.type() == QEvent.Type.MouseMove:
            self._handle_mouse_move(forwarded)
        elif event.type() == QEvent.Type.MouseButtonRelease:
            self._handle_mouse_release(forwarded)

    def _handle_mouse_press(self, event: QMouseEvent) -> None:
        self._mark_mouse_event("press")
        if event.button() == Qt.MouseButton.RightButton and self.current_stroke is not None:
            self.current_stroke = None
            self.update()
            return
        if event.button() == Qt.MouseButton.RightButton and self._can_right_erase():
            self.store.erase_at(self._event_point(event), self._right_eraser_radius())
            self.update()
            return
        if event.button() == Qt.MouseButton.LeftButton and self._can_start_screenshot_selection():
            self._start_screenshot_selection(event)
            return
        if event.button() != Qt.MouseButton.LeftButton:
            return
        point = self._event_point(event)
        if self.mode == DrawMode.DRAW:
            self.current_stroke = Stroke(color=self.pen_color, width=self.pen_width)
            self.current_stroke.add_point(point)
        elif self.mode in (DrawMode.BOX, DrawMode.ELLIPSE, DrawMode.ARROW):
            self.current_stroke = Stroke(
                color=self.pen_color,
                width=self.pen_width,
                shape=_shape_for_mode(self.mode),
            )
            self.current_stroke.add_point(point)
            self.current_stroke.add_point(point)
        elif self.mode == DrawMode.ERASE:
            self.store.erase_at(point, self.eraser_width)
        self.update()

    def _handle_mouse_move(self, event: QMouseEvent) -> None:
        self._mark_mouse_event("move")
        if self._screenshot_start is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self._update_screenshot_selection(event)
            return
        if self._can_right_erase() and event.buttons() & Qt.MouseButton.RightButton:
            self.store.erase_at(self._event_point(event), self._right_eraser_radius())
            self.update()
            return
        point = self._event_point(event)
        if self.mode == DrawMode.DRAW and self.current_stroke is not None:
            self.current_stroke.add_point(point)
        elif self.mode in (DrawMode.BOX, DrawMode.ELLIPSE, DrawMode.ARROW) and self.current_stroke is not None:
            self.current_stroke.add_point(point)
        elif self.mode == DrawMode.ERASE and event.buttons() & Qt.MouseButton.LeftButton:
            self.store.erase_at(point, self.eraser_width)
        self.update()

    def _handle_mouse_release(self, event: QMouseEvent) -> None:
        self._mark_mouse_event("release")
        if event.button() == Qt.MouseButton.LeftButton and self._screenshot_start is not None:
            self._finish_screenshot_selection(event)
            return
        if event.button() == Qt.MouseButton.LeftButton and self.current_stroke is not None:
            self.store.add(self.current_stroke)
            self.current_stroke = None
            self.update()

    def _can_start_screenshot_selection(self) -> bool:
        return self.mode == DrawMode.SCREENSHOT and self.current_stroke is None

    def _can_right_erase(self) -> bool:
        return self.mode in (DrawMode.DRAW, DrawMode.BOX, DrawMode.ELLIPSE, DrawMode.ARROW, DrawMode.ERASE)

    def _right_eraser_radius(self) -> int:
        return max(12, self.pen_width * 4)

    def _start_screenshot_selection(self, event: QMouseEvent) -> None:
        self._hide_screenshot_toolbar()
        self._screenshot_pixmap = None
        self._screenshot_start = event.position().toPoint()
        self.screenshot_selection_rect = QRect(self._screenshot_start, self._screenshot_start)
        self.update()

    def _update_screenshot_selection(self, event: QMouseEvent) -> None:
        if self._screenshot_start is None:
            return
        previous_rect = self.screenshot_selection_rect
        self.screenshot_selection_rect = QRect(self._screenshot_start, event.position().toPoint()).normalized()
        self._update_screenshot_rects(previous_rect, self.screenshot_selection_rect)

    def _finish_screenshot_selection(self, event: QMouseEvent) -> None:
        self._update_screenshot_selection(event)
        rect = self.screenshot_selection_rect
        self._screenshot_start = None
        if rect is None or rect.width() < MIN_SCREENSHOT_SELECTION_SIZE or rect.height() < MIN_SCREENSHOT_SELECTION_SIZE:
            self.screenshot_selection_rect = None
            self.update()
            return

        self._screenshot_pixmap = None
        self.update()
        self._show_screenshot_toolbar(rect)

    def _capture_screenshot_selection(self, rect: QRect) -> QPixmap:
        global_rect = QRect(self.mapToGlobal(rect.topLeft()), rect.size())
        control = self.control_window
        control_visible = bool(control is not None and getattr(control, "isVisible", lambda: False)())
        toolbar = self._screenshot_toolbar
        toolbar_visible = bool(toolbar is not None and toolbar.isVisible())
        selection_rect = self.screenshot_selection_rect

        self.screenshot_selection_rect = None
        self.update()
        if control is not None and control_visible:
            control.hide()
        if toolbar is not None and toolbar_visible:
            toolbar.hide()
        QCoreApplication.processEvents()
        try:
            return _grab_virtual_desktop(global_rect)
        finally:
            self.screenshot_selection_rect = selection_rect
            self.update()
            self.raise_()
            if control is not None and control_visible:
                control.show()
                control.ensure_on_top()
            if toolbar is not None and toolbar_visible:
                toolbar.show()
                toolbar.raise_()

    def _show_screenshot_toolbar(self, rect: QRect) -> None:
        self._hide_screenshot_toolbar()
        toolbar = ScreenshotToolbar(
            on_save=self._save_screenshot,
            on_copy=self._copy_screenshot,
            on_pin=self._pin_screenshot,
            on_cancel=self._exit_screenshot_mode,
        )
        toolbar.adjustSize()
        toolbar.move(self._toolbar_position(rect, toolbar.size()))
        toolbar.show()
        toolbar.raise_()
        self._screenshot_toolbar = toolbar

    def _toolbar_position(self, selection_rect: QRect, toolbar_size) -> QPoint:
        global_rect = QRect(self.mapToGlobal(selection_rect.topLeft()), selection_rect.size())
        screen = QGuiApplication.screenAt(global_rect.center()) or QGuiApplication.primaryScreen()
        if screen is None:
            return global_rect.bottomLeft() + QPoint(0, 8)

        available = screen.availableGeometry()
        x = global_rect.center().x() - toolbar_size.width() // 2
        y = global_rect.bottom() + 8
        if y + toolbar_size.height() > available.bottom():
            y = global_rect.top() - toolbar_size.height() - 8
        x = min(max(x, available.left()), available.right() - toolbar_size.width() + 1)
        y = min(max(y, available.top()), available.bottom() - toolbar_size.height() + 1)
        return QPoint(x, y)

    def _save_screenshot(self) -> None:
        pixmap = self._current_screenshot_pixmap()
        if pixmap is not None and not pixmap.isNull():
            save_screenshot(pixmap)
        self._exit_screenshot_mode()

    def _copy_screenshot(self) -> None:
        pixmap = self._current_screenshot_pixmap()
        if pixmap is not None and not pixmap.isNull():
            QGuiApplication.clipboard().setPixmap(pixmap)
        self._exit_screenshot_mode()

    def _pin_screenshot(self) -> None:
        pixmap = self._current_screenshot_pixmap()
        if pixmap is None or pixmap.isNull():
            self._exit_screenshot_mode()
            return
        pinned = PinnedScreenshotWindow(pixmap)
        cursor_pos = QGuiApplication.primaryScreen().availableGeometry().center() if QGuiApplication.primaryScreen() else QPoint(80, 80)
        if self._screenshot_toolbar is not None:
            cursor_pos = self._screenshot_toolbar.pos()
        pinned.move(cursor_pos)
        pinned.show()
        pinned.raise_()
        pinned.destroyed.connect(lambda _obj=None, window=pinned: self._forget_pinned_screenshot(window))
        self._pinned_screenshots.append(pinned)
        self._exit_screenshot_mode()

    def _current_screenshot_pixmap(self) -> QPixmap | None:
        if self.screenshot_selection_rect is not None:
            self._screenshot_pixmap = self._capture_screenshot_selection(self.screenshot_selection_rect)
        return self._screenshot_pixmap

    def _cancel_screenshot(self) -> None:
        self._screenshot_start = None
        self._screenshot_edit_mode = None
        self._screenshot_edit_start = None
        self._screenshot_edit_rect = None
        self.screenshot_selection_rect = None
        self._screenshot_pixmap = None
        self._hide_screenshot_toolbar()
        self.update()

    def _exit_screenshot_mode(self) -> None:
        self._cancel_screenshot()
        self.set_mode(DrawMode.PASSTHROUGH)

    def _hide_screenshot_toolbar(self) -> None:
        if self._screenshot_toolbar is None:
            return
        self._screenshot_toolbar.close()
        self._screenshot_toolbar.deleteLater()
        self._screenshot_toolbar = None

    def _forget_pinned_screenshot(self, window: PinnedScreenshotWindow) -> None:
        if window in self._pinned_screenshots:
            self._pinned_screenshots.remove(window)

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        if event.key() == Qt.Key.Key_Escape:
            self.set_mode(DrawMode.PASSTHROUGH)
        else:
            super().keyPressEvent(event)

    def _event_point(self, event: QMouseEvent) -> Point:
        pos = event.position()
        return Point(pos.x(), pos.y())

    def _mark_mouse_event(self, event_name: str) -> None:
        self.mouse_event_count += 1
        self.last_mouse_event = event_name

    def _handle_screenshot_editor_event(self, event: QMouseEvent) -> bool:
        if self._screenshot_toolbar is None:
            return False
        if self.screenshot_selection_rect is None:
            return True
        if event.type() == QEvent.Type.MouseButtonPress:
            if event.button() != Qt.MouseButton.LeftButton:
                return True
            mode = self._screenshot_hit_test(event.position().toPoint())
            if mode is None:
                return True
            self._screenshot_edit_mode = mode
            self._screenshot_edit_start = event.position().toPoint()
            self._screenshot_edit_rect = QRect(self.screenshot_selection_rect)
            event.accept()
            return True
        if event.type() == QEvent.Type.MouseMove:
            if self._screenshot_edit_mode is not None and self._screenshot_edit_start is not None and self._screenshot_edit_rect is not None:
                self._update_screenshot_edit(event.position().toPoint())
            return True
        if event.type() == QEvent.Type.MouseButtonRelease:
            self._screenshot_edit_mode = None
            self._screenshot_edit_start = None
            self._screenshot_edit_rect = None
            return True
        return True

    def _screenshot_hit_test(self, point: QPoint) -> str | None:
        rect = self.screenshot_selection_rect
        if rect is None:
            return None
        outer = rect.adjusted(
            -SCREENSHOT_SELECTION_HANDLE_MARGIN,
            -SCREENSHOT_SELECTION_HANDLE_MARGIN,
            SCREENSHOT_SELECTION_HANDLE_MARGIN,
            SCREENSHOT_SELECTION_HANDLE_MARGIN,
        )
        if not outer.contains(point):
            return None

        left = abs(point.x() - rect.left()) <= SCREENSHOT_SELECTION_HANDLE_MARGIN
        right = abs(point.x() - rect.right()) <= SCREENSHOT_SELECTION_HANDLE_MARGIN
        top = abs(point.y() - rect.top()) <= SCREENSHOT_SELECTION_HANDLE_MARGIN
        bottom = abs(point.y() - rect.bottom()) <= SCREENSHOT_SELECTION_HANDLE_MARGIN

        if top and left:
            return "top-left"
        if top and right:
            return "top-right"
        if bottom and left:
            return "bottom-left"
        if bottom and right:
            return "bottom-right"
        if left:
            return "left"
        if right:
            return "right"
        if top:
            return "top"
        if bottom:
            return "bottom"
        return "move" if rect.contains(point) else None

    def _update_screenshot_edit(self, point: QPoint) -> None:
        if self._screenshot_edit_mode is None or self._screenshot_edit_start is None or self._screenshot_edit_rect is None:
            return
        delta = point - self._screenshot_edit_start
        rect = QRect(self._screenshot_edit_rect)
        mode = self._screenshot_edit_mode
        if mode == "move":
            rect.translate(delta)
            rect = self._clamp_rect_to_overlay(rect)
        else:
            if "left" in mode:
                rect.setLeft(rect.left() + delta.x())
            if "right" in mode:
                rect.setRight(rect.right() + delta.x())
            if "top" in mode:
                rect.setTop(rect.top() + delta.y())
            if "bottom" in mode:
                rect.setBottom(rect.bottom() + delta.y())
            rect = self._normalized_minimum_screenshot_rect(rect)
        previous_rect = self.screenshot_selection_rect
        self.screenshot_selection_rect = rect
        self._move_screenshot_toolbar(raise_toolbar=False)
        self._update_screenshot_rects(previous_rect, rect)

    def _normalized_minimum_screenshot_rect(self, rect: QRect) -> QRect:
        rect = rect.normalized()
        if rect.width() < MIN_SCREENSHOT_SELECTION_SIZE:
            rect.setWidth(MIN_SCREENSHOT_SELECTION_SIZE)
        if rect.height() < MIN_SCREENSHOT_SELECTION_SIZE:
            rect.setHeight(MIN_SCREENSHOT_SELECTION_SIZE)
        return rect.intersected(self.rect())

    def _clamp_rect_to_overlay(self, rect: QRect) -> QRect:
        bounds = self.rect()
        if rect.left() < bounds.left():
            rect.moveLeft(bounds.left())
        if rect.top() < bounds.top():
            rect.moveTop(bounds.top())
        if rect.right() > bounds.right():
            rect.moveRight(bounds.right())
        if rect.bottom() > bounds.bottom():
            rect.moveBottom(bounds.bottom())
        return rect

    def _move_screenshot_toolbar(self, raise_toolbar: bool = True) -> None:
        if self._screenshot_toolbar is None or self.screenshot_selection_rect is None:
            return
        position = self._toolbar_position(self.screenshot_selection_rect, self._screenshot_toolbar.size())
        if self._screenshot_toolbar.pos() != position:
            self._screenshot_toolbar.move(position)
        if raise_toolbar:
            self._screenshot_toolbar.raise_()

    def _update_screenshot_rects(self, previous_rect: QRect | None, current_rect: QRect | None) -> None:
        dirty_rect = QRect()
        for rect in (previous_rect, current_rect):
            if rect is not None:
                dirty_rect = dirty_rect.united(
                    rect.adjusted(
                        -SCREENSHOT_REPAINT_MARGIN,
                        -SCREENSHOT_REPAINT_MARGIN,
                        SCREENSHOT_REPAINT_MARGIN,
                        SCREENSHOT_REPAINT_MARGIN,
                    )
                )
        self.update(dirty_rect if not dirty_rect.isNull() else self.rect())

    def _forward_mouse_event_to_pinned_screenshot(self, event: QMouseEvent) -> bool:
        global_pos = event.globalPosition().toPoint()
        if event.type() == QEvent.Type.MouseButtonPress:
            self._forwarding_pinned_screenshot = self._pinned_screenshot_at(global_pos)
        pinned = self._forwarding_pinned_screenshot
        if pinned is None or not pinned.isVisible():
            self._forwarding_pinned_screenshot = None
            return False

        pinned.raise_()
        target = self._widget_event_target(pinned, global_pos)
        local_pos = QPointF(target.mapFromGlobal(global_pos))
        forwarded = QMouseEvent(
            event.type(),
            local_pos,
            local_pos,
            QPointF(global_pos),
            event.button(),
            event.buttons(),
            event.modifiers(),
        )
        QCoreApplication.sendEvent(target, forwarded)
        if event.type() == QEvent.Type.MouseButtonRelease:
            self._forwarding_pinned_screenshot = None
        return True

    def _pinned_screenshot_at(self, global_pos: QPoint) -> PinnedScreenshotWindow | None:
        for pinned in reversed(self._pinned_screenshots):
            if pinned.isVisible() and pinned.frameGeometry().contains(global_pos):
                return pinned
        return None

    def _forward_mouse_event_to_screenshot_toolbar(self, event: QMouseEvent) -> bool:
        toolbar = self._screenshot_toolbar
        if toolbar is None or not toolbar.isVisible():
            self._forwarding_screenshot_toolbar_events = False
            return False

        global_pos = event.globalPosition().toPoint()
        inside_toolbar = toolbar.frameGeometry().contains(global_pos)
        if event.type() == QEvent.Type.MouseButtonPress:
            self._forwarding_screenshot_toolbar_events = inside_toolbar
            if not inside_toolbar:
                return False
        elif not self._forwarding_screenshot_toolbar_events:
            return False

        if inside_toolbar or self._forwarding_screenshot_toolbar_events:
            toolbar.raise_()
            target = self._widget_event_target(toolbar, global_pos)
            local_pos = QPointF(target.mapFromGlobal(global_pos))
            forwarded = QMouseEvent(
                event.type(),
                local_pos,
                local_pos,
                QPointF(global_pos),
                event.button(),
                event.buttons(),
                event.modifiers(),
            )
            QCoreApplication.sendEvent(target, forwarded)

        if event.type() == QEvent.Type.MouseButtonRelease:
            self._forwarding_screenshot_toolbar_events = False
        return True

    def _forward_mouse_event_to_control(self, event: QMouseEvent) -> bool:
        control = self.control_window
        if control is None:
            return False

        global_pos = event.globalPosition().toPoint()
        inside_control = control.frameGeometry().contains(global_pos)
        if event.type() == QEvent.Type.MouseButtonPress:
            self._forwarding_control_events = inside_control
        elif not self._forwarding_control_events:
            return False

        if not inside_control and event.type() == QEvent.Type.MouseButtonPress:
            return False

        control.ensure_on_top()
        target = self._widget_event_target(control, global_pos)
        local_pos = QPointF(target.mapFromGlobal(global_pos))
        forwarded = QMouseEvent(
            event.type(),
            local_pos,
            local_pos,
            QPointF(global_pos),
            event.button(),
            event.buttons(),
            event.modifiers(),
        )
        QCoreApplication.sendEvent(target, forwarded)

        if event.type() == QEvent.Type.MouseButtonRelease:
            self._forwarding_control_events = False
        return True

    def _widget_event_target(self, widget, global_pos: QPoint):
        widget_pos = widget.mapFromGlobal(global_pos)
        target = widget.childAt(widget_pos)
        return target if target is not None else widget


def _rect_from_points(start: Point, end: Point) -> QRectF:
    return QRectF(QPointF(start.x, start.y), QPointF(end.x, end.y)).normalized()


def _shape_for_mode(mode: DrawMode) -> StrokeShape:
    return {
        DrawMode.BOX: StrokeShape.BOX,
        DrawMode.ELLIPSE: StrokeShape.ELLIPSE,
        DrawMode.ARROW: StrokeShape.ARROW,
    }[mode]


def _grab_virtual_desktop(global_rect: QRect) -> QPixmap:
    captures: list[tuple[QRect, QPixmap]] = []
    for screen in QGuiApplication.screens():
        screen_geometry = screen.geometry()
        capture_rect = global_rect.intersected(screen_geometry)
        if capture_rect.isEmpty():
            continue
        screen_pixmap = screen.grabWindow(
            0,
            capture_rect.x() - screen_geometry.x(),
            capture_rect.y() - screen_geometry.y(),
            capture_rect.width(),
            capture_rect.height(),
        )
        captures.append((capture_rect, screen_pixmap))

    if len(captures) == 1 and captures[0][0] == global_rect:
        return captures[0][1]

    dpr = max((pixmap.devicePixelRatio() for _, pixmap in captures), default=1.0)
    pixmap = QPixmap(
        max(1, round(global_rect.width() * dpr)),
        max(1, round(global_rect.height() * dpr)),
    )
    pixmap.setDevicePixelRatio(dpr)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    for capture_rect, screen_pixmap in captures:
        target = capture_rect.topLeft() - global_rect.topLeft()
        painter.drawPixmap(target, screen_pixmap)
    painter.end()
    return pixmap
