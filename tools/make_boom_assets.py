#!/usr/bin/env python3
"""
Rebuild boom_py's art from CC0 sources.

The example shipped ~18 MB of textures, sprites and audio with no
provenance -- almost certainly not redistributable. Everything is replaced
here with Kenney CC0 art (public domain) plus procedurally generated pieces,
so the whole example can ship under this repo's own licence.

Kenney assets are used from the "Game Assets All-in-1" bundle. Their licence
permits redistributing individual assets; it asks that the bundle itself not
be redistributed, which this does not do.

Run:  python3 tools/make_boom_assets.py [path-to-kenney-bundle]
"""
import os, sys, struct, zlib, math, shutil, random

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RES = os.path.join(HERE, 'examples/boom_py/resources')
KENNEY = sys.argv[1] if len(sys.argv) > 1 else os.path.expanduser(
    '~/Downloads/Kenney Game Assets All-in-1 3.6.0')

random.seed(7)   # deterministic output: regenerating gives identical bytes


# ── minimal PNG writer (RGBA) ────────────────────────────────────────
def write_png(path, px, w, h):
    raw = bytearray()
    for y in range(h):
        raw.append(0)
        for x in range(w):
            raw += bytes(px[y * w + x])
    def chunk(t, d):
        c = t + d
        return struct.pack('>I', len(d)) + c + struct.pack('>I', zlib.crc32(c) & 0xffffffff)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    open(path, 'wb').write(
        b'\x89PNG\r\n\x1a\n'
        + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 6, 0, 0, 0))
        + chunk(b'IDAT', zlib.compress(bytes(raw), 9))
        + chunk(b'IEND', b''))


def solid(w, h, rgba):
    return [tuple(rgba)] * (w * h)


def brick(w, h, base, mortar, bh=64, bw=128):
    """A tiling brick wall. Wall textures are sampled by the raycaster at
    arbitrary columns, so they must tile horizontally without a seam."""
    px = []
    for y in range(h):
        row_i = y // bh
        offset = (row_i % 2) * (bw // 2)
        for x in range(w):
            gx = (x + offset) % bw
            gy = y % bh
            edge = gx < 4 or gy < 4
            if edge:
                px.append(mortar)
            else:
                n = random.randint(-12, 12)
                px.append((max(0, min(255, base[0] + n)),
                           max(0, min(255, base[1] + n)),
                           max(0, min(255, base[2] + n)), 255))
    return px


def vgrad(w, h, top, bottom):
    px = []
    for y in range(h):
        t = y / max(1, h - 1)
        c = tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3)) + (255,)
        px += [c] * w
    return px


def digit(n, size=64):
    """7-segment digit, drawn rather than fetched: a font pack would need
    rasterizing and these are only ever shown as an ammo/health counter."""
    SEG = {0: 'abcdef', 1: 'bc', 2: 'abdeg', 3: 'abcdg', 4: 'bcfg',
           5: 'acdfg', 6: 'acdefg', 7: 'abc', 8: 'abcdefg', 9: 'abcdfg',
           10: ''}
    on = SEG.get(n, '')
    px = [(0, 0, 0, 0)] * (size * size)
    col = (222, 202, 90, 255)
    t, m, b = 8, size // 2, size - 8
    lo, hi = 12, size - 12
    def hbar(y):
        for yy in range(y - 3, y + 4):
            for xx in range(lo, hi):
                if 0 <= yy < size: px[yy * size + xx] = col
    def vbar(x, y0, y1):
        for yy in range(y0, y1):
            for xx in range(x - 3, x + 4):
                if 0 <= xx < size: px[yy * size + xx] = col
    if 'a' in on: hbar(t)
    if 'g' in on: hbar(m)
    if 'd' in on: hbar(b)
    if 'f' in on: vbar(lo, t, m)
    if 'b' in on: vbar(hi, t, m)
    if 'e' in on: vbar(lo, m, b)
    if 'c' in on: vbar(hi, m, b)
    return px


# ── Kenney sprite import ─────────────────────────────────────────────
def load_png_rgba(path):
    """Decode a Kenney PNG well enough to re-emit it (8-bit RGB/RGBA, no
    interlace) -- avoids a Pillow dependency for a build-time script."""
    d = open(path, 'rb').read()
    assert d[:8] == b'\x89PNG\r\n\x1a\n', path
    pos, w, h, depth, ctype, idat = 8, 0, 0, 0, 0, b''
    plte, trns = b'', b''
    while pos < len(d):
        ln = struct.unpack('>I', d[pos:pos+4])[0]
        typ = d[pos+4:pos+8]
        body = d[pos+8:pos+8+ln]
        if typ == b'IHDR':
            w, h, depth, ctype = struct.unpack('>IIBB', body[:10])
        elif typ == b'PLTE':
            plte = body
        elif typ == b'tRNS':
            trns = body
        elif typ == b'IDAT':
            idat += body
        elif typ == b'IEND':
            break
        pos += 12 + ln
    # Kenney ships a mix of truecolour (2/6) and PALETTE (3) PNGs.
    assert depth == 8 and ctype in (2, 3, 6), f'{path}: depth {depth} ctype {ctype}'
    nch = {2: 3, 3: 1, 6: 4}[ctype]
    raw = zlib.decompress(idat)
    out, stride, prev = [], w * nch, bytearray(w * nch)
    p = 0
    for y in range(h):
        f = raw[p]; p += 1
        line = bytearray(raw[p:p+stride]); p += stride
        for i in range(stride):
            a = line[i-nch] if i >= nch else 0
            b = prev[i]
            c = prev[i-nch] if i >= nch else 0
            if f == 1: line[i] = (line[i] + a) & 255
            elif f == 2: line[i] = (line[i] + b) & 255
            elif f == 3: line[i] = (line[i] + (a + b) // 2) & 255
            elif f == 4:
                pp = a + b - c
                pa, pb, pc = abs(pp-a), abs(pp-b), abs(pp-c)
                pr = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                line[i] = (line[i] + pr) & 255
        for x in range(w):
            o = x * nch
            if ctype == 3:
                idx = line[o]
                r, g, b_ = plte[idx*3], plte[idx*3+1], plte[idx*3+2]
                a = trns[idx] if idx < len(trns) else 255
                out.append((r, g, b_, a))
            else:
                out.append((line[o], line[o+1], line[o+2],
                            line[o+3] if nch == 4 else 255))
        prev = line
    return out, w, h


def scaled(px, w, h, tw, th):
    out = []
    for y in range(th):
        sy = min(h - 1, y * h // th)
        for x in range(tw):
            sx = min(w - 1, x * w // tw)
            out.append(px[sy * w + sx])
    return out


def tinted(px, mul):
    return [(min(255, int(p[0]*mul[0])), min(255, int(p[1]*mul[1])),
             min(255, int(p[2]*mul[2])), p[3]) for p in px]


def main():
    mons = os.path.join(KENNEY, '2D assets/Monster Builder Pack/PNG/Default')
    if not os.path.isdir(mons):
        sys.exit(f'Kenney bundle not found at {KENNEY}\n'
                 f'pass its path as the first argument')

    # walls: five tiling brick variants
    for i, (base, mortar) in enumerate([
            ((116, 106, 96, 255), (58, 54, 50, 255)),
            ((96, 108, 116, 255), (44, 52, 58, 255)),
            ((120, 96, 84, 255), (60, 46, 40, 255)),
            ((100, 116, 96, 255), (48, 58, 46, 255)),
            ((110, 100, 120, 255), (54, 48, 60, 255))], 1):
        write_png(f'{RES}/textures/{i}.png', brick(512, 512, base, mortar), 512, 512)
        print(f'  textures/{i}.png')

    # sky, full-screen overlays
    write_png(f'{RES}/textures/sky.png', vgrad(1024, 512, (30, 34, 52), (120, 96, 84)), 1024, 512)
    write_png(f'{RES}/textures/blood_screen.png',
              [(150, 0, 0, max(0, 190 - int(((x-800)**2 + (y-450)**2) ** .5 // 3)))
               for y in range(0, 900, 4) for x in range(0, 1600, 4)], 400, 225)
    write_png(f'{RES}/textures/game_over.png', vgrad(400, 225, (60, 0, 0), (10, 0, 0)), 400, 225)
    write_png(f'{RES}/textures/win.png', vgrad(400, 225, (0, 50, 20), (0, 10, 5)), 400, 225)
    print('  textures/sky, blood_screen, game_over, win')

    for n in range(11):
        write_png(f'{RES}/textures/digits/{n}.png', digit(n), 64, 64)
    print('  textures/digits/0-10')

    # NPCs: three Kenney monster bodies, tinted per type
    npcs = {'soldier': ('body_greenD.png', (1.0, 1.0, 1.0)),
            'caco_demon': ('body_redC.png', (1.0, 0.85, 0.85)),
            'cyber_demon': ('body_blueE.png', (0.9, 0.9, 1.1))}
    for name, (src, tint) in npcs.items():
        path = os.path.join(mons, src)
        if not os.path.exists(path):
            cands = [f for f in os.listdir(mons) if f.startswith('body_')]
            path = os.path.join(mons, sorted(cands)[0])
        px, w, h = load_png_rgba(path)
        px = tinted(scaled(px, w, h, 82, 110), tint)
        base = f'{RES}/sprites/npc/{name}'
        shutil.rmtree(base, ignore_errors=True)
        write_png(f'{base}/0.png', px, 82, 110)
        for sub, count in (('idle', 8), ('walk', 4), ('attack', 2),
                           ('death', 9), ('pain', 1)):
            for i in range(count):
                # cheap animation: brighten on attack, fade through death
                if sub == 'death':
                    f = 1.0 - i / count
                    frame = [(int(p[0]*f), int(p[1]*f), int(p[2]*f), p[3]) for p in px]
                elif sub == 'attack':
                    frame = tinted(px, (1.3, 1.1, 1.1))
                elif sub == 'pain':
                    frame = tinted(px, (1.5, 0.7, 0.7))
                else:
                    s = 1.0 + 0.05 * math.sin(i / max(1, count) * math.tau)
                    frame = tinted(px, (s, s, s))
                write_png(f'{base}/{sub}/{i}.png', frame, 82, 110)
        print(f'  sprites/npc/{name} (24 frames)')

    # weapon: a simple barrel that recoils across its 6 frames
    for i in range(6):
        w, h = 970, 1050
        px = [(0, 0, 0, 0)] * (w * h)
        lift = int(60 * math.sin(i / 6 * math.pi))
        for y in range(h // 2 + lift, h):
            for x in range(w // 2 - 90, w // 2 + 90):
                d = abs(x - w // 2) / 90
                v = int(150 - 60 * d)
                px[y * w + x] = (v, v, v + 6, 255)
        if i in (1, 2):     # muzzle flash
            cx, cy = w // 2, h // 2 + lift
            for y in range(max(0, cy - 120), cy + 40):
                for x in range(cx - 120, cx + 120):
                    dd = ((x - cx) ** 2 + (y - cy) ** 2) ** .5
                    if dd < 110:
                        a = int(255 * (1 - dd / 110))
                        px[y * w + x] = (255, 220, 120, a)
        write_png(f'{RES}/sprites/weapon/shotgun/{i}.png', px, w, h)
    print('  sprites/weapon/shotgun (6 frames)')

    # static + animated scenery
    write_png(f'{RES}/sprites/static_sprites/candlebra.png',
              [(200, 160, 60, 255) if 12 < y < 60 and 18 < x < 30 else (0, 0, 0, 0)
               for y in range(66) for x in range(48)], 48, 66)
    for name, col in (('green_light', (80, 220, 120)), ('red_light', (220, 80, 80))):
        for i in range(4):
            s = 0.6 + 0.4 * math.sin(i / 4 * math.tau)
            # Small: SPRITE_SCALE in sprite_object.py is relative to the
            # source image, so an oversized source fills the screen.
            R_ = 24
            px = [(int(col[0]*s), int(col[1]*s), int(col[2]*s), 255)
                  if ((x-R_)**2 + (y-R_)**2) ** .5 < R_ * 0.8 else (0, 0, 0, 0)
                  for y in range(R_*2) for x in range(R_*2)]
            write_png(f'{RES}/sprites/animated_sprites/{name}/{i}.png', px, R_*2, R_*2)
    print('  sprites/static + animated lights')


if __name__ == '__main__':
    main()
