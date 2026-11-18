# SPDX-License-Identifier: GPL-3.0-or-later
"""Meter Vision: reads water, gas and energy meters with a camera and an AI Task entity."""

from __future__ import annotations

from pathlib import Path

from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, service
from homeassistant.helpers.typing import ConfigType
from homeassistant.loader import async_get_integration
import voluptuous as vol

from .const import ATTR_VALUE, CARD_FILENAME, CARD_URL, DOMAIN, SERVICE_SET_READING
from .monitor import MeterMonitor

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.IMAGE,
    Platform.NUMBER,
    Platform.SENSOR,
    Platform.SWITCH,
]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

type MeterReaderConfigEntry = ConfigEntry[MeterMonitor]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Serve the bundled dashboard card, load it in every dashboard, register the actions.

    The version in ``manifest.json`` is the single source of truth: it is
    appended to the card URL, which busts the browser cache after an update
    and tells the card its own version.
    """
    version = str((await async_get_integration(hass, DOMAIN)).version)
    hass.data[DOMAIN] = version
    card = Path(__file__).parent / "frontend" / CARD_FILENAME
    await hass.http.async_register_static_paths([StaticPathConfig(CARD_URL, str(card), cache_headers=False)])
    add_extra_js_url(hass, f"{CARD_URL}?v={version}")

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_SET_READING,
        entity_domain=SENSOR_DOMAIN,
        schema={vol.Required(ATTR_VALUE): vol.All(vol.Coerce(float), vol.Range(min=0))},
        func="async_set_reading",
    )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: MeterReaderConfigEntry) -> bool:
    """Set up a meter from a config entry."""
    monitor = MeterMonitor(hass, entry, hass.data[DOMAIN])
    await monitor.async_load()
    entry.runtime_data = monitor

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    monitor.async_start()
    entry.async_on_unload(entry.add_update_listener(_async_reload))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: MeterReaderConfigEntry) -> bool:
    """Unload a config entry."""
    if unloaded := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        await entry.runtime_data.async_stop()
    return unloaded


async def _async_reload(hass: HomeAssistant, entry: MeterReaderConfigEntry) -> None:
    """Reload when the options change."""
    await hass.config_entries.async_reload(entry.entry_id)
