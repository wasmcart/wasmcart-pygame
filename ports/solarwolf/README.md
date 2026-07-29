# SolarWolf -- a real pygame game, ported

[SolarWolf](https://github.com/pygame/solarwolf) is a complete arcade game by
Pete Shinners, pygame's creator, written as the reference project for pygame
itself. This directory runs it on the wasmcart pygame runtime.

It is the port that proves the runtime: not a demo written to fit, but a
finished 2002 game with 6,696 lines of its own code, 60 levels, 86 data files
and a handler-driven state machine that expects to own the process.

## The game's own source is unmodified

**37 of the game's 38 Python modules are byte-identical to upstream**,
verified by `cmp` against a fresh clone. `gameplay.py`, `gfx.py`, `snd.py`,
`input.py`, every object class, every handler -- untouched.

Exactly one file was replaced, and four were dropped:

| File | What happened | Why |
|---|---|---|
| `main.py` | replaced | the loop inversion, below |
| `cli.py` | dropped | the desktop launcher: `os.chdir`, `sys.path` surgery, dependency checks against pygame 1.5.6 |
| `errorbox.py` | dropped | fallback error dialogs via win32ui / wxPython / tkinter |
| `__main__.py`, `__init__.py` | dropped | the `python -m solarwolf` packaging entry |

`85 of the 86 data files are byte-identical` too. The one exception is a
licensing exclusion, below.

## The loop inversion

This is the single structural change any pygame port needs, and it is the
whole of the new `main.py`.

Upstream `gamemain()` sets up, then owns the process:

```python
while game.handler:
    handler = game.handler
    for event in pygame.event.get():
        ...
    handler.run()
    game.clockticks = game.clock.tick(40)
    gfx.update()
```

A cart cannot own the loop: the host calls `_wc_frame()` once per frame and
expects it to return. So the setup half runs at import time and the body of
the `while` becomes `_wc_frame()`. Because SolarWolf's game state already
lives in a swappable `game.handler` object rather than in local variables, the
loop body translated line for line. That is not luck: a state-machine game
inverts cleanly, and a game that keeps its state in the loop's own locals will
not.

Three things inside the loop needed a decision rather than a translation:

- **`pygame.time.set_timer(USEREVENT, 1000)`** drives the star-density
  recalculation. SDL timers need a background thread to tick them, which a
  single-threaded cart has none of, so the same 1000 ms cadence is derived
  from the frame clock. The `USEREVENT` branch is still there and still works
  if the event ever arrives.
- **Alt+Enter fullscreen toggle** is dropped. The host owns the window.
- **`ACTIVEEVENT` focus handling** is dropped, along with upstream's
  `while not pygame.display.get_active(): pygame.time.wait(100)` spin -- a cart
  that blocks waiting for focus never returns from `_wc_frame`.

## Everything here is freely licensed

**One file was excluded and is not in this repo.** Upstream ships
`data/oldsolarfox.png`, a screenshot of the Atari 2600 game the credits screen
tips its hat to. That is somebody else's copyrighted commercial game.

| Excluded | Replaced by |
|---|---|
| `data/oldsolarfox.png` (Atari 2600 screenshot) | `tools/make_solarwolf_assets.py` draws an original stylised retro console at the same 235x210 |

The generator is deterministic -- no RNG -- so a rebuild is byte-identical. It
quantizes to a palette on purpose, because that is the loader path the rest of
this game's art exercises.

Everything else is SolarWolf's own: game code by Pete Shinners (LGPL, see
`lgpl.txt`), graphics by Eero Tamminen, music by "theGREENzebra", all
redistributable under the LGPL the project ships.

## What the port forced into the runtime

Every gap below was found by this game hitting it, and fixed in the runtime
rather than worked around in the game. That is the point of the exercise: any
other pygame port hits the same ones.

### 1. `pygame.ver` did not exist

`src/cart_shim.c` -- Upstream `pygame/__init__.py` does
`from pygame.version import *`. BUILD_STATIC has no `__init__.py`, so
`pygame.version` was imported and never re-exported and `pygame.ver` raised
`AttributeError`. SolarWolf's `txt.py` version-gates on it at import time
(`if pygame.ver <= '1.6.1'`), so this was a hard boot failure three modules
deep. Now `ver`, `vernum`, `rev` and `SDL` are exported from the version
module.

### 2. Paletted images were flattened to RGBA

`src/cart_shim.c` -- **the deepest gap.** The image loader decoded everything
through stb_image at 4 channels, so 8-bit indexed surfaces did not exist in
the runtime. 40 of SolarWolf's 60 images are paletted, and the game recolours
sprite sheets by swapping palettes:

```python
imgs = gfx.load_raw('boxes.png')
origpal = imgs.get_palette()
boximages = gfx.animstrip(imgs)
pal = [(g, g, b) for (r, g, b) in origpal]   # tint yellow
imgs.set_palette(pal)
yboximages = gfx.animstrip(imgs)
```

`get_palette()` raised `Surface has no palette to get` and resource loading
died. Palette-swap recolouring is not a fringe trick; it is how a sprite sheet
from this era makes its variants. `pygame.image.load` now decodes through
pygame's own SDL_image path first -- which returns the surface in the file's
native format, palette intact -- and falls back to stb only for what SDL_image
refuses.

### 3. GIF did not decode at all

`src/cart_shim.c`, `build_full.sh` -- stb was compiled `STBI_ONLY_PNG/JPEG/BMP`
and the emscripten SDL_image port compiles in only the formats named by
`SDL2_IMAGE_FORMATS`, which was unset. So every GIF raised
`unknown image type`. SolarWolf ships ten, including both HUD frames. Both
decoders now handle GIF.

### 4. `threading.Thread.start()` raised

`src/cart_shim.c` -- WASM here is single-threaded, so
`_thread.start_new_thread` raised `RuntimeError: can't start new thread`.
The common pygame idiom for a loading screen is to run the resource loader on
a background thread and poll `is_alive()` from the draw loop, which is exactly
what `GameInit` does, so the game raised before drawing a frame.

`Thread.start()` now runs the target inline and returns a thread that is
already finished. `join()` returns immediately, `is_alive()` is always False.
A loading bar snaps to done rather than animating -- correctness over
cosmetics. A game that needs a thread running *concurrently* with the draw
loop (streaming, a watchdog) is still not served and cannot be until the
runtime grows real threads.

### 5. `pygame.mixer.music` was a silent no-op

`src/cart_shim.c`, `build_full.sh` -- `music.load()` was patched to `pass`,
with the comment "Music loading not yet supported". Every cart was mute and
nothing said so: `load()` succeeded, `play()` did nothing, no error. pygame's
own `music.load` goes through `SDL_RWFromFile`, which is C and never sees the
asset shim, so it cannot open anything inside a `.wasc`.

Music now streams from cart assets via `Mix_LoadMUS_RW` over the asset bytes,
with `SDL2_MIXER_FORMATS=['ogg','mod']` so libmodplug handles the two `.xm`
tracker modules SolarWolf ships alongside its `.ogg`. `play`, `stop`,
`fadeout`, `set_volume`, `get_volume`, `get_busy`, `pause`, `unpause` are all
wired. `set_endevent` is accepted and ignored -- nothing drives SDL_mixer's
finished-music hook into pygame's event queue, so a playlist degrades to the
track looping.

`Sound.play()` also now returns the `Channel` it grabbed, as upstream does.
It returned `None`, and `chan = sound.play(); chan.set_volume(l, r)` is how
stereo panning is written -- SolarWolf's `snd.play()` does exactly that.

### 6. The clock was wall-clock, not frame-derived

`src/cart_shim.c`, `build_full.sh` -- **the subtlest one.** SDL's tick source
was real time, which is the wrong clock for a cart: the host decides when
`wc_render` is called and may run frames much faster than real time (a
headless `--frames` pass) or much slower.

Everything a game times in milliseconds reads that clock --
`pygame.time.get_ticks()`, `Clock.tick(fps)`, `Clock.get_fps()`. In a headless
run frames are back to back, so after 300 frames `get_ticks()` read 384 ms
instead of 7500. SolarWolf's splash waits 1200 ms before handing off to the
menu and simply never did, while rendering the splash perfectly, forever.
`Clock.tick(40)` returned 0 or 1, so every delta-scaled movement stood still.

`SDL_GetTicks`/`SDL_GetTicks64` are now wrapped to a game clock that advances
one nominal frame per `wc_render`. Deriving it from `wc_time.delta_ms` with a
floor was tried first and is subtly wrong: a host that renders a heavy frame
in 1.7 ms of wall time passes any floor below that, and the game still runs
~10x slow while looking correct frame to frame. The step is unconditional for
that reason. The host's real delta is still used for audio pumping, which has
to track the wall clock the speaker runs on.

### 7. `urllib` was missing, and that killed the boot

`stdlib_extra/urllib/` -- `pack_game.sh` drops `urllib` from the packed stdlib,
correctly: a cart has no sockets and `urllib.request` drags in `http.client`,
`email` and `socket`. But `gamenews.py` imports it at module scope for an
optional news-download feature whose fetch is already wrapped in
`try/except`. The network being absent is fine; the *import* failing is not,
and it took down the whole game four modules from the entry point.

`urllib` now exists as a small package: the real `urllib.parse` (pure string
manipulation), the real exception hierarchy in `urllib.error`, and a
`urllib.request` that carries the API surface and raises `URLError` on any
fetch. A fetch failing is the honest answer, and it fails where a caller
already handles it.

### 8. The resolution scraper missed `SIZE = 800, 600`

`tools/find_resolution.py` -- the pack-time scraper had patterns for
`WIDTH, HEIGHT = ...`, `set_mode((w, h))` and friends, but not for a
width/height pair named as one value. SolarWolf writes `size = 800, 600` and
passes it straight to `set_mode`, so the manifest silently declared the shim
default of 640x480 and the host sized its window and GL context to that. Now
recognised, with no change to the nine existing examples' detected sizes.

## Testing

Frame counts are not evidence -- the failure mode this port is guarding against
is a cart that boots, returns frames, and renders nothing.

```bash
bash pack_game.sh ports/solarwolf/ out/solarwolf.wasc "SolarWolf"

# drive input on a schedule and screenshot specific frames
node tools/drive_cart.mjs out/solarwolf.wasc --frames 900 \
  --script "120:;130:START;140:;300:START;310:;420:START;430:;460:UP;520:" \
  --shots "110:menu.png,270:play.png,580:action.png"

# then check the pixels, not the frame count
node tools/check_render.mjs play.png
```

`tools/drive_cart.mjs` exists because `wasmcart --frames N --shot out.png` has
no way to press a button, so every screenshot it can take is of the title
screen. It drives the same `CartHost` the player does, including the GL
readback -- a pygame cart blits through GL, so reading CartHost's 2D
framebuffer gives a black PNG for a cart that is rendering perfectly.

**The control that must fail.** A build with the `pygame.display.update()`
call removed from `gfx.py` runs the same 700 frames and reports the same
800x600, and comes back `colors=1 ink=0.00% -> BLANK`. Working frames read
1301 to 10926 colors at 14-39% ink. The gate discriminates; the frame count
does not.

`check_render.mjs`'s colour floor is deliberately low (3). A first pass
required 24 and flagged two working examples -- `threepy` renders flat-shaded
polygons in 4 colours and `hello_python` writes solid blocks in 4. Ink
coverage is the load-bearing check: a frame the cart never pushed is one
uniform colour, everywhere.

## Status

Runs end to end. Verified by screenshot at each stage:

| Stage | What renders |
|---|---|
| splash | logo, progress bar, pygame badge, starfield |
| main menu | all five menu items, animated ship with exhaust, floating box |
| gameplay | level-1 box diamond, four guardians, player ship, HUD with wolf head, timer bar, lives |
| in-game help | wrapped text overlay over live gameplay |
| movement | ship traverses the arena, guardians reposition and fire, boxes collect |

Audio confirmed against a captured WAV: peak 28803 of 32767, 98% of samples
non-silent. All three music files load -- both `.xm` trackers and the `.ogg`.

Not exercised: the news downloader (no network, by design), fullscreen
toggling (the host owns the window), preference and player-score persistence
(the `.wasc` filesystem is read-only, and SolarWolf's save paths are already
wrapped in `try/except` so they degrade to defaults each run).
