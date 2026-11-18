# SPDX-License-Identifier: GPL-3.0-or-later
"""Maximum increase per reading, adjustable from the dashboard."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberEntityDescription, NumberMode
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import MeterReaderConfigEntry
from .entity import MeterReaderEntity
from .monitor import MeterMonitor

MAX_INCREASE = NumberEntityDescription(
    key="max_increase",
    entity_category=EntityCategory.CONFIG,
    mode=NumberMode.BOX,
    native_min_value=0,
    native_max_value=1_000_000,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MeterReaderConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the number entity."""
    async_add_entities([MaxIncreaseNumber(entry.runtime_data, MAX_INCREASE, "number")])


class MaxIncreaseNumber(MeterReaderEntity, NumberEntity):
    """Largest growth accepted between two readings one interval apart; more needs confirmation."""

    def __init__(self, monitor: MeterMonitor, description: NumberEntityDescription, platform: str) -> None:
        """Use the unit of the meter and a step as fine as its last digit."""
        super().__init__(monitor, description, platform)
        self._attr_native_unit_of_measurement = monitor.unit
        self._attr_native_step = 10.0**-monitor.precision if monitor.precision else 1.0

    @property
    def native_value(self) -> float:
        """Current value."""
        return self.monitor.max_increase

    async def async_set_native_value(self, value: float) -> None:
        """Store a new value."""
        self.monitor.set_max_increase(value)
