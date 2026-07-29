#!/usr/bin/env python3
"""Generate the replacement art SolarWolf's port needs.

Upstream SolarWolf ships `data/oldsolarfox.png`, a screenshot of the Atari
2600 game the credits screen tips its hat to. That is somebody else's
copyrighted commercial game, so it is not in this repo and never will be.
This draws an original stand-in for the same slot: a stylised retro console
frame at the same 235x210 the credits layout positions.

Deterministic -- no RNG, so a rebuild is byte-identical.

    python3 tools/make_solarwolf_assets.py [outdir]

Default outdir is ports/solarwolf/data/.
"""
import os
import sys

from PIL import Image, ImageDraw

W, H = 235, 210

BEZEL = (28, 26, 34)
BEZEL_EDGE = (58, 56, 70)
SCREEN_BG = (8, 10, 26)
SCANLINE = (0, 0, 0)
GRID = (26, 52, 96)
SHIP = (120, 240, 170)
BOX = (232, 208, 96)
BOX_ALT = (208, 112, 96)
LABEL = (150, 156, 176)


def build():
    img = Image.new('RGB', (W, H), BEZEL)
    d = ImageDraw.Draw(img)

    # Console bezel: rounded outer shell with a lighter lip.
    d.rounded_rectangle([2, 2, W - 3, H - 3], radius=12, outline=BEZEL_EDGE,
                        width=2)

    # The "screen" the mock gameplay is drawn into.
    sx0, sy0, sx1, sy1 = 18, 16, W - 19, H - 44
    d.rounded_rectangle([sx0, sy0, sx1, sy1], radius=6, fill=SCREEN_BG,
                        outline=BEZEL_EDGE, width=1)

    # Playfield grid: the arena a Solarfox-alike is played on.
    step = 16
    for x in range(sx0 + step, sx1, step):
        d.line([(x, sy0 + 6), (x, sy1 - 6)], fill=GRID, width=1)
    for y in range(sy0 + step, sy1, step):
        d.line([(sx0 + 6, y), (sx1 - 6, y)], fill=GRID, width=1)

    # Rows of collectible boxes, the shape of the real game's playfield.
    for row in range(3):
        y = sy0 + 26 + row * 22
        for col in range(7):
            x = sx0 + 18 + col * 24
            fill = BOX if (row + col) % 3 else BOX_ALT
            d.rectangle([x, y, x + 12, y + 12], fill=fill)

    # Player ship: a chunky low-res triangle near the bottom of the screen.
    cx = (sx0 + sx1) // 2
    cy = sy1 - 20
    d.polygon([(cx, cy - 11), (cx - 9, cy + 8), (cx, cy + 3), (cx + 9, cy + 8)],
              fill=SHIP)

    # Two shots in flight.
    for dx in (-26, 30):
        d.rectangle([cx + dx, cy - 24, cx + dx + 2, cy - 14], fill=SHIP)

    # CRT scanlines over the whole screen area.
    for y in range(sy0 + 1, sy1, 3):
        d.line([(sx0 + 1, y), (sx1 - 1, y)], fill=SCANLINE, width=1)

    # Console front: a cartridge slot and two chunky switches.
    d.rectangle([sx0 + 4, sy1 + 12, sx1 - 4, sy1 + 18], fill=(16, 15, 20),
                outline=BEZEL_EDGE)
    for i in range(3):
        x = sx0 + 12 + i * 34
        d.rectangle([x, sy1 + 26, x + 20, sy1 + 32], fill=BEZEL_EDGE)

    d.text((sx1 - 74, sy1 + 25), 'HOME  VIDEO', fill=LABEL)

    # Quantize to a palette, the way every other image in this game's data
    # directory is stored -- the loader path that handles it is the one under
    # test here.
    return img.convert('P', palette=Image.Palette.ADAPTIVE, colors=64)


def main():
    outdir = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        '..', 'ports', 'solarwolf', 'data')
    outdir = os.path.abspath(outdir)
    os.makedirs(outdir, exist_ok=True)
    dest = os.path.join(outdir, 'oldsolarfox.png')
    build().save(dest, optimize=True)
    print(f'wrote {dest}')


if __name__ == '__main__':
    main()
