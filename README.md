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
| `pygame.image.load()` | Working (PNG, JPG, GIF, BMP; paletted images keep their palette) |
| `Surface.get_palette()` / `set_palette()` | Working (palette-swap recolouring) |
| `pygame.mixer.Sound()` | Working (WAV, OGG via SDL_mixer; `play()` returns a Channel) |
| `pygame.mixer.music` | Working (OGG + `.xm`/`.mod` trackers, streamed from cart assets) |
| `pygame.time.get_ticks()` / `Clock` | Working (frame-derived clock, see below) |
| `threading.Thread` | Cooperative: `start()` runs the target inline, `is_alive()` is False |
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
npx wasmcart boom_py.wasc
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

Pad state reaches Python two ways, both live at once. A game that only reads
the keyboard keeps working untouched; one that opens a joystick gets axes,
buttons, a hat and rumble.

```
Physical keyboard/gamepad
    ↓
wasmcart host writes to wc_pads[] shared memory
    ↓
    ├── sdl2_wc video backend PumpEvents()
    │       ↓
    │   Translates pad buttons → SDL keyboard/mouse events
    │       (D-pad → arrows, START → Return, SELECT → Escape,
    │        X → Space, A/B → left/right mouse click)
    │       ↓
    │   pygame.key.get_pressed() / pygame.event.get()
    │
    └── sdl2_wc joystick backend
            ↓
        Real SDL joystick devices (6 axes, 8 buttons, 1 hat)
            ↓
        pygame.joystick.Joystick(i).get_axis/get_button/get_hat
```

### Rumble

Rumble runs the opposite way to everything else: the cart drives the pad. It
uses the standard pygame API, and the wasmcart specifics are all below the
`pygame` line.

```python
import pygame
pygame.init()
pygame.joystick.init()

joy = pygame.joystick.Joystick(0)
joy.init()

# low-frequency (strong) motor, high-frequency (weak) motor, duration in ms
if joy.rumble(1.0, 0.0, 200):
    ...   # motors driven
else:
    ...   # this pad has no rumble; show something instead

joy.stop_rumble()
```

```
joy.rumble(low, high, duration)
    ↓
SDL_JoystickRumble()
    ↓
sdl2_wc joystick backend Rumble()
    ↓
wc_pad_rumble(pad, low, high, ms)  ← wasmcart host import
    ↓
host's rumble handler → physical motors
```

Things worth knowing:

- **Ask, do not assume.** Rumble capability is per-DEVICE. An Xbox 360 pad has
  rumble but no trigger rumble; a keyboard-only setup has none. `rumble()`
  returns `False` when the pad cannot do it, and a headless run (no rumble
  handler wired) is one of those cases. Check the return value.
- **Enumerate per frame, not at import.** Module import runs during `wc_init`,
  before the host has written a single frame of pad state, so
  `pygame.joystick.get_count()` is `0` there no matter what is plugged in.
  Re-scan in your frame function; this is the same hot-plug handling an
  upstream pygame game needs anyway.
- **Pump events.** `pygame.event.get()` drives `SDL_JoystickUpdate`, which
  refreshes button state and expires a finished rumble effect. A game that
  never pumps will see stale input and a motor that keeps running.
- **Device index equals wasmcart pad id.** The joystick backend does not
  compact its device list, so pad slot 2 connected alone still reports a count
  of 3 with slots 0 and 1 failing to open. That keeps the two numbering
  schemes in agreement.
- **The direct path.** `_wasmcart.pad_has_rumble(pad)`,
  `_wasmcart.pad_rumble(pad, low, high, ms)` and
  `_wasmcart.pad_rumble_stop(pad)` call the host imports without going through
  SDL. Use `pygame.joystick` for real games; this is for a cart that wants to
  rumble without opening a joystick, and for checking whether the ABI itself is
  wired up.

`examples/rumble/` is a working demo, and `tools/test_rumble.mjs` drives it
headlessly with a rumble handler attached and asserts the calls arrive.

### The clock

`pygame.time.get_ticks()`, `Clock.tick(fps)` and `Clock.get_fps()` all read
SDL's tick source, and in a cart that is **not** wall-clock time. The host
decides when `wc_render` is called: a headless `--frames` screenshot run goes
back to back, far faster than real time, and a dragged window or a paused
debugger goes far slower.

So the tick source advances one nominal frame per `wc_render`. Game time is a
function of frames rendered, which means a cart behaves identically headless
and in a window, and a screenshot at frame N shows what frame N should show.

This matters more than it sounds. On wall-clock time, a headless run reported
384 ms after 300 frames instead of 7500: every timed transition stalled and
every delta-scaled movement stood still, while the game rendered its first
screen perfectly, forever. A cart that looks like it is running and is frozen
in game-time is exactly the failure that reads as success.

Audio pumping still uses the host's real delta, because that has to track the
wall clock the speaker runs on.

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

Nine, all verified rendering. Pack and run any of them:

```bash
bash pack_game.sh examples/boom_py/ out/boom_py.wasc "Boom"
npx wasmcart out/boom_py.wasc
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
| `boom_py` | a raycaster: textured walls, sprite NPCs, weapon, HUD | 13 MB |
| `rumble` | gamepad rumble via `pygame.joystick.Joystick.rumble()` | 11 MB |
| `surfarray` | per-pixel work through `pygame.surfarray`: live `pixels3d` writes, `array3d`/`blit_array`, `make_surface`, channel planes | 11 MB |
| `surfarray_test` | the `surfarray` correctness gate: asserts exact pixel values and prints its verdict on screen | 11 MB |

Every asset is CC0 or generated for this project — see
[`examples/ASSETS-LICENSE.md`](examples/ASSETS-LICENSE.md).

## Ports

Existing finished games running on this runtime unmodified. Where an example
is written to fit, a port is the thing that finds out what is actually
missing.

| Port | What it is | Game code changed |
|---|---|---|
| [`ports/solarwolf`](ports/solarwolf/README.md) | Pete Shinners' SolarWolf, pygame's own reference game, 6,696 lines, 60 levels | 1 of 38 modules (the loop inversion) |

SolarWolf found eight runtime gaps, all fixed here rather than worked around
in the game: missing `pygame.ver`, paletted images flattened to RGBA, no GIF
decoder, `threading.Thread.start()` raising, `mixer.music` being a silent
no-op, a wall-clock instead of frame-derived clock, a missing `urllib` taking
down the boot, and a resolution scraper blind to `SIZE = 800, 600`. Its README
documents each one.

### Testing a port

Frame counts are not evidence. A cart that boots, returns frames and renders
nothing reports success exactly as loudly as one that works.

```bash
# drive input on a schedule and screenshot specific frames
node tools/drive_cart.mjs out/solarwolf.wasc --frames 900 \
  --script "120:;130:START;140:;300:START;310:" \
  --shots "110:menu.png,270:play.png"

# then check the pixels
node tools/check_render.mjs play.png
```

`drive_cart.mjs` exists because `wasmcart --frames N --shot out.png` cannot
press a button, so every screenshot it can take is of the title screen. It
drives the same `CartHost` the player does, including the GL readback. A
pygame cart blits through GL, so reading CartHost's 2D framebuffer gives a
black PNG for a cart that is rendering perfectly.

`check_render.mjs` reports distinct colours and ink coverage. Verified against
a control: a build with `pygame.display.update()` removed runs the same 700
frames and comes back `colors=1 ink=0.00%`.

## Limitations

- **Fonts**: `pygame.font.Font(None, size)` and `Font("path.ttf", size)` both
  work, including the bundled FreeSansBold. `SysFont` resolves to the bundled
  font rather than matching a system one, since a cart has no font directory
  to search; `match_font` is not available for the same reason.
- **File writing**: The `.wasc` filesystem is read-only. Save data should use the wasmcart save ABI (not yet exposed to Python).
- **Threading**: `threading.Thread` imports and `start()` works, but
  cooperatively: the target runs inline on `start()` and `is_alive()` is
  False from the first poll. That covers the common loading-screen idiom
  (run the loader on a thread, poll from the draw loop); it does not cover a
  thread meant to run *concurrently* with the draw loop. WASM here is
  single-threaded and real threads are not available.
- **Networking**: Not available. `urllib` imports and `urllib.parse` is real,
  but any fetch raises `URLError`. A cart has no sockets, and the wasmcart
  WebSocket/DataChannel ABI has no Python bindings yet. This is deliberate:
  a game with an optional online feature should reach its `except URLError`,
  not die on the import.
- **`pygame.surfarray`**: Available, but it is a wasmcart-native
  implementation rather than upstream's. Upstream `surfarray.py` builds every
  reference array with `numpy.array(surface.get_view("3"), copy=False)`, which
  asks numpy to alias a strided C buffer with no copy. The numpy shim in
  `stdlib_extra/numpy/` is a `list` subclass and cannot alias foreign memory,
  so bundling upstream would have made `pixels3d` return a *copy*, and every game
  that mutates pixels in place would render an unchanged surface while the
  frame counter kept ticking.

  `stdlib_extra/pygame/surfarray.py` instead builds the reference arrays
  directly on the `memoryview` that `Surface.get_view()` already exports, so
  `pixels3d` / `pixels2d` / `pixels_red|green|blue|alpha` are **true live
  views**: writes land in the Surface. The copying calls (`array3d`,
  `array2d`, `array_*`, `blit_array`, `make_surface`, `map_array`) delegate to
  the `pixelcopy` C extension. The arrays are ordinary Python objects, not
  numpy arrays, so they index, slice, iterate and `tolist()` but do not
  support numpy's vectorized arithmetic; per-pixel loops are the idiom here.

  `examples/surfarray/` renders each capability as a labelled panel, and
  `examples/surfarray_test/` asserts exact pixel values and prints its verdict
  on screen.
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
