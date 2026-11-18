"""Tests for the plausibility check (pure Python)."""

from datetime import UTC, datetime, timedelta

import pytest

from custom_components.meter_vision.const import RUN_SPAN, WINDOW_SIZE
from custom_components.meter_vision.validator import Outcome, ReadingValidator

T0 = datetime(2026, 1, 1, tzinfo=UTC)
INTERVAL = timedelta(minutes=15)


def _at(minutes: float) -> datetime:
    return T0 + timedelta(minutes=minutes)


def _validator(value: float = 1000) -> ReadingValidator:
    validator = ReadingValidator()
    validator.set(value, T0)
    return validator


def _feed(validator: ReadingValidator, values: list[float], start: int = 1, **kwargs) -> list[Outcome]:
    """One reading per interval, starting at interval ``start``."""
    kwargs.setdefault("max_increase", 300)
    kwargs.setdefault("interval", INTERVAL)
    return [validator.check(v, _at(15 * (start + i)), **kwargs) for i, v in enumerate(values)]


def test_the_reading_is_the_median_of_the_plausible_readings() -> None:
    validator = _validator(1000)
    assert _feed(validator, [1010, 1020, 1030, 1040]) == [Outcome.ACCEPTED] * 4
    assert validator.value == 1020  # median of 1000, 1010, 1020, 1030, 1040
    assert validator.value_at == _at(60)
    assert len(validator.window) == WINDOW_SIZE


def test_after_setup_a_single_misread_is_outvoted() -> None:
    # The setup reading fills the window: the first readings need a majority too.
    validator = _validator(100.0)
    assert _feed(validator, [99.75], max_increase=0.3, tolerance=0.0001) == [Outcome.ACCEPTED]
    assert validator.value == 100.0
    _feed(validator, [100.3, 100.3], start=2, max_increase=0.3, tolerance=0.0001)
    assert validator.value == 100.0


def test_a_large_decrease_is_rejected() -> None:
    validator = _validator()
    assert _feed(validator, [600]) == [Outcome.DECREASE]
    assert validator.value == 1000


def test_a_small_step_down_joins_the_window_and_is_outvoted() -> None:
    # A last wheel between two numbers, read low once.
    validator = _validator(140.926)
    assert _feed(validator, [140.925, 140.926, 140.927], max_increase=0.3, tolerance=0.001) == [Outcome.ACCEPTED] * 3
    assert validator.value == 140.926


def test_a_single_misread_never_reaches_the_reading() -> None:
    validator = _validator(1250922)
    outcomes = _feed(validator, [1250930, 1251122, 1250940, 1250950])  # +192 L misread, within the gate
    assert outcomes == [Outcome.ACCEPTED] * 4
    assert validator.value == 1250940


def test_a_repeated_misread_must_win_the_majority() -> None:
    # The field failure of a "confirm by the next reading" validator: the same
    # misread twice in a row was confirmed, and the reading stuck 1 m³ high.
    validator = _validator(140.9112)
    _feed(validator, [140.9123, 141.9116, 141.9116, 140.9166, 140.9166], max_increase=0.3, tolerance=0.0001)
    assert validator.value < 141


def test_a_jump_past_the_gate_is_taken_after_two_hours_of_agreement() -> None:
    # The camera was offline while the pool filled: 1.9 m³ more when it comes back.
    validator = _validator(1000)
    reads = 1 + int(RUN_SPAN / INTERVAL)  # first to last spans RUN_SPAN
    outcomes = _feed(validator, [2900 + i for i in range(reads)])
    assert outcomes == [Outcome.IMPLAUSIBLE] * (reads - 1) + [Outcome.ACCEPTED]
    assert 2900 < validator.value <= 2900 + reads


def test_a_plausible_reading_breaks_a_run_of_misreads() -> None:
    validator = _validator(1000)
    outcomes = _feed(validator, [2900, 2900, 1010, 2900, 2900, 2900, 2900])
    assert Outcome.ACCEPTED not in outcomes[3:]
    assert validator.value == 1000


def test_more_than_a_day_at_the_maximum_increase_is_never_taken() -> None:
    validator = _validator(345705)
    for minutes in (60, 120, 180, 240, 300, 360):
        assert validator.check(9347418 + minutes, _at(minutes), 300, timedelta(hours=1)) is Outcome.IMPLAUSIBLE
    assert validator.value == 345705
    assert validator.pending_value is None


def test_the_growth_gate_is_capped() -> None:
    validator = _validator(1000)
    # Ten hours without a reading: still only GROWTH_CAP_PERIODS intervals' worth of growth.
    assert validator.check(1000 + 300 * 3, _at(600), 300, INTERVAL) is Outcome.ACCEPTED
    validator = _validator(1000)
    assert validator.check(1000 + 300 * 4, _at(600), 300, INTERVAL) is Outcome.IMPLAUSIBLE


def test_starting_without_a_value_needs_a_majority_of_a_full_window() -> None:
    validator = ReadingValidator()
    readings = [1000, 1900, 1001, 1002, 1003]
    outcomes = [validator.check(v, _at(15 * i), 300, INTERVAL, tolerance=1) for i, v in enumerate(readings)]
    assert outcomes == [Outcome.UNCONFIRMED] * 4 + [Outcome.ACCEPTED]
    assert validator.value == 1001
    assert [p.value for p in validator.window] == [1000, 1001, 1002, 1003]


def test_starting_without_agreement_waits() -> None:
    validator = ReadingValidator()
    readings = [1000, 1900, 2800, 1001, 3700]
    outcomes = [validator.check(v, _at(15 * i), 300, INTERVAL, tolerance=1) for i, v in enumerate(readings)]
    assert outcomes == [Outcome.UNCONFIRMED] * 5
    assert validator.value is None


def test_decimals_do_not_suffer_from_float_rounding() -> None:
    validator = _validator(1250.922)
    assert validator.check(1251.222, _at(15), 0.3, INTERVAL) is Outcome.ACCEPTED


def test_round_trip() -> None:
    validator = _validator()
    _feed(validator, [1010, 5000, 1020])
    restored = ReadingValidator.from_dict(validator.as_dict())
    assert restored.as_dict() == validator.as_dict()
    assert ReadingValidator.from_dict({"value": "x", "value_at": "nope"}).value is None
    assert ReadingValidator.from_dict(None).value is None


def test_state_saved_by_the_first_release_is_restored() -> None:
    old = {"value": 140.925, "value_at": T0.isoformat(), "pending": []}
    validator = ReadingValidator.from_dict(old)
    assert validator.value == 140.925
    assert [p.value for p in validator.window] == [140.925] * WINDOW_SIZE


def test_the_published_value_survives_a_restart_with_its_hysteresis() -> None:
    validator = _validator(140.926)
    _feed(validator, [140.925] * 2 + [140.926], max_increase=0.3, tolerance=0.001)
    held = validator.value
    assert ReadingValidator.from_dict(validator.as_dict()).value == held


def test_failed_outcomes() -> None:
    assert {o for o in Outcome if o.failed} == {
        Outcome.UNCONFIRMED,
        Outcome.DECREASE,
        Outcome.IMPLAUSIBLE,
        Outcome.UNREADABLE,
        Outcome.WRONG_DIGITS,
        Outcome.ERROR,
    }


# ---------------------------------------------------------------- review regressions
def test_a_misread_repeated_for_less_than_two_hours_is_never_published() -> None:
    # A persistent reflection: the same +1 m³ misread, 8 times in a row (1 h 45 min).
    validator = _validator(140.915)
    outcomes = _feed(validator, [141.9] * 8 + [140.916] * 10, max_increase=0.3, tolerance=0.0001)
    assert Outcome.ACCEPTED not in outcomes[:8]
    assert outcomes[8:] == [Outcome.ACCEPTED] * 10
    assert validator.value == 140.916


def _run_length() -> int:
    return 1 + int(RUN_SPAN / INTERVAL)  # first to last spans RUN_SPAN


def test_a_misread_that_held_for_two_hours_is_undone_by_two_hours_of_true_readings() -> None:
    validator = _validator(140.915)
    n = _run_length()
    _feed(validator, [141.9] * n, max_increase=0.3, tolerance=0.0001)
    assert validator.value == 141.9  # a broken camera, held for RUN_SPAN: it got in
    assert validator.rebased_from.value == 140.915
    outcomes = _feed(
        validator, [140.916 + 0.0001 * i for i in range(n)], start=n + 1, max_increase=0.3, tolerance=0.0001
    )
    assert outcomes[:-1] == [Outcome.DECREASE] * (n - 1)
    assert outcomes[-1] is Outcome.ACCEPTED
    assert 140.916 <= validator.value < 140.92
    assert validator.rebased_from is None


@pytest.mark.parametrize("misread", [139.93, 11.93])  # a wheel one low; a dropped digit
def test_a_repeated_low_misread_never_takes_the_reading_down(misread: float) -> None:
    validator = _validator(140.915)
    outcomes = _feed(validator, [misread] * (4 * _run_length()), max_increase=0.3, tolerance=0.0001)
    assert set(outcomes) == {Outcome.DECREASE}
    assert validator.value == 140.915


def test_a_downward_run_stops_where_the_upward_one_started() -> None:
    validator = _validator(140.915)
    n = _run_length()
    _feed(validator, [141.9] * n, max_increase=0.3, tolerance=0.0001)
    outcomes = _feed(validator, [139.93] * (2 * n), start=n + 1, max_increase=0.3, tolerance=0.0001)
    assert Outcome.ACCEPTED not in outcomes
    assert validator.value == 141.9  # the problem alert has long fired; set_reading fixes it


def test_an_upward_re_base_can_only_be_undone_within_a_day() -> None:
    validator = _validator(140.915)
    n = _run_length()
    _feed(validator, [141.9] * n, max_increase=0.3, tolerance=0.0001)
    _feed(validator, [141.9] * 96, start=n + 1, max_increase=0.3, tolerance=0.0001)  # a day of agreement
    outcomes = _feed(validator, [140.916] * n, start=n + 97, max_increase=0.3, tolerance=0.0001)
    assert Outcome.ACCEPTED not in outcomes


def test_the_re_base_origin_survives_a_restart() -> None:
    validator = _validator(140.915)
    _feed(validator, [141.9] * _run_length(), max_increase=0.3, tolerance=0.0001)
    restored = ReadingValidator.from_dict(validator.as_dict())
    assert restored.rebased_from == validator.rebased_from


@pytest.mark.parametrize("rate", [0.05, 0.1, 0.15, 0.2, 0.3])
def test_a_meter_running_at_up_to_the_maximum_increase_is_followed(rate: float) -> None:
    validator = _validator(100.0)
    true = [100.0 + rate * n for n in range(1, 41)]  # ten hours
    outcomes = _feed(validator, true, max_increase=0.3, tolerance=0.001)
    assert outcomes == [Outcome.ACCEPTED] * len(true)
    # The median trails by about half the window.
    assert true[-1] - validator.value == pytest.approx(rate * (WINDOW_SIZE // 2), abs=1e-6)


def test_a_meter_running_twice_the_maximum_increase_is_never_stuck() -> None:
    validator = _validator(100.0)
    true = [100.0 + 0.6 * n for n in range(1, 401)]
    _feed(validator, true, max_increase=0.3, tolerance=0.001)
    # It lags while it runs too fast (raise the maximum increase), but it keeps up in steps.
    lag_limit = 0.6 * (RUN_SPAN / INTERVAL + WINDOW_SIZE + 1)
    assert true[-1] - validator.value <= lag_limit
