from __future__ import annotations

import sys


def make_owned_window(widget, owner) -> None:
    if owner is None or sys.platform != "win32":
        return

    from ctypes import windll

    gwlp_hwndparent = -8
    windll.user32.SetWindowLongPtrW(
        int(widget.winId()),
        gwlp_hwndparent,
        int(owner.winId()),
    )


def force_topmost(widget) -> None:
    if sys.platform != "win32":
        widget.show()
        widget.raise_()
        widget.activateWindow()
        return

    from ctypes import windll

    hwnd = int(widget.winId())
    hwnd_topmost = -1
    swp_nosize = 0x0001
    swp_nomove = 0x0002
    swp_showwindow = 0x0040

    windll.user32.SetWindowPos(
        hwnd,
        hwnd_topmost,
        0,
        0,
        0,
        0,
        swp_nomove | swp_nosize | swp_showwindow,
    )


def raise_above(widget, owner=None) -> None:
    make_owned_window(widget, owner)
    widget.show()
    widget.raise_()
    widget.activateWindow()
    force_topmost(widget)
