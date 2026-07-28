#!/bin/bash
#
# pack.sh — Pack hello_pygame into a .wasc cart
#
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$HERE/../.."

if [ ! -f "$ROOT/out/cart.wasm" ]; then
    echo "ERROR: cart.wasm not found. Run build.sh first."
    exit 1
fi

# Pack: cart.wasm + game files -> .wasc
npx wasmcart-pack \
    --wasm "$ROOT/out/cart.wasm" \
    --assets "$HERE/" \
    --name "Hello Pygame" \
    --pointer \
    --keyboard \
    -o "$ROOT/out/hello_pygame.wasc"

echo "Created: out/hello_pygame.wasc"
