from __future__ import annotations

from PySide6.QtCore import QEvent, QPointF, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication

from writevewhere.core import DrawMode
from writevewhere.windows import OverlayWindow


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
