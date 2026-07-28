#!/bin/bash
# setup_pygame.sh — fetch pygame-ce into vendor/ for build_full.sh.
# Pinned so a cart built today is reproducible tomorrow.
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
PYGAME_SRC="${PYGAME_SRC:-$HERE/vendor/pygame-ce}"
PYGAME_TAG="${PYGAME_TAG:-2.5.2}"
if [ -d "$PYGAME_SRC" ]; then echo "=== pygame-ce already present ==="; exit 0; fi
mkdir -p "$(dirname "$PYGAME_SRC")"
git clone --depth 1 --branch "$PYGAME_TAG" \
  https://github.com/pygame-community/pygame-ce.git "$PYGAME_SRC"
echo "fetched pygame-ce $PYGAME_TAG -> $PYGAME_SRC"
