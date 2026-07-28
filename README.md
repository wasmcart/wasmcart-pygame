# wasmcart-pygame

Run pygame games as wasmcart `.wasc` carts. Write Python, pack it, run it on every wasmcart host — browser, terminal, ARM handheld.

## What This Is

A single reusable **`cart.wasm`** (~8 MB) containing CPython 3.13 + pygame-ce + SDL2 + OpenGL. Every pygame game is just a different set of assets packed into the `.wasc` ZIP alongside the same runtime. The game developer writes standard Python — no C, no WASM toolchain, no wasmcart-specific code.

```
my_game.wasc (ZIP)
├── cart.wasm          ← reusable runtime (same for every game)
├── manifest.json
└── assets/
    ├── main.py        ← your game
    ├── player.py      ← your modules
    ├── gfx/
    │   └── player.png
    └── sounds/
        └── jump.wav
```

## What Works

| Feature | Status |
|---------|--------|
| `pygame.init()` | Working |
| `pygame.display.set_mode()` | Working (2D software rendering) |
| `screen.fill()` | Working |
| `pygame.draw.*` | Working (rect, circle, line, polygon) |
| `pygame.Surface` + `blit()` | Working (compositing, colorkey, alpha) |
| `pygame.sprite.*` | Working (Sprite, Group, collide, groupcollide) |
| `pygame.transform.*` | Working (rotate, scale, flip) |
| `pygame.image.load()` | Working (PNG, JPG, BMP via stb_image) |
| `pygame.mixer.Sound()` | Working (WAV, OGG via SDL_mixer) |
| `pygame.font.Font()` | Working (with bundled .ttf) |
| `pygame.key.get_pressed()` | Working (via wasmcart pad → SDL key translation) |
| `pygame.event.get()` | Working |
| `from OpenGL.GL import *` | Working (GLES3 backed by wasmcart GL ABI) |
| `print()` | Working (stdout → host console) |
| Relative imports | Working (`import player` loads `assets/player.py`) |
| Package imports | Working (`from enemies.boss import Boss`) |

## Quick Start

### Just play something

Eight prebuilt carts are attached to the
[latest release](https://github.com/wasmcart/wasmcart-pygame/releases/latest) —
download one and run it. No Python, no pygame, no build:

```bash
npx wasmcart doom_py.wasc
```

Each cart carries CPython 3.13, pygame-ce, and the game's own code and assets.

### Pack a game

```bash
bash pack_game.sh my_game_dir/ out/my_game.wasc "My Game"
```

This bundles `cart.wasm` + your game files + Python stdlib + pygame helpers into a single `.wasc`.

### Run it

```bash
npx wasmcart out/my_game.wasc            # SDL window (auto-detects GL)
npx wasmcart out/my_game.wasc --term     # ANSI terminal, SSH-friendly
npx wasmcart out/my_game.wasc --frames 120 --shot out.png   # headless
```

Every wasmcart host runs the same `.wasc`: the CLI above, a browser via
`CartHostWeb`, RetroArch through the libretro core, or a handheld.

### Write a game

Standard pygame. No wasmcart-specific code.

**Callback mode** (recommended — works everywhere including screenshot tool):

```python
import pygame

pygame.init()
screen = pygame.display.set_mode((480, 600))

def _wc_frame():
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            return

    screen.fill((0, 0, 0))
    pygame.draw.circle(screen, (255, 0, 0), (240, 300), 40)
    pygame.display.flip()
```

**Standard loop** (requires ASYNCIFY — `clock.tick()` suspends the WASM stack):

```python
import pygame

pygame.init()
screen = pygame.display.set_mode((480, 600))
clock = pygame.time.Clock()

while True:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            pygame.quit()
            break

    screen.fill((0, 0, 0))
    pygame.draw.circle(screen, (255, 0, 0), (240, 300), 40)
    pygame.display.flip()
    clock.tick(60)
```

## How It Works

### Boot sequence

1. Host loads `.wasc`, instantiates `cart.wasm`, calls `_initialize()` then `wc_init()`
2. `wc_init()` initializes SDL2 + SDL_mixer + SDL_image via sdl2_wc backends
3. CPython boots with frozen stdlib (encodings, codecs, io, abc)
4. Custom `sys.meta_path` finder registered — intercepts all imports
5. pygame C extensions initialized (BUILD_STATIC — all submodules in one binary)
6. `import main` loads your game from `.wasc` assets
7. Host calls `wc_render()` 60 times per second

### Asset loading

Games use standard filesystem paths. The runtime intercepts file operations transparently:

- `pygame.image.load("gfx/player.png")` → stb_image decodes PNG from `.wasc` asset
- `pygame.mixer.Sound("sounds/pew.wav")` → SDL_mixer loads WAV/OGG from `.wasc` asset
- `pygame.font.Font(None, 24)` → loads bundled `freesansbold.ttf`
- `open("data/levels.json")` → reads from `.wasc` asset
- `import player` → loads `assets/player.py` from `.wasc`

No code changes needed. `os.path.join`, `__file__`, relative paths — all work.

### Rendering pipeline

```
pygame.draw / Surface.blit
    ↓
SDL2 software renderer (libSDL2_wc.a)
    ↓
sdl2_wc video backend → wc_framebuffer (ARGB8888)
    ↓
wasmcart host reads framebuffer, displays it
```

### Audio pipeline

```
pygame.mixer.Sound.play() / pygame.mixer.music
    ↓
SDL_mixer callback (Mix_PlayChannel)
    ↓
sdl2_wc audio backend (wasmcart_audio_pump per frame)
    ↓
wc_audio_ring (F32 stereo ring buffer)
    ↓
wasmcart host reads ring buffer, plays through speakers
```

### Input pipeline

```
Physical keyboard/gamepad
    ↓
wasmcart host writes to wc_pads[] shared memory
    ↓
sdl2_wc video backend PumpEvents()
    ↓
Translates pad buttons → SDL keyboard events
    (D-pad → arrows, A → Return+Space, B → Escape)
    ↓
pygame.key.get_pressed() / pygame.event.get()
```

### Import hook

Python modules load from `.wasc` assets without filesystem access:

```
import player
    ↓
_WascFinder.find_spec("player")
    ↓
wc_asset_size("assets/player.py") → found
    ↓
wc_load_asset("assets/player.py") → bytes
    ↓
compile() + exec() → module object in sys.modules
```

Packages work: `from enemies.boss import Boss` → `assets/enemies/__init__.py` + `assets/enemies/boss.py`.

## Built-in Packages

These are compiled into `cart.wasm` — no installation needed, no asset loading overhead:

| Package | What | How |
|---------|------|-----|
| `pygame` | Full pygame-ce 2.5 | C extension (BUILD_STATIC) linked against libSDL2_wc.a |
| `OpenGL.GL` | GLES 3.0 | C extension wrapping wasmcart GL ABI imports |
| Python stdlib | encodings, codecs, io, abc | Frozen bytecode in cart.wasm data segment |

Additional stdlib modules (struct, os, collections, json, re, etc.) load from `.wasc` assets on first import.

## Building from Source

### Prerequisites

- Emscripten SDK (`source emsdk_env.sh` before building)
- a host `python3` and `git`
- sibling checkouts of [wasmcart](https://github.com/wasmcart/wasmcart) and
  [wasmcart-sdl2](https://github.com/wasmcart/wasmcart-sdl2), or
  `WASMCART_REPO` / `WASMCART_SDL2` pointing at them

### Build the runtime

```bash
bash setup_cpython.sh      # fetch + build CPython 3.13 for wasm (slow, once)
bash setup_pygame.sh       # fetch pygame-ce (pinned)
bash build_full.sh         # -> out/cart.wasm   (CPython + pygame + SDL2 + GL)
bash build_minimal.sh      # -> out/cart_minimal.wasm  (no pygame; smaller)
```

Everything fetched lands in `vendor/`, which is gitignored. Nothing is built
into `/tmp` — that is wiped on reboot and previously left this project
unbuildable.

`build_full.sh` links with `-sERROR_ON_UNDEFINED_SYMBOLS=1` on purpose. An
unresolved symbol otherwise becomes a wasm import that traps when called,
which surfaces as a bare `unreachable` with no diagnostic rather than a link
error.

### Pack a game

```bash
bash pack_game.sh path/to/game/ output.wasc "Game Name"
```

`pack_game.sh` bundles:
- `cart.wasm` (the reusable runtime)
- Your game's `.py` files and assets (images, sounds, fonts)
- the Python stdlib, minus what a cart cannot reach (no filesystem, sockets,
  threads or subprocesses, so `asyncio`, `multiprocessing`, `http`, `urllib`,
  `email`, `sqlite3` and friends are dropped — about 42 MB per cart)
- pygame Python helper modules (sprite, colordict, etc.)

## Project Structure

```
wasmcart-pygame/
├── src/
│   ├── cart_shim.c          # wasmcart ABI ↔ CPython ↔ pygame bridge
│   ├── opengl_module.c      # OpenGL.GL C extension (GLES3 via wasmcart GL ABI)
│   ├── pystubs.c            # WASI/syscall stubs for standalone WASM
│   ├── frozen_stdlib.c      # Frozen bytecode for boot modules
│   ├── frozen_opengl.c      # Frozen OpenGL package shims
│   ├── pg_version_fix.h     # PG_VERSION_TAG shell quoting fix
│   └── stb_image.h          # Image decoder (symlink to porting/include/)
├── build_full.sh            # Build cart.wasm with everything
├── build_minimal.sh         # Build minimal cart (no pygame, for testing)
├── pack_game.sh             # Pack a game into .wasc
├── examples/
│   ├── hello_pygame/        # Basic rendering test
│   ├── hello_python/        # Minimal CPython test (no pygame)
│   ├── hello_gl_python/     # OpenGL triangle test
│   └── spaceshooter/        # Full game port (images, sounds, sprites)
└── out/
    ├── cart.wasm             # Reusable runtime (~8.9 MB)
    └── *.wasc                # Packed games
```

## Examples

Eight, all verified rendering. Pack and run any of them:

```bash
bash pack_game.sh examples/doom_py/ out/doom_py.wasc "Doom"
npx wasmcart out/doom_py.wasc
```

| Example | What it shows | `.wasc` |
|---|---|---|
| `hello_python` | CPython in a cart with no pygame — direct framebuffer writes | 11 MB |
| `hello_pygame` | the pygame drawing primitives: fill, rect, circle, line, blit | 11 MB |
| `hello_gl_python` | `from OpenGL.GL import *` straight onto the wasmcart GL ABI | 11 MB |
| `bench` | frame-time microbenchmarks | 11 MB |
| `spaceshooter` | a full game port — sprite groups, collisions, HUD, powerups | 13 MB |
| `threepy` | a three.py scene graph driving GL: lit spinning cube | 12 MB |
| `3d_engine` | textured model, cubemap skybox, per-pixel lighting via moderngl | 12 MB |
| `doom_py` | a raycaster: textured walls, sprite NPCs, weapon, HUD | 13 MB |

Every asset is CC0 or generated for this project — see
[`examples/ASSETS-LICENSE.md`](examples/ASSETS-LICENSE.md).

## Limitations

- **Font rendering**: `pygame.font.Font(None, size)` works with the bundled FreeSansBold font. System font matching (`match_font`) is not available.
- **File writing**: The `.wasc` filesystem is read-only. Save data should use the wasmcart save ABI (not yet exposed to Python).
- **Threading**: Python threading is not available (WASM is single-threaded).
- **Networking**: Not yet exposed to Python (wasmcart WebSocket/DataChannel ABI exists but no Python bindings).
- **ASYNCIFY**: Standard `while True` game loops require ASYNCIFY in the link step (adds ~15% binary size). The `_wc_frame()` callback pattern avoids this.

## Size

| Component | Size |
|-----------|------|
| CPython 3.13 interpreter | ~6 MB |
| pygame-ce (BUILD_STATIC) | ~1.4 MB |
| SDL2 + sdl2_wc backends | ~0.5 MB |
| OpenGL module + stb_image | ~0.3 MB |
| Stubs + shims | ~0.1 MB |
| **cart.wasm total** | **~9 MB** |
| Python stdlib (in .wasc) | ~200 KB compressed |
| pygame helpers (in .wasc) | ~50 KB compressed |
| **Typical game .wasc** | **10-15 MB** |

## The wasmcart ecosystem

| Repo | What it is |
|------|------------|
| [**wasmcart**](https://github.com/wasmcart/wasmcart) | the spec, the JS reference hosts, the `wasmcart` CLI and packer |
| [**wasmcart-sdl2**](https://github.com/wasmcart/wasmcart-sdl2) | the SDL2 backend this runtime links against, plus the porting guide |
| [**wasmcart-lua**](https://github.com/wasmcart/wasmcart-lua) | write games in Lua (LÖVE-style API, batched GL2D renderer) |
| [**wasmcart-mruby**](https://github.com/wasmcart/wasmcart-mruby) | write games in Ruby (DragonRuby-style API) |
| [**wasmcart-jsgame**](https://github.com/wasmcart/wasmcart-jsgame) | write games in JavaScript (QuickJS + Canvas2D/WebGL2) |
| [**wasmcart-libretro**](https://github.com/wasmcart/wasmcart-libretro) | run carts in RetroArch / RetroDECK |

## License

MIT — see [LICENSE](LICENSE). Example assets are CC0 or generated for this
project; see [`examples/ASSETS-LICENSE.md`](examples/ASSETS-LICENSE.md).
