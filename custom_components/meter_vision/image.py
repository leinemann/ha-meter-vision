# SPDX-License-Identifier: GPL-3.0-or-later
"""The last frame sent to the AI: what the reading is based on."""

from __future__ import annotations

from datetime import datetime

from homeassistant.components.image import ImageEntity, ImageEntityDescription
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import MeterReaderConfigEntry
from .entity import MeterReaderEntity
from .monitor import MeterMonitor

LAST_FRAME = ImageEntityDescription(key="last_frame")


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MeterReaderConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the image entity."""
    async_add_entities([LastFrameImage(hass, entry.runtime_data)])


class LastFrameImage(MeterReaderEntity, ImageEntity):
    """The frame of the last reading attempt, served from memory."""

    _attr_content_type = "image/jpeg"

    def __init__(self, hass: HomeAssistant, monitor: MeterMonitor) -> None:
        """Initialise both parents."""
        MeterReaderEntity.__init__(self, monitor, LAST_FRAME, "image")
        ImageEntity.__init__(self, hass)

    @property
    def image_last_updated(self) -> datetime | None:  # type: ignore[override]
        """Time of the last frame: it is also the state."""
        return self.monitor.frame_at

    @callback
    def _on_update(self) -> None:
        """Rotate the access token when the frame changes, so browsers fetch the new one."""
        if self.monitor.frame_at != getattr(self, "_frame_at", None):
            self._frame_at = self.monitor.frame_at
            self.async_update_token()
        super()._on_update()

    async def async_image(self) -> bytes | None:
        """The bytes of the last frame."""
        return self.monitor.frame
