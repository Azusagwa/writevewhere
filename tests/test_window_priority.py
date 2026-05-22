from __future__ import annotations

from PySide6.QtCore import QPoint, QSettings, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QGraphicsOpacityEffect

import writevewhere.windows.control_window as control_module
from writevewhere.core import DrawMode
from writevewhere.windows import ControlWindow, OverlayWindow


def _app() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def _opacity(widget) -> float:
    effect = widget.graphicsEffect()
    assert isinstance(effect, QGraphicsOpacityEffect)
    return effect.opacity()


def _expanded_menu_empty_pos(control: ControlWindow) -> QPoint:
    for x in range(5, control.width() - 5):
        for y in range(5, control.height() - 5):
            point = QPoint(x, y)
            if control.childAt(point) is None and not control.main_button.geometry().contains(point):
                return point
    raise AssertionError("expanded menu has no empty hit-tested point")


def test_control_window_keeps_itself_on_top_after_mode_change(monkeypatch):
    _app()
    overlay = OverlayWindow()
    control = ControlWindow(overlay)

    calls: list[str] = []

    monkeypatch.setattr(overlay, "set_mode", lambda mode: calls.append(f"mode:{mode}"))
    monkeypatch.setattr(control, "ensure_on_top", lambda: calls.append("top"))

    control._set_mode(DrawMode.DRAW)
    QApplication.processEvents()

    assert calls == [f"mode:{DrawMode.DRAW}", "top", "top"]
    assert control.draw_button.isChecked()
    assert not control.erase_button.isChecked()

    control.close()
    overlay.close()


def test_pen_button_toggles_drawing_mode(monkeypatch):
    _app()
    overlay = OverlayWindow()
    control = ControlWindow(overlay)

    modes: list[DrawMode] = []
    monkeypatch.setattr(overlay, "set_mode", lambda mode: modes.append(mode))
    monkeypatch.setattr(control, "ensure_on_top", lambda: None)

    control._set_mode(DrawMode.PASSTHROUGH)
    control.draw_button.click()

    assert modes[-1] == DrawMode.DRAW
    assert control.draw_button.isChecked()
    assert not control.erase_button.isChecked()

    control.draw_button.click()

    assert modes[-1] == DrawMode.PASSTHROUGH
    assert not control.draw_button.isChecked()
    assert not control.erase_button.isChecked()

    control.close()
    overlay.close()


def test_control_window_starts_as_collapsed_icon_only_menu(monkeypatch):
    _app()
    overlay = OverlayWindow()
    control = ControlWindow(overlay)
    monkeypatch.setattr(control, "ensure_on_top", lambda: None)

    assert not control._expanded
    assert control.size().width() == 210
    assert control.size().height() == 220
    assert all(not widget.isVisible() for widget in control.menu_widgets)

    for button in [
        control.main_button,
        control.draw_button,
        control.box_button,
        control.ellipse_button,
        control.arrow_button,
        control.erase_button,
        control.color_button,
        control.width_button,
        control.clear_button,
        control.exit_button,
    ]:
        assert button.text() == ""

    control.close()
    overlay.close()


def test_control_window_expands_secondary_menu(monkeypatch):
    _app()
    overlay = OverlayWindow()
    control = ControlWindow(overlay)
    monkeypatch.setattr(control, "ensure_on_top", lambda: None)

    control.set_menu_expanded(True)

    assert control._expanded
    assert control.size().width() == 210
    assert control.size().height() == 220
    assert all(widget.isVisible() for widget in control.menu_widgets)
    assert not control.width_slider.isVisible()

    control.close()
    overlay.close()


def test_menu_animation_keeps_widgets_visible_and_updates_opacity(monkeypatch):
    _app()
    overlay = OverlayWindow()
    control = ControlWindow(overlay)
    monkeypatch.setattr(control, "ensure_on_top", lambda: None)

    control.set_menu_expanded(True)

    assert control._menu_animating
    assert all(widget.isVisible() for widget in control.menu_widgets)
    assert all(_opacity(widget) == 0.0 for widget in control.menu_widgets)

    QTest.qWait(320)

    assert not control._menu_animating
    assert all(widget.isVisible() for widget in control.menu_widgets)
    assert all(_opacity(widget) == 1.0 for widget in control.menu_widgets)

    control.set_menu_expanded(False)

    assert control._menu_animating
    assert all(widget.isVisible() for widget in control.menu_widgets)

    QTest.qWait(320)

    assert not control._menu_animating
    assert all(not widget.isVisible() for widget in control.menu_widgets)
    assert all(_opacity(widget) == 0.0 for widget in control.menu_widgets)

    control.close()
    overlay.close()


def test_collapse_keeps_expanded_mask_until_animation_finishes(monkeypatch):
    _app()
    overlay = OverlayWindow()
    control = ControlWindow(overlay)
    monkeypatch.setattr(control, "ensure_on_top", lambda: None)

    control.set_menu_expanded(True)
    QTest.qWait(320)

    control.set_menu_expanded(False)

    collapsing_mask = control.mask()
    assert collapsing_mask.contains(control.draw_button.geometry().center())
    assert collapsing_mask.contains(control.color_button.geometry().center())

    QTest.qWait(320)

    collapsed_mask = control.mask()
    assert collapsed_mask.contains(control.main_button.geometry().center())
    assert not collapsed_mask.contains(control._targets[control.draw_button])
    assert control.size().width() == 210
    assert control.size().height() == 220

    control.close()
    overlay.close()


def test_collapse_hides_width_slider_at_animation_finish(monkeypatch):
    _app()
    overlay = OverlayWindow()
    control = ControlWindow(overlay)
    monkeypatch.setattr(control, "ensure_on_top", lambda: None)

    control.set_menu_expanded(True)
    QTest.qWait(320)
    control.width_button.click()

    assert control.width_slider.isVisible()

    control.set_menu_expanded(False)

    assert control.width_slider.isVisible()
    assert _opacity(control.width_slider) == 0.0

    QTest.qWait(320)

    assert not control.width_slider.isVisible()
    assert not control.width_button.isChecked()

    control.close()
    overlay.close()


def test_menu_animation_only_raises_after_expand_finishes(monkeypatch):
    _app()
    overlay = OverlayWindow()
    control = ControlWindow(overlay)

    calls: list[str] = []
    monkeypatch.setattr(
        "writevewhere.windows.control_window.raise_above",
        lambda widget, owner=None: calls.append("top"),
    )

    control.set_menu_expanded(True)

    assert calls == []

    QTest.qWait(320)

    assert calls == ["top"]

    calls.clear()
    control.set_menu_expanded(False)

    assert calls == []

    QTest.qWait(320)

    assert calls == []

    control.close()
    overlay.close()


def test_control_window_position_is_clamped_to_screen_edges(monkeypatch):
    app = _app()
    overlay = OverlayWindow()
    control = ControlWindow(overlay)
    monkeypatch.setattr(control, "ensure_on_top", lambda: None)

    geometry = app.primaryScreen().availableGeometry()

    control._move_within_screen(QPoint(geometry.x() - 200, geometry.y() - 200))
    main_rect = control.main_button.geometry().translated(control.pos())
    assert main_rect.x() >= geometry.x()
    assert main_rect.y() >= geometry.y()

    control._move_within_screen(QPoint(geometry.x() + geometry.width() + 200, geometry.y() + geometry.height() + 200))
    main_rect = control.main_button.geometry().translated(control.pos())
    assert main_rect.right() <= geometry.right()
    assert main_rect.bottom() <= geometry.bottom()

    control.set_menu_expanded(True)
    control._move_within_screen(QPoint(geometry.x() + geometry.width() + 200, geometry.y() + geometry.height() + 200))
    assert control.x() + control.width() <= geometry.x() + geometry.width()
    assert control.y() + control.height() <= geometry.y() + geometry.height()

    control.close()
    overlay.close()


def test_expanded_menu_uses_non_overlapping_centered_radial_layout(monkeypatch):
    _app()
    overlay = OverlayWindow()
    control = ControlWindow(overlay)
    monkeypatch.setattr(control, "ensure_on_top", lambda: None)

    control.set_menu_expanded(True)
    QTest.qWait(180)

    all_buttons = [*control.mode_buttons.values(), *control.utility_buttons]
    all_rects = [button.geometry() for button in all_buttons]
    main_center = control.main_button.geometry().center()

    for index, rect in enumerate(all_rects):
        assert all(not rect.intersects(other) for other in all_rects[index + 1 :])
        assert abs((rect.center() - main_center).manhattanLength()) > 42

    assert control.width_button.geometry().center().y() > main_center.y()
    assert control.width_button.geometry().center().x() == main_center.x()

    control.close()
    overlay.close()


def test_first_click_after_dragging_main_button_still_toggles_menu(monkeypatch):
    _app()
    overlay = OverlayWindow()
    control = ControlWindow(overlay)
    monkeypatch.setattr(control, "ensure_on_top", lambda: None)
    control.show()

    QTest.mousePress(control.main_button, Qt.MouseButton.LeftButton, pos=QPoint(25, 25))
    QTest.mouseMove(control.main_button, QPoint(45, 25))
    QTest.mouseRelease(control.main_button, Qt.MouseButton.LeftButton, pos=QPoint(45, 25))

    assert not control._expanded

    control.main_button.click()

    assert control._expanded

    control.close()
    overlay.close()


def test_collapsed_secondary_menu_area_does_not_drag_window(monkeypatch):
    _app()
    overlay = OverlayWindow()
    control = ControlWindow(overlay)
    monkeypatch.setattr(control, "ensure_on_top", lambda: None)
    control.show()

    control._set_mode(DrawMode.DRAW)
    control.set_menu_expanded(False)
    start_pos = control.pos()
    hidden_button_center = control._targets[control.draw_button] + control.draw_button.rect().center()

    QTest.mousePress(control, Qt.MouseButton.LeftButton, pos=hidden_button_center)
    QTest.mouseMove(control, hidden_button_center + QPoint(30, 0))
    QTest.mouseRelease(control, Qt.MouseButton.LeftButton, pos=hidden_button_center + QPoint(30, 0))

    assert control.pos() == start_pos
    assert len(overlay.store.strokes) == 1

    control.close()
    overlay.close()


def test_expanded_secondary_menu_empty_area_draws_on_overlay(monkeypatch):
    _app()
    overlay = OverlayWindow()
    control = ControlWindow(overlay)
    monkeypatch.setattr(control, "ensure_on_top", lambda: None)
    control.show()

    control._set_mode(DrawMode.DRAW)
    control.set_menu_expanded(True)
    QTest.qWait(320)
    start_pos = control.pos()
    empty_menu_pos = _expanded_menu_empty_pos(control)

    QTest.mousePress(control, Qt.MouseButton.LeftButton, pos=empty_menu_pos)
    QTest.mouseMove(control, empty_menu_pos + QPoint(20, 0))
    QTest.mouseRelease(control, Qt.MouseButton.LeftButton, pos=empty_menu_pos + QPoint(20, 0))

    assert control.pos() == start_pos
    assert len(overlay.store.strokes) == 1

    control.close()
    overlay.close()


def test_expanded_secondary_menu_buttons_do_not_draw_on_overlay(monkeypatch):
    _app()
    overlay = OverlayWindow()
    control = ControlWindow(overlay)
    monkeypatch.setattr(control, "ensure_on_top", lambda: None)
    control.show()

    control._set_mode(DrawMode.DRAW)
    control.set_menu_expanded(True)
    QTest.qWait(320)

    control.width_button.click()

    assert control.width_slider.isVisible()
    assert overlay.store.strokes == []

    control.close()
    overlay.close()


def test_width_slider_updates_current_mode_width(monkeypatch, tmp_path):
    _app()
    settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    overlay = OverlayWindow()
    control = ControlWindow(overlay, settings=settings)
    monkeypatch.setattr(control, "ensure_on_top", lambda: None)

    pen_widths: list[int] = []
    eraser_widths: list[int] = []
    monkeypatch.setattr(overlay, "set_pen_width", lambda width: pen_widths.append(width))
    monkeypatch.setattr(overlay, "set_eraser_width", lambda width: eraser_widths.append(width))

    control.set_menu_expanded(True)
    control.width_button.click()
    assert control.width_slider.isVisible()

    control._set_mode(DrawMode.DRAW)
    control.width_slider.setValue(12)

    assert pen_widths[-1] == 12

    control._set_mode(DrawMode.ERASE)
    control.width_slider.setValue(12)

    assert eraser_widths[-1] == 48
    assert control._expanded

    control.close()
    overlay.close()


def test_width_slider_keeps_independent_width_per_draw_mode(monkeypatch, tmp_path):
    _app()
    settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    overlay = OverlayWindow()
    control = ControlWindow(overlay, settings=settings)
    monkeypatch.setattr(control, "ensure_on_top", lambda: None)

    control._set_mode(DrawMode.DRAW)
    control.width_slider.setValue(8)

    control._set_mode(DrawMode.BOX)

    assert control.width_slider.value() == 6
    assert overlay.pen_width == 6

    control.width_slider.setValue(14)

    control._set_mode(DrawMode.DRAW)

    assert control.width_slider.value() == 8
    assert overlay.pen_width == 8

    control._set_mode(DrawMode.ERASE)

    assert control.width_slider.value() == 6
    assert overlay.eraser_width == 24

    control.width_slider.setValue(9)

    assert overlay.eraser_width == 36

    control.close()
    overlay.close()


def test_width_settings_persist_between_control_windows(monkeypatch, tmp_path):
    _app()
    settings_path = tmp_path / "settings.ini"

    overlay = OverlayWindow()
    control = ControlWindow(overlay, settings=QSettings(str(settings_path), QSettings.Format.IniFormat))
    monkeypatch.setattr(control, "ensure_on_top", lambda: None)

    control._set_mode(DrawMode.ARROW)
    control.width_slider.setValue(17)
    control._set_mode(DrawMode.ERASE)
    control.width_slider.setValue(11)
    control.close()
    overlay.close()

    restored_overlay = OverlayWindow()
    restored_control = ControlWindow(
        restored_overlay,
        settings=QSettings(str(settings_path), QSettings.Format.IniFormat),
    )
    monkeypatch.setattr(restored_control, "ensure_on_top", lambda: None)

    restored_control._set_mode(DrawMode.ARROW)

    assert restored_control.width_slider.value() == 17
    assert restored_overlay.pen_width == 17

    restored_control._set_mode(DrawMode.ERASE)

    assert restored_control.width_slider.value() == 11
    assert restored_overlay.eraser_width == 44

    restored_control.close()
    restored_overlay.close()


def test_window_mask_follows_collapsed_and_expanded_hit_regions(monkeypatch):
    _app()
    overlay = OverlayWindow()
    control = ControlWindow(overlay)
    monkeypatch.setattr(control, "ensure_on_top", lambda: None)

    collapsed_mask = control.mask()
    assert collapsed_mask.contains(control.main_button.geometry().center())
    assert not collapsed_mask.contains(control._targets[control.draw_button])

    control.set_menu_expanded(True)
    expanded_mask = control.mask()
    assert expanded_mask.contains(control.main_button.geometry().center())
    assert expanded_mask.contains(control.draw_button.geometry().center())
    assert expanded_mask.contains(control.color_button.geometry().center())

    assert not expanded_mask.contains(control.width_slider.geometry().center())
    control.width_button.click()
    slider_mask = control.mask()
    assert slider_mask.contains(control.width_slider.geometry().center())

    control.close()
    overlay.close()


def test_selecting_mode_collapses_secondary_menu(monkeypatch):
    _app()
    overlay = OverlayWindow()
    control = ControlWindow(overlay)

    modes: list[DrawMode] = []
    monkeypatch.setattr(overlay, "set_mode", lambda mode: modes.append(mode))
    monkeypatch.setattr(control, "ensure_on_top", lambda: None)

    control.set_menu_expanded(True)
    control.erase_button.click()
    QTest.qWait(320)

    assert modes[-1] == DrawMode.ERASE
    assert control.erase_button.isChecked()
    assert not control._expanded
    assert control.size().width() == 210

    control.close()
    overlay.close()


def test_pen_button_switches_from_eraser_to_drawing(monkeypatch):
    _app()
    overlay = OverlayWindow()
    control = ControlWindow(overlay)

    modes: list[DrawMode] = []
    monkeypatch.setattr(overlay, "set_mode", lambda mode: modes.append(mode))
    monkeypatch.setattr(control, "ensure_on_top", lambda: None)

    control._set_mode(DrawMode.ERASE)
    control.draw_button.click()

    assert modes[-1] == DrawMode.DRAW
    assert control.draw_button.isChecked()
    assert not control.erase_button.isChecked()

    control.close()
    overlay.close()


def test_shape_buttons_select_matching_modes(monkeypatch):
    _app()
    overlay = OverlayWindow()
    control = ControlWindow(overlay)

    modes: list[DrawMode] = []
    monkeypatch.setattr(overlay, "set_mode", lambda mode: modes.append(mode))
    monkeypatch.setattr(control, "ensure_on_top", lambda: None)

    control.box_button.click()
    assert modes[-1] == DrawMode.BOX
    assert control.box_button.isChecked()
    assert not control.draw_button.isChecked()

    control.ellipse_button.click()
    assert modes[-1] == DrawMode.ELLIPSE
    assert control.ellipse_button.isChecked()
    assert not control.box_button.isChecked()

    control.arrow_button.click()
    assert modes[-1] == DrawMode.ARROW
    assert control.arrow_button.isChecked()
    assert not control.ellipse_button.isChecked()

    control.close()
    overlay.close()


def test_mode_buttons_toggle_back_to_passthrough(monkeypatch):
    _app()
    overlay = OverlayWindow()
    control = ControlWindow(overlay)

    modes: list[DrawMode] = []
    monkeypatch.setattr(overlay, "set_mode", lambda mode: modes.append(mode))
    monkeypatch.setattr(control, "ensure_on_top", lambda: None)

    for mode, button in control.mode_buttons.items():
        control._set_mode(mode)
        button.click()

        assert modes[-1] == DrawMode.PASSTHROUGH
        assert not button.isChecked()
        assert all(not mode_button.isChecked() for mode_button in control.mode_buttons.values())

    control.close()
    overlay.close()


def test_control_window_ensure_on_top_uses_window_priority_helper(monkeypatch):
    _app()
    overlay = OverlayWindow()
    control = ControlWindow(overlay)

    calls: list[object] = []
    monkeypatch.setattr(
        "writevewhere.windows.control_window.raise_above",
        lambda widget, owner=None: calls.append((widget, owner)),
    )

    control.ensure_on_top()

    assert calls == [(control, overlay)]

    control.close()
    overlay.close()


def test_overlay_set_mode_keeps_click_through_behavior_without_activation(monkeypatch):
    _app()
    overlay = OverlayWindow()

    click_through_calls: list[tuple[object, bool]] = []
    ensure_calls: list[str] = []
    monkeypatch.setattr(
        "writevewhere.windows.overlay_window.set_click_through",
        lambda widget, enabled: click_through_calls.append((widget, enabled)),
    )
    monkeypatch.setattr(overlay, "activateWindow", lambda: ensure_calls.append("activate"))

    class Control:
        def ensure_on_top(self) -> None:
            ensure_calls.append("top")

    overlay.set_control_window(Control())

    overlay.set_mode(DrawMode.DRAW)
    overlay.set_mode(DrawMode.PASSTHROUGH)

    assert click_through_calls == [(overlay, False), (overlay, True)]
    assert ensure_calls == ["top", "top"]

    overlay.close()


def test_control_window_ui_assets_load():
    _app()
    control_module._ui_asset_pixmap.cache_clear()

    assert not control_module._button_background("main", False).isNull()
    assert not control_module._button_background("secondary", True).isNull()
    assert not control_module._ui_asset_pixmap("icon-pen.png").isNull()


def test_control_window_falls_back_when_ui_assets_are_missing(monkeypatch):
    _app()
    control_module._ui_asset_pixmap.cache_clear()

    def missing_files(_package):
        raise FileNotFoundError

    monkeypatch.setattr(control_module.resources, "files", missing_files)

    assert control_module._button_background("main", False).isNull()
    assert not control_module._icon_for_mode(DrawMode.DRAW, False, "#ff3333").isNull()
    assert not control_module._utility_icon("clear").isNull()

    control_module._ui_asset_pixmap.cache_clear()
