"""Replay two real days of a glitching water-meter camera through the validator (pure Python).

The fixture is an AI-on-the-Edge camera read every 5 minutes. About a third of its
rounds are misreads: 139.93 and 141.94 (a whole-number wheel off by one), 1139.93
and 11140.93 (a phantom leading digit), several of them repeated on consecutive
rounds. The true reading stays between 140.910 and 140.923 m³ for both days.

A validator that accepts a jump once the next reading confirms it ends 1 m³ high
on this corpus (0.1.0 did: 141.9507 m³, 80 true readings rejected as decreases).
These readings came from a CNN, not a vision model: they test the validator, not
how well any model reads a frame.
"""

import csv
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from custom_components.meter_vision.validator import Outcome, ReadingValidator

FIXTURE = Path(__file__).parent / "fixtures" / "field_water_meter_2026-11-16_18.csv"
LOW, HIGH = 140.9100, 140.9230  # the true reading over the two days
STEP = 0.0001  # one step of the x0.0001 dial: the finest digit read
MAX_INCREASE_15_MIN = 0.3  # the default for m³ of water


def _rounds() -> list[tuple[datetime, float]]:
    with FIXTURE.open(encoding="utf-8") as file:
        rows = csv.DictReader(line for line in file if not line.startswith("#"))
        return [
            (datetime.fromisoformat(r["time"]).replace(tzinfo=UTC), float(r["value"]))
            for r in rows
            if r["value"] not in ("unknown", "unavailable")
        ]


def _error_litres(value: float | None) -> float:
    return 0.0 if value is None else max(LOW - value, value - HIGH, 0.0) * 1000


def _replay(rounds: list[tuple[datetime, float]], interval: timedelta, max_increase: float) -> tuple[float, list]:
    validator = ReadingValidator()
    validator.set(140.9112, rounds[0][0] - interval)  # the reading typed in at setup
    worst, outcomes = 0.0, []
    for at, value in rounds:
        outcomes.append(validator.check(value, at, max_increase, interval, tolerance=STEP))
        worst = max(worst, _error_litres(validator.value))
    return worst, outcomes


def test_the_corpus_is_what_the_docstring_says() -> None:
    rounds = _rounds()
    misreads = [v for _, v in rounds if not LOW - 0.002 <= v <= HIGH + 0.002]
    assert len(rounds) == 111
    assert 30 <= len(misreads) <= 45
    assert {1139.9344, 11140.9305, 141.9116} <= {v for _, v in rounds}


def test_every_5_minutes_the_reading_never_leaves_the_true_range() -> None:
    worst, outcomes = _replay(_rounds(), timedelta(minutes=5), MAX_INCREASE_15_MIN / 3)
    assert worst == 0
    assert outcomes.count(Outcome.ACCEPTED) >= 70


@pytest.mark.parametrize("phase", [0, 1, 2])
def test_every_15_minutes_the_reading_never_leaves_the_true_range(phase: int) -> None:
    # Every third round, each of the three possible phases: what a 15-minute
    # interval would have seen of the same two days.
    worst, _ = _replay(_rounds()[phase::3], timedelta(minutes=15), MAX_INCREASE_15_MIN)
    assert worst == 0
