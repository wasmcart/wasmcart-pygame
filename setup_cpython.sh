#!/bin/bash
#
# setup_cpython.sh — fetch and build CPython for wasm into vendor/cpython.
#
# Run once. build_minimal.sh / build_full.sh consume libpython3.13.a from the
# resulting builddir. Everything lands under vendor/ (gitignored) rather than
# /tmp, which is wiped on reboot and left this project unbuildable.
#
# Override CPYTHON_SRC to share one build tree across checkouts.
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
CPYTHON_SRC="${CPYTHON_SRC:-$HERE/vendor/cpython}"
CPYTHON_TAG="${CPYTHON_TAG:-v3.13.1}"

command -v emcc >/dev/null || { echo "emcc not found: source emsdk_env.sh first" >&2; exit 1; }

# CPython's wasm_build.py checks EM_CONFIG explicitly; emsdk_env.sh does not
# always export it, so derive it from where emcc actually lives.
if [ -z "$EM_CONFIG" ]; then
  EMSDK_ROOT="$(dirname "$(dirname "$(dirname "$(command -v emcc)")")")"
  [ -f "$EMSDK_ROOT/.emscripten" ] && export EM_CONFIG="$EMSDK_ROOT/.emscripten"
fi

if [ ! -d "$CPYTHON_SRC" ]; then
  echo "=== fetching CPython $CPYTHON_TAG ==="
  mkdir -p "$(dirname "$CPYTHON_SRC")"
  git clone --depth 1 --branch "$CPYTHON_TAG" \
    https://github.com/python/cpython.git "$CPYTHON_SRC"
fi

BUILD="$CPYTHON_SRC/builddir/emscripten-node-dl"
if [ -f "$BUILD/libpython3.13.a" ]; then
  echo "=== libpython3.13.a already built ==="
  exit 0
fi

echo "=== building CPython for emscripten (this takes a while) ==="
cd "$CPYTHON_SRC"
# The build needs a matching host python to run its own scripts.
python3 Tools/wasm/wasm_build.py emscripten-node-dl build

[ -f "$BUILD/libpython3.13.a" ] \
  && echo "built $BUILD/libpython3.13.a" \
  || { echo "build finished but libpython3.13.a is missing" >&2; exit 1; }
