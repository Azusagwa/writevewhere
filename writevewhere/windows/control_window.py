from __future__ import annotations

from functools import lru_cache
from importlib import resources
from math import cos, radians, sin

from PySide6.QtCore import (
    QEvent,
    QEasingCurve,
    QPoint,
    QPropertyAnimation,
    QRect,
    QSettings,
    QSignalBlocker,
    QSize,
    QTimer,
    Qt,
)
from PySide6.QtGui import QColor, QGuiApplication, QIcon, QPainter, QPainterPath, QPen, QPixmap, QRadialGradient, QRegion
from PySide6.QtWidgets import (
    QApplication,
    QColorDialog,
    QGraphicsOpacityEffect,
    QLabel,
    QSlider,
    QToolButton,
    QWidget,
)

from writevewhere.core import DrawMode
from writevewhere.system import raise_above
from writevewhere.windows.overlay_window import OverlayWindow

MODE_LABELS = {
    DrawMode.DRAW: "\u753b\u7b14",
    DrawMode.ERASE: "\u6a61\u76ae\u64e6",
    DrawMode.SCREENSHOT: "\u622a\u56fe",
    DrawMode.PASSTHROUGH: "\u900f\u4f20",
    DrawMode.BOX: "\u77e9\u5f62",
    DrawMode.ELLIPSE: "\u692d\u5706",
    DrawMode.ARROW: "\u7bad\u5934",
}

WINDOW_EXPANDED = QSize(210, 220)
EXPANDED_ANCHOR = QPoint(105, 100)
MAIN_SIZE = 50
MENU_SIZE = 32
UTILITY_SIZE = 32
ACCENT = "#ff4f4f"
MENU_POSITION_ANIMATION_MS = 165
MENU_OPACITY_ANIMATION_MS = 140
MENU_FINISH_DELAY_MS = 230
ICON_STROKE = "#46525d"
DEFAULT_WIDTH = 6
CONFIGURABLE_WIDTH_MODES = (
    DrawMode.DRAW,
    DrawMode.BOX,
    DrawMode.ELLIPSE,
    DrawMode.ARROW,
)

MODE_ICON_ASSETS = {
    DrawMode.DRAW: "icon-pen.png",
    DrawMode.BOX: "icon-box.png",
    DrawMode.ELLIPSE: "icon-ellipse.png",
    DrawMode.ARROW: "icon-arrow.png",
    DrawMode.ERASE: "icon-eraser.png",
    DrawMode.SCREENSHOT: "icon-camera.png",
    DrawMode.PASSTHROUGH: "icon-passthrough.png",
}

UTILITY_ICON_ASSETS = {
    "clear": "icon-clear.png",
    "exit": "icon-exit.png",
    "off": "icon-passthrough.png",
}


class _GlassToolButton(QToolButton):
    def __init__(self, role: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._role = role
        self._hovered = False
        self._visual_active = False

    def set_visual_active(self, active: bool) -> None:
        if self._visual_active == active:
            return
        self._visual_active = active
        self.update()

    def enterEvent(self, event) -> None:  # noqa: N802
        self._hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802
        self._hovered = False
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

        background = _button_background(self._role, self.isChecked() or self._visual_active)
        if not background.isNull():
            _draw_asset_pixmap(painter, self.rect(), background)
        else:
            _paint_fallback_button(painter, self.rect(), self.isChecked() or self._visual_active)

        if self._hovered and self.isEnabled():
            painter.setPen(QPen(QColor(255, 255, 255, 170), 1.2))
            painter.setBrush(QColor(255, 255, 255, 34))
            painter.drawEllipse(self.rect().adjusted(3, 3, -3, -3))

        icon = self.icon()
        if not icon.isNull():
            icon_size = self.iconSize()
            dpr = max(1.0, self.devicePixelRatioF())
            physical_size = QSize(round(icon_size.width() * dpr), round(icon_size.height() * dpr))
            pixmap = icon.pixmap(physical_size)
            pixmap.setDevicePixelRatio(dpr)
            logical_width = round(pixmap.width() / dpr)
            logical_height = round(pixmap.height() / dpr)
            top_left = self.rect().center() - QPoint(logical_width // 2, logical_height // 2)
            painter.drawPixmap(top_left, pixmap)

        painter.end()


class ControlWindow(QWidget):
    def __init__(self, overlay: OverlayWindow, settings: QSettings | None = None) -> None:
        super().__init__()
        self.overlay = overlay
        self._settings = settings or QSettings("Writevewhere", "Writevewhere")
        self._mode_widths = {mode: self._load_mode_width(mode) for mode in CONFIGURABLE_WIDTH_MODES}
        self._drag_start: QPoint | None = None
        self._drag_global_start: QPoint | None = None
        self._drag_window_start: QPoint | None = None
        self._dragging = False
        self._forwarding_overlay_events = False
        self._current_color = "#ff3333"
        self._mode = DrawMode.PASSTHROUGH
        self._expanded = False
        self._menu_animating = False
        self._menu_animation_id = 0
        self._animations: list[QPropertyAnimation] = []

        self.setWindowTitle("Writevewhere")
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setFixedSize(WINDOW_EXPANDED)
        self._build_ui()
        self._apply_window_mask(False)
        self.overlay.set_control_window(self)
        self._sync_width_slider_to_mode(DrawMode.DRAW, apply_overlay=True)
        self._set_mode(DrawMode.PASSTHROUGH)

    def _build_ui(self) -> None:
        self.setStyleSheet(
            """
            QSlider::groove:horizontal {
                height: 4px;
                background: rgba(235, 240, 246, 190);
                border: 1px solid rgba(78, 88, 102, 95);
                border-radius: 2px;
            }
            QSlider::handle:horizontal {
                width: 14px;
                margin: -6px 0;
                background: #ffffff;
                border: 1px solid rgba(57, 65, 79, 150);
                border-radius: 7px;
            }
            """
        )

        self.main_button = self._tool_button("\u83dc\u5355", MAIN_SIZE, role="main")
        self.main_button.setObjectName("mainButton")
        self.main_button.installEventFilter(self)
        self.main_button.clicked.connect(self.toggle_menu)

        self.color_dot = QLabel(self)
        self.color_dot.setFixedSize(8, 8)
        self.color_dot.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self._update_color_dot()

        self.draw_button = self._tool_button(MODE_LABELS[DrawMode.DRAW], MENU_SIZE, True)
        self.box_button = self._tool_button(MODE_LABELS[DrawMode.BOX], MENU_SIZE, True)
        self.ellipse_button = self._tool_button(MODE_LABELS[DrawMode.ELLIPSE], MENU_SIZE, True)
        self.arrow_button = self._tool_button(MODE_LABELS[DrawMode.ARROW], MENU_SIZE, True)
        self.screenshot_button = self._tool_button(MODE_LABELS[DrawMode.SCREENSHOT], MENU_SIZE, True)
        self.erase_button = self.screenshot_button

        self.mode_buttons: dict[DrawMode, QToolButton] = {
            DrawMode.DRAW: self.draw_button,
            DrawMode.BOX: self.box_button,
            DrawMode.ELLIPSE: self.ellipse_button,
            DrawMode.ARROW: self.arrow_button,
            DrawMode.SCREENSHOT: self.screenshot_button,
        }
        for mode, button in self.mode_buttons.items():
            button.setIcon(_icon_for_mode(mode, checked=False, color=self._current_color))
            button.clicked.connect(lambda _checked=False, selected=mode: self._select_mode(selected))

        self.color_button = self._tool_button("\u989c\u8272", UTILITY_SIZE, role="utility")
        self.color_button.setObjectName("utilityButton")
        self.color_button.clicked.connect(self._pick_color)

        self.width_button = self._tool_button("\u7c97\u7ec6", UTILITY_SIZE, role="utility")
        self.width_button.setObjectName("utilityButton")
        self.width_button.clicked.connect(self._toggle_width_slider)

        self.clear_button = self._tool_button("\u6e05\u7a7a", UTILITY_SIZE, role="utility")
        self.clear_button.setObjectName("utilityButton")
        self.clear_button.clicked.connect(self._clear_and_collapse)

        self.exit_button = self._tool_button("\u9000\u51fa", UTILITY_SIZE, role="utility")
        self.exit_button.setObjectName("utilityButton")
        self.exit_button.clicked.connect(self.close_app)

        self.width_slider = QSlider(Qt.Orientation.Horizontal, self)
        self.width_slider.setFixedSize(78, 22)
        self.width_slider.setRange(1, 30)
        self.width_slider.setValue(self._mode_widths[DrawMode.DRAW])
        self.width_slider.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.width_slider.setToolTip("\u7c97\u7ec6")
        self.width_slider.valueChanged.connect(self._set_width)
        self._install_opacity(self.width_slider, 0.0)

        self.utility_buttons = [self.color_button, self.width_button, self.clear_button, self.exit_button]
        self.menu_widgets: list[QWidget] = [*self.mode_buttons.values(), *self.utility_buttons]

        self._layout_expanded_targets()
        self._place_main_button()
        for widget in self.menu_widgets:
            widget.hide()
            widget.move(self._origin_for(widget))
            self._install_opacity(widget, 0.0)
        self.width_slider.hide()
        self.width_slider.move(self._targets[self.width_slider])

    def _tool_button(
        self,
        tooltip: str,
        size: int,
        checkable: bool = False,
        role: str = "secondary",
    ) -> QToolButton:
        button = _GlassToolButton(role, self)
        button.setFixedSize(size, size)
        button.setCheckable(checkable)
        button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        button.setToolTipDuration(1200)
        button.setToolTip(tooltip)
        icon_size = round(size * (0.62 if role == "main" else 0.68))
        button.setIconSize(QSize(icon_size, icon_size))
        return button

    def _layout_expanded_targets(self) -> None:
        self._targets: dict[QWidget, QPoint] = {}
        radial_items = [
            (self.draw_button, -72, MENU_SIZE),
            (self.box_button, -31, MENU_SIZE),
            (self.ellipse_button, 10, MENU_SIZE),
            (self.arrow_button, 51, MENU_SIZE),
            (self.width_button, 90, UTILITY_SIZE),
            (self.screenshot_button, 129, MENU_SIZE),
            (self.color_button, 170, UTILITY_SIZE),
            (self.clear_button, 211, UTILITY_SIZE),
            (self.exit_button, 252, UTILITY_SIZE),
        ]
        for button, angle, size in radial_items:
            self._targets[button] = self._point_on_arc(EXPANDED_ANCHOR, 58, angle, size)
        self._targets[self.width_slider] = QPoint(EXPANDED_ANCHOR.x() - self.width_slider.width() // 2, 186)

        self.color_button.setIcon(_color_icon(self._current_color))
        self.width_button.setIcon(_width_icon(self.width_slider.value()))
        self.clear_button.setIcon(_utility_icon("clear"))
        self.exit_button.setIcon(_utility_icon("exit"))

    def _point_on_arc(self, center: QPoint, radius: int, angle: int, size: int) -> QPoint:
        return QPoint(
            round(center.x() + radius * cos(radians(angle)) - size / 2),
            round(center.y() + radius * sin(radians(angle)) - size / 2),
        )

    def toggle_menu(self) -> None:
        self.set_menu_expanded(not self._expanded)

    def set_menu_expanded(self, expanded: bool) -> None:
        if self._expanded == expanded and not self._menu_animating:
            return

        anchor_global = self.mapToGlobal(self._main_center())
        self._menu_animation_id += 1
        animation_id = self._menu_animation_id
        self._menu_animating = True
        self._stop_animations()

        if expanded:
            self._expanded = True
            self._move_within_screen(anchor_global - self._main_center())
            self._place_main_button()
            self._apply_window_mask(True, include_slider=False)
            for widget in self.menu_widgets:
                widget.move(self._origin_for(widget))
                self._set_opacity(widget, 0.0)
                widget.show()
                widget.raise_()
            self.width_slider.hide()
            self.main_button.raise_()
            self.color_dot.raise_()
        else:
            self._expanded = True
            self._move_within_screen(anchor_global - self._main_center())
            self._place_main_button()
            self._apply_window_mask(True, include_slider=self.width_slider.isVisible())
            for widget in self.menu_widgets:
                self._set_opacity(widget, 1.0)
                widget.show()
                widget.raise_()
            self.main_button.raise_()
            self.color_dot.raise_()

        animations: list[QPropertyAnimation] = []
        for widget in self.menu_widgets:
            start = self._origin_for(widget) if expanded else widget.pos()
            end = self._targets[widget] if expanded else self._origin_for(widget)
            widget.move(start)
            animations.append(self._animate_pos(widget, end))
            animations.append(self._animate_opacity(widget, 1.0 if expanded else 0.0))

        self._animations = animations
        for animation in self._animations:
            animation.start()

        if not expanded and self.width_slider.isVisible():
            self._set_opacity(self.width_slider, 0.0)
        QTimer.singleShot(
            MENU_FINISH_DELAY_MS,
            lambda target=expanded, anchor=anchor_global, current_id=animation_id: self._finish_menu_animation(
                target, anchor, current_id
            ),
        )

    def _finish_menu_animation(self, expanded: bool, anchor_global: QPoint, animation_id: int) -> None:
        if animation_id != self._menu_animation_id:
            return
        self._menu_animating = False
        if expanded:
            self._expanded = True
            for widget in self.menu_widgets:
                self._set_opacity(widget, 1.0)
        else:
            self._expanded = False
            self._finish_collapse(anchor_global)
        if expanded:
            self.ensure_on_top()

    def _finish_collapse(self, anchor_global: QPoint) -> None:
        self.setUpdatesEnabled(False)
        try:
            for widget in self.menu_widgets:
                self._set_opacity(widget, 0.0)
                widget.hide()
            self._set_opacity(self.width_slider, 0.0)
            self.width_slider.hide()
            self.width_button.setChecked(False)
            self._move_within_screen(anchor_global - self._main_center())
            self._place_main_button()
            self._apply_window_mask(False, include_slider=False)
        finally:
            self.setUpdatesEnabled(True)
        self.update()

    def _animate_pos(self, widget: QWidget, end: QPoint) -> QPropertyAnimation:
        animation = QPropertyAnimation(widget, b"pos", self)
        animation.setDuration(MENU_POSITION_ANIMATION_MS)
        animation.setEndValue(end)
        animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        return animation

    def _animate_opacity(self, widget: QWidget, end: float) -> QPropertyAnimation:
        effect = widget.graphicsEffect()
        if not isinstance(effect, QGraphicsOpacityEffect):
            effect = self._install_opacity(widget, 0.0)
        animation = QPropertyAnimation(effect, b"opacity", self)
        animation.setDuration(MENU_OPACITY_ANIMATION_MS)
        animation.setEndValue(end)
        animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        return animation

    def _install_opacity(self, widget: QWidget, opacity: float) -> QGraphicsOpacityEffect:
        effect = QGraphicsOpacityEffect(widget)
        effect.setOpacity(opacity)
        widget.setGraphicsEffect(effect)
        return effect

    def _set_opacity(self, widget: QWidget, opacity: float) -> None:
        effect = widget.graphicsEffect()
        if not isinstance(effect, QGraphicsOpacityEffect):
            effect = self._install_opacity(widget, opacity)
        effect.setOpacity(opacity)

    def _stop_animations(self) -> None:
        for animation in self._animations:
            animation.stop()
            animation.deleteLater()
        self._animations = []

    def _main_center(self) -> QPoint:
        return EXPANDED_ANCHOR

    def _main_top_left(self) -> QPoint:
        center = self._main_center()
        return center - QPoint(MAIN_SIZE // 2, MAIN_SIZE // 2)

    def _place_main_button(self) -> None:
        self.main_button.move(self._main_top_left())
        self.color_dot.move(self.main_button.x() + MAIN_SIZE - 15, self.main_button.y() + MAIN_SIZE - 15)

    def _origin_for(self, widget: QWidget) -> QPoint:
        return self._main_center() - QPoint(widget.width() // 2, widget.height() // 2)

    def move_icon_top_left(self, position: QPoint) -> None:
        self._move_within_screen(position - self._main_top_left())

    def _apply_window_mask(self, expanded: bool, include_slider: bool = False) -> None:
        main_region = QRegion(QRect(self._main_top_left(), QSize(MAIN_SIZE, MAIN_SIZE)), QRegion.RegionType.Ellipse)
        if not expanded:
            self.setMask(main_region)
            return

        region = QRegion(QRect(QPoint(0, 0), self.size()))
        if not include_slider:
            slider_rect = QRect(self._targets[self.width_slider], self.width_slider.size()).adjusted(-6, -8, 6, 8)
            region = region.subtracted(QRegion(slider_rect))
        for widget, point in self._targets.items():
            if widget is self.width_slider and not include_slider:
                continue
            rect = QRect(point, widget.size())
            if isinstance(widget, QToolButton):
                region = region.united(QRegion(rect, QRegion.RegionType.Ellipse))
            else:
                region = region.united(QRegion(rect.adjusted(-6, -8, 6, 8)))
        self.setMask(region)

    def _select_mode(self, mode: DrawMode) -> None:
        if mode == self._mode:
            self._set_mode(DrawMode.PASSTHROUGH)
        else:
            self._set_mode(mode)
        self.set_menu_expanded(False)

    def _toggle_draw_mode(self) -> None:
        self._select_mode(DrawMode.DRAW)

    def sync_overlay_mode(self, mode: DrawMode) -> None:
        self._set_mode(mode, apply_overlay=False)

    def _set_mode(self, mode: DrawMode, apply_overlay: bool = True) -> None:
        self._mode = mode
        if mode in CONFIGURABLE_WIDTH_MODES:
            self._sync_width_slider_to_mode(mode, apply_overlay=apply_overlay)
        if apply_overlay:
            self.overlay.set_mode(mode)
        for button_mode, button in self.mode_buttons.items():
            checked = mode == button_mode
            button.setChecked(checked)
            button.setIcon(_icon_for_mode(button_mode, checked, self._current_color))
        self.main_button.setToolTip(MODE_LABELS[mode])
        self.main_button.setIcon(_icon_for_mode(mode, mode != DrawMode.PASSTHROUGH, self._current_color))
        if isinstance(self.main_button, _GlassToolButton):
            self.main_button.set_visual_active(mode != DrawMode.PASSTHROUGH)
        self.ensure_on_top()
        QTimer.singleShot(0, self.ensure_on_top)

    def ensure_on_top(self) -> None:
        if self._menu_animating:
            return
        raise_above(self, self.overlay)

    def _move_within_screen(self, position: QPoint) -> None:
        self.move(self._clamp_to_screen(position))

    def _clamp_to_screen(self, position: QPoint) -> QPoint:
        screen = QGuiApplication.screenAt(position + self._main_center())
        if screen is None:
            screen = self.screen() or QGuiApplication.primaryScreen()
        if screen is None:
            return position

        geometry = screen.availableGeometry()
        visible_rect = self._visible_bounds()
        min_x = geometry.x() - visible_rect.x()
        min_y = geometry.y() - visible_rect.y()
        max_x = geometry.x() + geometry.width() - visible_rect.x() - visible_rect.width()
        max_y = geometry.y() + geometry.height() - visible_rect.y() - visible_rect.height()
        x = min(max(position.x(), min_x), max_x)
        y = min(max(position.y(), min_y), max_y)
        return QPoint(x, y)

    def _visible_bounds(self) -> QRect:
        if self._expanded or self._menu_animating:
            return QRect(QPoint(0, 0), self.size())
        return QRect(self._main_top_left(), QSize(MAIN_SIZE, MAIN_SIZE))

    def _pick_color(self) -> None:
        color = QColorDialog.getColor(QColor(self._current_color), self, "\u9009\u62e9\u753b\u7b14\u989c\u8272")
        if not color.isValid():
            return
        self._current_color = color.name()
        self.overlay.set_pen_color(self._current_color)
        self.color_button.setIcon(_color_icon(self._current_color))
        self._update_color_dot()
        self._set_mode(self._mode)
        self.set_menu_expanded(False)

    def _toggle_width_slider(self) -> None:
        if self.width_slider.isVisible():
            self._hide_width_slider()
            return

        self.width_slider.move(self._targets[self.width_slider])
        self.width_slider.show()
        self.width_slider.raise_()
        self.main_button.raise_()
        self.color_dot.raise_()
        effect = self.width_slider.graphicsEffect()
        if isinstance(effect, QGraphicsOpacityEffect):
            effect.setOpacity(1.0)
        self.width_button.setChecked(True)
        self._apply_window_mask(True, include_slider=True)

    def _hide_width_slider(self) -> None:
        self.width_slider.hide()
        self.width_button.setChecked(False)
        if self._expanded:
            self._apply_window_mask(True, include_slider=False)

    def _set_width(self, width: int) -> None:
        mode = self._current_width_mode()
        width = self._clamp_width(width)
        self._mode_widths[mode] = width
        self._save_mode_width(mode, width)
        self._apply_width_to_overlay(mode, width)
        if hasattr(self, "width_button"):
            self.width_button.setIcon(_width_icon(width))

    def _current_width_mode(self) -> DrawMode:
        return self._mode if self._mode in CONFIGURABLE_WIDTH_MODES else DrawMode.DRAW

    def _sync_width_slider_to_mode(self, mode: DrawMode, apply_overlay: bool = False) -> None:
        width = self._mode_widths[mode]
        if hasattr(self, "width_slider"):
            blocker = QSignalBlocker(self.width_slider)
            self.width_slider.setValue(width)
            del blocker
        if hasattr(self, "width_button"):
            self.width_button.setIcon(_width_icon(width))
        if apply_overlay:
            self._apply_width_to_overlay(mode, width)

    def _apply_width_to_overlay(self, mode: DrawMode, width: int) -> None:
        self.overlay.set_pen_width(width)

    def _load_mode_width(self, mode: DrawMode) -> int:
        return self._clamp_width(self._settings.value(self._width_setting_key(mode), DEFAULT_WIDTH))

    def _save_mode_width(self, mode: DrawMode, width: int) -> None:
        self._settings.setValue(self._width_setting_key(mode), width)
        self._settings.sync()

    def _width_setting_key(self, mode: DrawMode) -> str:
        return f"widths/{mode.value}"

    def _clamp_width(self, width: object) -> int:
        try:
            return max(1, min(30, int(width)))
        except (TypeError, ValueError):
            return DEFAULT_WIDTH

    def _clear_and_collapse(self) -> None:
        self.overlay.clear()
        self.set_menu_expanded(False)

    def close_app(self) -> None:
        self.overlay.close()
        self.close()
        QApplication.instance().quit()

    def _update_color_dot(self) -> None:
        self.color_dot.setStyleSheet(
            f"background: {self._current_color}; border: 1px solid rgba(255, 255, 255, 210); border-radius: 5px;"
        )

    def eventFilter(self, watched, event) -> bool:  # noqa: N802
        if watched is self.main_button:
            if event.type() == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton:
                self._drag_global_start = event.globalPosition().toPoint()
                self._drag_window_start = self.pos()
                self._dragging = False
            elif event.type() == QEvent.Type.MouseMove and self._drag_global_start is not None:
                delta = event.globalPosition().toPoint() - self._drag_global_start
                if delta.manhattanLength() > 4:
                    self._dragging = True
                    if self._drag_window_start is not None:
                        self._move_within_screen(self._drag_window_start + delta)
                    return True
            elif event.type() == QEvent.Type.MouseButtonRelease:
                if self._dragging:
                    self._dragging = False
                    self._drag_global_start = None
                    self._drag_window_start = None
                    self.ensure_on_top()
                    return True
                self._drag_global_start = None
                self._drag_window_start = None
        return super().eventFilter(watched, event)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if self._should_forward_to_overlay(event):
            self._forwarding_overlay_events = True
            self.overlay.handle_control_passthrough_mouse_event(event)
            event.accept()
            return
        if (
            event.button() == Qt.MouseButton.LeftButton
            and self.main_button.geometry().contains(event.position().toPoint())
        ):
            self._drag_start = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
        else:
            self._drag_start = None
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        if self._forwarding_overlay_events:
            self.overlay.handle_control_passthrough_mouse_event(event)
            event.accept()
            return
        if self._drag_start is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self._move_within_screen(event.globalPosition().toPoint() - self._drag_start)
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if self._forwarding_overlay_events:
            self.overlay.handle_control_passthrough_mouse_event(event)
            self._forwarding_overlay_events = False
            event.accept()
            return
        self._drag_start = None
        self.ensure_on_top()
        super().mouseReleaseEvent(event)

    def _should_forward_to_overlay(self, event) -> bool:
        if event.button() != Qt.MouseButton.LeftButton or self._mode == DrawMode.PASSTHROUGH:
            return False

        event_pos = event.position().toPoint()
        if self.main_button.geometry().contains(event_pos):
            return False

        return not self._expanded or self.childAt(event_pos) is None

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        QTimer.singleShot(0, self.ensure_on_top)


def _icon_for_mode(mode: DrawMode, checked: bool, color: str) -> QIcon:
    fallback_color = QColor(color if checked else ICON_STROKE)
    fallback = _utility_icon("off", fallback_color) if mode == DrawMode.PASSTHROUGH else _draw_icon(mode.value, fallback_color)
    icon = _asset_icon(MODE_ICON_ASSETS[mode], fallback)
    if not icon.isNull():
        return icon
    return fallback


def _asset_icon(asset_name: str, fallback: QIcon | None = None) -> QIcon:
    pixmap = _ui_asset_pixmap(asset_name)
    if not pixmap.isNull():
        return QIcon(pixmap)
    return fallback or QIcon()


def _button_background(role: str, active: bool) -> QPixmap:
    if role == "main":
        return _ui_asset_pixmap("button-main-active.png" if active else "button-main.png")
    if role == "utility":
        return _ui_asset_pixmap("button-secondary-active.png" if active else "button-utility.png")
    return _ui_asset_pixmap("button-secondary-active.png" if active else "button-secondary.png")


def _draw_asset_pixmap(painter: QPainter, rect: QRect, pixmap: QPixmap) -> None:
    if pixmap.isNull():
        return

    device_pixmap = QPixmap(pixmap)
    dpr_x = pixmap.width() / max(1, rect.width())
    dpr_y = pixmap.height() / max(1, rect.height())
    device_pixmap.setDevicePixelRatio(min(dpr_x, dpr_y))
    painter.drawPixmap(rect.topLeft(), device_pixmap)


@lru_cache(maxsize=None)
def _ui_asset_pixmap(asset_name: str) -> QPixmap:
    try:
        asset_path = resources.files("writevewhere").joinpath("assets", "ui", asset_name)
    except (FileNotFoundError, ModuleNotFoundError):
        return QPixmap()
    pixmap = QPixmap(str(asset_path))
    return pixmap if not pixmap.isNull() else QPixmap()


def _paint_fallback_button(painter: QPainter, rect: QRect, active: bool) -> None:
    radius = max(rect.width(), rect.height()) * 0.56
    gradient = QRadialGradient(rect.center(), radius)
    gradient.setColorAt(0.0, QColor(255, 255, 255, 235))
    gradient.setColorAt(0.65, QColor(236, 244, 252, 185))
    gradient.setColorAt(1.0, QColor(208, 220, 233, 145))
    painter.setBrush(gradient)
    painter.setPen(QPen(QColor(255, 255, 255, 220), 1.2))
    painter.drawEllipse(rect.adjusted(2, 2, -2, -2))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.setPen(QPen(QColor(255, 91, 104, 215) if active else QColor(86, 98, 116, 100), 2 if active else 1))
    painter.drawEllipse(rect.adjusted(5, 5, -5, -5))


def _draw_icon(kind: str, color: QColor) -> QIcon:
    pixmap = QPixmap(64, 64)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(QPen(color, 5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))

    if kind == DrawMode.DRAW.value:
        path = QPainterPath()
        path.moveTo(14, 43)
        path.cubicTo(23, 22, 35, 50, 50, 18)
        painter.drawPath(path)
    elif kind == DrawMode.BOX.value:
        painter.drawRoundedRect(17, 18, 30, 28, 3, 3)
    elif kind == DrawMode.ELLIPSE.value:
        painter.drawEllipse(16, 18, 32, 28)
    elif kind == DrawMode.ARROW.value:
        painter.drawLine(16, 46, 47, 17)
        painter.drawLine(47, 17, 44, 32)
        painter.drawLine(47, 17, 32, 20)
    elif kind == DrawMode.ERASE.value:
        painter.drawRoundedRect(18, 28, 28, 18, 5, 5)
        painter.drawLine(25, 45, 48, 45)
    elif kind == DrawMode.SCREENSHOT.value:
        painter.drawRoundedRect(15, 22, 34, 24, 5, 5)
        painter.drawRoundedRect(21, 17, 12, 7, 3, 3)
        painter.drawEllipse(26, 27, 12, 12)
        painter.drawPoint(43, 27)

    painter.end()
    return QIcon(pixmap)


def _utility_icon(kind: str, color: QColor | None = None) -> QIcon:
    stroke = color or QColor(ICON_STROKE)
    if kind in UTILITY_ICON_ASSETS:
        fallback = _utility_icon_fallback(kind, stroke)
        return _asset_icon(UTILITY_ICON_ASSETS[kind], fallback)
    return _utility_icon_fallback(kind, stroke)


def _utility_icon_fallback(kind: str, stroke: QColor) -> QIcon:
    pixmap = QPixmap(64, 64)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(QPen(stroke, 5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))

    if kind == "clear":
        painter.drawArc(17, 18, 30, 30, 30 * 16, 285 * 16)
        painter.drawLine(19, 18, 17, 32)
        painter.drawLine(19, 18, 31, 21)
    elif kind == "exit":
        painter.drawLine(22, 22, 42, 42)
        painter.drawLine(42, 22, 22, 42)
    else:
        painter.drawEllipse(20, 20, 24, 24)
        painter.drawLine(18, 46, 46, 18)

    painter.end()
    return QIcon(pixmap)


def _width_icon(width: int) -> QIcon:
    pixmap = QPixmap(64, 64)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    base = _ui_asset_pixmap("icon-width.png")
    if not base.isNull():
        painter.drawPixmap(0, 0, base)
    else:
        painter.setPen(QPen(QColor(ICON_STROKE), 3.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawLine(17, 23, 47, 23)

    painter.setPen(QPen(QColor(ACCENT), max(3, min(12, width)), Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
    painter.drawLine(16, 46, 48, 46)
    painter.end()
    return QIcon(pixmap)


def _color_icon(color: str) -> QIcon:
    pixmap = QPixmap(64, 64)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    base = _ui_asset_pixmap("icon-color.png")
    if not base.isNull():
        painter.drawPixmap(0, 0, base)
    else:
        painter.setPen(QPen(QColor(ICON_STROKE), 4))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(19, 17, 26, 26)

    painter.setPen(QPen(QColor("#ffffff"), 3))
    painter.setBrush(QColor(color))
    painter.drawEllipse(36, 36, 14, 14)
    painter.end()
    return QIcon(pixmap)
