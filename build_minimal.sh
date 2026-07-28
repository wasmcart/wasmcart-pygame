#!/bin/bash
#
# build_minimal.sh — Build minimal Python cart (no pygame, no SDL)
#
# Proves: CPython boots in a wasmcart, loads .py from .wasc assets,
#         Python code writes pixels to framebuffer.
#

set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
cd "$HERE"

# ── Paths ────────────────────────────────────────────────────────────

EMSDK_ROOT="$(cd ../emsdk && pwd)"
source "$EMSDK_ROOT/emsdk_env.sh" 2>/dev/null || true

# CPython for wasm. vendor/ by convention (the sibling runtimes vendor their
# VM the same way) and NEVER /tmp, which is wiped on reboot -- the previous
# default, and why nothing here could be rebuilt. Overridable for a shared
# build tree.
CPYTHON_SRC="${CPYTHON_SRC:-$HERE/vendor/cpython}"
CPYTHON_BUILD="${CPYTHON_BUILD:-$CPYTHON_SRC/builddir/emscripten-node-dl}"
LIBPYTHON="$CPYTHON_BUILD/libpython3.13.a"
PY_INCLUDE="$CPYTHON_SRC/Include"
PY_INTERNAL_INCLUDE="$CPYTHON_BUILD"
# The ABI header ships in the wasmcart package's include/. It used to be read
# out of a wasmcart-examples checkout, which is a sibling repo this project
# should not need just for a header.
WASMCART_REPO="${WASMCART_REPO:-$HERE/../wasmcart}"
WASMCART_H="$WASMCART_REPO/include/wasmcart.h"
LIBMPDEC="$CPYTHON_BUILD/Modules/_decimal/libmpdec/libmpdec.a"
LIBEXPAT="$CPYTHON_BUILD/Modules/expat/libexpat.a"
LIBHACL="$CPYTHON_BUILD/Modules/_hacl/libHacl_Hash_SHA2.a"

if [ ! -f "$LIBPYTHON" ]; then
    echo "ERROR: libpython3.13.a not found at $LIBPYTHON"
    echo "Build CPython first:  bash setup_cpython.sh"
    exit 1
fi

mkdir -p out obj

# ── Compile cart shim ────────────────────────────────────────────────

echo "=== Compiling cart_shim_minimal.c ==="
emcc -O2 \
    -I"$PY_INCLUDE" \
    -I"$PY_INTERNAL_INCLUDE" \
    -I"$(dirname $WASMCART_H)" \
    -c src/cart_shim_minimal.c -o obj/cart_shim_minimal.o

# ── Compile emstubs ──────────────────────────────────────────────────

echo "=== Compiling stubs ==="
emcc -O2 -c "${WASMCART_SDL2:-$HERE/../wasmcart-sdl2}/emstubs.c" -o obj/emstubs.o
emcc -O2 -c src/pystubs.c -o obj/pystubs.o

echo "=== Compiling OpenGL module ==="
emcc -O2 -I"$PY_INCLUDE" -I"$PY_INTERNAL_INCLUDE" -c src/opengl_module.c -o obj/opengl_module.o

# ── Link ─────────────────────────────────────────────────────────────

echo "=== Preparing minimal stdlib ==="
STDLIB_DIR="${STDLIB_DIR:-$HERE/vendor/pystdlib}"
if [ ! -d "$STDLIB_DIR/lib/python3.13/encodings" ]; then
    mkdir -p "$STDLIB_DIR/lib/python3.13/encodings"
    mkdir -p "$STDLIB_DIR/lib/python3.13/importlib"
    # Essential boot modules
    for f in encodings/__init__.py encodings/aliases.py encodings/utf_8.py \
             encodings/ascii.py encodings/latin_1.py; do
        cp /usr/lib/python3.13/$f "$STDLIB_DIR/lib/python3.13/$f" 2>/dev/null || true
    done
    for f in io.py abc.py codecs.py _collections_abc.py; do
        cp /usr/lib/python3.13/$f "$STDLIB_DIR/lib/python3.13/$f" 2>/dev/null || true
    done
    for f in importlib/__init__.py importlib/abc.py importlib/machinery.py; do
        cp /usr/lib/python3.13/$f "$STDLIB_DIR/lib/python3.13/$f" 2>/dev/null || true
    done
fi

echo "=== Linking cart.wasm ==="

# Embed the minimal stdlib into the WASM binary via Emscripten's
# virtual filesystem. CPython needs encodings + codecs at boot time.
# After boot, our import hook loads game .py files from .wasc assets.

emcc -O2 \
    -sSTANDALONE_WASM=1 \
    -sALLOW_MEMORY_GROWTH=1 \
    -sMAXIMUM_MEMORY=536870912 \
    -sERROR_ON_UNDEFINED_SYMBOLS=0 \
    -sTOTAL_STACK=2097152 \
    -sUSE_ZLIB \
    -sUSE_BZIP2 \
    --no-entry \
    -sEXPORTED_FUNCTIONS='["_wc_get_info","_wc_init","_wc_render"]' \
    obj/cart_shim_minimal.o \
    obj/emstubs.o \
    obj/pystubs.o \
    obj/opengl_module.o \
    "$LIBPYTHON" \
    "$LIBMPDEC" \
    "$LIBEXPAT" \
    "$LIBHACL" \
    -o out/cart_minimal.wasm

WASM_SIZE=$(wc -c < out/cart_minimal.wasm)
echo ""
echo "=== Build complete ==="
echo "  out/cart_minimal.wasm ($WASM_SIZE bytes, $(( WASM_SIZE / 1024 / 1024 )) MB)"
echo ""
echo "Pack a game:"
echo "  npx wasmcart-pack --wasm out/cart_minimal.wasm --assets examples/hello_python/ -o out/hello_python.wasc"
