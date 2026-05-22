from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QPoint, QSize, Qt
from PySide6.QtGui import QColor, QMouseEvent, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QWidget


class ScreenshotToolbar(QWidget):
    def __init__(
        self,
        on_save: Callable[[], None],
        on_copy: Callable[[], None],
        on_pin: Callable[[], None],
        on_cancel: Callable[[], None],
    ) -> None:
        super().__init__()
        self.setWindowTitle("\u622a\u56fe\u64cd\u4f5c")
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.save_button = self._button("\u4fdd\u5b58")
        self.copy_button = self._button("\u590d\u5236")
        self.pin_button = self._button("\u56fa\u5b9a")
        self.cancel_button = self._button("\u53d6\u6d88")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(6)
        for button in (self.save_button, self.copy_button, self.pin_button, self.cancel_button):
            layout.addWidget(button)

        self.save_button.clicked.connect(on_save)
        self.copy_button.clicked.connect(on_copy)
        self.pin_button.clicked.connect(on_pin)
        self.cancel_button.clicked.connect(on_cancel)

    def _button(self, text: str) -> QPushButton:
        button = QPushButton(text, self)
        button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        button.setFixedSize(58, 28)
        button.setStyleSheet(
            """
            QPushButton {
                background: rgba(255, 255, 255, 235);
                border: 1px solid rgba(70, 82, 93, 90);
                border-radius: 6px;
                color: #2d3742;
                font-size: 12px;
            }
            QPushButton:hover {
                background: rgba(255, 245, 245, 245);
                border-color: rgba(255, 79, 79, 170);
            }
            """
        )
        return button

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(QPen(Qt.GlobalColor.transparent))
        painter.setBrush(Qt.GlobalColor.transparent)
        painter.drawRoundedRect(self.rect(), 8, 8)
        painter.end()
        super().paintEvent(event)


class PinnedScreenshotWindow(QWidget):
    _resize_margin = 14
    _minimum_size = QSize(80, 60)
    _border_color = "#ff4f4f"
    _border_width = 2

    def __init__(self, pixmap: QPixmap) -> None:
        super().__init__()
        self._pixmap = pixmap
        self._drag_start: QPoint | None = None
        self._drag_window_start: QPoint | None = None
        self._resize_mode: str | None = None
        self._resize_start: QPoint | None = None
        self._resize_size_start: QSize | None = None
        self._resize_pos_start: QPoint | None = None
        self._last_scaled_size: QSize | None = None
        self._last_scaled_fast = False

        self.setWindowTitle("\u56fa\u5b9a\u622a\u56fe")
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setMinimumSize(self._minimum_size)
        initial_size = _device_independent_pixmap_size(pixmap) + QSize(self._border_width * 2, self._border_width * 2)
        if initial_size.width() < self._minimum_size.width() or initial_size.height() < self._minimum_size.height():
            initial_size = initial_size.expandedTo(self._minimum_size)
        self.resize(initial_size)

        self.image_label = QLabel(self)
        self.image_label.setScaledContents(False)
        self.image_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.close_button = QPushButton("x", self)
        self.close_button.setFixedSize(24, 24)
        self.close_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.close_button.clicked.connect(self.close)
        self.close_button.setStyleSheet(
            """
            QPushButton {
                background: rgba(25, 30, 36, 170);
                border: 1px solid rgba(255, 255, 255, 120);
                border-radius: 12px;
                color: white;
                font-size: 16px;
            }
            QPushButton:hover { background: rgba(255, 79, 79, 220); }
            """
        )
        self._layout_children()
        self._sync_pixmap()

    def resizeEvent(self, event) -> None:  # noqa: N802
        self._layout_children()
        self._sync_pixmap(fast=self._resize_mode is not None)
        super().resizeEvent(event)

    def _layout_children(self) -> None:
        inset = self._border_width
        self.image_label.setGeometry(self.rect().adjusted(inset, inset, -inset, -inset))
        self.close_button.move(self.width() - self.close_button.width() - 6, 6)

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.RightButton:
            self.close()
            return
        if event.button() != Qt.MouseButton.LeftButton:
            super().mousePressEvent(event)
            return

        global_pos = event.globalPosition().toPoint()
        resize_mode = self._resize_hit_test(event.position().toPoint())
        if resize_mode is not None:
            self._resize_mode = resize_mode
            self._resize_start = global_pos
            self._resize_size_start = self.size()
            self._resize_pos_start = self.pos()
        else:
            self._drag_start = global_pos
            self._drag_window_start = self.pos()
        event.accept()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        global_pos = event.globalPosition().toPoint()
        if (
            self._resize_mode is not None
            and self._resize_start is not None
            and self._resize_size_start is not None
            and self._resize_pos_start is not None
        ):
            self._resize_from_global_pos(global_pos)
            event.accept()
            return
        if self._drag_start is not None and self._drag_window_start is not None:
            self.move(self._drag_window_start + global_pos - self._drag_start)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        self._drag_start = None
        self._drag_window_start = None
        self._resize_mode = None
        self._resize_start = None
        self._resize_size_start = None
        self._resize_pos_start = None
        self._sync_pixmap()
        super().mouseReleaseEvent(event)

    def paintEvent(self, event) -> None:  # noqa: N802
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        painter.setPen(QPen(QColor(self._border_color), self._border_width))
        inset = self._border_width // 2
        painter.drawRect(self.rect().adjusted(inset, inset, -inset - 1, -inset - 1))
        painter.setPen(QPen(Qt.GlobalColor.white, 2))
        base = self.rect().bottomRight()
        painter.drawLine(base - QPoint(16, 4), base - QPoint(4, 16))
        painter.drawLine(base - QPoint(10, 4), base - QPoint(4, 10))
        painter.end()

    def _resize_hit_test(self, point: QPoint) -> str | None:
        left = point.x() <= self._resize_margin
        right = point.x() >= self.width() - self._resize_margin
        top = point.y() <= self._resize_margin
        bottom = point.y() >= self.height() - self._resize_margin

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
        return None

    def _resize_from_global_pos(self, global_pos: QPoint) -> None:
        if (
            self._resize_mode is None
            or self._resize_start is None
            or self._resize_size_start is None
            or self._resize_pos_start is None
        ):
            return

        delta = global_pos - self._resize_start
        x = self._resize_pos_start.x()
        y = self._resize_pos_start.y()
        width = self._resize_size_start.width()
        height = self._resize_size_start.height()
        mode = self._resize_mode

        if "left" in mode:
            width = self._resize_size_start.width() - delta.x()
            if width >= self._minimum_size.width():
                x = self._resize_pos_start.x() + delta.x()
            else:
                width = self._minimum_size.width()
                x = self._resize_pos_start.x() + self._resize_size_start.width() - width
        if "right" in mode:
            width = max(self._minimum_size.width(), self._resize_size_start.width() + delta.x())
        if "top" in mode:
            height = self._resize_size_start.height() - delta.y()
            if height >= self._minimum_size.height():
                y = self._resize_pos_start.y() + delta.y()
            else:
                height = self._minimum_size.height()
                y = self._resize_pos_start.y() + self._resize_size_start.height() - height
        if "bottom" in mode:
            height = max(self._minimum_size.height(), self._resize_size_start.height() + delta.y())

        self.setGeometry(x, y, width, height)

    def _sync_pixmap(self, fast: bool = False) -> None:
        if self._pixmap.isNull():
            return
        target_size = self.image_label.size()
        if target_size.isEmpty():
            return
        if self._last_scaled_size == target_size and self._last_scaled_fast == fast:
            return
        dpr = max(1.0, self._pixmap.devicePixelRatio())
        source = QPixmap(self._pixmap)
        source.setDevicePixelRatio(1.0)
        target_pixels = QSize(
            max(1, round(target_size.width() * dpr)),
            max(1, round(target_size.height() * dpr)),
        )
        scaled = source.scaled(
            target_pixels,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.FastTransformation if fast else Qt.TransformationMode.SmoothTransformation,
        )
        scaled.setDevicePixelRatio(dpr)
        self.image_label.setPixmap(scaled)
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._last_scaled_size = QSize(target_size)
        self._last_scaled_fast = fast


def _device_independent_pixmap_size(pixmap: QPixmap) -> QSize:
    dpr = max(1.0, pixmap.devicePixelRatio())
    return QSize(
        max(1, round(pixmap.width() / dpr)),
        max(1, round(pixmap.height() / dpr)),
    )
