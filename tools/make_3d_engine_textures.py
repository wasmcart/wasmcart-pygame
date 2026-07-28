#!/usr/bin/env python3
"""
Generate the 3d_engine surface textures from Kenney's CC0 Pattern Pack.

Why this exists: the example previously shipped near-uniform light-grey
placeholders. The renderer was fine, but the shader gamma-corrects a dim
ambient term, so a flat pale texture came out looking almost black -- which
reads as a lighting bug and is not one. Real textures with actual tonal range
make the scene legible.

The source pack is CC0 (Kenney, www.kenney.nl). Only the individual pattern
PNGs this script consumes are redistributed, tinted and tiled into the three
textures the example binds; the bundle itself is not redistributed.

Usage:
    python3 tools/make_3d_engine_textures.py [path-to-Pattern-Pack]

Defaults to the Kenney all-in-1 layout under ~/Downloads. Pass an explicit
path if the pack lives elsewhere.
"""
import os
import sys
from PIL import Image, ImageEnhance

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, '..', 'examples', '3d_engine', 'textures')

DEFAULT_PACK = os.path.expanduser(
    '~/Downloads/Kenney Game Assets All-in-1 3.6.0/2D assets/Pattern Pack/PNG/Default')

SIZE = 1024

# (output name, source pattern, tint, tile count across)
# Tints keep the three surfaces distinguishable. The shader multiplies this
# base colour by the lighting term, so mid-tone sources survive gamma while
# near-white ones wash out to nothing.
#
# The pack is mostly high-contrast graphic patterns; the masonry row is the
# only set that reads as a real surface at grazing angles. Stripes and zigzags
# alias into moire across a receding floor, which looks like a rendering bug.
TEXTURES = [
    ('img.png',   'pattern_17.png', (150, 120, 100), 6),   # brick, warm stone
    ('img_1.png', 'pattern_19.png', (115, 130, 150), 6),   # small tile, cool
    ('img_2.png', 'pattern_22.png', (120, 140, 115), 6),   # block, muted green
]


def build(src_dir, name, pattern, tint, tiles):
    path = os.path.join(src_dir, pattern)
    if not os.path.exists(path):
        return f'missing source {pattern}'
    tile = Image.open(path).convert('RGB')
    step = SIZE // tiles
    tile = tile.resize((step, step), Image.LANCZOS)

    out = Image.new('RGB', (SIZE, SIZE))
    for y in range(tiles):
        for x in range(tiles):
            out.paste(tile, (x * step, y * step))

    # Map black->dark tint and white->light tint rather than multiplying,
    # which would leave the black areas pure black and the result reading as
    # line art instead of a material.
    r, g, b = tint
    lo = tuple(int(c * 0.45) for c in (r, g, b))
    hi = tuple(min(255, int(c * 1.25)) for c in (r, g, b))
    out = Image.merge('RGB', [
        ch.point(lambda v, a=a, bb=bb: int(a + (bb - a) * v / 255))
        for ch, a, bb in zip(out.split(), lo, hi)
    ])
    # Lift contrast: the lighting pass compresses midtones, and a flat source
    # loses its pattern entirely once gamma is applied.
    out = ImageEnhance.Contrast(out).enhance(1.1)

    dest = os.path.join(OUT, name)
    out.save(dest, optimize=True)
    return f'{name}  {SIZE}x{SIZE}  from {pattern}'


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_PACK
    if not os.path.isdir(src):
        print(f'Kenney Pattern Pack not found at:\n  {src}\n'
              'Pass the path to its PNG/Default directory as an argument.',
              file=sys.stderr)
        return 1
    os.makedirs(OUT, exist_ok=True)
    for name, pattern, tint, tiles in TEXTURES:
        print(build(src, name, pattern, tint, tiles))
    return 0


if __name__ == '__main__':
    sys.exit(main())
