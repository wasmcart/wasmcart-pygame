# wasmcart-pygame Research

## Goal

Run pygame games as `.wasc` carts. Developer writes `.py` files, packs them into a `.wasc`, game runs on every wasmcart host (browser, terminal, ARM handheld).

The `cart.wasm` is a **reusable runtime** — built once. Every pygame game is just different assets in the `.wasc` ZIP. Same cart.wasm, different `assets/`.

---

## Approaches Ranked by Feasibility

### Approach 1: MicroPython + Custom C Graphics Layer (Smallest, Fastest to Prototype)

**What**: Compile MicroPython to WASM with a custom C module providing pygame-like drawing/input/audio functions that call wasmcart imports internally.

**Size**: ~300KB–1MB for interpreter + graphics layer.

**Pros**:
- Tiny binary, fast startup
- MicroPython compiles cleanly to WASM (proven: `micropython-wasm`)
- No Emscripten dependency needed — can build with wasi-sdk or clang directly
- Custom C module has direct access to wasmcart framebuffer/audio/input
- Could have a working prototype in days

**Cons**:
- **Not real pygame**. Games need adaptation or a compatibility shim
- MicroPython's Python compatibility is a subset (no full stdlib, no C extensions)
- Would need to write a `micropygame` module from scratch (draw, Surface, Rect, image loading, mixer)
- Limited ecosystem — no pip packages, no numpy

**Implementation sketch**:
```c
// micropygame.c — C module registered in MicroPython
#include "py/runtime.h"
#include "wasmcart.h"

// mp_pygame_draw_rect(surface, color, rect)
// → writes directly to wc_framebuffer
```

**Best for**: Simple games (snake, tetris, platformers). Not viable for existing pygame games.

---

### Approach 2: CPython WASI Build + SDL2 Stub (Most Compatible, Pragmatic)

**What**: Build CPython for `wasm32-wasi`, statically link pygame-ce compiled against an SDL2 that routes to wasmcart's ABI. Load `.py` files from WASI virtual filesystem (mapped from .wasc assets).

**Size**: ~15–25 MB for CPython + pygame + trimmed stdlib.

**How it works**:
1. CPython's WASI build already exists (Tier 3 in 3.14, PEP 776)
2. WASI provides `fd_read`, `fd_write`, etc. — wasmcart host implements a minimal WASI layer
3. pygame-ce is built against `sdl2_wc` backends (same pattern as neverball_es, flare_es)
4. `.py` files loaded from WASI mapped filesystem (populated from .wasc assets at startup)

**WASI syscalls needed** (only ~10):
- `fd_read`, `fd_write`, `fd_seek`, `fd_close` — for stdio + file I/O
- `fd_prestat_get`, `fd_prestat_dir_name` — for mapped directories
- `environ_get`, `environ_sizes_get` — CPython reads env vars at startup
- `proc_exit` — clean exit
- `clock_time_get` — `time.time()`, `pygame.time.Clock`
- `random_get` — `random` module seeding

**Challenge**: CPython WASI builds are less mature than Emscripten builds. The build system uses `Tools/wasm/wasi.py` in CPython source. pygame-ce hasn't been built for WASI before — only Emscripten.

**Key question**: Can pygame-ce's C extensions (SDL calls) be compiled for WASI with our custom SDL2? WASI targets don't have Emscripten's port system (`-sUSE_SDL=2`). We'd need to provide SDL2 headers and link `libSDL2_wc.a` manually.

**Pros**:
- Real CPython, real pygame API
- WASI is a cleaner abstraction than Emscripten's JS glue
- wasmcart already handles WASM modules with custom imports
- File I/O "just works" via WASI fd mapping

**Cons**:
- CPython WASI is Tier 3, less tested
- pygame-ce for WASI is uncharted territory
- Larger binary than MicroPython approach
- No threading (but games don't need it)

---

### Approach 3: Emscripten Build with sdl2_wc (Proven Pattern, Best Compatibility)

**What**: Take python-wasm-sdk's existing Emscripten build of CPython + pygame-ce, swap SDL2 backends for `sdl2_wc`. This is exactly what works for neverball_es, ccleste_es, flare_es.

**Size**: ~15–25 MB .wasm (comparable to Godot at 52 MB).

**How it works**:
1. python-wasm-sdk already builds CPython 3.11–3.14 + pygame-ce to WASM via Emscripten
2. Replace Emscripten's SDL2 with our `libSDL2_wc.a` (compile with `-sUSE_SDL=2`, link with `-sUSE_SDL=0`)
3. Write a C shim exporting `wc_get_info`, `wc_init`, `wc_render`
4. Boot CPython in `wc_init`, call game's frame function in `wc_render`
5. `.py` files loaded via `wc_load_asset()` → custom Python import hook

**The proven build trick**:
```bash
# Compile phase — use Emscripten's SDL2 headers
emcc -sUSE_SDL=2 -c pygame_module.c -o pygame_module.o

# Link phase — use OUR SDL2 implementation
emcc -sUSE_SDL=0 pygame_module.o ... lib/libSDL2_wc.a -o cart.wasm
```

**C shim (cart entry point)**:
```c
#include "wasmcart.h"
#include <Python.h>

WC_CART_BUFFERS(640, 480, 0);  // 2D framebuffer, no GL

__attribute__((export_name("wc_init")))
void wc_init(void) {
    Py_Initialize();
    // Register custom importer that reads .py from wc_load_asset()
    // Run: import game
}

__attribute__((export_name("wc_render")))
void wc_render(void) {
    // Pump audio
    wasmcart_audio_pump(wc_audio_ring, WC_AUDIO_CAP, &wc_audio_write, 48000, delta_ms);
    // Call game frame
    PyRun_SimpleString("game._wc_frame()");
}
```

**Game loop bridge**: pygbag games use `await asyncio.sleep(0)` to yield. wasmcart calls `wc_render()` per frame. Two options:
1. Shim pumps Python's asyncio loop once per `wc_render()` call
2. Provide `wasmcart.tick()` that games call instead of `asyncio.sleep(0)`

**Python import hook for .wasc assets**:
```python
import importlib.abc, importlib.machinery, sys

class WascLoader(importlib.abc.Loader):
    def create_module(self, spec): return None
    def exec_module(self, module):
        # _wc_load_asset is a C extension that calls wc_load_asset()
        source = _wc_load_asset(f"assets/{spec.name.replace('.','/')}.py")
        exec(compile(source, spec.origin, 'exec'), module.__dict__)

class WascFinder(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path, target=None):
        asset_path = f"assets/{fullname.replace('.','/')}.py"
        if _wc_asset_exists(asset_path):
            return importlib.machinery.ModuleSpec(fullname, WascLoader(), origin=asset_path)
        return None

sys.meta_path.insert(0, WascFinder())
```

**Pros**:
- Proven pattern (4 games already ship this way)
- Real CPython, real pygame-ce, full compatibility
- Existing build recipes in python-wasm-sdk
- sdl2_wc backends handle video, audio, input translation
- Emscripten's port ecosystem (SDL_image, SDL_mixer, SDL_ttf, FreeType, libpng) all work

**Cons**:
- python-wasm-sdk build system surgery required
- Large binary (~15–25 MB)
- Emscripten JS glue needs to be eliminated or stubbed (STANDALONE_WASM mode)
- Game loop adaptation needed (asyncio bridge)

---

### Approach 4: Pyodide (Not Viable)

Pyodide requires browser or Node.js. Its JS glue is essential and cannot be replaced with wasmcart imports. Not viable for standalone carts.

### Approach 5: RustPython (Not Viable for pygame)

RustPython compiles to WASM (~22–30 MB) but has no C extension support. No path to pygame. Would need a complete Python game framework in pure Python.

---

## Recommended Path

**Start with Approach 3 (Emscripten + sdl2_wc)** because:

1. It's the **proven pattern** — identical to how neverball_es, ccleste_es, flare_es work
2. python-wasm-sdk already does the hard work of building CPython + pygame-ce for Emscripten
3. The only new work is: swap SDL2 backend, write C shim, write Python import hook
4. Full pygame API compatibility — existing games work without modification

**Prototype with Approach 1 (MicroPython)** if you want a quick proof-of-concept with a tiny binary. Good for "hello world" but not for real pygame games.

---

## Technical Deep Dive: What Needs to Be Built

### 1. Build CPython + pygame-ce with sdl2_wc

```
python-wasm-sdk build pipeline:
  CPython source → cross-compile → libpython3.XX.a
  pygame-ce source → compile against SDL2 headers → libpygame.a
  SDL2 (Emscripten port) → REPLACE with libSDL2_wc.a
  Link everything → cart.wasm
```

**Key files to study in python-wasm-sdk**:
- `scripts/cpython-build-emsdk.sh` — CPython cross-compile
- `scripts/pygame-build.sh` or equivalent — pygame-ce compilation
- Emscripten port flags: `-sUSE_SDL=2 -sUSE_SDL_IMAGE=2 -sUSE_SDL_MIXER=2`

### 2. C Shim (wasmcart ABI entry point)

Needs to:
- Export `wc_get_info()`, `wc_init()`, `wc_render()`
- Boot CPython with `Py_Initialize()`
- Register import hook for `.wasc` assets
- Pump audio each frame via `wasmcart_audio_pump()`
- Translate `wc_pads` input (SDL_wasmcart_video.c already does this)

### 3. Emscripten STANDALONE_WASM

Key challenge: Emscripten normally generates `.wasm` + `.js` glue. wasmcart needs a standalone `.wasm` with custom exports.

Options:
- `-sSTANDALONE_WASM=1` — Emscripten outputs standalone WASM (uses WASI-like imports)
- Stub out any remaining Emscripten JS imports (`emscripten_*` functions)
- `porting/emstubs.c` already provides stubs for common Emscripten runtime functions

### 4. Python File Loading

Two options:
- **WASI-style**: Mount `.wasc` assets as a virtual filesystem, CPython's normal `import` works
- **Custom importer**: Register `sys.meta_path` finder that calls `wc_load_asset()` C function

The WASI-style approach is simpler if we use Emscripten's `STANDALONE_WASM` mode (which provides WASI fd imports). The wasmcart host would need to implement the WASI fd layer and populate it from `.wasc` assets.

### 5. Game Loop Adaptation

pygame games typically look like:
```python
while True:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            sys.exit()
    # update game state
    # draw
    pygame.display.flip()
    clock.tick(60)
```

wasmcart calls `wc_render()` per frame. Bridge options:

**Option A**: Intercept `pygame.display.flip()` to yield back to host
- Override `SDL_GL_SwapWindow` / display update in sdl2_wc backend
- When called, return from `wc_render()`, resume next frame
- Requires Emscripten's `ASYNCIFY` or equivalent to suspend/resume the Python stack

**Option B**: pygbag-style async loop
```python
async def main():
    while True:
        # game logic
        pygame.display.flip()
        await asyncio.sleep(0)  # yields to host
```
- Shim pumps asyncio event loop once per `wc_render()` call
- Compatible with existing pygbag games

**Option C**: Explicit frame callback
```python
def on_frame():
    # game logic + draw
    pygame.display.flip()

wasmcart.set_frame_callback(on_frame)
```
- Cleanest for new games, requires game restructuring for existing ones

**Recommendation**: Option B (asyncio bridge) — matches pygbag's existing pattern, maximizes compatibility with games already adapted for web.

---

## Size Estimates

| Component | Estimated Size |
|-----------|---------------|
| CPython interpreter | ~10–15 MB |
| pygame-ce C extensions | ~2–3 MB |
| Python stdlib (trimmed) | ~3–5 MB |
| SDL2 (libSDL2_wc.a) | ~0.5 MB |
| SDL_image, SDL_mixer | ~1–2 MB |
| C shim + import hook | ~0.01 MB |
| **cart.wasm total** | **~15–25 MB** |
| **Compressed in .wasc** | **~5–8 MB** |

For comparison: Godot wasmcart port is 52 MB .wasm, pygbag output is ~7–8 MB compressed.

---

## Stdlib Trimming

Modules safe to remove for game use cases:
- `email`, `http`, `xmlrpc`, `ftplib`, `smtplib`, `imaplib` — no networking
- `unittest`, `doctest`, `pdb` — no testing/debugging
- `tkinter`, `turtle`, `idlelib` — no GUI toolkit
- `multiprocessing`, `subprocess`, `os.spawn*` — no processes
- `sqlite3` — no database (unless game uses it for saves)
- `distutils`, `ensurepip`, `venv` — no package management

Modules to keep:
- `json`, `struct`, `io`, `collections`, `itertools`, `functools` — commonly used
- `math`, `random` — game essentials
- `asyncio` — for game loop bridge
- `pathlib`, `os.path` — file path handling
- `re` — text processing
- `zipimport` — loading from .wasc

---

## Open Questions

1. **ASYNCIFY budget**: Suspending/resuming the Python interpreter stack mid-frame requires Emscripten's ASYNCIFY. What's the performance/size cost? pygbag already uses this.

2. **python-wasm-sdk build integration**: How invasive is swapping SDL2 in their build scripts? Need to study `scripts/` directory in detail.

3. **Frozen modules**: Can we freeze the stdlib + import hook into the `.wasm` binary (no runtime file loading for stdlib)? This would reduce startup time and simplify the asset layout.

4. **pygame-ce version**: Target pygame-ce 2.5.x (SDL2) or wait for 3.0 (SDL3)? SDL2 is proven with sdl2_wc.

5. **Reusable cart.wasm**: Can we ship one cart.wasm that works for any pygame game? Or do some games need custom C extensions compiled in?
   - Pure Python games: one cart.wasm fits all
   - Games using numpy/C extensions: need custom build

---

## Next Steps

1. **Clone python-wasm-sdk**, study the build scripts
2. **Build stock CPython + pygame-ce** for Emscripten (verify the baseline works)
3. **Swap SDL2 backend** for `libSDL2_wc.a` in the link step
4. **Write C shim** exporting wasmcart ABI, booting CPython
5. **Test with a simple pygame game** (e.g., bouncing ball)
6. **Add .wasc asset loading** for `.py` files
7. **Test with a real pygbag-compatible game**
