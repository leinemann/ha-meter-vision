# SPDX-License-Identifier: GPL-3.0-or-later
"""Binary sensors for Meter Vision."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import MeterReaderConfigEntry
from .entity import MeterReaderEntity
from .monitor import MeterMonitor


@dataclass(frozen=True, kw_only=True)
class MeterBinarySensorDescription(BinarySensorEntityDescription):
    """Describes an Meter Vision binary sensor."""

    is_on_fn: Callable[[MeterMonitor], bool | None]


BINARY_SENSORS: tuple[MeterBinarySensorDescription, ...] = (
    MeterBinarySensorDescription(
        key="problem",
        device_class=BinarySensorDeviceClass.PROBLEM,
        is_on_fn=lambda m: m.problem,
    ),
    MeterBinarySensorDescription(
        key="reading_in_progress",
        device_class=BinarySensorDeviceClass.RUNNING,
        is_on_fn=lambda m: m.reading,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MeterReaderConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the binary sensors."""
    async_add_entities(
        MeterBinarySensor(entry.runtime_data, description, "binary_sensor") for description in BINARY_SENSORS
    )


class MeterBinarySensor(MeterReaderEntity, BinarySensorEntity):
    """An Meter Vision binary sensor."""

    entity_description: MeterBinarySensorDescription

    @property
    def is_on(self) -> bool | None:
        """Current value."""
        return self.entity_description.is_on_fn(self.monitor)
