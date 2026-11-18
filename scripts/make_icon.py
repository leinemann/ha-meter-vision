# SPDX-License-Identifier: GPL-3.0-or-later
"""Meter Vision icon: a meter counter inside a camera viewfinder. Pure shapes, no fonts.

Regenerate the brand images with:

    python scripts/make_icon.py custom_components/meter_vision/brand
"""

import sys

from PIL import Image, ImageDraw

SEGMENTS = {"0": "abcdef", "1": "bc", "4": "bcfg", "7": "abc", "9": "abcdfg"}


def segment_boxes(x, y, w, h, t):
    """Seven segments of a digit cell at (x, y), size w*h, stroke t, as rounded bars."""
    m, g = y + h / 2, t * 0.12  # g: small gap between segments
    return {
        "a": (x + t / 2 + g, y, x + w - t / 2 - g, y + t),
        "g": (x + t / 2 + g, m - t / 2, x + w - t / 2 - g, m + t / 2),
        "d": (x + t / 2 + g, y + h - t, x + w - t / 2 - g, y + h),
        "f": (x, y + t / 2 + g, x + t, m - g),
        "b": (x + w - t, y + t / 2 + g, x + w, m - g),
        "e": (x, m + g, x + t, y + h - t / 2 - g),
        "c": (x + w - t, m + g, x + w, y + h - t / 2 - g),
    }


def draw_icon(size):
    s = size / 512
    im = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((0, 0, size - 1, size - 1), radius=int(104 * s), fill=(14, 87, 160))
    # viewfinder corners
    c, L, T = 64 * s, 92 * s, int(24 * s)
    white = (255, 255, 255)
    for x, y, dx, dy in ((c, c, 1, 1), (size - c, c, -1, 1), (c, size - c, 1, -1), (size - c, size - c, -1, -1)):
        d.line([(x, y + dy * L), (x, y), (x + dx * L, y)], fill=white, width=T, joint="curve")
    # counter window
    wx0, wy0, wx1, wy1 = 92 * s, 176 * s, 420 * s, 336 * s
    d.rounded_rectangle((wx0, wy0, wx1, wy1), radius=int(22 * s), fill=white)
    digits, cells = "0147", 4
    pad, gap = 12 * s, 8 * s
    cw = (wx1 - wx0 - 2 * pad - gap * (cells - 1)) / cells
    for i, ch in enumerate(digits):
        x = wx0 + pad + i * (cw + gap)
        if i < cells - 1:
            divider = [(x + cw + gap / 2, wy0 + 18 * s), (x + cw + gap / 2, wy1 - 18 * s)]
            d.line(divider, fill=(200, 205, 212), width=max(1, int(3 * s)))
        colour = (211, 47, 47) if i == cells - 1 else (32, 33, 36)
        stroke = 17 * s
        boxes = segment_boxes(x + 8 * s, wy0 + 22 * s, cw - 16 * s, wy1 - wy0 - 44 * s, stroke)
        for seg in SEGMENTS[ch]:
            d.rounded_rectangle(boxes[seg], radius=stroke / 2, fill=colour)
    return im


out = sys.argv[1]
draw_icon(512).save(f"{out}/icon@2x.png", optimize=True)
draw_icon(256).save(f"{out}/icon.png", optimize=True)
