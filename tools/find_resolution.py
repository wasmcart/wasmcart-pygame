#!/usr/bin/env python3
"""
Report a game's resolution as WxH. Always prints something.

A host sizes its window -- and a self-provisioned GL context -- before the
cart runs, so the resolution has to be known at pack time. Scraped from the
game's own source rather than configured separately, so there is nothing to
keep in sync.

A game that declares no resolution gets cart_shim.c's DEFAULT_WIDTH/HEIGHT,
which is what it will report anyway. Printing that explicitly, rather than
staying silent and letting the manifest omit the field, means the manifest
always states the resolution: omitting it only works while the host's own
fallback happens to match the shim's, which is a coincidence and not a
contract.

Recognizes the forms these examples actually use:
    RES = WIDTH, HEIGHT = 1600, 900
    WIDTH, HEIGHT = 480, 600
    WIDTH = 480  /  HEIGHT = 600
    setWindowSize(640, 480)  /  set_mode((800, 600))
    win_size=(800, 600)   as a default argument
"""
import re, sys, os, glob

HERE = os.path.dirname(os.path.abspath(__file__))
MIN, MAX = 64, 4096


def shim_defaults():
    """DEFAULT_WIDTH/HEIGHT from cart_shim.c, the size a cart that declares
    nothing will actually report. Read from the C rather than duplicated here,
    so the two cannot drift apart silently."""
    shim = os.path.join(HERE, '..', 'src', 'cart_shim.c')
    got = {}
    try:
        with open(shim, encoding='utf-8', errors='ignore') as fh:
            for line in fh:
                m = re.match(r'\s*#define\s+DEFAULT_(WIDTH|HEIGHT)\s+(\d+)', line)
                if m:
                    got[m.group(1)] = int(m.group(2))
    except OSError:
        pass
    return got.get('WIDTH', 640), got.get('HEIGHT', 480)


SHIM_DEFAULT_W, SHIM_DEFAULT_H = shim_defaults()


def plausible(w, h):
    return MIN <= w <= MAX and MIN <= h <= MAX


def scan(text):
    # explicit call sites first: least ambiguous
    for pat in (r'setWindowSize\(\s*(\d+)\s*,\s*(\d+)\s*\)',
                r'set_mode\(\s*\(\s*(\d+)\s*,\s*(\d+)\s*\)',
                r'setViewportSize\(\s*(\d+)\s*,\s*(\d+)\s*\)'):
        m = re.search(pat, text)
        if m:
            w, h = int(m.group(1)), int(m.group(2))
            if plausible(w, h):
                return w, h

    # RES = WIDTH, HEIGHT = 1600, 900
    m = re.search(r'^\s*RES\s*=\s*WIDTH\s*,\s*HEIGHT\s*=\s*(\d+)\s*,\s*(\d+)',
                  text, re.M)
    if m:
        w, h = int(m.group(1)), int(m.group(2))
        if plausible(w, h):
            return w, h

    # WIDTH, HEIGHT = 480, 600   (no RES on the left)
    m = re.search(r'^\s*WIDTH\s*,\s*HEIGHT\s*=\s*(\d+)\s*,\s*(\d+)', text, re.M)
    if m:
        w, h = int(m.group(1)), int(m.group(2))
        if plausible(w, h):
            return w, h

    # win_size=(800, 600) as a default argument
    m = re.search(r'win_size\s*=\s*\(\s*(\d+)\s*,\s*(\d+)\s*\)', text)
    if m:
        w, h = int(m.group(1)), int(m.group(2))
        if plausible(w, h):
            return w, h

    # separate WIDTH = / HEIGHT = assignments
    mw = re.search(r'^\s*WIDTH\s*=\s*(\d+)\s*$', text, re.M)
    mh = re.search(r'^\s*HEIGHT\s*=\s*(\d+)\s*$', text, re.M)
    if mw and mh:
        w, h = int(mw.group(1)), int(mh.group(1))
        if plausible(w, h):
            return w, h
    return None


def main():
    d = sys.argv[1]
    # main.py and settings.py first -- a resolution in a helper module is
    # more likely to be a texture size than the window size.
    files = ([os.path.join(d, n) for n in ('main.py', 'settings.py')
              if os.path.exists(os.path.join(d, n))]
             + sorted(glob.glob(os.path.join(d, '*.py'))))
    seen = set()
    for f in files:
        if f in seen:
            continue
        seen.add(f)
        try:
            hit = scan(open(f, encoding='utf-8', errors='ignore').read())
        except OSError:
            continue
        if hit:
            print(f'{hit[0]}x{hit[1]}')
            return
    # Nothing declared in the Python: the cart will report cart_shim.c's
    # DEFAULT_WIDTH/HEIGHT. Emit that explicitly rather than staying silent,
    # so the manifest always states the resolution. Leaving it out only works
    # while the host's own fallback happens to match this one -- a coincidence,
    # not a contract, and exactly the kind that breaks quietly later.
    print(f'{SHIM_DEFAULT_W}x{SHIM_DEFAULT_H}')


if __name__ == '__main__':
    main()
