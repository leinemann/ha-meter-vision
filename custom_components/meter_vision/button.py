# SPDX-License-Identifier: GPL-3.0-or-later
"""Button that reads the meter now."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import MeterReaderConfigEntry
from .entity import MeterReaderEntity

READ_NOW = ButtonEntityDescription(key="read_now")


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MeterReaderConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the button."""
    async_add_entities([ReadNowButton(entry.runtime_data, READ_NOW, "button")])


class ReadNowButton(MeterReaderEntity, ButtonEntity):
    """Starts a reading of the meter."""

    async def async_press(self) -> None:
        """Read in the background (light warm-up and AI take up to a few minutes)."""
        self.monitor.async_request_reading()
