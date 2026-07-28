#!/usr/bin/env python3
"""
Report a game's declared resolution as WxH, or nothing if it cannot be found.

A host sizes its window -- and a self-provisioned GL context -- before the
cart runs, so the resolution has to be known at pack time. Scraped from the
game's own source rather than configured separately, so there is nothing to
keep in sync.

Recognizes the three forms these examples actually use:
    RES = WIDTH, HEIGHT = 1600, 900
    WIDTH = 480  /  HEIGHT = 600
    setWindowSize(640, 480)  /  set_mode((800, 600))
"""
import re, sys, os, glob

MIN, MAX = 64, 4096


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
    # nothing found: caller falls back to the cart default


if __name__ == '__main__':
    main()
