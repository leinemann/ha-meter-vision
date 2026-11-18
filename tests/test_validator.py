"""Tests for the plausibility check (pure Python)."""

from datetime import UTC, datetime, timedelta

from custom_components.meter_vision.validator import Outcome, ReadingValidator

T0 = datetime(2026, 1, 1, tzinfo=UTC)
INTERVAL = timedelta(minutes=15)


def _at(minutes: float) -> datetime:
    return T0 + timedelta(minutes=minutes)


def _validator(value: float = 1000) -> ReadingValidator:
    validator = ReadingValidator()
    validator.set(value, T0)
    return validator


def test_normal_growth_is_accepted() -> None:
    validator = _validator()
    assert validator.check(1000, _at(15), 300, INTERVAL) is Outcome.ACCEPTED
    assert validator.check(1250, _at(30), 300, INTERVAL) is Outcome.ACCEPTED
    assert validator.value == 1250
    assert validator.value_at == _at(30)


def test_a_decrease_is_rejected() -> None:
    validator = _validator()
    assert validator.check(999, _at(15), 300, INTERVAL) is Outcome.DECREASE
    assert validator.value == 1000


def test_a_single_misread_digit_never_passes() -> None:
    validator = _validator(1250922)
    assert validator.check(1260922, _at(15), 300, INTERVAL) is Outcome.UNCONFIRMED
    assert validator.value == 1250922
    assert validator.pending_value == 1260922
    # The next reading is the real one: accepted, and the misread is forgotten.
    assert validator.check(1250950, _at(30), 300, INTERVAL) is Outcome.ACCEPTED
    assert validator.pending_value is None


def test_a_misread_repeated_every_time_is_never_confirmed() -> None:
    # The first wheel hidden by a reflection and read as 9 on every frame.
    validator = _validator(345705)
    for minutes in (60, 120, 180):
        assert validator.check(9347418 + minutes, _at(minutes), 300, timedelta(hours=1)) is Outcome.IMPLAUSIBLE
    assert validator.value == 345705
    assert validator.pending_value is None
    # Within a day's worth of maximum increase, a confirmed jump is still accepted.
    assert validator.check(347418, _at(240), 300, timedelta(hours=1)) is Outcome.UNCONFIRMED
    assert validator.check(347420, _at(300), 300, timedelta(hours=1)) is Outcome.ACCEPTED


def test_the_implausible_limit_grows_after_a_long_outage() -> None:
    validator = _validator()
    # Ten days without an accepted value: up to ten days at the maximum increase.
    assert validator.check(400000, _at(10 * 1440), 300, INTERVAL) is Outcome.IMPLAUSIBLE
    assert validator.check(200000, _at(10 * 1440 + 15), 300, INTERVAL) is Outcome.ACCEPTED


def test_a_real_jump_is_accepted_once_confirmed() -> None:
    validator = _validator()
    # The camera was offline for a while, but only one interval passed since the last value.
    assert validator.check(2000, _at(15), 300, INTERVAL) is Outcome.UNCONFIRMED
    assert validator.check(2010, _at(30), 300, INTERVAL) is Outcome.ACCEPTED
    assert validator.value == 2010


def test_inconsistent_jumps_restart_the_confirmation() -> None:
    validator = _validator()
    assert validator.check(5000, _at(15), 300, INTERVAL) is Outcome.UNCONFIRMED
    assert validator.check(9000, _at(30), 300, INTERVAL) is Outcome.UNCONFIRMED
    assert validator.check(4000, _at(45), 300, INTERVAL) is Outcome.UNCONFIRMED  # lower than 9000: restart
    assert validator.check(4100, _at(60), 300, INTERVAL) is Outcome.ACCEPTED
    assert validator.value == 4100


def test_the_allowed_increase_grows_with_the_time_elapsed() -> None:
    validator = _validator()
    # Two hours without readings: up to 8 intervals' worth is plausible.
    assert validator.allowed(300, timedelta(hours=2), INTERVAL) == 2400
    assert validator.allowed(300, timedelta(minutes=1), INTERVAL) == 300
    assert validator.check(3300, _at(120), 300, INTERVAL) is Outcome.ACCEPTED


def test_the_first_reading_needs_confirmation() -> None:
    validator = ReadingValidator()
    assert validator.check(1000, _at(0), 300, INTERVAL) is Outcome.UNCONFIRMED
    assert validator.value is None
    assert validator.check(1001, _at(15), 300, INTERVAL) is Outcome.ACCEPTED
    assert validator.value == 1001


def test_decimals_do_not_suffer_from_float_rounding() -> None:
    validator = _validator(1250.922)
    assert validator.check(1251.222, _at(15), 0.3, INTERVAL) is Outcome.ACCEPTED


def test_round_trip() -> None:
    validator = _validator()
    validator.check(5000, _at(15), 300, INTERVAL)
    restored = ReadingValidator.from_dict(validator.as_dict())
    assert restored.as_dict() == validator.as_dict()
    assert ReadingValidator.from_dict({"value": "x", "value_at": "nope"}).value is None
    assert ReadingValidator.from_dict(None).value is None


def test_failed_outcomes() -> None:
    assert {o for o in Outcome if o.failed} == {
        Outcome.DECREASE,
        Outcome.IMPLAUSIBLE,
        Outcome.UNREADABLE,
        Outcome.WRONG_DIGITS,
        Outcome.ERROR,
    }


# ---------------------------------------------------------------- Meter Vision additions
def test_a_wheel_between_two_numbers_is_not_a_decrease() -> None:
    validator = _validator(140.926)
    # Read as 140.925 on the next frame (the wheel half way to 6): consistent, kept at 140.926.
    assert validator.check(140.925, _at(15), 0.3, INTERVAL, tolerance=0.001) is Outcome.ACCEPTED
    assert validator.value == 140.926
    assert validator.value_at == _at(15)
    assert validator.check(140.927, _at(30), 0.3, INTERVAL, tolerance=0.001) is Outcome.ACCEPTED
    assert validator.value == 140.927


def test_more_than_the_tolerance_below_is_still_a_decrease() -> None:
    validator = _validator(140.926)
    assert validator.check(140.924, _at(15), 0.3, INTERVAL, tolerance=0.001) is Outcome.DECREASE
    assert validator.value == 140.926


def test_an_unknown_last_wheel_keeps_the_value_within_ten_steps() -> None:
    validator = _validator(140.929)
    assert validator.check(140.92, _at(15), 0.3, INTERVAL, tolerance=0.01) is Outcome.ACCEPTED
    assert validator.value == 140.929
    # A lower bound above the accepted value moves it up, never past the meter.
    assert validator.check(140.93, _at(30), 0.3, INTERVAL, tolerance=0.01) is Outcome.ACCEPTED
    assert validator.value == 140.93


def test_confirmation_tolerates_a_rolling_wheel() -> None:
    validator = ReadingValidator()
    assert validator.check(140.926, _at(0), 0.3, INTERVAL, tolerance=0.001) is Outcome.UNCONFIRMED
    assert validator.check(140.925, _at(15), 0.3, INTERVAL, tolerance=0.001) is Outcome.ACCEPTED


def test_a_whole_frame_misread_is_rejected_with_any_tolerance() -> None:
    # Misreads seen from an AI-on-the-Edge device on this kind of meter: 1139.93 and 11140.93 m³.
    validator = _validator(140.925)
    for minutes, misread in ((15, 1139.93), (30, 11140.93), (45, 1139.93)):
        assert validator.check(misread, _at(minutes), 0.3, INTERVAL, tolerance=0.001) is Outcome.IMPLAUSIBLE
    assert validator.value == 140.925
