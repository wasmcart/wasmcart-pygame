#!/usr/bin/env python3
"""
Generate the 3d_engine skybox as six gradient faces.

The original was ~24 MB of photographic skybox with no provenance. A
procedural gradient is a few KB, unambiguously ours, and reads correctly as
sky in a demo whose point is the renderer rather than the art.
"""
import struct, zlib, os, math

SIZE = 256


def png(path, pixels, w, h):
    raw = bytearray()
    for y in range(h):
        raw.append(0)
        for x in range(w):
            raw += bytes(pixels[y * w + x])
    def chunk(t, d):
        c = t + d
        return struct.pack('>I', len(d)) + c + struct.pack('>I', zlib.crc32(c) & 0xffffffff)
    open(path, 'wb').write(
        b'\x89PNG\r\n\x1a\n'
        + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 2, 0, 0, 0))
        + chunk(b'IDAT', zlib.compress(bytes(raw), 9))
        + chunk(b'IEND', b''))


def lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


HORIZON = (188, 205, 232)
ZENITH = (58, 106, 178)
GROUND = (74, 68, 60)


def face(name):
    px = []
    for y in range(SIZE):
        v = y / (SIZE - 1)
        for x in range(SIZE):
            if name == 'top':
                # radial falloff from zenith at centre to horizon at edges
                dx, dy = (x / SIZE - .5) * 2, (y / SIZE - .5) * 2
                t = min(1.0, math.hypot(dx, dy))
                px.append(lerp(ZENITH, HORIZON, t))
            elif name == 'bottom':
                px.append(GROUND)
            else:
                # side faces: zenith at the top, horizon at the bottom
                px.append(lerp(ZENITH, HORIZON, v))
    return px


out = os.path.join(os.path.dirname(__file__), 'examples/3d_engine/textures/skybox1')
os.makedirs(out, exist_ok=True)
for f in ('left', 'right', 'top', 'bottom', 'front', 'back'):
    png(os.path.join(out, f + '.png'), face(f), SIZE, SIZE)
    print('wrote', f + '.png')
