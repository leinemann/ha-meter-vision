# SPDX-License-Identifier: GPL-3.0-or-later
"""Diagnostics support for Meter Vision."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from . import MeterReaderConfigEntry
from .const import CONF_NOTIFY_SERVICES


async def async_get_config_entry_diagnostics(hass: HomeAssistant, entry: MeterReaderConfigEntry) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    return {
        "config": async_redact_data({**entry.data, **entry.options}, {CONF_NOTIFY_SERVICES}),
        "monitor": entry.runtime_data.diagnostics(),
    }
