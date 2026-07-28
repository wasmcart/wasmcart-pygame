# GPU Rendering Notes for wasmcart-pygame

## Summary

All wasmcart carts should now use `gpu_api=1` and render through GL. This includes 2D carts like wasmcart-pygame. The old 2D framebuffer display path (`gpu_api=0`) is legacy.

## Why

The host has two display paths: read the 2D framebuffer (CPU pixels) or swap the GL buffer. Having both causes repeated "black screen" bugs where the host picks the wrong path. With `gpu_api=1` always, there's one path: GL swapBuffers. No detection logic, no heuristics, no hybrid mode confusion.

Performance is also better: at 1080p, the old CPU pixel copy ran at ~30fps. The GL texture upload (DMA) runs at 60fps.

## What to Change

### 1. Set gpu_api=1 in wc_get_info()

In `cart_shim.c`, after filling `wc_info`, add:

```c
wc_info.gpu_api = 1;
```

The `gpu_api` field is at the end of `wc_info_t` (uint32_t, offset 64). If your `wasmcart.h` doesn't have it, add it after `keys_ptr`:

```c
uint32_t gpu_api;  // 0=2D framebuffer, 1=WebGL2/GLES3
```

### 2. Enable GL blit in SDL2

In `wc_init()`, after `SDL_Init()`, call:

```c
SDL_WASMCART_SetGLBlit(1);
```

This tells the sdl2_wc video backend to upload SDL surface pixels as a GL texture instead of copying to `wc_framebuffer`. The function is declared in `SDL_wasmcart_video.h`.

### 3. Link sdl2_gl_blit.c

Add `sdl2_gl_blit.c` to your build. It's at `wasmcart/porting/sdl2_wc/sdl2_gl_blit.c`.

This file provides the `wc_sdl_gl_blit()` function that the sdl2_wc video backend calls during `UpdateWindowFramebuffer`. It uses `wc_gl_blit.h` (a single-header library in `porting/include/`) to:

1. Compile a fullscreen quad shader (once, on first call)
2. Upload the pixel buffer as a GL texture via `glTexImage2D`
3. Draw the fullscreen quad

### 4. Link with GL imports

The cart needs to import GL functions from the `"gl"` WASM module. Add `#define WC_USE_GL` before `#include "wasmcart.h"` in `sdl2_gl_blit.c` (it already does this).

Make sure your link step includes `-sERROR_ON_UNDEFINED_SYMBOLS=0` (you already have this) since GL imports are resolved by the host at runtime.

## What NOT to Change

- **Game code**: Zero changes to any Python game. `pygame.display.set_mode()`, `pygame.display.flip()`, all drawing — unchanged.
- **SDL2**: Still uses software renderer internally. The GPU part is just the final display step.
- **Audio**: No changes. `wasmcart_audio_pump()` is independent of the video path.
- **Framebuffer allocation**: Keep `wc_framebuffer` allocated. The sdl2_wc backend still needs it as an intermediate surface. The host just doesn't read it anymore — it gets GL output instead.
- **SDL_WASMCART_SetFramebuffer()**: Still call this. The software renderer needs it. GL blit reads from SDL's surface, not from `wc_framebuffer` directly.

## Display Pipeline After Changes

```
pygame.draw / Surface.blit
    ↓
SDL2 software renderer (unchanged)
    ↓
sdl2_wc UpdateWindowFramebuffer
    ↓ (GL blit enabled)
BGRA→RGBA conversion (tight loop)
    ↓
glTexImage2D (GPU DMA upload)
    ↓
fullscreen quad shader (wc_gl_blit)
    ↓
wasmcart GL imports → host GPU → swapBuffers → screen
```

## Files

| File | What |
|------|------|
| `wasmcart/porting/include/wc_gl_blit.h` | Single-header GL blit library (texture upload + fullscreen quad) |
| `wasmcart/porting/sdl2_wc/sdl2_gl_blit.c` | Drop-in implementation of `wc_sdl_gl_blit()` for SDL2 carts |
| `wasmcart/porting/sdl2_wc/SDL_wasmcart_video.c` | Updated with `SDL_WASMCART_SetGLBlit()` and GL upload path |
| `wasmcart/porting/sdl2_wc/SDL_wasmcart_video.h` | Header with `SDL_WASMCART_SetGLBlit()` declaration |

## Build Changes

In `build_full.sh`, add to the link step:

```bash
# Add GL blit support
emcc -O2 -I"$(dirname $WASMCART_H)" -I"$PORTING/include" \
    -c "$SDL2_WC/sdl2_gl_blit.c" -o obj/sdl2_gl_blit.o

# Add to LIBS
LIBS="$LIBS obj/sdl2_gl_blit.o"
```

## Testing

After making these changes:

1. `bash build_full.sh` — should compile without errors
2. `bash pack_game.sh examples/spaceshooter/ out/spaceshooter.wasc "Space Shooter"`
3. `node retroemu/bin/cli.js out/spaceshooter.wasc --video sdl --res 1920x1080`
4. Should see the game at 60fps at 1080p (was ~30fps before)

## Retroemu Host Notes

The retroemu host (`retroemu/bin/cli.js`) has been updated:
- `cartUsesGL = hasGLImports` — always provides GL if the cart imports GL functions
- Hybrid check: if cart has GL imports AND fbPtr, keeps GL mode
- The `gpu_api` field is read from `wc_info_t` after `wc_init()` — value > 0 means GL

If you see a black screen, check:
1. Is `gpu_api` set to 1 in `wc_get_info()`?
2. Is `SDL_WASMCART_SetGLBlit(1)` called after SDL_Init?
3. Is `sdl2_gl_blit.c` linked?
4. Does the cart import GL functions? (needed for wc_gl_blit to work)

## Future: Skia Ganesh GL

When Skia's Ganesh GL backend works in WASM (currently blocked by global constructor crash), SDL's software renderer step disappears entirely. Skia renders directly to a GL texture. Zero CPU pixels. This is tracked but not yet implemented.
