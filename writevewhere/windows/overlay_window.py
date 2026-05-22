from __future__ import annotations

from math import atan2, cos, sin
from typing import Protocol

from PySide6.QtCore import QEvent, QPoint, QPointF, QCoreApplication, QRect, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QGuiApplication, QKeyEvent, QMouseEvent, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import QWidget

from writevewhere.core import DrawMode, Point, Stroke, StrokeShape, StrokeStore
from writevewhere.system import set_click_through


class _ControlWindowLike(Protocol):
    def ensure_on_top(self) -> None:
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
        self.mouse_event_count = 0
        self.last_mouse_event: str | None = None

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
        self.show()
        self.raise_()
        if self.mode in (DrawMode.DRAW, DrawMode.ERASE, DrawMode.BOX, DrawMode.ELLIPSE, DrawMode.ARROW):
            self.setFocus(Qt.FocusReason.ActiveWindowFocusReason)
        else:
            self.releaseMouse()
        if self.control_window is not None:
            self.control_window.ensure_on_top()

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
        if self.mode in (DrawMode.DRAW, DrawMode.ERASE, DrawMode.BOX, DrawMode.ELLIPSE, DrawMode.ARROW):
            painter.fillRect(self.rect(), QColor(0, 0, 0, 1))
        for stroke in self.store.strokes:
            self._paint_stroke(painter, stroke)
        if self.current_stroke is not None:
            self._paint_stroke(painter, self.current_stroke)
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

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if self._forward_mouse_event_to_control(event):
            return
        self._handle_mouse_press(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if self._forward_mouse_event_to_control(event):
            return
        self._handle_mouse_move(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
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
        if event.button() == Qt.MouseButton.LeftButton and self.current_stroke is not None:
            self.store.add(self.current_stroke)
            self.current_stroke = None
            self.update()

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
        target = self._control_event_target(control, global_pos)
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

    def _control_event_target(self, control, global_pos: QPoint):
        control_pos = control.mapFromGlobal(global_pos)
        target = control.childAt(control_pos)
        return target if target is not None else control


def _rect_from_points(start: Point, end: Point) -> QRectF:
    return QRectF(QPointF(start.x, start.y), QPointF(end.x, end.y)).normalized()


def _shape_for_mode(mode: DrawMode) -> StrokeShape:
    return {
        DrawMode.BOX: StrokeShape.BOX,
        DrawMode.ELLIPSE: StrokeShape.ELLIPSE,
        DrawMode.ARROW: StrokeShape.ARROW,
    }[mode]
