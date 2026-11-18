"""The annotated frame: regions parsed, boxes derived, drawn on a real JPEG with Pillow."""

from io import BytesIO
import itertools

from PIL import Image
import pytest

from custom_components.meter_vision.annotate import (
    Annotation,
    Region,
    annotate,
    caption,
    digit_boxes,
    parse_region,
    parse_regions,
)

WIDTH, HEIGHT = 640, 480
COUNTER = Region(120, 200, 400, 80)  # 8 wheels of 50 px
DIAL = Region(400, 330, 80, 80)


def _frame(colour: tuple[int, int, int] = (128, 128, 128)) -> bytes:
    out = BytesIO()
    Image.new("RGB", (WIDTH, HEIGHT), colour).save(out, "JPEG", quality=95)
    return out.getvalue()


def _note(**changes) -> Annotation:
    base = {
        "outcome": "accepted",
        "at": "2026-11-18 15:04:05",
        "digits": "00140925",
        "dials": "3",
        "confidence": 9,
        "rolling": False,
        "value": "140.9253 m³",
    }
    return Annotation(**{**base, **changes})


def _pixel(jpeg: bytes, x: int, y: int) -> tuple[int, int, int]:
    return Image.open(BytesIO(jpeg)).convert("RGB").getpixel((x, y))


def _is(rgb: tuple[int, int, int], channel: str) -> bool:
    """Dominant colour, tolerant of JPEG noise: red, green or amber (red and green, little blue)."""
    r, g, b = rgb
    return {
        "red": r > 180 and g < 100 and b < 120,
        "green": g > 150 and r < 100 and b < 140,
        "amber": r > 180 and g > 120 and b < 80,
    }[channel]


# ------------------------------------------------------------ regions
def test_parse_region() -> None:
    assert parse_region(" 120, 200,400 ,80 ") == Region(120, 200, 400, 80)


@pytest.mark.parametrize("text", ["", "1,2,3", "1,2,3,4,5", "a,2,3,4", "-1,2,3,4", "1,2,0,4", "1,2,3,-4", "1.5,2,3,4"])
def test_parse_region_rejects(text: str) -> None:
    with pytest.raises(ValueError):
        parse_region(text)


def test_parse_regions() -> None:
    assert parse_regions("") == []
    assert parse_regions("  ") == []
    assert parse_regions("1,2,3,4; 5,6,7,8;") == [Region(1, 2, 3, 4), Region(5, 6, 7, 8)]
    with pytest.raises(ValueError):
        parse_regions("1,2,3,4; nonsense")


def test_digit_boxes_are_equal_slices_without_gaps() -> None:
    boxes = digit_boxes(Region(10, 20, 101, 30), 4)
    assert [b.x for b in boxes] == [10, 35, 60, 86]
    assert boxes[-1].x + boxes[-1].width == 111  # ends where the region ends
    assert all(b.y == 20 and b.height == 30 for b in boxes)
    assert all(b.x + b.width == n.x for b, n in itertools.pairwise(boxes))
    assert digit_boxes(COUNTER, 0) == []


# ------------------------------------------------------------ caption
def test_caption_says_outcome_value_time_and_what_was_read() -> None:
    first, second = caption(_note())
    assert first == "ACCEPTED · 140.9253 m3 · 2026-11-18 15:04:05"  # the built-in font has no ³
    assert second == "read 00140925 + dial 3 · confidence 9"
    assert caption(_note(outcome="implausible", rolling=True))[0].startswith("IMPLAUSIBLE")
    assert "last wheel rolling" in caption(_note(rolling=True))[1]
    assert caption(_note(outcome="error", digits=None, dials=None, confidence=None, value=None)) == (
        "ERROR · 2026-11-18 15:04:05",
        "nothing read",
    )
    assert caption(_note(outcome="wrong_digits"))[0].startswith("WRONG DIGITS")


# ------------------------------------------------------------ drawing
def test_annotated_frame_is_a_jpeg_of_the_same_size() -> None:
    out = annotate(_frame(), COUNTER, [DIAL], 8, _note())
    image = Image.open(BytesIO(out))
    assert image.format == "JPEG"
    assert image.size == (WIDTH, HEIGHT)


def test_confident_digits_are_green_boxes() -> None:
    out = annotate(_frame(), COUNTER, [], 8, _note(confidence=9))
    for box in digit_boxes(COUNTER, 8):
        assert _is(_pixel(out, box.x + box.width // 2, box.y + box.height - 1), "green"), box


def test_doubtful_reading_is_amber_and_an_unreadable_one_red() -> None:
    box = digit_boxes(COUNTER, 8)[3]
    bottom = (box.x + box.width // 2, box.y + box.height - 1)
    assert _is(_pixel(annotate(_frame(), COUNTER, [], 8, _note(confidence=5)), *bottom), "amber")
    assert _is(_pixel(annotate(_frame(), COUNTER, [], 8, _note(confidence=2)), *bottom), "red")


def test_an_unreadable_digit_is_red_and_crossed_out() -> None:
    out = annotate(_frame(), COUNTER, [], 8, _note(digits="0014X925", confidence=8))
    boxes = digit_boxes(COUNTER, 8)
    x_box, ok_box = boxes[4], boxes[3]
    assert _is(_pixel(out, x_box.x + x_box.width // 2, x_box.y + x_box.height - 1), "red")
    assert _is(_pixel(out, x_box.x + x_box.width // 2, x_box.y + x_box.height // 2), "red")  # the cross
    assert _is(_pixel(out, ok_box.x + ok_box.width // 2, ok_box.y + ok_box.height - 1), "green")
    assert not _is(_pixel(out, ok_box.x + ok_box.width // 2, ok_box.y + ok_box.height // 2), "red")


def test_a_digit_count_that_does_not_fit_the_boxes_marks_every_box_red() -> None:
    out = annotate(_frame(), COUNTER, [], 8, _note(outcome="wrong_digits", digits="1001409253", confidence=9))
    for box in digit_boxes(COUNTER, 8):
        assert _is(_pixel(out, box.x + box.width // 2, box.y + box.height - 1), "red"), box


def test_dial_is_circled_and_red_when_unreadable() -> None:
    bottom = (DIAL.x + DIAL.width // 2, DIAL.y + DIAL.height - 1)
    assert _is(_pixel(annotate(_frame(), COUNTER, [DIAL], 8, _note(dials="3")), *bottom), "green")
    assert _is(_pixel(annotate(_frame(), COUNTER, [DIAL], 8, _note(dials="X")), *bottom), "red")


def test_banner_on_top_even_without_regions() -> None:
    plain = _frame((200, 200, 200))
    out = annotate(plain, None, [], 8, _note())
    assert sum(_pixel(out, 2, 2)) < sum(_pixel(plain, 2, 2)) - 150  # darkened banner
    assert _pixel(out, WIDTH // 2, HEIGHT - 5) == pytest.approx(_pixel(plain, WIDTH // 2, HEIGHT - 5), abs=6)


def test_a_region_partly_outside_the_frame_is_clipped_not_an_error() -> None:
    out = annotate(_frame(), Region(600, 450, 400, 80), [Region(5000, 5000, 10, 10)], 8, _note())
    assert Image.open(BytesIO(out)).size == (WIDTH, HEIGHT)


def test_without_digit_count_the_boxes_follow_the_digits_read() -> None:
    out = annotate(_frame(), COUNTER, [], 0, _note(digits="1234"))
    box = digit_boxes(COUNTER, 4)[1]
    assert _is(_pixel(out, box.x, box.y + box.height // 2), "green")  # a slice edge at 1/4 of the region


def test_a_frame_that_is_not_an_image_raises_value_error() -> None:
    with pytest.raises(ValueError):
        annotate(b"\xff\xd8 not a jpeg", COUNTER, [], 8, _note())


def test_annotation_round_trips_through_storage() -> None:
    note = _note(rolling=True)
    assert Annotation.from_dict(note.as_dict()) == note
    assert Annotation.from_dict(None) is None
    assert Annotation.from_dict({"outcome": 3}) is None
