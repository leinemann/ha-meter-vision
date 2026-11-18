"""Tests for the config and options flows."""

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.meter_vision.const import DOMAIN

METER = {
    "unit_of_measurement": "m³",
    "camera_entity": "camera.meter",
    "ai_task_entity": "ai_task.vision",
    "digits": 8.0,
    "decimal_places": 3.0,
}


async def test_user_flow(hass: HomeAssistant) -> None:
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"meter_type": "gas"})
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "meter"
    assert result["description_placeholders"] == {"name": "Gas meter"}

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {**METER, "initial_reading": 1234.5})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Gas meter"
    assert result["data"]["digits"] == 8
    assert result["data"]["meter_type"] == "gas"
    await hass.async_block_till_done()
    state = hass.states.get("sensor.gas_meter_reading")
    assert state.state == "1234.5"
    assert state.attributes["device_class"] == "gas"


async def test_user_flow_errors(hass: HomeAssistant) -> None:
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"meter_type": "water", "name": "Tap"})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**METER, "unit_of_measurement": "L", "digits": 3.0}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"decimal_places": "too_many_decimals"}


async def test_options_flow(hass: HomeAssistant) -> None:
    data = {**METER, "meter_type": "water", "digits": 8, "decimal_places": 3}
    entry = MockConfigEntry(domain=DOMAIN, title="Water meter", data=data)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    options = {
        "camera_entity": "camera.meter",
        "ai_task_entity": "ai_task.vision",
        "digits": 7.0,
        "decimal_places": 0.0,
        "read_interval": 30.0,
        "light_warmup": 25.0,
        "notify_services": [],
        "persistent_notification": False,
    }
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {**options, "fallback_ai_task_entity": "ai_task.vision"}
    )
    assert result["errors"] == {"fallback_ai_task_entity": "same_ai_task"}
    result = await hass.config_entries.options.async_configure(result["flow_id"], options)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    monitor = entry.runtime_data
    assert monitor.digits == 7
    assert monitor.interval.total_seconds() == 1800
    assert monitor.light_entity is None
    assert monitor.config["meter_notes"] == ""
