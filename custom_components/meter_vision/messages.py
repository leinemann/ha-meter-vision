# SPDX-License-Identifier: GPL-3.0-or-later
"""Notification texts, in the language of Home Assistant (English fallback).

Placeholders: {name} meter name, {count} consecutive failed readings,
{reason} why the last reading failed (one of ``REASONS``), {value} the last
accepted reading with its unit.
"""

from __future__ import annotations

from typing import Final

MESSAGES: Final[dict[str, dict[str, tuple[str, str]]]] = {
    "en": {
        "failing": (
            "⚠️ {name}: the meter cannot be read",
            "The last {count} readings failed ({reason}). The reading stays at {value} until a valid one arrives: "
            "check the camera, the light and the AI Task entity.",
        ),
    },
    "it": {
        "failing": (
            "⚠️ {name}: impossibile leggere il contatore",
            "Le ultime {count} letture non sono andate a buon fine ({reason}). La lettura resta a {value} finché "
            "non ne arriva una valida: controlla la telecamera, la luce e l'entità AI Task.",
        ),
    },
}

REASONS: Final[dict[str, dict[str, str]]] = {
    "en": {
        "decrease": "lower than the last reading",
        "implausible": "far higher than the last reading",
        "unreadable": "digits not readable",
        "wrong_digits": "too many digits",
        "error": "camera or AI not responding",
    },
    "it": {
        "decrease": "inferiore all'ultima lettura",
        "implausible": "molto superiore all'ultima lettura",
        "unreadable": "cifre non leggibili",
        "wrong_digits": "troppe cifre",
        "error": "telecamera o AI non rispondono",
    },
}

NO_VALUE: Final = {"en": "no value", "it": "nessun valore"}


def _table(language: str) -> str:
    code = language.split("-")[0].lower()
    return code if code in MESSAGES else "en"


def message(language: str, key: str, **values: object) -> tuple[str, str]:
    """Title and body of a notification."""
    title, body = MESSAGES[_table(language)][key]
    return title.format(**values), body.format(**values)


def reason(language: str, outcome: str) -> str:
    """Short description of a failed reading."""
    return REASONS[_table(language)].get(outcome, outcome)


def no_value(language: str) -> str:
    """Placeholder when there is no accepted reading yet."""
    return NO_VALUE[_table(language)]
