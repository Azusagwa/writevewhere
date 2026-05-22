from writevewhere.core import Point, Stroke, StrokeShape, StrokeStore


def test_stroke_add_point_skips_consecutive_duplicates():
    stroke = Stroke()

    stroke.add_point(Point(1, 2))
    stroke.add_point(Point(1, 2))
    stroke.add_point(Point(2, 3))

    assert stroke.points == [Point(1, 2), Point(2, 3)]


def test_stroke_intersects_line_segment_with_radius():
    stroke = Stroke(points=[Point(0, 0), Point(10, 0)], width=4)

    assert stroke.intersects(Point(5, 2), radius=2)
    assert not stroke.intersects(Point(5, 10), radius=2)


def test_store_erase_at_removes_only_hit_strokes():
    hit = Stroke(points=[Point(0, 0), Point(10, 0)], width=4)
    miss = Stroke(points=[Point(100, 100), Point(120, 100)], width=4)
    store = StrokeStore([hit, miss])

    removed = store.erase_at(Point(5, 1), radius=3)

    assert removed == 1
    assert store.strokes == [miss]


def test_store_clear_removes_all_strokes():
    store = StrokeStore([Stroke(points=[Point(1, 1)])])

    store.clear()

    assert store.strokes == []


def test_box_stroke_intersects_rectangle_outline():
    stroke = Stroke(points=[Point(0, 0), Point(20, 10)], width=4, shape=StrokeShape.BOX)

    assert stroke.intersects(Point(10, 1), radius=2)
    assert not stroke.intersects(Point(10, 5), radius=1)


def test_ellipse_stroke_intersects_ellipse_outline():
    stroke = Stroke(points=[Point(0, 0), Point(20, 10)], width=4, shape=StrokeShape.ELLIPSE)

    assert stroke.intersects(Point(10, 0), radius=2)
    assert not stroke.intersects(Point(10, 5), radius=1)


def test_arrow_stroke_intersects_arrow_line():
    stroke = Stroke(points=[Point(0, 0), Point(20, 0)], width=4, shape=StrokeShape.ARROW)

    assert stroke.intersects(Point(10, 1), radius=2)
    assert not stroke.intersects(Point(10, 8), radius=2)
