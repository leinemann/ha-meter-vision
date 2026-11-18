# SPDX-License-Identifier: GPL-3.0-or-later
# Based on image.py of ha-ai-meter-reader v1.0.1 (https://github.com/artech-lab/ha-ai-meter-reader).
# Modified for Meter Vision: the last frame is annotated, the clean frame is a second entity.
"""The frames of the last reading: annotated for the dashboard, and as sent to the AI."""

from __future__ import annotations

from datetime import datetime

from homeassistant.components.image import ImageEntity, ImageEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import MeterReaderConfigEntry
from .entity import MeterReaderEntity
from .monitor import MeterMonitor

LAST_FRAME = ImageEntityDescription(key="last_frame")
RAW_FRAME = ImageEntityDescription(key="raw_frame", entity_category=EntityCategory.DIAGNOSTIC)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MeterReaderConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the image entities."""
    monitor = entry.runtime_data
    async_add_entities([LastFrameImage(hass, monitor, LAST_FRAME), RawFrameImage(hass, monitor, RAW_FRAME)])


class RawFrameImage(MeterReaderEntity, ImageEntity):
    """The frame exactly as it was sent to the AI, served from memory."""

    _attr_content_type = "image/jpeg"

    def __init__(self, hass: HomeAssistant, monitor: MeterMonitor, description: ImageEntityDescription) -> None:
        """Initialise both parents."""
        MeterReaderEntity.__init__(self, monitor, description, "image")
        ImageEntity.__init__(self, hass)
        self._shown: tuple[datetime | None, ...] | None = None

    @property
    def image_last_updated(self) -> datetime | None:  # type: ignore[override]
        """Time of the frame: it is also the state."""
        return self.monitor.frame_at

    @property
    def _version(self) -> tuple[datetime | None, ...]:
        """Changes whenever the bytes served change."""
        return (self.monitor.frame_at,)

    @callback
    def _on_update(self) -> None:
        """Rotate the access token when the image changes, so browsers fetch the new one."""
        if self._version != self._shown:
            self._shown = self._version
            self.async_update_token()
            self._written = None  # the picture URL changed: write it even if the state didn't
        super()._on_update()

    async def async_image(self) -> bytes | None:
        """The bytes of the frame."""
        return self.monitor.frame


class LastFrameImage(RawFrameImage):
    """The frame with the counter region, the digits read and the outcome drawn on it.

    Falls back to the clean frame when nothing could be drawn (no reading yet,
    a frame Pillow can't open).
    """

    @property
    def image_last_updated(self) -> datetime | None:  # type: ignore[override]
        """Time it was drawn, or of the frame when shown as it is."""
        return self.monitor.annotated_at or self.monitor.frame_at

    @property
    def _version(self) -> tuple[datetime | None, ...]:
        """A new frame, then its drawing a moment later: both are a new image."""
        return (self.monitor.frame_at, self.monitor.annotated_at)

    async def async_image(self) -> bytes | None:
        """The annotated frame, else the clean one."""
        return self.monitor.annotated or self.monitor.frame
