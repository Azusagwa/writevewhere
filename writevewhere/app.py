from __future__ import annotations

import sys

from PySide6.QtCore import QPoint
from PySide6.QtWidgets import QApplication

from writevewhere.windows import ControlWindow, OverlayWindow


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Writevewhere")

    overlay = OverlayWindow()
    overlay.show()

    control = ControlWindow(overlay)
    control.move_icon_top_left(QPoint(80, 80))
    control.show()
    control.ensure_on_top()

    return app.exec()
