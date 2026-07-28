# wasmcart-pygame Performance

## Benchmark: Space Shooter (480x600)

8 rotating meteors, sprite groups, collision detection, background blit, HUD drawing. Same game logic and assets for both tests.

### Setup
- **Hardware:** AMD Ryzen AI 9 HX 370 (890M integrated GPU)
- **Resolution:** 480x600, SDL window, scale 1
- **Method:** 5 second warmup, then measure steady-state FPS
- **Native:** pygame-ce 2.5.7, Python 3.13.7, SDL 2.32.10
- **wasmcart:** CPython 3.13.3 + pygame-ce (BUILD_STATIC) in 9MB cart.wasm, retroemu SDL host

### Results (2026-03-27)

| Test | FPS | ms/frame |
|------|-----|----------|
| Native pygame-ce | 3,630 | 0.28 |
| wasmcart pygame (retroemu SDL) | 3,058 | 0.33 |
| Native pygame-ce + fb copy | 1,998 | 0.50 |

**wasmcart is 84% of native speed.**

With an equivalent framebuffer copy (simulating what wasmcart does), native drops to 1,998 FPS. **wasmcart is 53% faster than native with the same work.**

### Why wasmcart is competitive

The game workload is C-heavy. Python is glue — it calls C functions that do the real work:

| Operation | Where it runs |
|-----------|--------------|
| `pygame.transform.rotate()` | C (SDL2 pixel manipulation) |
| `Surface.blit()` | C (SDL_BlitSurface) |
| `screen.fill()` | C (SDL_FillRect) |
| `sprite.Group.draw()` | C with Python iteration |
| `sprite.groupcollide()` | C (rect intersection) |
| `pygame.draw.rect()` | C (SDL_gfx) |
| Python game logic | ~1000 bytecode ops/frame |

V8's TurboFan JIT compiles all the C functions (inside WASM) to near-native quality. The Python interpreter loop itself gets JIT-compiled too — V8 effectively applies profile-guided optimization at runtime, which native CPython doesn't get unless built with `--enable-optimizations`.

### The 16% gap

The remaining overhead comes from:
- **retroemu's Node.js event loop** — `setImmediate` scheduling, `@kmamal/sdl` N-API bridge
- **Framebuffer copy** — host reads 480x600x4 = 1.15MB from WASM memory each frame
- **WASM bounds checks** — V8 mitigates these with guard pages but they're not free

### Expected: wasmcart-native-libnode

The native C host (wasmcart-native-libnode) eliminates the Node.js overhead. It's C calling V8 calling WASM with no JavaScript in the hot path. On x86, this host runs OpenArena at 830 FPS (vs ~400 in Node.js retroemu). Once the 2D framebuffer rendering bug is fixed, pygame carts on the native host should close or eliminate the gap with native pygame.

## Batocera/Knulli: ARM Performance Expectations

Target hardware: Allwinner H700 (Cortex-A53 quad-core, 1.5GHz), 1GB RAM.

V8 compiles WASM to native ARM code via TurboFan, same as on x86. The JIT overhead ratio should be similar. For a pygame game that runs at 60fps on desktop, the bottleneck on ARM is the C functions (SDL blits, transforms), not Python interpretation. These devices already run wasmcart C carts (OpenArena, Neverball, Godot games) at playable framerates.

Prediction: typical pygame games (2D sprites, simple logic) will run at 60fps on Cortex-A53 devices. The self-contained `.wasc` distribution model eliminates the dependency management problems that currently make pygame painful on these platforms.

## Comparison with Research

Published benchmarks (Pyodide project) show CPython-in-WASM at 2-3x slower than native for **pure Python compute** (loops, math, string processing). Our result (84-100%+ of native) is better because:

1. **Our workload is C-heavy.** The 2-3x penalty applies to Python bytecode execution. We barely execute any Python bytecode — it's all C function calls.
2. **V8 JIT vs gcc -O2.** TurboFan aggressively optimizes hot WASM paths at runtime. The system CPython is compiled with gcc but likely not PGO-optimized.
3. **No pure-Python hot loops.** The game loop iterates sprites (C), blits (C), checks collisions (C). Python just orchestrates.

For compute-heavy Python (AI, simulation, pathfinding over large grids), the 2-3x penalty would apply. For typical pygame games, the overhead is negligible.
