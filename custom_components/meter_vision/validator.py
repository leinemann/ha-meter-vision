# SPDX-License-Identifier: GPL-3.0-or-later
# Based on validator.py of ha-ai-meter-reader v1.0.1 (https://github.com/artech-lab/ha-ai-meter-reader).
# Modified for Meter Vision: the published reading is the median of a window of
# plausible readings, not the last reading confirmed by the next one.
"""Plausibility check of the readings: pure Python, no Home Assistant imports.

Why a median: a camera that misreads tends to repeat the *same* misread on the
next frames (the same reflection, the same wheel half turned). "Accept a jump
once the next reading confirms it" then accepts it, and a validator that only
moves forward is stuck above the meter for good, rejecting every true reading
as a decrease. Two real days of an AI-on-the-Edge camera on a water meter
(``tests/fixtures``) end 1 m³ too high that way. The median of the last
``WINDOW_SIZE`` plausible readings only moves when a misread wins the majority,
and moves back when it stops winning.

Each reading is judged against the published value:

- no more than the maximum increase below it, and no more than the maximum
  increase per interval above the newest plausible reading (counted since that
  reading, capped at ``GROWTH_CAP_PERIODS``) → plausible: it joins the window
  and the published value becomes the median of the window. The gate is measured
  from the newest reading, not the median, because the median trails a running
  meter: a meter growing at up to the maximum increase stays inside it;
- a step down of the median by no more than the reading's tolerance (a last
  wheel flipping between two numbers) is ignored, so the reading doesn't flicker;
- further below → ``decrease``, further above → ``implausible``; neither joins
  the window. Both count towards the problem alert.

The published value can step down when a misread had briefly won the majority:
the reading sensor is a ``total`` sensor, so a correction is subtracted from the
consumption instead of being counted as a meter reset.

Rejected readings on the same side of the gate that keep agreeing (never
dropping by more than their tolerance) for ``RUN_SPAN``, at least
``WINDOW_SIZE`` of them, replace the window. That is the way back after a camera
outage, from a meter running faster than the maximum increase, and from a
misread that did get in. Upwards it is never more than the meter could do in
``MAX_JUMP_SPAN``. The field data's longest misread run was 15 minutes; a
frozen camera, which would repeat itself for ever, is caught before it gets
here (an identical frame is an error).

``set`` fills the window with the given value, so the first readings after it
need a majority like every later one. Without any value (saved state lost and
no setup reading), readings are collected until a majority of a full window
agrees within ``AGREE_STEPS`` steps of the last digit, and the wait counts as a
failure: with a camera that misreads often this can lock onto a cluster of
misreads, which is why the setup asks for the current reading.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
import statistics
from typing import Any

from .const import AGREE_STEPS, GROWTH_CAP_PERIODS, MAX_JUMP_SPAN, RUN_SPAN, WINDOW_SIZE

_EPSILON = 1e-9


class Outcome(StrEnum):
    """Result of the last reading, as shown by the last result sensor."""

    ACCEPTED = "accepted"  # plausible: joined the window
    UNCONFIRMED = "unconfirmed"  # no value (state lost): waiting for a majority; counts as a failure
    DECREASE = "decrease"
    UNREADABLE = "unreadable"
    WRONG_DIGITS = "wrong_digits"
    IMPLAUSIBLE = "implausible"  # more than the meter could have done
    ERROR = "error"  # camera or AI failure
    CORRECTED = "corrected"  # set by hand with the set_reading action

    @property
    def failed(self) -> bool:
        """Counts towards a problem."""
        return self in (
            Outcome.UNCONFIRMED,
            Outcome.DECREASE,
            Outcome.IMPLAUSIBLE,
            Outcome.UNREADABLE,
            Outcome.WRONG_DIGITS,
            Outcome.ERROR,
        )


@dataclass(frozen=True)
class _Point:
    value: float
    at: datetime


def _median(points: list[_Point]) -> float:
    return float(statistics.median_low(p.value for p in points))


class ReadingValidator:
    """Holds the window of plausible readings, the published value and the rejected run."""

    def __init__(self) -> None:
        """Start without a value."""
        self.value: float | None = None  # the published reading: median of the window
        self.value_at: datetime | None = None  # time of the last plausible reading
        self.window: list[_Point] = []
        self.pending: list[_Point] = []  # rejected readings in a row, or the start-up collection

    @staticmethod
    def allowed(max_increase: float, elapsed: timedelta, interval: timedelta) -> float:
        """Largest plausible growth over ``elapsed``: at least one interval's worth."""
        periods = max(1.0, elapsed / interval) if interval.total_seconds() > 0 else 1.0
        return max_increase * periods

    def check(
        self, value: float, now: datetime, max_increase: float, interval: timedelta, tolerance: float = 0.0
    ) -> Outcome:
        """Judge a new reading and update the published value.

        ``value`` is the lowest value the frame is consistent with, ``tolerance``
        how far above it the meter may really be (one step of the last digit read).
        """
        band = AGREE_STEPS * tolerance if tolerance > 0 else max_increase / AGREE_STEPS
        if self.value is None or self.value_at is None or not self.window:
            return self._start(_Point(value, now), band)

        # Growth is measured from the newest plausible reading, not from the median,
        # which trails a running meter: a meter growing at up to the maximum increase
        # per interval stays inside the gate however long it runs.
        newest = self.window[-1]
        periods = min(max((now - newest.at) / interval, 1.0), GROWTH_CAP_PERIODS) if interval.total_seconds() else 1
        low = self.value - max(max_increase, tolerance)
        high = max(self.value, newest.value) + max_increase * periods
        point = _Point(value, now)
        if low - _EPSILON <= value <= high + _EPSILON:
            self.pending = []
            self._add(point, tolerance)
            return Outcome.ACCEPTED
        outcome = Outcome.DECREASE if value < low else Outcome.IMPLAUSIBLE
        span = max(now - self.value_at, MAX_JUMP_SPAN)
        if value - self.value > self.allowed(max_increase, span, interval) + _EPSILON:
            self.pending = []  # more than the meter could do in a day: never taken
            return outcome
        return self._run(point, outcome, tolerance)

    def _run(self, point: _Point, outcome: Outcome, tolerance: float) -> Outcome:
        """Track rejected readings on one side of the gate; re-base on a long, steady run.

        The camera has been offline while the pool filled, the meter ran faster than
        the maximum increase, or a misread got published and every true reading is
        now a decrease: readings that keep agreeing for ``RUN_SPAN`` (and at least a
        full window of them) win. A misread repeated that long is a broken camera;
        the problem alert has fired long before.
        """
        assert self.value is not None
        side = point.value > self.value
        last = self.pending[-1] if self.pending else None
        if last is not None and (last.value > self.value) == side and point.value >= last.value - tolerance - _EPSILON:
            self.pending = [*self.pending, point]
        else:
            self.pending = [point]
        run = self.pending
        if len(run) < WINDOW_SIZE or run[-1].at - run[0].at < RUN_SPAN:
            return outcome
        self.pending, self.window, self.value = [], [], None
        for p in run[-WINDOW_SIZE:]:
            self._add(p)
        return Outcome.ACCEPTED

    def _start(self, point: _Point, band: float) -> Outcome:
        """No value yet: collect a window and publish once a majority agrees."""
        self.pending = [*self.pending, point][-WINDOW_SIZE:]
        if len(self.pending) < WINDOW_SIZE:
            return Outcome.UNCONFIRMED
        middle = _median(self.pending)
        agreeing = [p for p in self.pending if abs(p.value - middle) <= band + _EPSILON]
        if len(agreeing) <= WINDOW_SIZE // 2:
            return Outcome.UNCONFIRMED
        self.pending = []
        for p in agreeing:
            self._add(p)
        return Outcome.ACCEPTED

    def _add(self, point: _Point, tolerance: float = 0.0) -> None:
        self.window = [*self.window, point][-WINDOW_SIZE:]
        median = _median(self.window)
        # A last wheel flipping between two numbers moves the median by one step
        # and back: keep the value unless it drops by more than that step.
        if self.value is None or not 0 < self.value - median <= tolerance + _EPSILON:
            self.value = median
        self.value_at = point.at

    def set(self, value: float, now: datetime) -> None:
        """Set the value by hand (meter replaced, first setup, correction).

        The window is filled with it, so the first readings after it need a
        majority to move the value, like every later one.
        """
        self.pending = []
        self.window = [_Point(value, now)] * WINDOW_SIZE
        self.value, self.value_at = value, now

    @property
    def pending_value(self) -> float | None:
        """The last reading waiting: a rejected run, or the start-up collection."""
        return self.pending[-1].value if self.pending else None

    def as_dict(self) -> dict[str, Any]:
        """Serialisable state."""
        return {
            "value": self.value,
            "value_at": self.value_at.isoformat() if self.value_at else None,
            "window": [[p.value, p.at.isoformat()] for p in self.window],
            "pending": [[p.value, p.at.isoformat()] for p in self.pending],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> ReadingValidator:
        """Restore from ``as_dict``; anything malformed starts empty."""
        validator = cls()
        if not isinstance(data, dict):
            return validator
        try:
            if data.get("value") is not None and data.get("value_at"):
                value, at = float(data["value"]), datetime.fromisoformat(data["value_at"])
                window = [_Point(float(v), datetime.fromisoformat(t)) for v, t in data.get("window") or []]
                # State saved by the first release has no window: fill one with its value.
                validator.window = window[-WINDOW_SIZE:] or [_Point(value, at)] * WINDOW_SIZE
                validator.value, validator.value_at = value, at  # the published value, hysteresis included
            validator.pending = [_Point(float(v), datetime.fromisoformat(t)) for v, t in data.get("pending") or []]
        except (TypeError, ValueError):
            return cls()
        return validator
