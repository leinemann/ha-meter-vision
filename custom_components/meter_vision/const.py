# SPDX-License-Identifier: GPL-3.0-or-later
# Based on const.py of ha-ai-meter-reader v1.0.1 (https://github.com/artech-lab/ha-ai-meter-reader).
"""Constants for the Meter Vision integration."""

from __future__ import annotations

from datetime import timedelta
from enum import StrEnum
from typing import Final

from homeassistant.const import UnitOfEnergy, UnitOfVolume

DOMAIN: Final = "meter_vision"
DEFAULT_NAME: Final = "Water meter"

# Bundled dashboard card
CARD_FILENAME: Final = "meter-vision-card.js"
CARD_URL: Final = f"/{DOMAIN}/{CARD_FILENAME}"


class MeterType(StrEnum):
    """What the meter measures."""

    WATER = "water"
    GAS = "gas"
    ENERGY = "energy"


# Units offered for each meter type (the first one is the default) and the
# default "maximum increase per reading" of each unit: about a household peak
# over a 15-minute interval, generous enough for real use and tight enough to
# stop a misread digit.
UNITS: Final[dict[MeterType, dict[str, float]]] = {
    MeterType.WATER: {
        UnitOfVolume.LITERS: 300,
        UnitOfVolume.CUBIC_METERS: 0.3,
        UnitOfVolume.GALLONS: 80,
        UnitOfVolume.CUBIC_FEET: 10,
        UnitOfVolume.CENTUM_CUBIC_FEET: 0.1,
    },
    MeterType.GAS: {
        UnitOfVolume.CUBIC_METERS: 1,
        UnitOfVolume.CUBIC_FEET: 35,
        UnitOfVolume.CENTUM_CUBIC_FEET: 0.35,
    },
    MeterType.ENERGY: {
        UnitOfEnergy.KILO_WATT_HOUR: 5,
        UnitOfEnergy.WATT_HOUR: 5000,
        UnitOfEnergy.MEGA_WATT_HOUR: 0.005,
        UnitOfEnergy.GIGA_JOULE: 0.02,
    },
}

# Config entry keys (setup, fixed: they define the statistics of the reading)
CONF_METER_TYPE: Final = "meter_type"
CONF_UNIT: Final = "unit_of_measurement"
CONF_INITIAL_READING: Final = "initial_reading"
# Config entry keys (setup and options)
CONF_CAMERA: Final = "camera_entity"
CONF_LIGHT: Final = "light_entity"
CONF_AI_TASK: Final = "ai_task_entity"
CONF_AI_TASK_FALLBACK: Final = "fallback_ai_task_entity"
CONF_DIGITS: Final = "digits"
CONF_DECIMALS: Final = "decimal_places"
CONF_DIALS: Final = "pointer_dials"
CONF_READ_INTERVAL: Final = "read_interval"
CONF_LIGHT_WARMUP: Final = "light_warmup"
CONF_METER_NOTES: Final = "meter_notes"
CONF_NOTIFY_SERVICES: Final = "notify_services"
CONF_PERSISTENT_NOTIFICATION: Final = "persistent_notification"

DEFAULT_DIGITS: Final = 0  # 0 = do not check how many digits were read
DEFAULT_DECIMALS: Final = 0
DEFAULT_DIALS: Final = 0
DEFAULT_READ_INTERVAL: Final = 15  # minutes
# Small cameras with automatic exposure (ESP32-CAM and similar) need tens of
# seconds to adapt after the light turns on: with less the frame comes out black.
DEFAULT_LIGHT_WARMUP: Final = 30  # seconds
MAX_DIGITS: Final = 12
MAX_DECIMALS: Final = 3
# Small pointer dials after the decimal wheels (x0.0001, x0.001, ...), each one more decimal.
MAX_DIALS: Final = 4
# The last wheel turns while the first dial passes 9 → 0: a rolling wheel with that
# dial at this digit or below may already be on the higher number (the range is widened).
ROLLOVER_DIAL_MAX: Final = 2

# ------------------------------------------------------------ plausibility
# A reading that grows by more than the maximum increase (scaled by the time
# since the last accepted value) is held back and accepted only when the next
# readings confirm it: one misread digit never reaches the statistics, while a
# real jump (after a long camera outage, for example) is taken after a short delay.
CONFIRMATIONS: Final = 2
# A jump larger than the maximum increase sustained for this long (or since the
# last accepted value, if longer) is never confirmed: it needs set_reading.
MAX_JUMP_SPAN: Final = timedelta(days=1)
# Consecutive failed readings (unreadable, rejected, error) that raise a problem.
FAILURES_FOR_PROBLEM: Final = 3

# ------------------------------------------------------------- AI reading
MIN_CONFIDENCE: Final = 4  # below it the digits are not trusted
MAX_ATTEMPTS: Final = 2  # an unreadable frame is retried once
RETRY_DELAY_S: Final = 20
AI_TIMEOUT_S: Final = 180
SNAPSHOT_TIMEOUT_S: Final = 15
MEDIA_SUBDIR: Final = DOMAIN

STORAGE_VERSION: Final = 1

SERVICE_SET_READING: Final = "set_reading"
ATTR_VALUE: Final = "value"
