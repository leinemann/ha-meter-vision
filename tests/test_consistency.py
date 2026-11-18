"""Guards that keep the package easy to maintain."""

import json
from pathlib import Path
import re

from homeassistant.components.sensor.const import DEVICE_CLASS_UNITS

from custom_components.meter_vision.binary_sensor import BINARY_SENSORS
from custom_components.meter_vision.button import READ_NOW
from custom_components.meter_vision.const import UNITS, MeterType
from custom_components.meter_vision.image import LAST_FRAME, RAW_FRAME
from custom_components.meter_vision.messages import MESSAGES, NO_VALUE, REASONS
from custom_components.meter_vision.number import MAX_INCREASE
from custom_components.meter_vision.sensor import DEVICE_CLASSES, SENSORS
from custom_components.meter_vision.switch import AUTOMATIC_READING
from custom_components.meter_vision.validator import Outcome

ROOT = Path(__file__).parents[1] / "custom_components" / "meter_vision"
CARD = ROOT / "frontend" / "meter-vision-card.js"
PLATFORM_KEYS = {
    "sensor": {d.key for d in SENSORS},
    "binary_sensor": {d.key for d in BINARY_SENSORS},
    "button": {READ_NOW.key},
    "image": {LAST_FRAME.key, RAW_FRAME.key},
    "number": {MAX_INCREASE.key},
    "switch": {AUTOMATIC_READING.key},
}


def _keys(node, prefix=""):
    if isinstance(node, dict):
        for key, value in node.items():
            yield from _keys(value, f"{prefix}.{key}")
    else:
        yield prefix


def _json(name: str) -> dict:
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


def test_integration_translations_have_same_keys() -> None:
    assert set(_keys(_json("translations/en.json"))) == set(_keys(_json("translations/it.json")))


def test_every_entity_has_a_name_and_an_icon() -> None:
    names, icons = _json("translations/en.json")["entity"], _json("icons.json")["entity"]
    for platform, keys in PLATFORM_KEYS.items():
        assert set(names[platform]) == keys, platform
        assert set(icons[platform]) == keys, platform


def test_enum_states_are_translated_and_have_icons() -> None:
    names, icons = _json("translations/en.json")["entity"]["sensor"], _json("icons.json")["entity"]["sensor"]
    for description in SENSORS:
        if description.options:
            assert set(names[description.key]["state"]) == set(description.options), description.key
            assert set(icons[description.key]["state"]) == set(description.options), description.key


def test_meter_types_are_translated() -> None:
    selector = _json("translations/en.json")["selector"]["meter_type"]["options"]
    assert set(selector) == {t.value for t in MeterType}


def test_every_unit_is_valid_for_its_device_class() -> None:
    for meter_type, units in UNITS.items():
        assert set(units) <= DEVICE_CLASS_UNITS[DEVICE_CLASSES[meter_type]], meter_type


def test_card_translations_have_same_keys() -> None:
    english, italian = re.search(
        r"const STRINGS = \{\n  en: \{(.*?)\n  \},\n  it: \{(.*?)\n  \}\n\};", CARD.read_text(encoding="utf-8"), re.S
    ).groups()
    keys = [set(re.findall(r"^    (\w+):", block, re.M)) for block in (english, italian)]
    assert keys[0] and keys[0] == keys[1]


def test_card_knows_every_result_and_meter_type() -> None:
    card = CARD.read_text(encoding="utf-8")
    for outcome in Outcome:
        assert f"r_{outcome.value}:" in card
        assert re.search(rf"^  {outcome.value}: \{{ icon:", card, re.M), outcome
    for meter_type in MeterType:
        assert re.search(rf"^  {meter_type.value}: \{{ icon:", card, re.M), meter_type


def test_card_siblings_exist() -> None:
    siblings = re.search(r"const SIBLINGS = \{(.*?)\n\};", CARD.read_text(encoding="utf-8"), re.S).group(1)
    every_key = set().union(*PLATFORM_KEYS.values())
    for key in re.findall(r"^  (\w+):", siblings, re.M):
        assert key in every_key, key


def test_notification_texts_have_same_keys() -> None:
    assert set(MESSAGES["en"]) == set(MESSAGES["it"])
    assert set(REASONS) == set(MESSAGES) == set(NO_VALUE)
    for language in REASONS:
        assert set(REASONS[language]) == {o.value for o in Outcome if o.failed}


def test_version_lives_only_in_the_manifest() -> None:
    version = _json("manifest.json")["version"]
    assert re.fullmatch(r"\d+\.\d+\.\d+", version)
    for path in [*ROOT.glob("*.py"), CARD]:
        assert version not in path.read_text(encoding="utf-8"), f"hard-coded version in {path.name}"
