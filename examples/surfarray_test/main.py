"""surfarray correctness gate: exact values, not "it did not crash".

Run it and read either the log or the screen:

    bash pack_game.sh examples/surfarray_test out/surfarray_test.wasc
    node ../wasmcart/bin/wasmcart.js out/surfarray_test.wasc \\
        --frames 3 --shot shot.png

Every assertion compares against a value computed independently of surfarray
(set_at/get_at/map_rgb), so a surfarray that quietly does nothing cannot pass.
The pixels3d LIVE checks are the load-bearing ones: replace pixels3d with
array3d (a copy) and exactly those six go red while the rest stay green.

The verdict is also drawn on screen, so the screenshot alone is conclusive.
"""
import pygame

pygame.init()
screen = pygame.display.set_mode((320, 240))

import pygame.surfarray as sa

FAILS = []
PASSES = []


def check(name, got, want):
    if got == want:
        PASSES.append(name)
        print(f"PASS {name}: {got}")
    else:
        FAILS.append(name)
        print(f"FAIL {name}: got {got!r} want {want!r}")


def check_raises(name, exc, fn):
    try:
        fn()
    except exc as e:
        PASSES.append(name)
        print(f"PASS {name}: raised {type(e).__name__}")
        return
    except Exception as e:
        FAILS.append(name)
        print(f"FAIL {name}: raised {type(e).__name__} not {exc.__name__}: {e}")
        return
    FAILS.append(name)
    print(f"FAIL {name}: did not raise")


# ---------------------------------------------------------------- array3d
s = pygame.Surface((5, 4), pygame.SRCALPHA, 32)
s.fill((0, 0, 0, 255))
s.set_at((0, 0), (11, 22, 33, 255))
s.set_at((4, 3), (200, 100, 50, 255))
s.set_at((2, 1), (7, 8, 9, 255))

a3 = sa.array3d(s)
check("array3d shape", tuple(a3.shape), (5, 4, 3))
check("array3d[0,0]", (a3[0, 0, 0], a3[0, 0, 1], a3[0, 0, 2]), (11, 22, 33))
check("array3d[4,3]", (a3[4, 3, 0], a3[4, 3, 1], a3[4, 3, 2]), (200, 100, 50))
check("array3d[2,1]", (a3[2, 1, 0], a3[2, 1, 1], a3[2, 1, 2]), (7, 8, 9))
check("array3d partial idx", list(a3[2, 1]), [7, 8, 9])

# array3d must be a COPY: mutating it must NOT touch the surface
a3[0, 0, 0] = 250
check("array3d is a copy", s.get_at((0, 0))[0], 11)

# ---------------------------------------------------------------- pixels3d
p3 = sa.pixels3d(s)
check("pixels3d shape", tuple(p3.shape), (5, 4, 3))
check("pixels3d read [0,0]", (p3[0, 0, 0], p3[0, 0, 1], p3[0, 0, 2]), (11, 22, 33))

# THE critical property: write-back to the live surface
p3[0, 0, 0] = 250
check("pixels3d LIVE scalar write", s.get_at((0, 0))[0], 250)

p3[1, 1] = (60, 70, 80)
check("pixels3d LIVE tuple write", tuple(s.get_at((1, 1)))[:3], (60, 70, 80))

# chained partial indexing must also write through
p3[3][2][1] = 123
check("pixels3d LIVE chained write", s.get_at((3, 2))[1], 123)

# surface -> array direction stays live too
s.set_at((4, 0), (1, 2, 3, 255))
check("pixels3d LIVE read-back", (p3[4, 0, 0], p3[4, 0, 1], p3[4, 0, 2]), (1, 2, 3))

del p3

# ---------------------------------------------------------- round-trip gate
r = pygame.Surface((6, 5), pygame.SRCALPHA, 32)
r.fill((0, 0, 0, 255))
known = {(0, 0): (10, 20, 30), (5, 4): (240, 130, 60),
         (3, 2): (77, 88, 99), (1, 4): (5, 250, 15)}
for (x, y), c in known.items():
    r.set_at((x, y), c + (255,))

ra = sa.array3d(r)
ok = True
for (x, y), c in known.items():
    got = (ra[x, y, 0], ra[x, y, 1], ra[x, y, 2])
    if got != c:
        ok = False
        print(f"  roundtrip mismatch at {(x, y)}: {got} != {c}")
check("array3d round-trip after set_at", ok, True)

# blit_array -> get_at round-trip
dst = pygame.Surface((6, 5), pygame.SRCALPHA, 32)
sa.blit_array(dst, ra)
ok = True
for (x, y), c in known.items():
    got = tuple(dst.get_at((x, y)))[:3]
    if got != c:
        ok = False
        print(f"  blit_array mismatch at {(x, y)}: {got} != {c}")
check("blit_array round-trip", ok, True)

# ---------------------------------------------------------------- channels
c = pygame.Surface((3, 2), pygame.SRCALPHA, 32)
c.fill((0, 0, 0, 255))
c.set_at((0, 0), (90, 180, 270 % 256, 255))
c.set_at((2, 1), (1, 2, 3, 128))
check("array_red", sa.array_red(c)[0, 0], 90)
check("array_green", sa.array_green(c)[0, 0], 180)
check("array_blue", sa.array_blue(c)[0, 0], 14)
check("array_alpha", sa.array_alpha(c)[2, 1], 128)

# live channel views
pr = sa.pixels_red(c)
pr[0, 0] = 5
check("pixels_red LIVE write", c.get_at((0, 0))[0], 5)
del pr

pa = sa.pixels_alpha(c)
pa[0, 0] = 64
check("pixels_alpha LIVE write", c.get_at((0, 0))[3], 64)
del pa

# ---------------------------------------------------------------- 2d
d = pygame.Surface((3, 2), pygame.SRCALPHA, 32)
d.fill((0, 0, 0, 255))
d.set_at((1, 1), (10, 20, 30, 255))
a2 = sa.array2d(d)
check("array2d shape", tuple(a2.shape), (3, 2))
check("array2d value", a2[1, 1] & 0xFFFFFF, d.map_rgb((10, 20, 30, 255)) & 0xFFFFFF)

p2 = sa.pixels2d(d)
check("pixels2d read", p2[1, 1] & 0xFFFFFF, d.map_rgb((10, 20, 30, 255)) & 0xFFFFFF)
p2[0, 0] = d.map_rgb((200, 150, 100, 255))
check("pixels2d LIVE write", tuple(d.get_at((0, 0)))[:3], (200, 150, 100))
del p2

# 16-bit: pitch is padded, so this exercises the get_buffer() fallback path
d16 = pygame.Surface((5, 3), 0, 16)
d16.fill((0, 0, 0))
d16.set_at((1, 1), (255, 0, 0))
p16 = sa.pixels2d(d16)
check("pixels2d 16bit read", p16[1, 1], d16.map_rgb((255, 0, 0)))
p16[3, 2] = d16.map_rgb((0, 255, 0))
check("pixels2d 16bit LIVE write", tuple(d16.get_at((3, 2)))[:3],
      tuple(d16.unmap_rgb(d16.map_rgb((0, 255, 0))))[:3])
del p16

# 8-bit: also padded
d8 = pygame.Surface((5, 3), 0, 8)
d8.fill(0)
p8 = sa.pixels2d(d8)
p8[2, 1] = 7
check("pixels2d 8bit LIVE write", d8.get_at_mapped((2, 1)), 7)
del p8

# ---------------------------------------------------------------- make_surface
ms = sa.make_surface(ra)
check("make_surface size", ms.get_size(), (6, 5))
ok = True
for (x, y), col in known.items():
    got = tuple(ms.get_at((x, y)))[:3]
    if got != col:
        ok = False
        print(f"  make_surface mismatch at {(x, y)}: {got} != {col}")
check("make_surface round-trip", ok, True)

# ---------------------------------------------------------------- map_array
m = sa.map_array(d, ra)
check("map_array shape", tuple(m.shape), (6, 5))
check("map_array value", m[0, 0] & 0xFFFFFF,
      d.map_rgb((10, 20, 30)) & 0xFFFFFF)

# ---------------------------------------------------------------- 24-bit
s24 = pygame.Surface((4, 3), 0, 24)
s24.fill((0, 0, 0))
s24.set_at((1, 1), (100, 110, 120))
check("24bit array3d", tuple(sa.array3d(s24)[1, 1]), (100, 110, 120))
p24 = sa.pixels3d(s24)
p24[2, 2] = (9, 19, 29)
check("24bit pixels3d LIVE write", tuple(s24.get_at((2, 2)))[:3], (9, 19, 29))
del p24

# ------------------------------------------------- display surface live view
dp = sa.pixels3d(screen)
check("screen pixels3d shape", tuple(dp.shape), (320, 240, 3))
dp[10, 10] = (255, 0, 0)
check("screen pixels3d LIVE write", tuple(screen.get_at((10, 10)))[:3], (255, 0, 0))
del dp

# ------------------------------------------------------------- deprecated
check("get_arraytype", sa.get_arraytype(), "numpy")
check("get_arraytypes", sa.get_arraytypes(), ("numpy",))
check_raises("use_arraytype bad", ValueError, lambda: sa.use_arraytype("numeric"))

# ------------------------------------------------- pygame.surfarray attribute
check("pygame.surfarray attribute", hasattr(pygame, "surfarray"), True)

print(f"\nSURFARRAY RESULT: {len(PASSES)} passed, {len(FAILS)} failed")
if FAILS:
    print("FAILED: " + ", ".join(FAILS))
print("SURFARRAY " + ("ALL GREEN" if not FAILS else "RED"))

frame = 0
_font = pygame.font.Font(None, 26)
_small = pygame.font.Font(None, 18)


def _wc_frame():
    global frame
    frame += 1
    # Green screen for a clean pass, red for any failure, with the failing
    # names listed. The screenshot is then a verdict on its own, with no need
    # to go digging in the log.
    screen.fill((10, 60, 20) if not FAILS else (70, 12, 12))
    head = _font.render(
        "surfarray: ALL GREEN" if not FAILS else "surfarray: RED",
        True, (170, 255, 180) if not FAILS else (255, 190, 190))
    screen.blit(head, (16, 20))
    tally = _small.render(f"{len(PASSES)} passed, {len(FAILS)} failed",
                          True, (225, 235, 225))
    screen.blit(tally, (16, 54))
    for i, name in enumerate(FAILS[:8]):
        screen.blit(_small.render(name[:44], True, (255, 205, 205)),
                    (16, 80 + i * 18))
    pygame.display.flip()
