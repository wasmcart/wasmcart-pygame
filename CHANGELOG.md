# Changelog

## 0.3.0

**Game time follows the host's frame clock.** `pygame.time.get_ticks()`, `Clock.tick()`, `Clock.get_time()` and
`Clock.get_fps()` read `wc_time.time_ms`, which the host writes before every frame and already clamps to 250 ms per
frame. The runtime used to advance a fixed 16.667 ms per frame whatever the host reported, so every game timed in
milliseconds ran twice as fast on a 120 Hz display. A seeded run (`--seed`, or `deterministic: {seed, stepMs}` in
`CartHost.load`) gets the host's fixed step, 16.667 ms by default, so frame N stays reproducible. A headless run without
a seed gets real time, like any other host; the repo's harnesses now pass a seed.

**`time.monotonic()`, `time.perf_counter()` and `time.time()` read the same clock.** They read the WASI wall clock
before, so a game that measured its frame time with them disagreed with `get_ticks()` and was not reproducible under a
seed. `time.time()` keeps a real calendar origin and advances with game time. The minimal (no pygame) engine gets the
same patch and a `_wasmcart.game_ms()` call.

**`pygame.time.delay()` and `Clock.tick_busy_loop()` no longer hang the cart.** Both spun until the clock advanced, and
a cart's clock does not move inside a frame. They now return at once, as `pygame.time.wait()` already did
(`patch_pygame.py`).

**Checks.** `tests/verify-clock.mjs` runs a probe cart seeded at 16.667 ms (twice, bit-identical), seeded at 8.333 ms
and on the real clock with 40 ms between frames, and checks every clock against `wc_time` and a 1200 ms splash handoff
under each. The 0.2.1 engine fails 14 of its 21 checks. `tools/drive_cart.mjs` takes `--seed` and `--step-ms` and runs
seeded by default, `tools/test_rumble.mjs` runs seeded, `tools/check_render.mjs` reads RGBA PNGs, and
`pack_game.sh` takes `CART_WASM` to pack another engine.

Built against wasmcart 0.41.1 (ABI v4); packed manifests say `"abi": 4`.

## 0.2.1

Carts carry their real version, taken from the game directory's git checkout (wasmcart-pack `--version-from`) or
`CART_VERSION`. The ABI v4 pad reaches Python with the right field types.

## 0.2.0

The SolarWolf port and the eight runtime gaps it found, `pygame.surfarray` with live pixel views, gamepad rumble
through `pygame.joystick`, fonts in packed carts, and the doom_py example renamed to boom_py.

## 0.1.0

First release: CPython 3.13 and pygame-ce as one reusable `cart.wasm`, with eight playable carts.
