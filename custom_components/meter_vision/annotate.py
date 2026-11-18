# SPDX-License-Identifier: GPL-3.0-or-later
"""The annotated frame: what the model was shown, with what it read drawn on top.

Pure Python plus Pillow (a dependency of Home Assistant core, so no new
requirement). The digit boxes are equal slices of the counter region the owner
configured, never coordinates returned by the model: that is deterministic and
works the same with every provider.

The model returns one confidence for the whole reading, so every box takes the
colour of that confidence; a digit it marked unreadable (X) is red and crossed
out whatever the confidence.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import asdict, dataclass
from io import BytesIO
import itertools
from typing import Any

from PIL import Image, ImageDraw, ImageFont, ImageOps, UnidentifiedImageError

from .const import MIN_CONFIDENCE

UNREADABLE = "X"
GOOD_CONFIDENCE = 7  # this and above: green (the prompt calls 7-8 "typical clear frame")
GREEN = (0, 200, 83)
AMBER = (255, 171, 0)
RED = (255, 23, 68)
BLUE = (41, 121, 255)
WHITE = (255, 255, 255)
BANNER = (0, 0, 0, 170)
OUTCOME_COLOURS = {"accepted": GREEN, "corrected": BLUE, "unconfirmed": AMBER}
JPEG_QUALITY = 85
# Pillow's built-in font has no superscripts: "m³" would show a missing-glyph box.
_PLAIN = str.maketrans({"³": "3", "²": "2"})


@dataclass(frozen=True)
class Region:
    """A rectangle in frame pixels: left, top, width, height."""

    x: int
    y: int
    width: int
    height: int

    @property
    def corners(self) -> tuple[int, int, int, int]:
        """Left, top, right, bottom (inclusive), as Pillow draws them."""
        return self.x, self.y, self.x + self.width - 1, self.y + self.height - 1


def parse_region(text: str) -> Region:
    """``"x, y, width, height"`` in pixels. Raises ValueError."""
    parts = [part.strip() for part in str(text).split(",")]
    if len(parts) != 4 or not all(part.isdigit() for part in parts):
        raise ValueError(f"not 'x, y, width, height' in whole pixels: {text!r}")
    x, y, width, height = (int(part) for part in parts)
    if width <= 0 or height <= 0:
        raise ValueError(f"width and height must be above 0: {text!r}")
    return Region(x, y, width, height)


def parse_regions(text: str | None) -> list[Region]:
    """Regions separated by ``;``; empty text is no region."""
    return [parse_region(part) for part in str(text or "").split(";") if part.strip()]


def digit_boxes(region: Region, count: int) -> list[Region]:
    """The region cut into ``count`` equal slices, left to right, without gaps."""
    edges = [region.x + round(n * region.width / count) for n in range(count + 1)] if count > 0 else []
    return [Region(left, region.y, right - left, region.height) for left, right in itertools.pairwise(edges)]


@dataclass(frozen=True)
class Annotation:
    """What one frame gave, kept so the frame can be drawn again (after a restart, a new region)."""

    outcome: str  # an Outcome value
    at: str  # local time of the frame, as shown
    digits: str | None  # wheels as read, X for an unreadable one; None when nothing was read
    dials: str | None
    confidence: int | None
    rolling: bool
    value: str | None  # the published reading after this frame, with its unit

    def as_dict(self) -> dict[str, Any]:
        """For the store."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Any) -> Annotation | None:
        """From the store; None when missing or not what was saved."""
        if not isinstance(data, dict):
            return None
        try:
            note = cls(**data)
        except TypeError:
            return None
        return note if isinstance(note.outcome, str) and isinstance(note.at, str) else None


def caption(note: Annotation) -> tuple[str, str]:
    """The two banner lines: outcome, reading and time; then what the model read."""
    value = note.value.translate(_PLAIN) if note.value else None
    first = " · ".join(p for p in (note.outcome.replace("_", " ").upper(), value, note.at) if p)
    if note.digits is None:
        return first, "nothing read"
    read = f"read {note.digits}" + (f" + dial {note.dials}" if note.dials else "")
    if note.confidence is not None:
        read += f" · confidence {note.confidence}"
    if note.rolling:
        read += " · last wheel rolling"
    return first, read


def _confidence_colour(confidence: int | None) -> tuple[int, int, int]:
    if confidence is None or confidence < MIN_CONFIDENCE:
        return RED
    return GREEN if confidence >= GOOD_CONFIDENCE else AMBER


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    try:
        return ImageFont.load_default(size=size)
    except (TypeError, OSError):  # Pillow without FreeType: fixed-size bitmap font
        return ImageFont.load_default()


def _label(draw: ImageDraw.ImageDraw, xy: tuple[int, int], text: str, colour: tuple[int, int, int], font: Any) -> None:
    """Text on a dark plate, centred on ``xy``, readable on any background."""
    left, top, right, bottom = draw.textbbox(xy, text, font=font, anchor="mm")
    pad = max(2, (bottom - top) // 6)
    draw.rectangle((left - pad, top - pad, right + pad, bottom + pad), fill=BANNER)
    draw.text(xy, text, fill=colour, font=font, anchor="mm")


def _draw_counter(
    draw: ImageDraw.ImageDraw, counter: Region, count: int, note: Annotation, line: int, height: int
) -> None:
    digits = note.digits or ""
    boxes = digit_boxes(counter, count or len(digits))
    fits = len(digits) == len(boxes)
    base = _confidence_colour(note.confidence) if fits else RED
    font = _font(max(10, min(int(min(b.width for b in boxes) * 0.8) if boxes else 10, height // 12)))
    draw.rectangle(counter.corners, outline=WHITE, width=max(1, line // 2))
    for n, box in enumerate(boxes):
        digit = digits[n] if fits else ""
        colour = RED if digit == UNREADABLE else base
        draw.rectangle(box.corners, outline=colour, width=line)
        if digit == UNREADABLE:
            left, top, right, bottom = box.corners
            draw.line((left, top, right, bottom), fill=RED, width=line)
            draw.line((left, bottom, right, top), fill=RED, width=line)
        if digit:
            rolling = note.rolling and n == len(boxes) - 1 and digit.isdigit()
            text = f"{digit}/{(int(digit) + 1) % 10}" if rolling else digit
            size = font.size if isinstance(font, ImageFont.FreeTypeFont) else 10
            above = box.y - size // 2 - line * 2
            y = above if above - size // 2 > 0 else box.y + box.height + size // 2 + line * 2
            _label(draw, (box.x + box.width // 2, y), text, colour, font)


def _draw_dials(draw: ImageDraw.ImageDraw, dials: Sequence[Region], note: Annotation, line: int, height: int) -> None:
    read = note.dials or ""
    fits = len(read) == len(dials)
    font = _font(max(10, height // 14))
    for n, dial in enumerate(dials):
        digit = read[n] if fits else ""
        colour = RED if not digit.isdigit() else _confidence_colour(note.confidence)
        draw.ellipse(dial.corners, outline=colour, width=line)
        if digit:
            size = font.size if isinstance(font, ImageFont.FreeTypeFont) else 10
            _label(draw, (dial.x + dial.width // 2, max(size // 2, dial.y - size // 2 - line * 2)), digit, colour, font)


def _draw_banner(draw: ImageDraw.ImageDraw, note: Annotation, width: int, height: int) -> None:
    first, second = caption(note)
    size = max(10, min(height // 20, width // 32))
    font = _font(size)
    pad = size // 3
    draw.rectangle((0, 0, width, 2 * size + 3 * pad), fill=BANNER)
    draw.text((pad, pad), first, fill=OUTCOME_COLOURS.get(note.outcome, RED), font=font)
    draw.text((pad, size + 2 * pad), second, fill=WHITE, font=font)


def annotate(
    frame: bytes, counter: Region | None, dials: Sequence[Region], digit_count: int, note: Annotation
) -> bytes:
    """Draw the regions, the digits read and the outcome on a frame; return a JPEG.

    Regions are in pixels of the frame as a browser shows it (EXIF rotation
    applied) and may reach outside it: Pillow clips. Raises ValueError when the
    frame is not an image.
    """
    try:
        with Image.open(BytesIO(frame)) as source:
            image = ImageOps.exif_transpose(source).convert("RGBA")
    except (UnidentifiedImageError, OSError, SyntaxError) as err:
        raise ValueError(f"the frame is not an image: {err}") from err
    width, height = image.size
    line = max(2, width // 320)
    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    if counter is not None:
        _draw_counter(draw, counter, digit_count, note, line, height)
    _draw_dials(draw, dials, note, line, height)
    _draw_banner(draw, note, width, height)
    out = BytesIO()
    Image.alpha_composite(image, overlay).convert("RGB").save(out, "JPEG", quality=JPEG_QUALITY)
    return out.getvalue()
