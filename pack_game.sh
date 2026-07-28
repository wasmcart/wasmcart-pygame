#!/bin/bash
#
# pack_game.sh — Pack a Python game into a .wasc cart
#
# Usage: bash pack_game.sh <game_dir> <output.wasc> [name]
#
# Bundles: cart.wasm + stdlib/ + game assets
#

set -e
HERE="$(cd "$(dirname "$0")" && pwd)"

GAME_DIR="${1:?Usage: pack_game.sh <game_dir> <output.wasc> [name]}"
OUTPUT="${2:?Usage: pack_game.sh <game_dir> <output.wasc> [name]}"
NAME="${3:-Python Game}"

CART_WASM="$HERE/out/cart.wasm"
# Fall back to minimal if full build doesn't exist
if [ ! -f "$CART_WASM" ]; then
    CART_WASM="$HERE/out/cart_minimal.wasm"
fi
STDLIB_SRC="/usr/lib/python3.13"

if [ ! -f "$CART_WASM" ]; then
    echo "ERROR: cart.wasm not found. Run build_minimal.sh first."
    exit 1
fi

# Create temp directory with combined assets
TMPDIR=$(mktemp -d)
trap "rm -rf $TMPDIR" EXIT

# Copy game files
cp -r "$GAME_DIR"/* "$TMPDIR/"

# Copy only the stdlib modules that games actually need
# (boot modules like encodings/codecs are frozen in cart.wasm)
mkdir -p "$TMPDIR/stdlib"
# Copy the stdlib, dropping what a cart cannot reach. A wasmcart has no
# filesystem, no sockets, no threads and no subprocesses, so asyncio,
# multiprocessing, http/urllib/email and friends can never run -- they were
# adding ~9 MB of dead weight to every cart.
#
# encodings/ is the one big directory that must stay: Python needs a codec
# search path at import time, and a missing codec fails at boot rather than
# at use.
# NOTE: excludes must precede the includes -- rsync takes the FIRST matching
# rule, so --include='*/' ahead of them re-admits every directory and the
# excludes never fire.
rsync -a \
    --exclude='__pycache__' --exclude='test/' --exclude='tests/' \
    --exclude='idlelib/' --exclude='tkinter/' --exclude='turtledemo/' \
    --exclude='ensurepip/' --exclude='lib2to3/' --exclude='distutils/' \
    --exclude='pydoc_data/' --exclude='asyncio/' --exclude='multiprocessing/' \
    --exclude='concurrent/' --exclude='email/' --exclude='http/' \
    --exclude='urllib/' --exclude='xmlrpc/' --exclude='wsgiref/' \
    --exclude='sqlite3/' --exclude='venv/' --exclude='zoneinfo/' \
    --exclude='unittest/' --exclude='pydoc.py' --exclude='doctest.py' \
    --include='*/' --include='*.py' --exclude='*' \
    "$STDLIB_SRC/" "$TMPDIR/stdlib/"
# Remove empty dirs
find "$TMPDIR/stdlib" -type d -empty -delete 2>/dev/null || true

# Copy pygame-ce Python files (colordict, cursors, _data_classes, _sprite, etc.)
# The C extensions are built-in but they need some Python helper modules
PYGAME_SRC="${PYGAME_SRC:-$HERE/vendor/pygame-ce}"
if [ -d "$PYGAME_SRC/src_py" ]; then
    mkdir -p "$TMPDIR/stdlib/pygame"
    cp "$PYGAME_SRC"/src_py/*.py "$TMPDIR/stdlib/pygame/" 2>/dev/null || true
    # _sdl2 subpackage
    if [ -d "$PYGAME_SRC/src_py/_sdl2" ]; then
        mkdir -p "$TMPDIR/stdlib/pygame/_sdl2"
        cp "$PYGAME_SRC"/src_py/_sdl2/*.py "$TMPDIR/stdlib/pygame/_sdl2/" 2>/dev/null || true
    fi
    # Remove __init__.py — we don't want the import hook to find it,
    # since the C module IS the package
    rm -f "$TMPDIR/stdlib/pygame/__init__.py"
fi

# Copy extra stdlib shims (moderngl, glm, etc.)
EXTRA_STDLIB="$HERE/stdlib_extra"
if [ -d "$EXTRA_STDLIB" ]; then
    cp -r "$EXTRA_STDLIB"/* "$TMPDIR/stdlib/" 2>/dev/null || true
    # Copy default font
    cp "$PYGAME_SRC/src_py/freesansbold.ttf" "$TMPDIR/stdlib/pygame/" 2>/dev/null || true
fi

# Remove empty directories
find "$TMPDIR/stdlib" -type d -empty -delete 2>/dev/null || true

# Declare the game's resolution so the host can size its window -- and a
# self-provisioned GL context -- before the cart runs. pygame's set_mode()
# happens inside wc_init, far too late: a 1600x900 game was announced as
# 640x480 and rendered into a corner of the context.
RES="$(python3 "$HERE/tools/find_resolution.py" "$GAME_DIR" 2>/dev/null || true)"
RES_W="${RES%x*}"; RES_H="${RES#*x}"
if [ -n "$RES" ]; then
    printf '%s' "$RES" > "$TMPDIR/resolution.txt"
    echo "Resolution: $RES"
fi

echo "Game assets: $(find "$TMPDIR" -path "$TMPDIR/stdlib" -prune -o -type f -print | wc -l) files"
echo "Stdlib: $(find "$TMPDIR/stdlib" -name "*.py" | wc -l) .py files"

# Pack
RES_ARGS=""
[ -n "$RES_W" ] && [ -n "$RES_H" ] && RES_ARGS="--width $RES_W --height $RES_H"

node "$HERE/../wasmcart/bin/wasmcart-pack.js" \
    --wasm "$CART_WASM" \
    --assets "$TMPDIR/" \
    --name "$NAME" \
    $RES_ARGS \
    --keyboard \
    --pointer \
    -o "$OUTPUT"
