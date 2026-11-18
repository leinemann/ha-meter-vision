# SPDX-License-Identifier: GPL-3.0-or-later
"""Switch for the automatic readings."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import MeterReaderConfigEntry
from .entity import MeterReaderEntity

AUTOMATIC_READING = SwitchEntityDescription(key="automatic_reading", entity_category=EntityCategory.CONFIG)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MeterReaderConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the switch."""
    async_add_entities([AutomaticReadingSwitch(entry.runtime_data, AUTOMATIC_READING, "switch")])


class AutomaticReadingSwitch(MeterReaderEntity, SwitchEntity):
    """Periodic readings. The read now button works either way."""

    @property
    def is_on(self) -> bool:
        """Whether the meter is read at every interval."""
        return self.monitor.auto_read

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable the periodic readings."""
        self.monitor.set_auto_read(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable the periodic readings."""
        self.monitor.set_auto_read(False)
