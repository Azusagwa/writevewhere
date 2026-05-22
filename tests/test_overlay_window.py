from __future__ import annotations

from PySide6.QtCore import QEvent, QPoint, QPointF, QRect, Qt
from PySide6.QtGui import QColor, QMouseEvent, QPaintEvent, QPixmap
from PySide6.QtWidgets import QApplication

from writevewhere.core import DrawMode
import writevewhere.windows.overlay_window as overlay_module
from writevewhere.windows import OverlayWindow
from writevewhere.windows.screenshot_window import ScreenshotToolbar


def _app() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def _mouse_event(
    event_type: QEvent.Type,
    button: Qt.MouseButton,
    buttons: Qt.MouseButton,
    x: float,
    y: float,
) -> QMouseEvent:
    position = QPointF(x, y)
    return QMouseEvent(
        event_type,
        position,
        position,
        position,
        button,
        buttons,
        Qt.KeyboardModifier.NoModifier,
    )


def test_left_button_release_commits_current_stroke():
    _app()
    overlay = OverlayWindow()
    overlay.mode = DrawMode.DRAW

    overlay.mousePressEvent(
        _mouse_event(QEvent.Type.MouseButtonPress, Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton, 1, 2)
    )
    overlay.mouseMoveEvent(
        _mouse_event(QEvent.Type.MouseMove, Qt.MouseButton.NoButton, Qt.MouseButton.LeftButton, 3, 4)
    )
    overlay.mouseReleaseEvent(
        _mouse_event(QEvent.Type.MouseButtonRelease, Qt.MouseButton.LeftButton, Qt.MouseButton.NoButton, 3, 4)
    )

    assert len(overlay.store.strokes) == 1
    assert overlay.current_stroke is None

    overlay.close()


def test_right_click_cancels_current_left_button_stroke():
    _app()
    overlay = OverlayWindow()
    overlay.mode = DrawMode.DRAW

    overlay.mousePressEvent(
        _mouse_event(QEvent.Type.MouseButtonPress, Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton, 1, 2)
    )
    overlay.mouseMoveEvent(
        _mouse_event(QEvent.Type.MouseMove, Qt.MouseButton.NoButton, Qt.MouseButton.LeftButton, 3, 4)
    )
    overlay.mousePressEvent(
        _mouse_event(
            QEvent.Type.MouseButtonPress,
            Qt.MouseButton.RightButton,
            Qt.MouseButton.LeftButton | Qt.MouseButton.RightButton,
            3,
            4,
        )
    )
    overlay.mouseReleaseEvent(
        _mouse_event(QEvent.Type.MouseButtonRelease, Qt.MouseButton.LeftButton, Qt.MouseButton.NoButton, 3, 4)
    )

    assert overlay.store.strokes == []
    assert overlay.current_stroke is None

    overlay.close()


def test_left_drag_starts_screenshot_selection_in_screenshot_mode(monkeypatch):
    _app()
    overlay = OverlayWindow()
    overlay.mode = DrawMode.SCREENSHOT
    captures: list[object] = []
    monkeypatch.setattr(overlay, "_capture_screenshot_selection", lambda rect: captures.append(rect) or QPixmap(20, 20))
    monkeypatch.setattr(overlay, "_show_screenshot_toolbar", lambda rect: captures.append(rect))

    overlay.mousePressEvent(
        _mouse_event(QEvent.Type.MouseButtonPress, Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton, 10, 10)
    )
    overlay.mouseMoveEvent(
        _mouse_event(QEvent.Type.MouseMove, Qt.MouseButton.NoButton, Qt.MouseButton.LeftButton, 40, 50)
    )
    overlay.mouseReleaseEvent(
        _mouse_event(QEvent.Type.MouseButtonRelease, Qt.MouseButton.LeftButton, Qt.MouseButton.NoButton, 40, 50)
    )

    assert len(captures) == 1
    assert overlay.screenshot_selection_rect is not None
    assert overlay.current_stroke is None

    overlay.close()


def test_right_drag_does_not_start_screenshot_selection_in_draw_mode():
    _app()
    overlay = OverlayWindow()
    overlay.mode = DrawMode.DRAW

    overlay.mousePressEvent(
        _mouse_event(QEvent.Type.MouseButtonPress, Qt.MouseButton.RightButton, Qt.MouseButton.RightButton, 10, 10)
    )
    overlay.mouseMoveEvent(
        _mouse_event(QEvent.Type.MouseMove, Qt.MouseButton.NoButton, Qt.MouseButton.RightButton, 40, 50)
    )
    overlay.mouseReleaseEvent(
        _mouse_event(QEvent.Type.MouseButtonRelease, Qt.MouseButton.RightButton, Qt.MouseButton.NoButton, 40, 50)
    )

    assert overlay.screenshot_selection_rect is None

    overlay.close()


def test_screenshot_selection_is_painted_with_dash_line(monkeypatch):
    _app()
    overlay = OverlayWindow()
    overlay.screenshot_selection_rect = overlay.rect().adjusted(10, 10, -10, -10)
    pen_styles: list[object] = []

    original_set_pen = overlay_module.QPainter.setPen

    def record_pen(painter, pen):
        if hasattr(pen, "style"):
            pen_styles.append(pen.style())
        return original_set_pen(painter, pen)

    monkeypatch.setattr(overlay_module.QPainter, "setPen", record_pen)

    overlay.paintEvent(QPaintEvent(overlay.rect()))

    assert Qt.PenStyle.DashLine in pen_styles

    overlay.close()


def test_small_right_drag_cancels_screenshot_selection(monkeypatch):
    _app()
    overlay = OverlayWindow()
    overlay.mode = DrawMode.SCREENSHOT
    captures: list[object] = []
    monkeypatch.setattr(overlay, "_capture_screenshot_selection", lambda rect: captures.append(rect) or QPixmap(2, 2))

    overlay.mousePressEvent(
        _mouse_event(QEvent.Type.MouseButtonPress, Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton, 10, 10)
    )
    overlay.mouseMoveEvent(
        _mouse_event(QEvent.Type.MouseMove, Qt.MouseButton.NoButton, Qt.MouseButton.LeftButton, 12, 12)
    )
    overlay.mouseReleaseEvent(
        _mouse_event(QEvent.Type.MouseButtonRelease, Qt.MouseButton.LeftButton, Qt.MouseButton.NoButton, 12, 12)
    )

    assert captures == []
    assert overlay.screenshot_selection_rect is None

    overlay.close()


def test_right_button_erases_existing_strokes_with_current_width(monkeypatch):
    _app()
    overlay = OverlayWindow()
    overlay.mode = DrawMode.DRAW
    overlay.pen_width = 7
    radii: list[float] = []
    points: list[object] = []
    monkeypatch.setattr(overlay.store, "erase_at", lambda point, radius: points.append(point) or radii.append(radius) or 1)

    overlay.mousePressEvent(
        _mouse_event(QEvent.Type.MouseButtonPress, Qt.MouseButton.RightButton, Qt.MouseButton.RightButton, 10, 10)
    )
    overlay.mouseMoveEvent(
        _mouse_event(QEvent.Type.MouseMove, Qt.MouseButton.NoButton, Qt.MouseButton.RightButton, 20, 20)
    )

    assert radii == [28, 28]
    assert len(points) == 2

    overlay.close()


def test_passthrough_right_drag_does_not_start_screenshot_selection():
    _app()
    overlay = OverlayWindow()
    overlay.mode = DrawMode.PASSTHROUGH

    overlay.mousePressEvent(
        _mouse_event(QEvent.Type.MouseButtonPress, Qt.MouseButton.RightButton, Qt.MouseButton.RightButton, 10, 10)
    )

    assert overlay.screenshot_selection_rect is None

    overlay.close()


def test_screenshot_toolbar_clicks_are_prioritized_over_drawing():
    _app()
    overlay = OverlayWindow()
    overlay.mode = DrawMode.DRAW
    calls: list[str] = []
    toolbar = ScreenshotToolbar(
        on_save=lambda: calls.append("save"),
        on_copy=lambda: calls.append("copy"),
        on_pin=lambda: calls.append("pin"),
        on_cancel=lambda: calls.append("cancel"),
    )
    toolbar.move(20, 20)
    toolbar.show()
    overlay._screenshot_toolbar = toolbar
    overlay._screenshot_pixmap = QPixmap(20, 20)
    button_center = toolbar.save_button.mapToGlobal(toolbar.save_button.rect().center())

    overlay.mousePressEvent(
        _mouse_event(
            QEvent.Type.MouseButtonPress,
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            button_center.x(),
            button_center.y(),
        )
    )
    overlay.mouseReleaseEvent(
        _mouse_event(
            QEvent.Type.MouseButtonRelease,
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.NoButton,
            button_center.x(),
            button_center.y(),
        )
    )

    assert calls == ["save"]
    assert overlay.store.strokes == []
    assert overlay.current_stroke is None

    toolbar.close()
    overlay.close()


def test_screenshot_toolbar_pauses_drawing_for_outside_clicks():
    _app()
    overlay = OverlayWindow()
    overlay.mode = DrawMode.DRAW
    toolbar = ScreenshotToolbar(
        on_save=lambda: None,
        on_copy=lambda: None,
        on_pin=lambda: None,
        on_cancel=lambda: None,
    )
    toolbar.move(20, 20)
    toolbar.show()
    overlay._screenshot_toolbar = toolbar
    overlay._screenshot_pixmap = QPixmap(20, 20)
    outside = QPoint(toolbar.frameGeometry().right() + 30, toolbar.frameGeometry().bottom() + 30)

    overlay.mousePressEvent(
        _mouse_event(
            QEvent.Type.MouseButtonPress,
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            outside.x(),
            outside.y(),
        )
    )
    overlay.mouseMoveEvent(
        _mouse_event(
            QEvent.Type.MouseMove,
            Qt.MouseButton.NoButton,
            Qt.MouseButton.LeftButton,
            outside.x() + 20,
            outside.y() + 20,
        )
    )
    overlay.mouseReleaseEvent(
        _mouse_event(
            QEvent.Type.MouseButtonRelease,
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.NoButton,
            outside.x() + 20,
            outside.y() + 20,
        )
    )

    assert overlay.store.strokes == []
    assert overlay.current_stroke is None

    toolbar.close()
    overlay.close()


def test_screenshot_selection_can_be_moved_and_resized_after_release():
    _app()
    overlay = OverlayWindow()
    overlay.mode = DrawMode.DRAW
    overlay.screenshot_selection_rect = overlay.rect().adjusted(100, 100, -600, -400)
    toolbar = ScreenshotToolbar(
        on_save=lambda: None,
        on_copy=lambda: None,
        on_pin=lambda: None,
        on_cancel=lambda: None,
    )
    toolbar.show()
    overlay._screenshot_toolbar = toolbar
    start_rect = overlay.screenshot_selection_rect
    assert start_rect is not None

    center = start_rect.center()
    overlay.mousePressEvent(
        _mouse_event(QEvent.Type.MouseButtonPress, Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton, center.x(), center.y())
    )
    overlay.mouseMoveEvent(
        _mouse_event(QEvent.Type.MouseMove, Qt.MouseButton.NoButton, Qt.MouseButton.LeftButton, center.x() + 20, center.y() + 15)
    )
    overlay.mouseReleaseEvent(
        _mouse_event(QEvent.Type.MouseButtonRelease, Qt.MouseButton.LeftButton, Qt.MouseButton.NoButton, center.x() + 20, center.y() + 15)
    )

    moved_rect = overlay.screenshot_selection_rect
    assert moved_rect is not None
    assert moved_rect.topLeft() == start_rect.topLeft() + QPoint(20, 15)

    bottom_right = moved_rect.bottomRight()
    overlay.mousePressEvent(
        _mouse_event(
            QEvent.Type.MouseButtonPress,
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            bottom_right.x(),
            bottom_right.y(),
        )
    )
    overlay.mouseMoveEvent(
        _mouse_event(
            QEvent.Type.MouseMove,
            Qt.MouseButton.NoButton,
            Qt.MouseButton.LeftButton,
            bottom_right.x() + 30,
            bottom_right.y() + 25,
        )
    )
    overlay.mouseReleaseEvent(
        _mouse_event(
            QEvent.Type.MouseButtonRelease,
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.NoButton,
            bottom_right.x() + 30,
            bottom_right.y() + 25,
        )
    )

    resized_rect = overlay.screenshot_selection_rect
    assert resized_rect is not None
    assert resized_rect.width() > moved_rect.width()
    assert resized_rect.height() > moved_rect.height()
    assert overlay.store.strokes == []

    toolbar.close()
    overlay.close()


def test_screenshot_actions_capture_current_selection(monkeypatch):
    _app()
    overlay = OverlayWindow()
    overlay.mode = DrawMode.DRAW
    overlay.screenshot_selection_rect = overlay.rect().adjusted(100, 100, -600, -400)
    pixmaps: list[QPixmap] = []
    captured_rects: list[object] = []
    monkeypatch.setattr(
        overlay,
        "_capture_screenshot_selection",
        lambda rect: captured_rects.append(rect) or QPixmap(rect.size()),
    )
    monkeypatch.setattr(overlay_module, "save_screenshot", lambda pixmap: pixmaps.append(pixmap))

    overlay._save_screenshot()

    assert captured_rects == [overlay.rect().adjusted(100, 100, -600, -400)]
    assert len(pixmaps) == 1
    assert overlay.screenshot_selection_rect is None

    overlay.close()


def test_screenshot_action_exits_to_passthrough(monkeypatch):
    _app()
    overlay = OverlayWindow()
    overlay.mode = DrawMode.SCREENSHOT
    overlay.screenshot_selection_rect = overlay.rect().adjusted(100, 100, -600, -400)
    monkeypatch.setattr(
        overlay,
        "_capture_screenshot_selection",
        lambda rect: QPixmap(rect.size()),
    )
    monkeypatch.setattr(overlay_module, "save_screenshot", lambda pixmap: None)

    overlay._save_screenshot()

    assert overlay.mode == DrawMode.PASSTHROUGH
    assert overlay.screenshot_selection_rect is None

    overlay.close()


def test_pinned_screenshot_clicks_are_prioritized_over_drawing():
    _app()
    overlay = OverlayWindow()
    overlay.mode = DrawMode.DRAW
    pinned = overlay_module.PinnedScreenshotWindow(QPixmap(120, 90))
    pinned.move(30, 30)
    pinned.show()
    overlay._pinned_screenshots.append(pinned)
    center = pinned.mapToGlobal(pinned.rect().center())

    overlay.mousePressEvent(
        _mouse_event(QEvent.Type.MouseButtonPress, Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton, center.x(), center.y())
    )
    overlay.mouseMoveEvent(
        _mouse_event(QEvent.Type.MouseMove, Qt.MouseButton.NoButton, Qt.MouseButton.LeftButton, center.x() + 20, center.y() + 10)
    )
    overlay.mouseReleaseEvent(
        _mouse_event(
            QEvent.Type.MouseButtonRelease,
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.NoButton,
            center.x() + 20,
            center.y() + 10,
        )
    )

    assert overlay.store.strokes == []
    assert pinned.pos() != QPoint(30, 30)

    pinned.close()
    overlay.close()


def test_screenshot_capture_keeps_overlay_visible_and_hides_selection(monkeypatch):
    _app()
    overlay = OverlayWindow()
    overlay.mode = DrawMode.DRAW
    overlay.screenshot_selection_rect = overlay.rect().adjusted(0, 0, -10, -10)
    hidden: list[str] = []
    selection_during_capture: list[object] = []
    monkeypatch.setattr(overlay, "hide", lambda: hidden.append("overlay"))

    def grab(rect):
        selection_during_capture.append(overlay.screenshot_selection_rect)
        return QPixmap(rect.size())

    monkeypatch.setattr(overlay_module, "_grab_virtual_desktop", grab)

    overlay._capture_screenshot_selection(overlay.rect().adjusted(0, 0, -10, -10))

    assert hidden == []
    assert selection_during_capture == [None]
    assert overlay.screenshot_selection_rect is not None

    overlay.close()


def test_grab_virtual_desktop_preserves_single_screen_device_pixel_ratio(monkeypatch):
    _app()
    captured = QPixmap(200, 120)
    captured.setDevicePixelRatio(2.0)
    captured.fill(QColor("#ff3333"))

    class Screen:
        def geometry(self):
            return QRect(0, 0, 1000, 800)

        def grabWindow(self, *_args):
            return captured

    monkeypatch.setattr(overlay_module.QGuiApplication, "screens", lambda: [Screen()])

    pixmap = overlay_module._grab_virtual_desktop(QRect(10, 20, 100, 60))

    assert pixmap.devicePixelRatio() == 2.0
    assert pixmap.size() == captured.size()
