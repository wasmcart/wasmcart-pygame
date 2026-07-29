#!/bin/bash
#
# build_full.sh — Build the complete pygame cart.wasm
#
# Includes: CPython 3.13 + pygame-ce + SDL2 (sdl2_wc) + OpenGL shim + frozen stdlib
#
# Output: out/cart.wasm (~15-20 MB) — reusable across all pygame games
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

# sdl2_wc + the porting helpers moved out of wasmcart into their own repo.
# Overridable so a checkout elsewhere still builds.
WASMCART_SDL2="${WASMCART_SDL2:-$HERE/../wasmcart-sdl2}"
SDL2_WC="$WASMCART_SDL2/sdl2_wc"
PORTING="$WASMCART_SDL2"

PYGAME_SRC="${PYGAME_SRC:-$HERE/vendor/pygame-ce}"

if [ ! -f "$LIBPYTHON" ]; then
    echo "ERROR: libpython3.13.a not found. Build CPython first."
    exit 1
fi

if [ ! -d "$PYGAME_SRC/src_c" ]; then
    echo "ERROR: pygame-ce not found at $PYGAME_SRC"
    echo "Clone it:  bash setup_pygame.sh"
    exit 1
fi

mkdir -p out obj/pygame

# ── Step 1: Build libSDL2_wc.a if needed ────────────────────────────

if [ ! -f "$SDL2_WC/lib/libSDL2_wc.a" ]; then
    echo "=== Building libSDL2_wc.a ==="
    cd "$SDL2_WC" && bash build_sdl2_wc.sh && cd "$HERE"
fi

# ── Step 2: Compile pygame-ce C extensions ───────────────────────────

echo "=== Compiling pygame-ce ==="

# SDL2 headers from Emscripten's port cache
SDL2_SRC="$EMSDK_ROOT/upstream/emscripten/cache/ports/sdl2/SDL-release-2.32.8"
if [ ! -d "$SDL2_SRC" ]; then
    # Trigger download
    echo '#include <SDL.h>' > /tmp/_sdl2_trigger.c
    emcc -sUSE_SDL=2 -c /tmp/_sdl2_trigger.c -o /dev/null 2>/dev/null || true
    rm -f /tmp/_sdl2_trigger.c
fi

# pygame-ce: compile individual modules
PYGAME_CFLAGS="-O0 -sUSE_SDL=2 -sUSE_SDL_MIXER=2 -sUSE_SDL_IMAGE=2 \
    -sUSE_FREETYPE=1 -sUSE_SDL_TTF=2 \
    -DBUILD_STATIC -DSDL2 -D_REENTRANT \
    -DPG_MAJOR_VERSION=2 -DPG_MINOR_VERSION=5 -DPG_PATCH_VERSION=0 \
    -DPG_VERSION_TAG_EMPTY -include $HERE/src/pg_version_fix.h \
    -I$PY_INCLUDE -I$PY_INTERNAL_INCLUDE \
    -I$PYGAME_SRC/src_c -I$PYGAME_SRC/src_c/include \
    -I$(dirname $WASMCART_H) \
    -Wno-incompatible-pointer-types \
    -Wno-int-conversion \
    -Wno-deprecated-declarations \
    -Wno-unused-variable \
    -Wno-unused-function \
    -Wno-macro-redefined"

# Upstream's static.c still #includes _sdl2/controller_old.c, which they
# deleted, so BUILD_STATIC cannot compile as shipped. Idempotent.
python3 "$HERE/patch_pygame.py" "$PYGAME_SRC/src_c/static.c"

# BUILD_STATIC: static.c is the aggregation unit -- it #includes rect.c,
# display.c, font.c and the rest. Compiling base.c instead (as this did)
# builds ONLY pygame.base, so `import pygame` succeeds while every submodule
# is missing: "module 'pygame' has no attribute 'display'".
#
# Errors are no longer swallowed. These lines used to end in
# `2>&1 | grep error || true`, which discards the compiler's exit status --
# a failed pygame build then linked anyway and surfaced as a runtime
# AttributeError instead of a build failure.
emcc $PYGAME_CFLAGS -c "$PYGAME_SRC/src_c/SDL_gfx/SDL_gfxPrimitives.c" \
    -o obj/pygame/SDL_gfxPrimitives.o
emcc $PYGAME_CFLAGS -c "$PYGAME_SRC/src_c/static.c" -o obj/pygame/base_static.o

# constants.c and math.c are NOT #included by static.c, but their PyInit_*
# are called by it. Left out, they stay unresolved and -- with
# ERROR_ON_UNDEFINED_SYMBOLS=0 -- become imports that trap the moment
# PyInit_pygame_static is entered. Compile them alongside.
# static.c calls into these but does not #include them. Compiled separately
# so every symbol it references actually resolves; with
# ERROR_ON_UNDEFINED_SYMBOLS=1 a missing one is now a link error rather than
# a runtime trap.
for extra in constants math bitmask geometry_common circle line rotozoom \
             pgcompat; do
  [ -f "$PYGAME_SRC/src_c/$extra.c" ] || continue
  emcc $PYGAME_CFLAGS -c "$PYGAME_SRC/src_c/$extra.c" -o "obj/pygame/$extra.o"
done
echo "  pygame-ce compiled (BUILD_STATIC, static.c aggregation unit)"

rm -f obj/libpygame.a
emar rcs obj/libpygame.a obj/pygame/*.o
echo "  obj/libpygame.a ($(wc -c < obj/libpygame.a) bytes)"

# ── Step 3: Compile cart shim + OpenGL module + stubs ────────────────

echo "=== Compiling cart shim ==="
emcc -O2 -sUSE_SDL=2 -sUSE_SDL_TTF=2 -sUSE_SDL_IMAGE=2 -sUSE_SDL_MIXER=2 -sUSE_FREETYPE=1 \
    -I"$PY_INCLUDE" -I"$PY_INTERNAL_INCLUDE" \
    -I"$(dirname $WASMCART_H)" -I"$SDL2_WC" -I"$PORTING/include" \
    -I"$PYGAME_SRC/src_c" -I"$PYGAME_SRC/src_c/include" \
    -DPG_MAJOR_VERSION=2 -DPG_MINOR_VERSION=5 -DPG_PATCH_VERSION=0 \
    -DPG_VERSION_TAG_EMPTY -include $HERE/src/pg_version_fix.h \
    -c src/cart_shim.c -o obj/cart_shim.o

echo "=== Compiling OpenGL module ==="
emcc -O2 -I"$PY_INCLUDE" -I"$PY_INTERNAL_INCLUDE" \
    -c src/opengl_module.c -o obj/opengl_module.o

echo "=== Compiling stubs ==="
emcc -O2 -c src/pystubs.c -o obj/pystubs.o
# invoke_stubs includes emscripten runtime stubs (superset of emstubs.c)
emcc -O2 -sUSE_SDL=2 -I"$SDL2_WC" -c "$SDL2_WC/invoke_stubs.c" -o obj/invoke_stubs.o

echo "=== Compiling gl4es stubs ==="
emcc -O2 -c "$HERE/src/gl4es_stub.c" -o obj/gl4es_stub.o
emcc -O2 -c "$HERE/src/sqlite3_stub.c" -o obj/sqlite3_stub.o

echo "=== Compiling GL blit ==="
emcc -O2 -I"$(dirname $WASMCART_H)" -I"$PORTING" \
    -c "$SDL2_WC/sdl2_gl_blit.c" -o obj/sdl2_gl_blit.o

# ── Step 4: Link everything ──────────────────────────────────────────

echo "=== Linking cart.wasm ==="

# All libraries
LIBS="
    obj/cart_shim.o
    obj/opengl_module.o
    obj/pystubs.o
    obj/invoke_stubs.o
    obj/sdl2_gl_blit.o \
    obj/gl4es_stub.o \
    obj/sqlite3_stub.o
    obj/libpygame.a
    $SDL2_WC/lib/libSDL2_wc.a
    $LIBPYTHON
    $LIBMPDEC
    $LIBEXPAT
    $LIBHACL
"

# SDL_ttf if available
if [ -f "$SDL2_WC/lib/libSDL2_ttf_wc.a" ]; then
    LIBS="$LIBS $SDL2_WC/lib/libSDL2_ttf_wc.a"
fi

# ERROR_ON_UNDEFINED_SYMBOLS=1: undefined symbols must be a LINK error, not
# silent imports that trap at call time. With it off, six pygame PyInit_*
# symbols went unresolved and PyInit_pygame_static trapped the instant it was
# entered -- a bare `unreachable` with no diagnostic, which is what made this
# look like a data-segment mystery for months.
#
# INITIAL_MEMORY: 40 MB was not enough. CPython's heap plus pygame's
# 31-module static init overran it, and PyInit_pygame_static trapped with
# "memory access out of bounds" before its first statement -- which surfaced
# as a bare `unreachable` with no diagnostic. Growth is enabled, but the
# initial block still has to cover init itself.
emcc -O2 \
    -sSTANDALONE_WASM=1 \
    -sALLOW_MEMORY_GROWTH=1 \
    -sINITIAL_MEMORY=134217728 \
    -sMAXIMUM_MEMORY=1073741824 \
    -sERROR_ON_UNDEFINED_SYMBOLS=1 \
    -sTOTAL_STACK=4194304 \
    -sUSE_SDL=0 \
    -sUSE_SDL_MIXER=2 \
    -sSDL2_MIXER_FORMATS="['ogg','mod']" \
    -sUSE_SDL_IMAGE=2 \
    -sSDL2_IMAGE_FORMATS="['png','jpg','gif']" \
    -sUSE_FREETYPE=1 \
    -sUSE_ZLIB \
    -sUSE_BZIP2 \
    --no-entry \
    -sEXPORTED_FUNCTIONS='["_wc_get_info","_wc_init","_wc_render"]' \
    -Wl,--wrap=SDL_Delay \
    -Wl,--wrap=SDL_GetTicks \
    -Wl,--wrap=SDL_GetTicks64 \
    $LIBS \
    -o out/cart.wasm

WASM_SIZE=$(wc -c < out/cart.wasm)
echo ""
echo "=== Build complete ==="
echo "  out/cart.wasm ($WASM_SIZE bytes, $(( WASM_SIZE / 1024 / 1024 )) MB)"
echo ""
echo "Pack a game:"
echo "  bash pack_game.sh examples/hello_pygame/ out/my_game.wasc \"My Game\""
