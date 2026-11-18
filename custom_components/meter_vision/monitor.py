# SPDX-License-Identifier: GPL-3.0-or-later
# Based on monitor.py of ha-ai-meter-reader v1.0.1 (https://github.com/artech-lab/ha-ai-meter-reader).
# Modified for Meter Vision: pointer dials, reading tolerance, extra state persisted, annotated frame.
"""MeterMonitor: timer → light and camera frame → AI Task → validation → reading.

The monitor owns every piece of state; entities only read it. The prompt and
the parsing live in ``reading.py``, the plausibility check in ``validator.py``;
this module wires them to Home Assistant: the timer, the light, the camera, the
AI Task entities, notifications and storage.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
import hashlib
import logging
from pathlib import Path
from typing import Any

from homeassistant.components import camera, persistent_notification
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNAVAILABLE
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_call_later, async_track_time_interval
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util, slugify

from .annotate import Annotation, Region, annotate, parse_region, parse_regions
from .const import (
    AI_TIMEOUT_S,
    CONF_AI_TASK,
    CONF_AI_TASK_FALLBACK,
    CONF_CAMERA,
    CONF_COUNTER_REGION,
    CONF_DECIMALS,
    CONF_DIAL_REGIONS,
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
    FAILURES_FOR_PROBLEM,
    MAX_ATTEMPTS,
    MEDIA_SUBDIR,
    RETRY_DELAY_S,
    SNAPSHOT_TIMEOUT_S,
    STORAGE_VERSION,
    UNITS,
    MeterType,
)
from .messages import message, no_value, reason
from .reading import Problem, Reading, build_instructions, build_structure, parse_reading
from .validator import Outcome, ReadingValidator

_LOGGER = logging.getLogger(__name__)

FIRST_READ_DELAY_S = 30  # after start-up, when the last reading is older than one interval


class MeterMonitor:
    """Reads one meter."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, version: str) -> None:
        """Initialise from a config entry."""
        self.hass = hass
        self.entry = entry
        self.version = version
        self.signal = f"{DOMAIN}_{entry.entry_id}_update"
        self.slug = slugify(entry.title) or slugify(DEFAULT_NAME)
        self.validator = ReadingValidator()
        # At least one step of the last digit, or no reading would ever pass.
        self.max_increase = max(UNITS[self.meter_type].get(self.unit, 1.0), 10.0**-self.decimals)
        self.auto_read = True
        self.outcome: Outcome | None = None
        self.last_reading: Reading | None = None
        self.last_attempt: datetime | None = None
        self.last_engine: str | None = None
        self.last_error: str | None = None
        self.failures = 0
        self.reading = False
        self.frame: bytes | None = None
        self.frame_at: datetime | None = None
        # The frame drawn with what it gave (image entity "last frame"); None: show the frame as it is.
        self.annotation: Annotation | None = None
        self._annotated_frame: str | None = None  # sha256 of the frame the annotation belongs to
        self.annotated: bytes | None = None
        self.annotated_at: datetime | None = None
        self._lock = asyncio.Lock()
        self._store: Store[dict[str, Any]] = Store(hass, STORAGE_VERSION, f"{DOMAIN}.{entry.entry_id}")
        self._unsubs: list[CALLBACK_TYPE] = []

    # ------------------------------------------------------------ settings
    @property
    def config(self) -> dict[str, Any]:
        """Setup data merged with the options."""
        return {**self.entry.data, **self.entry.options}

    @property
    def meter_type(self) -> MeterType:
        """Water, gas or energy."""
        return MeterType(self.entry.data[CONF_METER_TYPE])

    @property
    def unit(self) -> str:
        """Unit of the reading (fixed at setup: it defines the statistics)."""
        return self.entry.data[CONF_UNIT]

    @property
    def camera_entity(self) -> str:
        """Camera looking at the counter."""
        return self.config[CONF_CAMERA]

    @property
    def light_entity(self) -> str | None:
        """Light turned on for the frame."""
        return self.config.get(CONF_LIGHT) or None

    @property
    def digits(self) -> int:
        """Digits of the counter, 0 when not checked."""
        return int(self.config.get(CONF_DIGITS, DEFAULT_DIGITS) or 0)

    @property
    def decimals(self) -> int:
        """Digits after the decimal point."""
        return int(self.config.get(CONF_DECIMALS, DEFAULT_DECIMALS) or 0)

    @property
    def dials(self) -> int:
        """Pointer dials after the decimal wheels, each one more decimal."""
        return int(self.config.get(CONF_DIALS, DEFAULT_DIALS) or 0)

    @property
    def precision(self) -> int:
        """Decimals of the reading: the decimal wheels plus the dials."""
        return self.decimals + self.dials

    @property
    def counter_region(self) -> Region | None:
        """Where the counter is in the frame, for the annotated frame."""
        text = (self.config.get(CONF_COUNTER_REGION) or "").strip()
        try:
            return parse_region(text) if text else None
        except ValueError:  # the options flow validates; anything else is ignored, not fatal
            return None

    @property
    def dial_regions(self) -> list[Region]:
        """Where the pointer dials are in the frame, largest factor first."""
        try:
            return parse_regions(self.config.get(CONF_DIAL_REGIONS))
        except ValueError:
            return []

    @property
    def interval(self) -> timedelta:
        """Time between two automatic readings."""
        return timedelta(minutes=self.config.get(CONF_READ_INTERVAL, DEFAULT_READ_INTERVAL))

    @property
    def ai_entities(self) -> list[str]:
        """AI Task entities in order of preference, the unavailable ones last."""
        engines = [e for e in (self.config.get(CONF_AI_TASK), self.config.get(CONF_AI_TASK_FALLBACK)) if e]
        return sorted(dict.fromkeys(engines), key=lambda e: self._state(e) in (None, STATE_UNAVAILABLE))

    @property
    def value(self) -> float | None:
        """Last accepted reading."""
        return self.validator.value

    @property
    def problem(self) -> bool:
        """Too many failed readings in a row."""
        return self.failures >= FAILURES_FOR_PROBLEM

    def _state(self, entity_id: str | None) -> str | None:
        state = self.hass.states.get(entity_id) if entity_id else None
        return state.state if state else None

    @property
    def _frame_path(self) -> Path | None:
        media_root = self.hass.config.media_dirs.get("local")
        return Path(media_root) / MEDIA_SUBDIR / f"{self.slug}.jpg" if media_root else None

    # ------------------------------------------------------------ lifecycle
    async def async_load(self) -> None:
        """Restore the saved state and the last frame."""
        data = await self._store.async_load() or {}
        self.validator = ReadingValidator.from_dict(data.get("validator"))
        initial = self.entry.data.get(CONF_INITIAL_READING)
        if self.validator.value is None and initial is not None:
            # First start, or stored state that could not be read: start from the
            # reading given at setup rather than from whatever the camera says.
            if data:
                _LOGGER.warning("%s: saved state unreadable, starting again from the setup reading", self.entry.title)
            self.validator.set(round(float(initial), self.precision), dt_util.utcnow())
        if isinstance(data.get("max_increase"), int | float):
            self.max_increase = float(data["max_increase"])
        self.auto_read = bool(data.get("auto_read", True))
        self.failures = int(data.get("failures", 0))
        self.outcome = Outcome(data["outcome"]) if data.get("outcome") in set(Outcome) else None
        if isinstance(last := data.get("last_reading"), dict):
            try:
                problem = Problem(last["problem"]) if last.get("problem") else None
                self.last_reading = Reading(
                    str(last["digits"]),
                    last["value"],
                    int(last["confidence"]),
                    problem,
                    float(last.get("tolerance") or 0.0),
                    bool(last.get("rolling")),
                    last.get("dials"),
                )
            except (KeyError, TypeError, ValueError):
                self.last_reading = None
        if stamp := data.get("last_attempt"):
            self.last_attempt = dt_util.parse_datetime(stamp)
        self.last_engine = data.get("last_engine")
        if (path := self._frame_path) is not None:
            self.frame, self.frame_at = await self.hass.async_add_executor_job(_read_frame, path)
        # Drawn again rather than stored: a changed region shows on the last frame at once.
        # The frame file is written at capture, the store after the answer: a restart in
        # between leaves a new frame with the previous frame's annotation. Only a matching
        # digest proves they belong together; otherwise the frame is shown clean.
        if self.frame is not None and data.get("annotation_frame") == _digest(self.frame):
            self.annotation = Annotation.from_dict(data.get("annotation"))
            self._annotated_frame = data["annotation_frame"]
        await self._async_draw()

    def _data(self) -> dict[str, Any]:
        last = None
        if self.last_reading:
            last = {
                "digits": self.last_reading.digits,
                "value": self.last_reading.value,
                "confidence": self.last_reading.confidence,
                "problem": self.last_reading.problem.value if self.last_reading.problem else None,
                "tolerance": self.last_reading.tolerance,
                "rolling": self.last_reading.rolling,
                "dials": self.last_reading.dials,
            }
        return {
            "validator": self.validator.as_dict(),
            "max_increase": self.max_increase,
            "auto_read": self.auto_read,
            "failures": self.failures,
            "outcome": self.outcome.value if self.outcome else None,
            "last_reading": last,
            "last_attempt": self.last_attempt.isoformat() if self.last_attempt else None,
            "last_engine": self.last_engine,
            "annotation": self.annotation.as_dict() if self.annotation else None,
            "annotation_frame": self._annotated_frame if self.annotation else None,
        }

    @callback
    def async_start(self) -> None:
        """Start the reading timer; read soon if the last reading is old."""
        self._unsubs.append(async_track_time_interval(self.hass, self._on_interval, self.interval))
        if self.last_attempt is None or dt_util.utcnow() - self.last_attempt >= self.interval:
            self._unsubs.append(async_call_later(self.hass, FIRST_READ_DELAY_S, self._on_interval))

    async def async_stop(self) -> None:
        """Stop every listener and save."""
        while self._unsubs:
            self._unsubs.pop()()
        await self._store.async_save(self._data())

    @callback
    def _save(self) -> None:
        self._store.async_delay_save(self._data, 5)

    @callback
    def _notify_entities(self) -> None:
        async_dispatcher_send(self.hass, self.signal)

    # ------------------------------------------------------------ controls
    def _spawn(self, coro: Any, name: str) -> None:
        self.entry.async_create_background_task(self.hass, coro, f"{DOMAIN} {self.entry.title} {name}")

    @callback
    def _on_interval(self, _now: datetime) -> None:
        if not self.auto_read or self._lock.locked():
            return
        if self._state(self.camera_entity) in (None, STATE_UNAVAILABLE):
            # An offline camera is a failed reading too: after a while it raises the problem.
            self.last_error = f"{self.camera_entity} unavailable"
            self._record(None)
            self._save()
            self._notify_entities()
            return
        self._spawn(self.async_read(), "reading")

    @callback
    def async_request_reading(self) -> None:
        """Read now (button). Ignored while a reading is running."""
        if not self.ai_entities:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="no_ai", translation_placeholders={"name": self.entry.title}
            )
        if not self._lock.locked():
            self._spawn(self.async_read(), "manual reading")

    @callback
    def set_reading(self, value: float) -> None:
        """Set the reading by hand (set_reading action)."""
        if value < 0:
            raise HomeAssistantError(translation_domain=DOMAIN, translation_key="negative_reading")
        self.validator.set(round(float(value), self.precision), dt_util.utcnow())
        self.outcome = Outcome.CORRECTED
        self._clear_problem()
        self._save()
        self._notify_entities()

    @callback
    def set_max_increase(self, value: float) -> None:
        """Change the maximum increase per reading."""
        self.max_increase = float(value)
        self._save()
        self._notify_entities()

    @callback
    def set_auto_read(self, enabled: bool) -> None:
        """Turn the automatic readings on or off."""
        self.auto_read = enabled
        self._save()
        self._notify_entities()

    # ------------------------------------------------------------ reading
    async def async_read(self) -> Outcome:
        """One reading: up to MAX_ATTEMPTS frames until one gives a number."""
        async with self._lock:
            self.reading = True
            self._notify_entities()
            result: Reading | None = None
            frame_before = self.frame_at
            try:
                instructions = build_instructions(
                    self.meter_type, self.digits, self.decimals, self.config.get(CONF_METER_NOTES, ""), self.dials
                )
                for attempt in range(1, MAX_ATTEMPTS + 1):
                    media_id = await self._async_capture()
                    result = await self._async_ask(instructions, media_id)
                    if result.value is not None or attempt == MAX_ATTEMPTS:
                        break
                    await asyncio.sleep(RETRY_DELAY_S)
            except (HomeAssistantError, TimeoutError, OSError) as err:
                self.last_error = str(err) or type(err).__name__
                _LOGGER.warning("%s: reading failed: %s", self.entry.title, self.last_error)
                result = None
            finally:
                self.reading = False
            outcome = self._record(result)
            if self.frame_at != frame_before:
                # Only a frame taken by this reading is labelled with its outcome.
                self.annotation = self._note(result, outcome)
                self._annotated_frame = _digest(self.frame) if self.frame else None
                await self._async_draw()
            self._save()
            self._notify_entities()
            return outcome

    def _record(self, result: Reading | None) -> Outcome:
        now = dt_util.utcnow()
        self.last_attempt = now
        if result is None:
            outcome = Outcome.ERROR
        else:
            self.last_reading = result
            self.last_error = None
            if result.problem is Problem.UNREADABLE:
                outcome = Outcome.UNREADABLE
            elif result.problem is Problem.WRONG_DIGITS:
                outcome = Outcome.WRONG_DIGITS
            else:
                assert result.value is not None
                if self.dials and not result.dials_used:
                    _LOGGER.warning(
                        "%s: pointer dials not readable (%r), using the wheels only", self.entry.title, result.dials
                    )
                outcome = self.validator.check(result.value, now, self.max_increase, self.interval, result.tolerance)
        _LOGGER.debug(
            "%s: %s (read %s, value %s)", self.entry.title, outcome, result.digits if result else None, self.value
        )
        self.outcome = outcome
        if outcome.failed:
            self.failures += 1
            if self.failures == FAILURES_FOR_PROBLEM:
                self._alert(outcome)
        elif outcome is Outcome.ACCEPTED:
            self._clear_problem()
        return outcome

    def _note(self, result: Reading | None, outcome: Outcome) -> Annotation:
        assert self.frame_at is not None
        return Annotation(
            outcome=outcome.value,
            at=dt_util.as_local(self.frame_at).strftime("%Y-%m-%d %H:%M:%S"),
            digits=result.digits if result else None,
            dials=result.dials if result else None,
            confidence=result.confidence if result else None,
            rolling=bool(result and result.rolling),
            value=f"{self.value:.{self.precision}f} {self.unit}" if self.value is not None else None,
        )

    async def _async_draw(self) -> None:
        """Draw the annotation on the last frame. A failure only costs the drawing, never the reading."""
        annotated = None
        if self.frame is not None and self.annotation is not None:
            try:
                annotated = await self.hass.async_add_executor_job(
                    annotate, self.frame, self.counter_region, self.dial_regions, self.digits, self.annotation
                )
            except ValueError as err:
                _LOGGER.warning("%s: could not draw the annotated frame: %s", self.entry.title, err)
            except Exception:  # Pillow raises many types; the raw frame is still served
                _LOGGER.exception("%s: could not draw the annotated frame", self.entry.title)
        self.annotated = annotated
        self.annotated_at = dt_util.utcnow() if annotated else None

    @asynccontextmanager
    async def _light_on(self) -> AsyncIterator[None]:
        light = self.light_entity
        if light is None or self._state(light) in (None, STATE_UNAVAILABLE):
            yield
            return
        await self.hass.services.async_call(
            "light", "turn_on", {ATTR_ENTITY_ID: light, "brightness_pct": 100}, blocking=True
        )
        try:
            await asyncio.sleep(float(self.config.get(CONF_LIGHT_WARMUP, DEFAULT_LIGHT_WARMUP)))
            yield
        finally:
            await self.hass.services.async_call("light", "turn_off", {ATTR_ENTITY_ID: light}, blocking=True)

    async def _async_capture(self) -> str:
        """Take one frame, keep it for the image entity and the media folder; return its media ID."""
        async with self._light_on():
            image = await camera.async_get_image(self.hass, self.camera_entity, timeout=SNAPSHOT_TIMEOUT_S)
        path = self._frame_path
        if path is None:
            raise HomeAssistantError("no local media folder configured")
        if self.frame is not None and image.content == self.frame:
            # A frozen camera (a cached snapshot, a hung stream) would repeat the same
            # answer for ever, and a long enough run of it replaces the reading.
            raise HomeAssistantError("the camera returned the same frame as last time")
        await self.hass.async_add_executor_job(_write_frame, path, image.content)
        self.frame, self.frame_at = image.content, dt_util.utcnow()
        self._notify_entities()
        return f"media-source://media_source/local/{MEDIA_SUBDIR}/{path.name}"

    async def _async_ask(self, instructions: str, media_id: str) -> Reading:
        """Ask the AI Task entities in order; the first valid answer wins."""
        errors: list[str] = []
        for engine in self.ai_entities:
            try:
                async with asyncio.timeout(AI_TIMEOUT_S):
                    response = await self.hass.services.async_call(
                        "ai_task",
                        "generate_data",
                        {
                            "task_name": f"{self.entry.title} reading",
                            ATTR_ENTITY_ID: engine,
                            "instructions": instructions,
                            "structure": build_structure(self.dials),
                            "attachments": [{"media_content_id": media_id, "media_content_type": "image/jpeg"}],
                        },
                        blocking=True,
                        return_response=True,
                    )
                result = parse_reading((response or {}).get("data"), self.digits, self.decimals, self.dials)
            except (HomeAssistantError, TimeoutError, ValueError) as err:
                errors.append(f"{engine}: {str(err) or type(err).__name__}")
                continue
            self.last_engine = engine
            return result
        raise HomeAssistantError("; ".join(errors) or "no AI Task entity")

    # ------------------------------------------------------------ notifications
    @property
    def _notification_id(self) -> str:
        return f"{DOMAIN}_{self.entry.entry_id}"

    @callback
    def _clear_problem(self) -> None:
        if self.failures >= FAILURES_FOR_PROBLEM:
            persistent_notification.async_dismiss(self.hass, self._notification_id)
        self.failures = 0

    @callback
    def _alert(self, outcome: Outcome) -> None:
        language = self.hass.config.language
        value = f"{self.value:.{self.precision}f} {self.unit}" if self.value is not None else no_value(language)
        title, body = message(
            language,
            "failing",
            name=self.entry.title,
            count=self.failures,
            reason=reason(language, outcome.value),
            value=value,
        )
        if self.config.get(CONF_PERSISTENT_NOTIFICATION, True):
            persistent_notification.async_create(self.hass, body, title, self._notification_id)
        for service in self.config.get(CONF_NOTIFY_SERVICES, []):
            domain, _, name = service.partition(".")
            if not name:
                domain, name = "notify", domain
            self._spawn(self._async_send(domain, name, title, body), f"notify {service}")

    async def _async_send(self, domain: str, service: str, title: str, body: str) -> None:
        try:
            await self.hass.services.async_call(domain, service, {"title": title, "message": body}, blocking=True)
        except HomeAssistantError as err:
            _LOGGER.warning("%s: notification via %s.%s failed: %s", self.entry.title, domain, service, err)

    # ------------------------------------------------------------ diagnostics
    def diagnostics(self) -> dict[str, Any]:
        """State for the diagnostics download."""
        return {
            **self._data(),
            "reading": self.reading,
            "last_error": self.last_error,
            "ai_entities": self.ai_entities,
            "frame_bytes": len(self.frame) if self.frame else 0,
            "frame_at": self.frame_at.isoformat() if self.frame_at else None,
            "annotated_bytes": len(self.annotated) if self.annotated else 0,
            "counter_region": self.config.get(CONF_COUNTER_REGION),
            "dial_regions": self.config.get(CONF_DIAL_REGIONS),
        }


def _digest(frame: bytes) -> str:
    return hashlib.sha256(frame).hexdigest()


def _read_frame(path: Path) -> tuple[bytes | None, datetime | None]:
    try:
        return path.read_bytes(), dt_util.utc_from_timestamp(path.stat().st_mtime)
    except OSError:
        return None, None


def _write_frame(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
