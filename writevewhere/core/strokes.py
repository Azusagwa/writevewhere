from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from math import hypot
from typing import Iterable


class DrawMode(str, Enum):
    DRAW = "draw"
    ERASE = "erase"
    PASSTHROUGH = "passthrough"
    BOX = "box"
    ELLIPSE = "ellipse"
    ARROW = "arrow"


class StrokeShape(str, Enum):
    FREEHAND = "freehand"
    BOX = "box"
    ELLIPSE = "ellipse"
    ARROW = "arrow"


@dataclass(frozen=True)
class Point:
    x: float
    y: float

    def distance_to(self, other: "Point") -> float:
        return hypot(self.x - other.x, self.y - other.y)


@dataclass
class Stroke:
    points: list[Point] = field(default_factory=list)
    color: str = "#ff3333"
    width: int = 5
    shape: StrokeShape = StrokeShape.FREEHAND

    def add_point(self, point: Point) -> None:
        if self.shape != StrokeShape.FREEHAND and self.points:
            if len(self.points) == 1:
                self.points.append(point)
            else:
                self.points[-1] = point
            return
        if not self.points or self.points[-1] != point:
            self.points.append(point)

    def intersects(self, point: Point, radius: float) -> bool:
        if not self.points:
            return False
        if self.shape == StrokeShape.BOX:
            return self._intersects_box(point, radius)
        if self.shape == StrokeShape.ELLIPSE:
            return self._intersects_ellipse(point, radius)
        if self.shape == StrokeShape.ARROW:
            return self._intersects_arrow(point, radius)
        if len(self.points) == 1:
            return self.points[0].distance_to(point) <= radius
        return any(
            _distance_to_segment(point, start, end) <= radius
            for start, end in zip(self.points, self.points[1:])
        )

    def _intersects_box(self, point: Point, radius: float) -> bool:
        if len(self.points) < 2:
            return self.points[0].distance_to(point) <= radius
        left, top, right, bottom = _bounds(self.points[0], self.points[1])
        corners = [
            Point(left, top),
            Point(right, top),
            Point(right, bottom),
            Point(left, bottom),
        ]
        edges = zip(corners, [*corners[1:], corners[0]])
        return any(_distance_to_segment(point, start, end) <= radius for start, end in edges)

    def _intersects_ellipse(self, point: Point, radius: float) -> bool:
        if len(self.points) < 2:
            return self.points[0].distance_to(point) <= radius
        left, top, right, bottom = _bounds(self.points[0], self.points[1])
        center_x = (left + right) / 2
        center_y = (top + bottom) / 2
        radius_x = max((right - left) / 2, 1)
        radius_y = max((bottom - top) / 2, 1)
        normalized = ((point.x - center_x) / radius_x) ** 2 + ((point.y - center_y) / radius_y) ** 2
        tolerance = radius / max(min(radius_x, radius_y), 1)
        return abs(normalized - 1) <= tolerance

    def _intersects_arrow(self, point: Point, radius: float) -> bool:
        if len(self.points) < 2:
            return self.points[0].distance_to(point) <= radius
        return _distance_to_segment(point, self.points[0], self.points[1]) <= radius


class StrokeStore:
    def __init__(self, strokes: Iterable[Stroke] | None = None) -> None:
        self.strokes: list[Stroke] = list(strokes or [])

    def add(self, stroke: Stroke) -> None:
        if stroke.points:
            self.strokes.append(stroke)

    def clear(self) -> None:
        self.strokes.clear()

    def erase_at(self, point: Point, radius: float) -> int:
        before = len(self.strokes)
        self.strokes = [
            stroke
            for stroke in self.strokes
            if not stroke.intersects(point, radius + stroke.width / 2)
        ]
        return before - len(self.strokes)


def _distance_to_segment(point: Point, start: Point, end: Point) -> float:
    dx = end.x - start.x
    dy = end.y - start.y
    if dx == 0 and dy == 0:
        return point.distance_to(start)

    t = ((point.x - start.x) * dx + (point.y - start.y) * dy) / (dx * dx + dy * dy)
    t = max(0.0, min(1.0, t))
    projection = Point(start.x + t * dx, start.y + t * dy)
    return point.distance_to(projection)


def _bounds(start: Point, end: Point) -> tuple[float, float, float, float]:
    return (
        min(start.x, end.x),
        min(start.y, end.y),
        max(start.x, end.x),
        max(start.y, end.y),
    )
