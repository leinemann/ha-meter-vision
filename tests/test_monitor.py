"""End-to-end tests on a real Home Assistant core: frames in, readings and alerts out."""

from collections.abc import Callable
from datetime import timedelta
from typing import Any
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
from homeassistant.components.camera import Image
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.exceptions import HomeAssistantError
import pytest
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
    async_mock_service,
)

from custom_components.meter_vision.const import DOMAIN

DATA = {
    "meter_type": "water",
    "unit_of_measurement": "L",
    "camera_entity": "camera.meter",
    "light_entity": "light.meter_flash",
    "ai_task_entity": "ai_task.vision",
    "digits": 8,
    "decimal_places": 0,
    "initial_reading": 1250922,
}
OPTIONS = {
    **{k: v for k, v in DATA.items() if k not in ("meter_type", "unit_of_measurement", "initial_reading")},
    "read_interval": 15,
    "light_warmup": 0,
    "notify_services": ["notify.phone"],
}
READING = "sensor.water_meter_reading"
RESULT = "sensor.water_meter_last_result"


def answer(digits: str, confidence: int = 8) -> dict[str, Any]:
    return {"digits": digits, "confidence": confidence}


class FakeAI:
    """Stands in for ai_task.generate_data; answers from a queue (the last answer repeats)."""

    def __init__(self, hass: HomeAssistant, answers: list[Any]) -> None:
        self.answers = answers
        self.calls: list[dict[str, Any]] = []
        hass.services.async_register("ai_task", "generate_data", self._handle, supports_response=SupportsResponse.ONLY)

    async def _handle(self, call: ServiceCall) -> dict[str, Any]:
        self.calls.append(dict(call.data))
        item = self.answers.pop(0) if len(self.answers) > 1 else self.answers[0]
        if isinstance(item, Exception):
            raise item
        if isinstance(item, Callable):
            item = item(call)
        return {"conversation_id": "x", "data": item}


@pytest.fixture(autouse=True)
def _fast():
    """No waits between retries, a fake camera frame."""
    image = Image("image/jpeg", b"\xff\xd8 fake jpeg")
    with (
        patch("custom_components.meter_vision.monitor.RETRY_DELAY_S", 0),
        patch("custom_components.meter_vision.monitor.camera.async_get_image", return_value=image) as grab,
    ):
        yield grab


async def _setup(
    hass: HomeAssistant, tmp_path, data: dict[str, Any] | None = None, options: dict[str, Any] | None = None
) -> MockConfigEntry:
    hass.config.media_dirs = {"local": str(tmp_path)}
    hass.config.language = "en"
    hass.states.async_set("camera.meter", "idle")
    hass.states.async_set("light.meter_flash", "off")
    for action in ("turn_on", "turn_off"):
        if not hass.services.has_service("light", action):
            async_mock_service(hass, "light", action)
    entry = MockConfigEntry(domain=DOMAIN, title="Water meter", data=data or DATA, options=options or OPTIONS)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def _advance(hass: HomeAssistant, freezer: FrozenDateTimeFactory, minutes: float) -> None:
    """Move the clock in one-minute steps so every timer fires in order."""
    await hass.async_block_till_done()
    for _ in range(int(minutes)):
        freezer.tick(timedelta(minutes=1))
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)


def _state(hass: HomeAssistant, entity_id: str) -> str:
    return hass.states.get(entity_id).state


async def test_periodic_readings(hass: HomeAssistant, freezer: FrozenDateTimeFactory, tmp_path) -> None:
    ai = FakeAI(hass, [answer("01250950"), answer("01251100")])
    light = async_mock_service(hass, "light", "turn_on")
    async_mock_service(hass, "light", "turn_off")
    await _setup(hass, tmp_path)

    state = hass.states.get(READING)
    assert state.state == "1250922.0"
    assert state.attributes["unit_of_measurement"] == "L"
    assert state.attributes["device_class"] == "water"
    assert state.attributes["state_class"] == "total_increasing"
    assert state.attributes["camera_entity"] == "camera.meter"

    await _advance(hass, freezer, 1)  # first reading 30 s after start-up
    assert len(ai.calls) == 1
    assert len(light) == 1
    assert ai.calls[0]["attachments"][0]["media_content_id"] == (
        "media-source://media_source/local/meter_vision/water_meter.jpg"
    )
    assert "exactly 8 wheels" in ai.calls[0]["instructions"]
    assert (tmp_path / "meter_vision" / "water_meter.jpg").read_bytes().startswith(b"\xff\xd8")
    assert _state(hass, READING) == "1250950.0"
    assert _state(hass, RESULT) == "accepted"
    assert _state(hass, "sensor.water_meter_confidence") == "8"
    assert _state(hass, "image.water_meter_last_frame") != "unknown"

    await _advance(hass, freezer, 15)
    assert len(ai.calls) == 2
    assert _state(hass, READING) == "1251100.0"


async def test_misreads_never_reach_the_reading(hass: HomeAssistant, freezer: FrozenDateTimeFactory, tmp_path) -> None:
    FakeAI(hass, [answer("01950922"), answer("01250000"), answer("012509X2"), answer("012509X2"), answer("01250960")])
    await _setup(hass, tmp_path, options={**OPTIONS, "light_entity": None})
    await _advance(hass, freezer, 1)
    assert _state(hass, RESULT) == "implausible"
    assert hass.states.get(READING).attributes["pending_value"] is None
    await _advance(hass, freezer, 15)
    assert _state(hass, RESULT) == "decrease"
    await _advance(hass, freezer, 15)
    assert _state(hass, RESULT) == "unreadable"  # retried once, still unreadable
    assert hass.states.get(RESULT).attributes["digits_read"] == "012509X2"
    assert _state(hass, READING) == "1250922.0"
    await _advance(hass, freezer, 15)
    assert _state(hass, RESULT) == "accepted"
    assert _state(hass, READING) == "1250960.0"


async def test_repeated_failures_raise_a_problem(hass: HomeAssistant, freezer: FrozenDateTimeFactory, tmp_path) -> None:
    offline = HomeAssistantError("model offline")
    FakeAI(hass, [offline, offline, offline, answer("01250930")])
    notify = async_mock_service(hass, "notify", "phone")
    await _setup(hass, tmp_path, options={**OPTIONS, "light_entity": None})
    await _advance(hass, freezer, 1 + 15 + 15)
    assert _state(hass, RESULT) == "error"
    assert hass.states.get(RESULT).attributes["last_error"].endswith("model offline")
    assert hass.states.get(RESULT).attributes["consecutive_failures"] == 3
    assert _state(hass, "binary_sensor.water_meter_problem") == "on"
    assert notify[-1].data["title"] == "⚠️ Water meter: the meter cannot be read"
    assert "stays at 1250922 L" in notify[-1].data["message"]

    await _advance(hass, freezer, 15)
    assert _state(hass, "binary_sensor.water_meter_problem") == "off"
    assert _state(hass, READING) == "1250930.0"


async def test_without_initial_reading(hass: HomeAssistant, freezer: FrozenDateTimeFactory, tmp_path) -> None:
    FakeAI(hass, [answer("00012345"), answer("00012346")])
    data = {k: v for k, v in DATA.items() if k != "initial_reading"}
    await _setup(hass, tmp_path, data=data)
    assert _state(hass, READING) == "unknown"
    await _advance(hass, freezer, 1)
    assert _state(hass, RESULT) == "unconfirmed"
    await _advance(hass, freezer, 15)
    assert _state(hass, READING) == "12346.0"


async def test_decimals_and_fallback(hass: HomeAssistant, freezer: FrozenDateTimeFactory, tmp_path) -> None:
    def by_engine(call: ServiceCall) -> dict[str, Any]:
        if call.data["entity_id"] == "ai_task.vision":
            raise HomeAssistantError("timeout")
        return answer("01250950")

    ai = FakeAI(hass, [by_engine])
    data = {**DATA, "unit_of_measurement": "m³", "decimal_places": 3, "initial_reading": 1250.922}
    options = {**OPTIONS, "decimal_places": 3, "fallback_ai_task_entity": "ai_task.cloud"}
    await _setup(hass, tmp_path, data=data, options=options)
    assert hass.states.get("number.water_meter_max_increase").state == "0.3"
    await _advance(hass, freezer, 1)
    assert [c["entity_id"] for c in ai.calls] == ["ai_task.vision", "ai_task.cloud"]
    assert _state(hass, READING) == "1250.95"
    assert hass.states.get(RESULT).attributes["ai_engine"] == "ai_task.cloud"


async def test_controls(hass: HomeAssistant, freezer: FrozenDateTimeFactory, tmp_path) -> None:
    ai = FakeAI(hass, [answer("01251000")])
    await _setup(hass, tmp_path, options={**OPTIONS, "light_entity": None})
    await hass.services.async_call(
        "switch", "turn_off", {"entity_id": "switch.water_meter_automatic_reading"}, blocking=True
    )
    await _advance(hass, freezer, 31)
    assert ai.calls == []

    await hass.services.async_call("button", "press", {"entity_id": "button.water_meter_read_now"}, blocking=True)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert len(ai.calls) == 1
    assert _state(hass, READING) == "1251000.0"

    await hass.services.async_call(DOMAIN, "set_reading", {"entity_id": READING, "value": 1260000}, blocking=True)
    assert _state(hass, READING) == "1260000.0"
    assert _state(hass, RESULT) == "corrected"

    await hass.services.async_call(
        "number", "set_value", {"entity_id": "number.water_meter_max_increase", "value": 50}, blocking=True
    )
    assert hass.states.get("number.water_meter_max_increase").state == "50.0"


async def test_state_survives_a_restart(hass: HomeAssistant, freezer: FrozenDateTimeFactory, tmp_path) -> None:
    FakeAI(hass, [answer("01250990")])
    entry = await _setup(hass, tmp_path)
    await _advance(hass, freezer, 1)
    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert _state(hass, READING) == "1250990.0"
    assert _state(hass, RESULT) == "accepted"
    assert entry.runtime_data.frame is not None


async def test_an_offline_camera_counts_as_a_failure(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, tmp_path
) -> None:
    ai = FakeAI(hass, [answer("01250930")])
    await _setup(hass, tmp_path)
    hass.states.async_set("camera.meter", "unavailable")
    await _advance(hass, freezer, 1 + 15 + 15)
    assert ai.calls == []
    assert _state(hass, RESULT) == "error"
    assert hass.states.get(RESULT).attributes["last_error"] == "camera.meter unavailable"
    assert _state(hass, "binary_sensor.water_meter_problem") == "on"


# ---------------------------------------------------------------- Meter Vision additions
FERRO_DATA = {
    **DATA,
    "unit_of_measurement": "m³",
    "digits": 8,
    "decimal_places": 3,
    "pointer_dials": 1,
    "initial_reading": 140.9251,
}
FERRO_OPTIONS = {**OPTIONS, "decimal_places": 3, "pointer_dials": 1, "light_entity": None}


def ferro(digits: str, dials: str, rolling: bool = False) -> dict[str, Any]:
    return {"digits": digits, "dials": dials, "last_wheel_rolling": rolling, "confidence": 8}


async def test_a_meter_with_a_pointer_dial(hass: HomeAssistant, freezer: FrozenDateTimeFactory, tmp_path) -> None:
    ai = FakeAI(
        hass,
        [
            ferro("00140925", "7"),
            ferro("00140925", "9", rolling=True),  # wheel turning, dial before 0: still 5
            ferro("00140926", "1"),
            ferro("00140925", "1", rolling=True),  # the lower number: within range of 140.9261, kept
            ferro("0014092X", "X"),  # last wheel unreadable: kept, not a failure
        ],
    )
    await _setup(hass, tmp_path, data=FERRO_DATA, options=FERRO_OPTIONS)
    assert _state(hass, READING) == "140.9251"
    assert hass.states.get(READING).attributes["pointer_dials"] == 1

    await _advance(hass, freezer, 1)
    call = ai.calls[0]
    assert "dials" in call["structure"]
    assert "(x0.0001)" in call["instructions"]
    assert _state(hass, READING) == "140.9257"
    for expected in ("140.9259", "140.9261", "140.9261", "140.9261"):
        await _advance(hass, freezer, 15)
        assert _state(hass, RESULT) == "accepted"
        assert _state(hass, READING) == expected
    attributes = hass.states.get(RESULT).attributes
    assert attributes["digits_read"] == "0014092X"
    assert attributes["consecutive_failures"] == 0


async def test_a_jittering_last_wheel_never_raises_a_problem(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, tmp_path
) -> None:
    # No dial: the model alternates between the two numbers of a wheel in motion.
    answers = [{"digits": d, "last_wheel_rolling": True, "confidence": 8} for d in ("00140926", "00140925")] * 3
    FakeAI(hass, answers)
    data = {**FERRO_DATA, "pointer_dials": 0, "initial_reading": 140.925}
    await _setup(hass, tmp_path, data=data, options={**FERRO_OPTIONS, "pointer_dials": 0})
    await _advance(hass, freezer, 1)
    for _ in range(5):
        await _advance(hass, freezer, 15)
        assert _state(hass, RESULT) == "accepted"
        assert _state(hass, READING) == "140.926"
    assert _state(hass, "binary_sensor.water_meter_problem") == "off"
    assert hass.states.get(RESULT).attributes["last_wheel_rolling"] is True


async def test_rolling_state_survives_a_restart(hass: HomeAssistant, freezer: FrozenDateTimeFactory, tmp_path) -> None:
    FakeAI(hass, [ferro("00140925", "8", rolling=True)])
    entry = await _setup(hass, tmp_path, data=FERRO_DATA, options=FERRO_OPTIONS)
    await _advance(hass, freezer, 1)
    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    last = entry.runtime_data.last_reading
    assert (last.value, last.tolerance, last.rolling, last.dials) == (140.9258, 0.0001, True, "8")


# Representative answer shapes (not captured from live APIs): providers and small local
# models differ in how they type the fields, and every shape must give the same reading.
ANSWER_STYLES = {
    "typed": {"digits": "00140927", "last_wheel_rolling": False, "confidence": 9, "dials": "3"},
    "all text": {"digits": "0014 0927", "last_wheel_rolling": "false", "confidence": "8", "dials": "3"},
    "loose local": {"digits": "140927", "last_wheel_rolling": "False", "confidence": 7.0, "dials": " 3 "},
}


@pytest.mark.parametrize("style", ANSWER_STYLES)
async def test_every_answer_style_gives_the_same_reading(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, tmp_path, style: str
) -> None:
    FakeAI(hass, [ANSWER_STYLES[style]])
    await _setup(hass, tmp_path, data=FERRO_DATA, options=FERRO_OPTIONS)
    await _advance(hass, freezer, 1)
    assert _state(hass, RESULT) == "accepted"
    assert _state(hass, READING) == "140.9273"
