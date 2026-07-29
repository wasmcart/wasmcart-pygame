"""surfarray: per-pixel work through the numpy bridge.

Everything drawn here is computed pixel by pixel, so the screen is its own
test. Each panel is labelled and fails in a VISUALLY OBVIOUS way:

  1. pixels3d gradient   -- built by writing into a live view. If the view is
                            not actually live, the panel stays black.
  2. pixels3d mutation   -- the same surface, then inverted IN PLACE. If the
                            write-back is broken the panel is identical to
                            panel 1 instead of inverted.
  3. array3d + blit_array-- copied out, channel-swapped, blitted back. A
                            broken round-trip gives black or garbage.
  4. make_surface        -- a plasma built from scratch in an array.
  5. per-channel arrays  -- array_red/green/blue recombined as three bars.

A blank or unchanged panel is the failure signal; the frame counter keeps
running either way, which is exactly why the panels have to be looked at.
"""

import math
import pygame
import pygame.surfarray as surfarray

pygame.init()
screen = pygame.display.set_mode((640, 480))
pygame.display.set_caption("surfarray")
clock = pygame.time.Clock()
font = pygame.font.Font(None, 20)

PANEL = 180
GAP = 20
COLS = 3


def panel_pos(i):
    x = GAP + (i % COLS) * (PANEL + GAP)
    y = 40 + (i // COLS) * (PANEL + GAP + 24)
    return x, y


# ---------------------------------------------------------------- panel 1+2
# A gradient written through a LIVE pixels3d view. Nothing here touches
# set_at: if pixels3d does not write back, this surface stays black.
grad = pygame.Surface((PANEL, PANEL))
px = surfarray.pixels3d(grad)
for x in range(PANEL):
    for y in range(PANEL):
        px[x, y, 0] = (x * 255) // (PANEL - 1)
        px[x, y, 1] = (y * 255) // (PANEL - 1)
        px[x, y, 2] = 255 - ((x + y) * 255) // (2 * (PANEL - 1))
del px  # release the view (and the surface lock) before blitting

# Panel 2 is the same image inverted IN PLACE through another live view.
inverted = grad.copy()
px = surfarray.pixels3d(inverted)
for x in range(PANEL):
    for y in range(PANEL):
        px[x, y, 0] = 255 - px[x, y, 0]
        px[x, y, 1] = 255 - px[x, y, 1]
        px[x, y, 2] = 255 - px[x, y, 2]
del px

# ------------------------------------------------------------------ panel 3
# Copy out with array3d, swap channels, blit back with blit_array.
swapped = pygame.Surface((PANEL, PANEL))
_src = surfarray.array3d(grad)
_dst = surfarray.array3d(swapped)
for x in range(PANEL):
    for y in range(PANEL):
        _dst[x, y, 0] = _src[x, y, 2]
        _dst[x, y, 1] = _src[x, y, 0]
        _dst[x, y, 2] = _src[x, y, 1]
surfarray.blit_array(swapped, _dst)

# ------------------------------------------------------------------ panel 4
# A plasma built entirely in an array, then turned into a Surface.
_plasma = surfarray.array3d(pygame.Surface((PANEL, PANEL)))
for x in range(PANEL):
    fx = x / PANEL * 6.0
    for y in range(PANEL):
        fy = y / PANEL * 6.0
        v = (math.sin(fx) + math.sin(fy)
             + math.sin((fx + fy) * 0.5) + math.sin(math.hypot(fx - 3, fy - 3)))
        v = (v + 4.0) / 8.0
        _plasma[x, y, 0] = int(127 + 127 * math.sin(v * math.pi * 2))
        _plasma[x, y, 1] = int(127 + 127 * math.sin(v * math.pi * 2 + 2.09))
        _plasma[x, y, 2] = int(127 + 127 * math.sin(v * math.pi * 2 + 4.19))
plasma = surfarray.make_surface(_plasma)

# ------------------------------------------------------------------ panel 5
# Pull each channel out separately and recombine them as three stacked bars,
# proving array_red/green/blue really are different planes.
channels = pygame.Surface((PANEL, PANEL))
_r = surfarray.array_red(grad)
_g = surfarray.array_green(grad)
_b = surfarray.array_blue(grad)
_out = surfarray.array3d(channels)
third = PANEL // 3
for x in range(PANEL):
    for y in range(PANEL):
        if y < third:
            _out[x, y, 0] = _r[x, y]
            _out[x, y, 1] = 0
            _out[x, y, 2] = 0
        elif y < 2 * third:
            _out[x, y, 0] = 0
            _out[x, y, 1] = _g[x, y]
            _out[x, y, 2] = 0
        else:
            _out[x, y, 0] = 0
            _out[x, y, 1] = 0
            _out[x, y, 2] = _b[x, y]
surfarray.blit_array(channels, _out)

PANELS = [
    (grad, "1 pixels3d gradient"),
    (inverted, "2 inverted in place"),
    (swapped, "3 array3d+blit"),
    (plasma, "4 make_surface"),
    (channels, "5 red/green/blue"),
]

# A live view of the display surface, used for the animated scanline band so
# that something is provably writing to the screen every frame.
frame_count = 0


def _wc_frame():
    global frame_count
    frame_count += 1

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            pass

    screen.fill((16, 16, 24))

    title = font.render(
        "pygame.surfarray  --  every panel computed per-pixel",
        True, (235, 235, 245))
    screen.blit(title, (GAP, 12))

    for i, (surf, label) in enumerate(PANELS):
        x, y = panel_pos(i)
        screen.blit(surf, (x, y))
        lab = font.render(label, True, (200, 200, 215))
        screen.blit(lab, (x, y + PANEL + 4))

    # Animated band written straight into the display surface through a live
    # pixels3d view -- if this stops moving, screen views are not live.
    band_y = 300 + (frame_count * 2) % 160
    dpx = surfarray.pixels3d(screen)
    x0, _ = panel_pos(5)
    for x in range(x0, min(x0 + PANEL, 640)):
        for dy in range(6):
            yy = band_y + dy
            if 0 <= yy < 480:
                dpx[x, yy, 0] = 255
                dpx[x, yy, 1] = 180
                dpx[x, yy, 2] = 40
    del dpx

    x5, y5 = panel_pos(5)
    lab = font.render("6 live screen band", True, (200, 200, 215))
    screen.blit(lab, (x5, y5 + PANEL + 4))

    fps = font.render(f"frame {frame_count}", True, (150, 150, 165))
    screen.blit(fps, (640 - 110, 12))

    pygame.display.flip()
    clock.tick(60)
