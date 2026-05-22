from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QColor, QMouseEvent, QPaintEvent, QPen, QPixmap
from PySide6.QtWidgets import QApplication

from writevewhere.system.screenshot import save_screenshot
import writevewhere.windows.screenshot_window as screenshot_module
from writevewhere.windows.screenshot_window import PinnedScreenshotWindow, ScreenshotToolbar


def _app() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def _pixmap() -> QPixmap:
    pixmap = QPixmap(20, 16)
    pixmap.fill(QColor("#ff3333"))
    return pixmap


def _high_dpi_pixmap() -> QPixmap:
    pixmap = QPixmap(240, 160)
    pixmap.setDevicePixelRatio(2.0)
    pixmap.fill(QColor("#ff3333"))
    return pixmap


def test_save_screenshot_creates_screenshot_directory(tmp_path):
    _app()
    saved_path = save_screenshot(_pixmap(), root=tmp_path, timestamp="20260522_153012")

    assert saved_path == tmp_path / "screenshot" / "screenshot_20260522_153012.png"
    assert saved_path.exists()


def test_screenshot_toolbar_buttons_call_handlers():
    _app()
    calls: list[str] = []
    toolbar = ScreenshotToolbar(
        on_save=lambda: calls.append("save"),
        on_copy=lambda: calls.append("copy"),
        on_pin=lambda: calls.append("pin"),
        on_cancel=lambda: calls.append("cancel"),
    )

    toolbar.save_button.click()
    toolbar.copy_button.click()
    toolbar.pin_button.click()
    toolbar.cancel_button.click()

    assert calls == ["save", "copy", "pin", "cancel"]

    toolbar.close()


def test_pinned_screenshot_window_drags_and_resizes():
    _app()
    window = PinnedScreenshotWindow(_pixmap())
    window.show()
    start_pos = window.pos()
    start_size = window.size()

    window.mousePressEvent(
        QMouseEvent(
            QMouseEvent.Type.MouseButtonPress,
            window.rect().center(),
            window.rect().center(),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
    )
    window.mouseMoveEvent(
        QMouseEvent(
            QMouseEvent.Type.MouseMove,
            window.rect().center() + QPoint(20, 10),
            window.rect().center() + QPoint(20, 10),
            Qt.MouseButton.NoButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
    )

    assert window.pos() != start_pos

    resize_point = window.rect().bottomRight() - QPoint(4, 4)
    window.mousePressEvent(
        QMouseEvent(
            QMouseEvent.Type.MouseButtonPress,
            resize_point,
            resize_point,
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
    )
    window.mouseMoveEvent(
        QMouseEvent(
            QMouseEvent.Type.MouseMove,
            resize_point + QPoint(30, 20),
            resize_point + QPoint(30, 20),
            Qt.MouseButton.NoButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
    )

    assert window.width() > start_size.width()
    assert window.height() > start_size.height()

    window.close()


def test_pinned_screenshot_window_uses_device_independent_initial_size():
    _app()
    window = PinnedScreenshotWindow(_high_dpi_pixmap())

    assert window.width() == 124
    assert window.height() == 84

    label_pixmap = window.image_label.pixmap()
    assert label_pixmap is not None
    assert window._pixmap.devicePixelRatio() == 2.0
    assert window._last_scaled_size == window.image_label.size()

    window.close()


def test_pinned_screenshot_window_paints_highlight_border(monkeypatch):
    _app()
    window = PinnedScreenshotWindow(_pixmap())
    pen_colors: list[str] = []
    original_set_pen = screenshot_module.QPainter.setPen

    def record_pen(painter, pen):
        if isinstance(pen, QPen):
            pen_colors.append(pen.color().name())
        return original_set_pen(painter, pen)

    monkeypatch.setattr(screenshot_module.QPainter, "setPen", record_pen)

    window.paintEvent(QPaintEvent(window.rect()))

    assert "#ff4f4f" in pen_colors

    window.close()


def test_pinned_screenshot_window_resizes_from_left_edge():
    _app()
    window = PinnedScreenshotWindow(_pixmap())
    window.resize(120, 90)
    window.move(80, 80)
    start_right = window.geometry().right()
    left_edge = QPoint(3, window.height() // 2)

    window.mousePressEvent(
        QMouseEvent(
            QMouseEvent.Type.MouseButtonPress,
            left_edge,
            left_edge,
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
    )
    window.mouseMoveEvent(
        QMouseEvent(
            QMouseEvent.Type.MouseMove,
            left_edge - QPoint(30, 0),
            left_edge - QPoint(30, 0),
            Qt.MouseButton.NoButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
    )

    assert window.width() > 120
    assert window.geometry().right() == start_right

    window.close()
