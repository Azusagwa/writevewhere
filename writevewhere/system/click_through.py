from __future__ import annotations

import sys

from PySide6.QtCore import Qt


def set_click_through(widget, enabled: bool) -> None:
    """切换点击穿透行为，尽可能使用原生 Windows 标志。"""
    widget.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, enabled)

    if sys.platform != "win32":
        widget.update()
        return

    from ctypes import windll

    hwnd = int(widget.winId())
    gwl_exstyle = -20
    ws_ex_layered = 0x00080000
    ws_ex_transparent = 0x00000020
    swp_nosize = 0x0001
    swp_nomove = 0x0002
    swp_nozorder = 0x0004
    swp_noactivate = 0x0010
    swp_framechanged = 0x0020

    get_window_long = getattr(windll.user32, "GetWindowLongPtrW", windll.user32.GetWindowLongW)
    set_window_long = getattr(windll.user32, "SetWindowLongPtrW", windll.user32.SetWindowLongW)
    set_window_pos = windll.user32.SetWindowPos

    style = get_window_long(hwnd, gwl_exstyle)
    if enabled:
        style |= ws_ex_layered | ws_ex_transparent
    else:
        style &= ~ws_ex_transparent
        style |= ws_ex_layered
    set_window_long(hwnd, gwl_exstyle, style)
    set_window_pos(
        hwnd,
        0,
        0,
        0,
        0,
        0,
        swp_nomove | swp_nosize | swp_nozorder | swp_noactivate | swp_framechanged,
    )
    widget.update()
