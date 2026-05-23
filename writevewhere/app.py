from __future__ import annotations

import os
import sys
import tempfile

from PySide6.QtCore import QLockFile, QPoint
from PySide6.QtWidgets import QApplication

from writevewhere.windows import ControlWindow, OverlayWindow


def main() -> int:
    lock_path = os.path.join(tempfile.gettempdir(), "Writevewhere.lock")
    lock = QLockFile(lock_path)
    lock.setStaleLockTime(0)

    if not lock.tryLock(0):
        return 0

    app = QApplication(sys.argv)
    app.setApplicationName("Writevewhere")

    overlay = OverlayWindow()
    overlay.show()

    control = ControlWindow(overlay)
    control.move_icon_top_left(QPoint(80, 80))
    control.show()
    control.ensure_on_top()

    result = app.exec()

    lock.unlock()
    return result
