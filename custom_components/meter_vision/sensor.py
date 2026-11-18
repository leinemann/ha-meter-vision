# SPDX-License-Identifier: GPL-3.0-or-later
# Based on sensor.py of ha-ai-meter-reader v1.0.1 (https://github.com/artech-lab/ha-ai-meter-reader).
"""Sensors for Meter Vision."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import MeterReaderConfigEntry
from .const import MeterType
from .entity import MeterReaderEntity
from .monitor import MeterMonitor
from .validator import Outcome

DEVICE_CLASSES = {
    MeterType.WATER: SensorDeviceClass.WATER,
    MeterType.GAS: SensorDeviceClass.GAS,
    MeterType.ENERGY: SensorDeviceClass.ENERGY,
}


def _reading_attributes(monitor: MeterMonitor) -> dict[str, Any]:
    validator = monitor.validator
    return {
        "updated_at": validator.value_at.isoformat() if validator.value_at else None,
        "pending_value": validator.pending_value,
        "meter_type": monitor.meter_type.value,
        "digits": monitor.digits or None,
        "decimal_places": monitor.decimals,
        "pointer_dials": monitor.dials,
        # Used by the card to find the source entities without configuration.
        "camera_entity": monitor.camera_entity,
        "light_entity": monitor.light_entity,
    }


def _result_attributes(monitor: MeterMonitor) -> dict[str, Any]:
    last = monitor.last_reading
    return {
        "digits_read": last.digits if last else None,
        "dials_read": last.dials if last else None,
        "last_wheel_rolling": last.rolling if last else None,
        "consecutive_failures": monitor.failures,
        "ai_engine": monitor.last_engine,
        "last_error": monitor.last_error,
    }


@dataclass(frozen=True, kw_only=True)
class MeterSensorDescription(SensorEntityDescription):
    """Describes an Meter Vision sensor."""

    value_fn: Callable[[MeterMonitor], Any]
    attributes_fn: Callable[[MeterMonitor], dict[str, Any]] | None = None
    with_unit: bool = False  # takes the unit and device class of the meter


SENSORS: tuple[MeterSensorDescription, ...] = (
    MeterSensorDescription(
        key="reading",
        state_class=SensorStateClass.TOTAL,
        with_unit=True,
        value_fn=lambda m: m.value,
        attributes_fn=_reading_attributes,
    ),
    MeterSensorDescription(
        key="last_result",
        device_class=SensorDeviceClass.ENUM,
        options=[o.value for o in Outcome],
        value_fn=lambda m: m.outcome.value if m.outcome else None,
        attributes_fn=_result_attributes,
    ),
    MeterSensorDescription(
        key="confidence",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=lambda m: m.last_reading.confidence if m.last_reading else None,
    ),
    MeterSensorDescription(
        key="last_read",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda m: m.last_attempt,
    ),
    MeterSensorDescription(
        key="value_read",
        entity_category=EntityCategory.DIAGNOSTIC,
        with_unit=True,
        value_fn=lambda m: m.last_reading.value if m.last_reading else None,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MeterReaderConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the sensors."""
    async_add_entities(MeterSensor(entry.runtime_data, description, "sensor") for description in SENSORS)


class MeterSensor(MeterReaderEntity, SensorEntity):
    """An Meter Vision sensor."""

    entity_description: MeterSensorDescription

    def __init__(self, monitor: MeterMonitor, description: MeterSensorDescription, platform: str) -> None:
        """Take the unit and the device class of the meter where needed."""
        super().__init__(monitor, description, platform)
        if description.with_unit:
            self._attr_device_class = DEVICE_CLASSES[monitor.meter_type]
            self._attr_native_unit_of_measurement = monitor.unit
            self._attr_suggested_display_precision = monitor.precision

    @property
    def native_value(self) -> Any:
        """Current value."""
        return self.entity_description.value_fn(self.monitor)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Extra attributes of the reading and last result sensors."""
        fn = self.entity_description.attributes_fn
        return fn(self.monitor) if fn else None

    async def async_set_reading(self, value: float) -> None:
        """Set the reading by hand (``meter_vision.set_reading``), on any sensor of the meter."""
        self.monitor.set_reading(value)
