"""Tests for the prompt and the parsing of the AI answer (pure Python)."""

import pytest

from custom_components.meter_vision.const import MeterType
from custom_components.meter_vision.reading import (
    Problem,
    build_instructions,
    build_structure,
    dial_labels,
    parse_reading,
)


def test_digits_become_a_value() -> None:
    reading = parse_reading({"digits": "01250922", "confidence": 8})
    assert reading.value == 1250922
    assert reading.problem is None
    assert reading.digits == "01250922"


def test_decimals_are_applied_here_not_by_the_model() -> None:
    assert parse_reading({"digits": "01250922", "confidence": 8}, digits=8, decimals=3).value == 1250.922


def test_separators_and_spaces_are_ignored() -> None:
    assert parse_reading({"digits": " 0125 0.922 ", "confidence": 8}).value == 1250922


@pytest.mark.parametrize(
    "answer",
    [
        {"digits": "0125X922", "confidence": 8},
        {"digits": "x", "confidence": 9},
        {"digits": "", "confidence": 9},
        {"digits": "12a4", "confidence": 9},
        {"digits": "01250922", "confidence": 2},
        {"digits": "01250922", "confidence": "high"},
    ],
)
def test_unreadable_frames(answer: dict) -> None:
    reading = parse_reading(answer)
    assert reading.value is None
    assert reading.problem is Problem.UNREADABLE


def test_digit_count() -> None:
    assert parse_reading({"digits": "101250922", "confidence": 8}, digits=8).problem is Problem.WRONG_DIGITS
    # A dropped leading zero is harmless.
    short = parse_reading({"digits": "1250922", "confidence": 8}, digits=8)
    assert short.value == 1250922
    assert short.digits == "01250922"


def test_confidence_is_clamped() -> None:
    assert parse_reading({"digits": "1", "confidence": 42}).confidence == 10


@pytest.mark.parametrize("data", [None, "1234", {"value": 1234}])
def test_not_an_answer(data) -> None:
    with pytest.raises(ValueError):
        parse_reading(data)


def test_instructions() -> None:
    text = build_instructions(MeterType.GAS, digits=8, decimals=3, notes="  ignore the blue digit ")
    assert "gas meter" in text
    assert "exactly 8 wheels" in text
    assert "last 3 wheel(s) are the decimal part" in text
    assert "NOTES FROM THE OWNER (they override the rules above): ignore the blue digit" in text
    plain = build_instructions(MeterType.WATER)
    assert "exactly 8" not in plain and "decimal part" not in plain and "NOTES" not in plain
    # Rules are numbered without gaps.
    assert "\n1. " in plain and "\n5. " in plain and "\n6. " not in plain


# ---------------------------------------------------------------- Meter Vision additions
# A Ferro water meter: 8 wheels in m³ with 3 red decimals and one x0.0001 pointer dial.
FERRO = {"digits": 8, "decimals": 3}


def test_a_rolling_last_wheel_is_a_reading_with_one_step_of_tolerance() -> None:
    reading = parse_reading({"digits": "00140925", "last_wheel_rolling": True, "confidence": 8}, **FERRO)
    assert reading.problem is None
    assert reading.value == 140.925
    assert reading.tolerance == 0.001
    assert reading.rolling is True


def test_only_the_last_wheel_unreadable_gives_a_lower_bound() -> None:
    reading = parse_reading({"digits": "0014092X", "confidence": 8}, **FERRO)
    assert reading.problem is None
    assert reading.value == 140.92
    assert reading.tolerance == 0.01
    assert reading.digits == "0014092X"


@pytest.mark.parametrize("digits", ["001X0925", "X0140925", "0014092XX"])
def test_any_other_unreadable_wheel_still_rejects_the_frame(digits: str) -> None:
    assert parse_reading({"digits": digits, "confidence": 8}, **FERRO).problem is Problem.UNREADABLE


def test_the_pointer_dial_adds_a_decimal() -> None:
    reading = parse_reading({"digits": "00140925", "dials": "7", "confidence": 8}, **FERRO, dials=1)
    assert reading.value == 140.9257
    assert reading.tolerance == 0.0001
    assert reading.dials == "7"


@pytest.mark.parametrize(("dial", "value"), [("0", 140.926), ("2", 140.9262), ("3", 140.9253), ("8", 140.9258)])
def test_a_rolling_wheel_is_resolved_by_the_dial(dial: str, value: float) -> None:
    # The last wheel turns while the dial passes 9 → 0: with the dial just past 0
    # the wheel is finishing its turn to the higher number.
    data = {"digits": "00140925", "dials": dial, "last_wheel_rolling": True, "confidence": 8}
    assert parse_reading(data, **FERRO, dials=1).value == value


@pytest.mark.parametrize("dials", ["X", "", "12", None])
def test_an_unreadable_dial_falls_back_to_the_wheels(dials) -> None:
    reading = parse_reading({"digits": "00140925", "dials": dials, "confidence": 8}, **FERRO, dials=1)
    assert reading.problem is None
    assert reading.value == 140.925
    assert reading.tolerance == 0.001


def test_the_dial_is_ignored_when_the_last_wheel_is_unknown() -> None:
    reading = parse_reading({"digits": "0014092X", "dials": "7", "confidence": 8}, **FERRO, dials=1)
    assert reading.value == 140.92
    assert reading.tolerance == 0.01


@pytest.mark.parametrize(("flag", "rolling"), [("true", True), ("false", False), (True, True), (None, False)])
def test_the_rolling_flag_accepts_text(flag, rolling: bool) -> None:
    assert parse_reading({"digits": "1", "last_wheel_rolling": flag, "confidence": 8}).rolling is rolling


def test_structure_asks_for_dials_only_when_the_meter_has_them() -> None:
    assert "dials" not in build_structure()
    structure = build_structure(1)
    assert set(structure) == {"digits", "last_wheel_rolling", "confidence", "dials"}
    structure["digits"]["selector"]["text"] = {"changed": True}
    assert build_structure(1)["digits"]["selector"] == {"text": {}}


def test_dial_labels() -> None:
    assert dial_labels(3, 1) == ["x0.0001"]
    assert dial_labels(0, 2) == ["x0.1", "x0.01"]


def test_instructions_with_dials() -> None:
    text = build_instructions(MeterType.WATER, digits=8, decimals=3, dials=1)
    assert "1 small round dial(s)" in text and "(x0.0001)" in text
    assert "small dials and pointers" not in text
    assert "never write X for a wheel that is only between two numbers" in text
