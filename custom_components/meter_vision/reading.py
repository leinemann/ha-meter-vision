# SPDX-License-Identifier: GPL-3.0-or-later
# Based on reading.py of ha-ai-meter-reader v1.0.1 (https://github.com/artech-lab/ha-ai-meter-reader).
# Modified for Meter Vision: rolling last wheel, optional pointer dials, readings as a range.
"""Prompt, output schema and parsing of one meter reading.

Pure Python, no Home Assistant imports besides the constants. The prompt is in
English on purpose: it is short, numbered and asks for digits only, which small
local vision models follow best. The model never does arithmetic: it copies the
digits it sees, and the decimal point and every check are applied here.

A reading is a range, not a point: ``value`` is the lowest value the frame is
consistent with and ``tolerance`` how far above it the meter may really be.
The last wheel of a counter turns continuously and is often caught between two
numbers; the model writes the lower one, so the true value lies within one step
of the last digit read. The validator uses that range to tell a wheel in motion
(``value`` just below the accepted reading) from a real decrease.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import re
from typing import Any

from .const import MIN_CONFIDENCE, ROLLOVER_DIAL_MAX, MeterType


class Problem(StrEnum):
    """Why a frame did not give a usable number."""

    UNREADABLE = "unreadable"  # a digit was marked unreadable, or nothing was read
    WRONG_DIGITS = "wrong_digits"  # more digits than the counter has


_METER_NAMES = {MeterType.WATER: "water", MeterType.GAS: "gas", MeterType.ENERGY: "electricity or heat"}
UNREADABLE_MARK = "X"
_SEPARATORS = re.compile(r"[\s.,'_\-]")

_BASE_STRUCTURE: dict[str, Any] = {
    # No minimum/maximum on numbers: some providers reject them in structured
    # output schemas. The range is enforced by parse_reading().
    "digits": {
        "description": "Counter wheels left to right, leading zeros included, X for an unreadable wheel",
        "required": True,
        "selector": {"text": {}},
    },
    "last_wheel_rolling": {
        "description": "true when the LAST wheel is caught between two numbers",
        "required": True,
        "selector": {"boolean": {}},
    },
    "confidence": {
        "description": "0-10: how sure you are of every single digit",
        "required": True,
        "selector": {"number": {"mode": "box"}},
    },
}
_DIALS_FIELD: dict[str, Any] = {
    "description": "One digit per pointer dial, largest factor first, X for an unreadable dial",
    "required": True,
    "selector": {"text": {}},
}


def build_structure(dials: int = 0) -> dict[str, Any]:
    """The structured-output schema: a fresh copy, the service call may mutate it."""
    structure = {key: {**field, "selector": dict(field["selector"])} for key, field in _BASE_STRUCTURE.items()}
    if dials:
        structure["dials"] = {**_DIALS_FIELD, "selector": {"text": {}}}
    return structure


def dial_labels(decimals: int, dials: int) -> list[str]:
    """Factors printed next to the dials, largest first: decimals 3, dials 1 → ["x0.0001"]."""
    return [f"x{10.0 ** -(decimals + n):.{decimals + n}f}" for n in range(1, dials + 1)]


def build_instructions(
    meter_type: MeterType, digits: int = 0, decimals: int = 0, notes: str = "", dials: int = 0
) -> str:
    """The instructions sent to the AI Task entity with one camera frame."""
    rules = ["Include leading zeros. No spaces, separators, units or decimal point."]
    if digits:
        rules.append(f"The counter has exactly {digits} wheels: write all {digits}.")
    if decimals:
        rules.append(
            f"The last {decimals} wheel(s) are the decimal part (often red, or on a coloured background): "
            "include them, without a decimal point."
        )
    rules += [
        "A wheel caught between two numbers: write the LOWER one (between 9 and 0, write 9). This is normal, "
        f"especially for the last wheel, which turns all the time: never write {UNREADABLE_MARK} for a wheel that "
        "is only between two numbers.",
        "last_wheel_rolling: true when the last wheel shows parts of two numbers, false when it shows one clearly.",
        f"A wheel that is blurred, hidden, reflected or not clearly readable: write {UNREADABLE_MARK} in its place. "
        f"Never guess a digit. If you cannot find the counter at all, write {UNREADABLE_MARK}.",
    ]
    if dials:
        labels = ", ".join(dial_labels(decimals, dials))
        rules += [
            "Ignore serial numbers, labels and barcodes.",
            f"The meter also has {dials} small round dial(s) with a pointer and a 0-9 scale ({labels}). In 'dials' "
            f"write one digit per dial in that order: the number the pointer has most recently passed going "
            f"clockwise (between 9 and 0, write 9). {UNREADABLE_MARK} for a dial you cannot read.",
        ]
    else:
        rules.append("Ignore serial numbers, labels, barcodes, small dials and pointers.")
    numbered = "\n".join(f"{n}. {rule}" for n, rule in enumerate(rules, 1))
    owner = (
        f"\nNOTES FROM THE OWNER (they override the rules above): {notes.strip()}\n" if notes and notes.strip() else ""
    )
    return f"""You read the counter of a {_METER_NAMES[meter_type]} meter from ONE photo, like a meter reader \
would. Copy the digits you see; never calculate, never estimate.

TASK: write the digits of the counter (the row of number wheels or the display) from left to right, exactly as \
printed.

RULES:
{numbered}
{owner}
IMAGE BASELINE: small meter cameras give dim, noisy, colour-tinted close-ups with a bright flash spot. Such an \
image IS readable when the digits are sharp.

CONFIDENCE 0-10: how sure you are of every single digit. 0-3 digits not readable, 5-6 some doubt, \
7-8 typical clear frame, 9-10 every digit unmistakable. A last wheel between two numbers is not a doubt."""


@dataclass(frozen=True)
class Reading:
    """Parsed output of one frame."""

    digits: str  # as returned, cleaned of separators and spaces
    value: float | None  # lowest value consistent with the frame; None when it gave no usable number
    confidence: int
    problem: Problem | None
    tolerance: float = 0.0  # the meter may really be up to this much above ``value``
    rolling: bool = False  # the model saw the last wheel between two numbers
    dials: str | None = None  # dial digits as returned, None when the meter has no dials


def _score(value: Any) -> int:
    """Clamp a 0-10 score; anything non-numeric counts as 0."""
    try:
        number = round(float(value))
    except (TypeError, ValueError, OverflowError):
        return 0
    return max(0, min(10, number))


def _flag(value: Any) -> bool:
    """A boolean from the AI: some providers answer "true"/"false" as text."""
    if isinstance(value, str):
        return value.strip().lower() in ("true", "yes", "1")
    return bool(value)


def _clean(value: Any) -> str:
    return _SEPARATORS.sub("", str(value or "")).upper()


def parse_reading(data: Any, digits: int = 0, decimals: int = 0, dials: int = 0) -> Reading:
    """Validate the structured output of the AI. Raises ValueError if it is not an answer at all."""
    if not isinstance(data, dict) or "digits" not in data:
        raise ValueError("the AI response has no digits")
    raw = _clean(data.get("digits"))
    confidence = _score(data.get("confidence"))
    rolling = _flag(data.get("last_wheel_rolling"))
    dials_raw = _clean(data.get("dials")) if dials else None

    def failed(problem: Problem) -> Reading:
        return Reading(raw, None, confidence, problem, rolling=rolling, dials=dials_raw)

    # Only the last wheel unreadable: it is the one that turns all the time. The
    # other wheels still bound the value from below (last digit taken as 0, the
    # true value at most ten steps higher), which is never above the meter.
    last_unknown = len(raw) >= 2 and raw[:-1].isdigit() and raw[-1] == UNREADABLE_MARK
    wheels = raw[:-1] + "0" if last_unknown else raw
    if not wheels or not wheels.isdigit() or confidence < MIN_CONFIDENCE:
        # Any other X, a stray letter or a low confidence: nothing in this frame is trusted.
        return failed(Problem.UNREADABLE)
    if digits and len(wheels) > digits:
        return failed(Problem.WRONG_DIGITS)

    # Fewer digits than expected are dropped leading zeros: harmless. A dropped
    # inner digit gives a far smaller number, which the validator rejects.
    step = 10.0**-decimals
    value = int(wheels) * step
    tolerance = step * (10 if last_unknown else 1)
    precision = decimals
    if dials_raw is not None and not last_unknown and len(dials_raw) == dials and dials_raw.isdigit():
        precision = decimals + dials
        tolerance = 10.0**-precision
        value += int(dials_raw) * tolerance
        # The last wheel turns while the first dial passes from 9 to 0. Rolling
        # with that dial just past 0 means the wheel is finishing its turn: the
        # lower number the model wrote is one step behind the dial.
        if rolling and int(dials_raw[0]) <= ROLLOVER_DIAL_MAX:
            value += step
    shown = wheels.zfill(digits) if digits else wheels
    if last_unknown:
        shown = shown[:-1] + UNREADABLE_MARK
    return Reading(shown, round(value, precision), confidence, None, round(tolerance, precision), rolling, dials_raw)
