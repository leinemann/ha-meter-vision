# SPDX-License-Identifier: GPL-3.0-or-later
# Based on validator.py of ha-ai-meter-reader v1.0.1 (https://github.com/artech-lab/ha-ai-meter-reader).
# Modified for Meter Vision: a reading carries a tolerance (rolling last wheel).
"""Plausibility check of the readings: pure Python, no Home Assistant imports.

A meter counter only grows, and only so fast. ``ReadingValidator`` keeps the
last accepted value and decides what to do with each new reading:

- growth up to the allowed increase → accepted;
- a reading just below the accepted value, but within its own tolerance (the
  last wheel caught between two numbers) → consistent: the accepted value is
  kept, never lowered, and the reading counts as a success;
- a larger decrease → rejected (a misread digit);
- growth above the allowed increase → held back until the next readings
  confirm it (``CONFIRMATIONS`` in a row, each consistent with the previous
  one). A single misread digit never reaches the statistics, while a real jump
  (a long camera outage, heavy use) is accepted after a short delay. The first
  reading of a new meter goes through the same confirmation;
- growth above what the meter could do in ``MAX_JUMP_SPAN`` (or since the
  last accepted value, if longer) → rejected as implausible, however many
  readings agree: a digit the model misreads the same way every time (a wheel
  hidden by a reflection) must never be confirmed. Only ``set`` moves past it.

The allowed increase is the "maximum increase per reading" scaled by the time
elapsed, so readings missed for a while do not lock the counter.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Any

from .const import CONFIRMATIONS, MAX_JUMP_SPAN

_EPSILON = 1e-9


class Outcome(StrEnum):
    """Result of the last reading, as shown by the last result sensor."""

    ACCEPTED = "accepted"
    UNCONFIRMED = "unconfirmed"  # larger than allowed: waiting for confirmation
    DECREASE = "decrease"
    UNREADABLE = "unreadable"
    WRONG_DIGITS = "wrong_digits"
    IMPLAUSIBLE = "implausible"  # far more than the meter could do: never confirmed
    ERROR = "error"  # camera or AI failure
    CORRECTED = "corrected"  # set by hand with the set_reading action

    @property
    def failed(self) -> bool:
        """Counts towards a problem."""
        return self in (
            Outcome.DECREASE,
            Outcome.IMPLAUSIBLE,
            Outcome.UNREADABLE,
            Outcome.WRONG_DIGITS,
            Outcome.ERROR,
        )


@dataclass
class _Point:
    value: float
    at: datetime


class ReadingValidator:
    """Holds the accepted value and the readings waiting for confirmation."""

    def __init__(self) -> None:
        """Start without a value."""
        self.value: float | None = None
        self.value_at: datetime | None = None
        self.pending: list[_Point] = []

    @staticmethod
    def allowed(max_increase: float, elapsed: timedelta, interval: timedelta) -> float:
        """Largest plausible growth over ``elapsed``: at least one interval's worth."""
        periods = max(1.0, elapsed / interval) if interval.total_seconds() > 0 else 1.0
        return max_increase * periods

    def check(
        self, value: float, now: datetime, max_increase: float, interval: timedelta, tolerance: float = 0.0
    ) -> Outcome:
        """Judge a new reading and update the accepted value.

        ``value`` is the lowest value the frame is consistent with, ``tolerance``
        how far above it the meter may really be (one step of the last digit read).
        """
        if self.value is not None and self.value_at is not None:
            diff = value - self.value
            if diff < -_EPSILON:
                if diff + tolerance >= -_EPSILON:
                    # The frame agrees with the accepted value: keep it, never lower it.
                    # value_at stays: the allowed growth is measured from when the
                    # value was actually reached, not from this frame.
                    self.pending = []
                    return Outcome.ACCEPTED
                self.pending = []
                return Outcome.DECREASE
            elapsed = now - self.value_at
            if diff <= self.allowed(max_increase, elapsed, interval) + _EPSILON:
                self._accept(value, now)
                return Outcome.ACCEPTED
            if diff > self.allowed(max_increase, max(elapsed, MAX_JUMP_SPAN), interval) + _EPSILON:
                self.pending = []
                return Outcome.IMPLAUSIBLE

        last = self.pending[-1] if self.pending else None
        if last is not None and -_EPSILON - tolerance <= value - last.value <= (
            self.allowed(max_increase, now - last.at, interval) + _EPSILON
        ):
            self.pending.append(_Point(value, now))
        else:
            self.pending = [_Point(value, now)]
        if len(self.pending) >= CONFIRMATIONS:
            self._accept(value, now)
            return Outcome.ACCEPTED
        return Outcome.UNCONFIRMED

    def set(self, value: float, now: datetime) -> None:
        """Set the value by hand (meter replaced, first setup, correction)."""
        self._accept(value, now)

    def _accept(self, value: float, now: datetime) -> None:
        self.value = value
        self.value_at = now
        self.pending = []

    @property
    def pending_value(self) -> float | None:
        """The last reading waiting for confirmation."""
        return self.pending[-1].value if self.pending else None

    def as_dict(self) -> dict[str, Any]:
        """Serialisable state."""
        return {
            "value": self.value,
            "value_at": self.value_at.isoformat() if self.value_at else None,
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
                validator.value = float(data["value"])
                validator.value_at = datetime.fromisoformat(data["value_at"])
            validator.pending = [_Point(float(v), datetime.fromisoformat(t)) for v, t in data.get("pending") or []]
        except (TypeError, ValueError):
            return cls()
        return validator
