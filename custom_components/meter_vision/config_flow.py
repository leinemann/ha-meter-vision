# SPDX-License-Identifier: GPL-3.0-or-later
# Based on config_flow.py of ha-ai-meter-reader v1.0.1 (https://github.com/artech-lab/ha-ai-meter-reader).
# Modified for Meter Vision: pointer dials.
"""Config and options flow for Meter Vision."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import selector
import voluptuous as vol

from .const import (
    CONF_AI_TASK,
    CONF_AI_TASK_FALLBACK,
    CONF_CAMERA,
    CONF_DECIMALS,
    CONF_DIALS,
    CONF_DIGITS,
    CONF_INITIAL_READING,
    CONF_LIGHT,
    CONF_LIGHT_WARMUP,
    CONF_METER_NOTES,
    CONF_METER_TYPE,
    CONF_NOTIFY_SERVICES,
    CONF_PERSISTENT_NOTIFICATION,
    CONF_READ_INTERVAL,
    CONF_UNIT,
    DEFAULT_DECIMALS,
    DEFAULT_DIALS,
    DEFAULT_DIGITS,
    DEFAULT_LIGHT_WARMUP,
    DEFAULT_NAME,
    DEFAULT_READ_INTERVAL,
    DOMAIN,
    MAX_DECIMALS,
    MAX_DIALS,
    MAX_DIGITS,
    UNITS,
    MeterType,
)

DEFAULT_NAMES = {MeterType.WATER: DEFAULT_NAME, MeterType.GAS: "Gas meter", MeterType.ENERGY: "Energy meter"}


def _entity(domain: str) -> selector.EntitySelector:
    return selector.EntitySelector(selector.EntitySelectorConfig(domain=domain))


def _box(minimum: float, maximum: float, unit: str | None = None) -> selector.NumberSelector:
    config = selector.NumberSelectorConfig(min=minimum, max=maximum, step=1, mode=selector.NumberSelectorMode.BOX)
    if unit:
        config["unit_of_measurement"] = unit
    return selector.NumberSelector(config)


def _suggested(current: dict[str, Any], key: str) -> dict[str, Any]:
    return {"suggested_value": current.get(key)}


def _sources(current: dict[str, Any], fallback: bool) -> dict[Any, Any]:
    """Fields shared by the setup and the options form."""
    fields: dict[Any, Any] = {
        vol.Required(CONF_CAMERA, default=current.get(CONF_CAMERA, vol.UNDEFINED)): _entity("camera"),
        vol.Optional(CONF_LIGHT, description=_suggested(current, CONF_LIGHT)): _entity("light"),
        vol.Required(CONF_AI_TASK, default=current.get(CONF_AI_TASK, vol.UNDEFINED)): _entity("ai_task"),
    }
    if fallback:
        fields[vol.Optional(CONF_AI_TASK_FALLBACK, description=_suggested(current, CONF_AI_TASK_FALLBACK))] = _entity(
            "ai_task"
        )
    fields[vol.Required(CONF_DIGITS, default=current.get(CONF_DIGITS, DEFAULT_DIGITS))] = _box(0, MAX_DIGITS)
    fields[vol.Required(CONF_DECIMALS, default=current.get(CONF_DECIMALS, DEFAULT_DECIMALS))] = _box(0, MAX_DECIMALS)
    fields[vol.Required(CONF_DIALS, default=current.get(CONF_DIALS, DEFAULT_DIALS))] = _box(0, MAX_DIALS)
    return fields


def _validate(user_input: dict[str, Any]) -> dict[str, str]:
    errors: dict[str, str] = {}
    digits, decimals = int(user_input.get(CONF_DIGITS) or 0), int(user_input.get(CONF_DECIMALS) or 0)
    if digits and decimals >= digits:
        errors[CONF_DECIMALS] = "too_many_decimals"
    if user_input.get(CONF_AI_TASK) and user_input.get(CONF_AI_TASK) == user_input.get(CONF_AI_TASK_FALLBACK):
        errors[CONF_AI_TASK_FALLBACK] = "same_ai_task"
    return errors


def _integers(user_input: dict[str, Any]) -> dict[str, Any]:
    """Number selectors return floats: store counts as integers."""
    for key in (CONF_DIGITS, CONF_DECIMALS, CONF_DIALS, CONF_READ_INTERVAL, CONF_LIGHT_WARMUP):
        if user_input.get(key) is not None:
            user_input[key] = int(user_input[key])
    return user_input


def _notify_services(hass: HomeAssistant) -> list[str]:
    services = hass.services.async_services_for_domain("notify")
    return sorted(f"notify.{name}" for name in services if name not in ("send_message", "persistent_notification"))


class MeterReaderConfigFlow(ConfigFlow, domain=DOMAIN):
    """Initial setup: what the meter measures, then camera, light and AI Task entity."""

    VERSION = 1

    def __init__(self) -> None:
        """Start an empty flow."""
        self._meter_type = MeterType.WATER
        self._name = DEFAULT_NAME

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Name and type of meter."""
        if user_input is not None:
            self._meter_type = MeterType(user_input[CONF_METER_TYPE])
            self._name = user_input.get(CONF_NAME) or DEFAULT_NAMES[self._meter_type]
            return await self.async_step_meter()
        schema = vol.Schema(
            {
                vol.Required(CONF_METER_TYPE, default=MeterType.WATER.value): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[t.value for t in MeterType],
                        translation_key=CONF_METER_TYPE,
                        mode=selector.SelectSelectorMode.LIST,
                    )
                ),
                vol.Optional(CONF_NAME): selector.TextSelector(),
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema)

    async def async_step_meter(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Unit, sources and counter format."""
        errors: dict[str, str] = {}
        if user_input is not None and not (errors := _validate(user_input)):
            data = {CONF_METER_TYPE: self._meter_type.value, **_integers(user_input)}
            return self.async_create_entry(title=self._name, data=data)

        current = user_input or {}
        units = [str(unit) for unit in UNITS[self._meter_type]]
        schema = vol.Schema(
            {
                vol.Required(CONF_UNIT, default=current.get(CONF_UNIT, units[0])): selector.SelectSelector(
                    selector.SelectSelectorConfig(options=units, mode=selector.SelectSelectorMode.DROPDOWN)
                ),
                **_sources(current, fallback=False),
                vol.Optional(CONF_INITIAL_READING, description=_suggested(current, CONF_INITIAL_READING)): (
                    selector.NumberSelector(
                        selector.NumberSelectorConfig(min=0, step="any", mode=selector.NumberSelectorMode.BOX)
                    )
                ),
            }
        )
        return self.async_show_form(
            step_id="meter", data_schema=schema, errors=errors, description_placeholders={"name": self._name}
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> MeterReaderOptionsFlow:
        """Return the options flow."""
        return MeterReaderOptionsFlow()


class MeterReaderOptionsFlow(OptionsFlow):
    """Change the sources, the counter format, the timing and the notifications."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Single options form."""
        errors: dict[str, str] = {}
        if user_input is not None and not (errors := _validate(user_input)):
            # An optional entity removed in the form must be cleared explicitly.
            for key in (CONF_LIGHT, CONF_AI_TASK_FALLBACK):
                user_input.setdefault(key, None)
            user_input.setdefault(CONF_METER_NOTES, "")
            return self.async_create_entry(data=_integers(user_input))

        current = {**self.config_entry.data, **self.config_entry.options, **(user_input or {})}
        schema = vol.Schema(
            {
                **_sources(current, fallback=True),
                vol.Required(CONF_READ_INTERVAL, default=current.get(CONF_READ_INTERVAL, DEFAULT_READ_INTERVAL)): _box(
                    1, 1440, "min"
                ),
                vol.Required(CONF_LIGHT_WARMUP, default=current.get(CONF_LIGHT_WARMUP, DEFAULT_LIGHT_WARMUP)): _box(
                    0, 120, "s"
                ),
                vol.Optional(CONF_METER_NOTES, description=_suggested(current, CONF_METER_NOTES)): (
                    selector.TextSelector(selector.TextSelectorConfig(multiline=True))
                ),
                vol.Optional(
                    CONF_NOTIFY_SERVICES, default=current.get(CONF_NOTIFY_SERVICES, [])
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(options=_notify_services(self.hass), multiple=True, custom_value=True)
                ),
                vol.Required(
                    CONF_PERSISTENT_NOTIFICATION, default=current.get(CONF_PERSISTENT_NOTIFICATION, True)
                ): selector.BooleanSelector(),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema, errors=errors)
