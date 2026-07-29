/*
 * cart_shim.c — wasmcart ABI entry point for CPython + pygame-ce
 *
 * This is the reusable cart runtime. It:
 *   1. Exports wc_get_info / wc_init / wc_render (the wasmcart ABI)
 *   2. Boots CPython with frozen stdlib + built-in pygame + OpenGL
 *   3. Registers import hook: game .py files load from .wasc assets
 *   4. Pumps SDL2 audio and runs game frames
 *
 * Game loop:
 *   ASYNCIFY suspends the WASM stack at SDL_Delay/clock.tick().
 *   Standard "while True: ... clock.tick(60)" loops work unmodified.
 *   Games can also export _wc_frame() for callback mode.
 *
 * Built-in packages (no pip install needed):
 *   - pygame (pygame-ce, compiled against sdl2_wc)
 *   - OpenGL.GL (GLES3 backed by wasmcart GL ABI)
 *   - Full Python 3.13 stdlib (loaded from .wasc assets)
 */

#include <stdint.h>
#include <string.h>
#include <stdlib.h>
#include <stdio.h>
#include <sys/stat.h>
#include <Python.h>
#include "wasmcart.h"
#include "SDL_wasmcart_video.h"
#include "SDL_wasmcart_audio.h"
#include "SDL_wasmcart_joystick.h"
#include <SDL.h>
#include <SDL_ttf.h>
#include <SDL_image.h>
#include <SDL_mixer.h>

#ifdef __EMSCRIPTEN__
#include <emscripten.h>
#endif

/* ── Frozen modules ──────────────────────────────────────────────── */

/* Minimal stdlib frozen into the binary (needed before import hook exists) */
#include "frozen_stdlib.c"

/* OpenGL package shims */
#include "frozen_opengl.c"

/* OpenGL C extension */
extern PyMODINIT_FUNC PyInit__opengl_gl(void);

/* pygame-ce (BUILD_STATIC) */
extern PyObject *PyInit_base(void);
/* PyMODINIT_FUNC, i.e. PyObject * -- NOT void. Declaring it void here made
 * the call an indirect call with a mismatched signature, which wasm traps as
 * `unreachable`/"memory access out of bounds" the instant it is entered,
 * before any statement of the callee runs. Nothing in the C source looks
 * wrong; the crash only shows up at runtime. */
extern PyObject *PyInit_pygame_static(void);

/*
 * Wrapper: create the pygame package, add it to sys.modules,
 * THEN call PyInit_base which populates it via load_submodule.
 */
/*
 * Wrapper for PyInit_base that adds 'pygame' to sys.modules
 * BEFORE PyInit_pygame_static runs, so load_submodule can find the parent.
 *
 * Flow: PyModule_Create -> add to sys.modules -> load_submodule works
 *       -> PyInit_pygame_static registers all submodules
 */
static PyObject *_pygame_init_wrapper(void) {
    /* Create placeholder */
    PyObject *placeholder = PyModule_New("pygame");
    PyObject *modules = PyImport_GetModuleDict();
    PyDict_SetItemString(modules, "pygame", placeholder);
    PyObject *path_list = PyList_New(0);
    PyObject_SetAttrString(placeholder, "__path__", path_list);
    Py_DECREF(path_list);

    /* PyInit_base builds pygame.base only. The submodules (display, rect,
     * font, draw, ...) are registered by PyInit_pygame_static, which is the
     * entry point of static.c, the BUILD_STATIC aggregation unit.
     *
     * This used to call PyInit_base alone, so `import pygame` succeeded and
     * every submodule was missing: "module 'pygame' has no attribute
     * 'display'". The comment above already described calling it -- the call
     * itself was never there. */
    /* static.c's PyInit_pygame_static calls PyInit_base itself, as the first
     * of its load_submodule calls -- so calling both here double-initializes
     * pygame.base and traps. Let the aggregation unit do all of it, then take
     * the base module back out of sys.modules. */
    PyInit_pygame_static();
    if (PyErr_Occurred()) PyErr_Clear();
    PyObject *base_module = PyImport_ImportModule("pygame.base");
    if (!base_module) { PyErr_Clear(); base_module = placeholder; Py_INCREF(base_module); }

    /* BUILD_STATIC's PyInit_pygame_static can leave stale exceptions
     * from submodules that fail to init (color, system). Clear them
     * so subsequent C API calls don't trigger SystemError. */
    if (PyErr_Occurred()) PyErr_Clear();

    if (base_module) {
        /* Copy all submodule references from placeholder to base_module */
        PyObject *base_dict = PyModule_GetDict(base_module);
        PyObject *placeholder_dict = PyModule_GetDict(placeholder);

        /* Iterate placeholder attrs and copy pygame.* submodules */
        PyObject *key, *value;
        Py_ssize_t pos = 0;
        while (PyDict_Next(placeholder_dict, &pos, &key, &value)) {
            const char *name = PyUnicode_AsUTF8(key);
            if (name && !PyDict_Contains(base_dict, key)) {
                PyDict_SetItem(base_dict, key, value);
            }
        }

        /* Replace placeholder in sys.modules */
        PyDict_SetItemString(modules, "pygame", base_module);

        /* Fix module identity — must look like the 'pygame' package */
        PyObject_SetAttrString(base_module, "__name__", PyUnicode_FromString("pygame"));
        PyObject_SetAttrString(base_module, "__package__", PyUnicode_FromString("pygame"));
        PyObject_SetAttrString(base_module, "__path__", path_list);
        /* Set __file__ so pkgdata.getResource can find freesansbold.ttf */
        PyObject_SetAttrString(base_module, "__file__", PyUnicode_FromString("stdlib/pygame/__init__.py"));
    }

    Py_DECREF(placeholder);
    return base_module;
}

/* ── Cart configuration ──────────────────────────────────────────── */

#define DEFAULT_WIDTH  640
#define DEFAULT_HEIGHT 480
#define MAX_WIDTH      1920
#define MAX_HEIGHT     1080
#define AUDIO_CAP      8192

/* ── Static buffers ──────────────────────────────────────────────── */

static uint32_t     wc_framebuffer[MAX_WIDTH * MAX_HEIGHT];
static float        wc_audio_ring[AUDIO_CAP * 2];
static uint32_t     wc_audio_write_cursor;
static wc_pad_t     wc_pads[4];
static wc_time_t    wc_time;
static wc_info_t    wc_info;
static wc_host_info_t wc_host_info;
static wc_pointer_t wc_pointers[10];
static uint8_t      wc_keys[32];

static int audio_rate = 0;
static int cart_width = DEFAULT_WIDTH;
static int cart_height = DEFAULT_HEIGHT;
static int initialized = 0;
static int use_callback = 0;

/* ── wc_get_info ─────────────────────────────────────────────────── */

/* Read the game's resolution BEFORE reporting it to the host.
 *
 * pygame.display.set_mode() happens inside wc_init, long after the host has
 * already read wc_get_info and sized its window -- so a game asking for
 * 1600x900 was announced as 640x480 and rendered into a corner. Assets are
 * host imports and readable here, so pack_game.sh writes the resolution it
 * finds in the game's settings into `resolution.txt` and this reads it. */
static void read_declared_resolution(void) {
    char buf[32];
    int n = wc_asset_size("resolution.txt", 14);
    if (n <= 0 || n >= (int)sizeof buf) return;
    if (wc_load_asset("resolution.txt", 14, buf, (unsigned int)n) != n) return;
    buf[n] = 0;
    int w = 0, h = 0;
    if (sscanf(buf, "%dx%d", &w, &h) != 2) return;
    if (w > 0 && w <= MAX_WIDTH && h > 0 && h <= MAX_HEIGHT) {
        cart_width = w;
        cart_height = h;
    }
}

__attribute__((export_name("wc_get_info")))
wc_info_t *wc_get_info(void) {
    read_declared_resolution();
    wc_info.version         = WC_ABI_VERSION;
    wc_info.width           = cart_width;
    wc_info.height          = cart_height;
    wc_info.fb_ptr          = (uint32_t)(uintptr_t)wc_framebuffer;
    wc_info.audio_ptr       = (uint32_t)(uintptr_t)wc_audio_ring;
    wc_info.audio_cap       = AUDIO_CAP;
    wc_info.audio_write_ptr = (uint32_t)(uintptr_t)&wc_audio_write_cursor;
    wc_info.input_ptr       = (uint32_t)(uintptr_t)wc_pads;
    wc_info.save_ptr        = 0;
    wc_info.save_size       = 0;
    wc_info.time_ptr        = (uint32_t)(uintptr_t)&wc_time;
    wc_info.host_info_ptr   = (uint32_t)(uintptr_t)&wc_host_info;
    wc_info.flags           = WC_FLAG_AUDIO_F32 | WC_FLAG_POINTER | WC_FLAG_KEYBOARD;
    wc_info.audio_sample_rate = 0;
    wc_info.pointer_ptr     = (uint32_t)(uintptr_t)wc_pointers;
    wc_info.keys_ptr        = (uint32_t)(uintptr_t)wc_keys;
    wc_info.gpu_api         = 1;  /* Always use GL display path */
    return &wc_info;
}

/* ── _wasmcart C extension module ────────────────────────────────── */

static PyObject *py_get_fb_info(PyObject *self, PyObject *args) {
    return Py_BuildValue("(KII)",
        (unsigned long long)(uintptr_t)wc_framebuffer,
        (unsigned int)cart_width, (unsigned int)cart_height);
}

static PyObject *py_set_pixel(PyObject *self, PyObject *args) {
    int x, y; uint32_t color;
    if (!PyArg_ParseTuple(args, "iiI", &x, &y, &color)) return NULL;
    if (x >= 0 && x < cart_width && y >= 0 && y < cart_height)
        wc_framebuffer[y * cart_width + x] = color;
    Py_RETURN_NONE;
}

static PyObject *py_fill_rect(PyObject *self, PyObject *args) {
    int x, y, w, h; uint32_t color;
    if (!PyArg_ParseTuple(args, "iiiiI", &x, &y, &w, &h, &color)) return NULL;
    for (int row = y; row < y + h && row < cart_height; row++) {
        if (row < 0) continue;
        for (int col = x; col < x + w && col < cart_width; col++) {
            if (col < 0) continue;
            wc_framebuffer[row * cart_width + col] = color;
        }
    }
    Py_RETURN_NONE;
}

static PyObject *py_clear(PyObject *self, PyObject *args) {
    uint32_t color;
    if (!PyArg_ParseTuple(args, "I", &color)) return NULL;
    for (int i = 0; i < cart_width * cart_height; i++)
        wc_framebuffer[i] = color;
    Py_RETURN_NONE;
}

static PyObject *py_get_pad(PyObject *self, PyObject *args) {
    int idx;
    if (!PyArg_ParseTuple(args, "i", &idx)) return NULL;
    if (idx < 0 || idx >= 4) Py_RETURN_NONE;
    wc_pad_t *p = &wc_pads[idx];
    return Py_BuildValue("(Hhhhhbbi)",
        p->buttons, p->left_x, p->left_y, p->right_x, p->right_y,
        p->left_trigger, p->right_trigger, p->connected);
}

/*
 * Rumble.
 *
 * pygame.joystick.Joystick.rumble() is the API a game should reach for, and it
 * works: SDL's joystick driver for wasmcart routes it at the same host imports
 * these call. These are the direct path, for a cart that wants to rumble
 * without opening a joystick -- and, being one call deep instead of three, the
 * one to reach for when the question is whether the ABI itself is wired up.
 *
 * Pad ids are 0-based and match wasmcart pad slots, NOT SDL device indices.
 * The two agree today because the joystick driver refuses to compact its
 * device list for exactly this reason.
 */
static PyObject *py_pad_has_rumble(PyObject *self, PyObject *args) {
    int pad;
    if (!PyArg_ParseTuple(args, "i", &pad)) return NULL;
    if (pad < 0 || pad >= 4) Py_RETURN_FALSE;
    return PyBool_FromLong(wc_pad_has_rumble((unsigned int)pad) ? 1 : 0);
}

static PyObject *py_pad_rumble(PyObject *self, PyObject *args) {
    int pad;
    float low, high;
    unsigned int duration_ms;
    if (!PyArg_ParseTuple(args, "iffI", &pad, &low, &high, &duration_ms))
        return NULL;
    if (pad < 0 || pad >= 4) Py_RETURN_FALSE;
    /* The host clamps intensity and caps duration, so this does not
     * pre-validate: a second clamp here would only disagree with the host on
     * where the edges are. */
    wc_pad_rumble((unsigned int)pad, low, high, duration_ms);
    Py_RETURN_TRUE;
}

static PyObject *py_pad_rumble_stop(PyObject *self, PyObject *args) {
    int pad;
    if (!PyArg_ParseTuple(args, "i", &pad)) return NULL;
    if (pad < 0 || pad >= 4) Py_RETURN_NONE;
    wc_pad_rumble_stop((unsigned int)pad);
    Py_RETURN_NONE;
}

static PyObject *py_get_time(PyObject *self, PyObject *args) {
    return Py_BuildValue("(ddI)", wc_time.time_ms, wc_time.delta_ms, wc_time.frame);
}

static PyObject *py_asset_size(PyObject *self, PyObject *args) {
    const char *path; Py_ssize_t path_len;
    if (!PyArg_ParseTuple(args, "s#", &path, &path_len)) return NULL;
    return PyLong_FromLong(wc_asset_size(path, (unsigned int)path_len));
}

static PyObject *py_load_asset(PyObject *self, PyObject *args) {
    const char *path; Py_ssize_t path_len;
    if (!PyArg_ParseTuple(args, "s#", &path, &path_len)) return NULL;
    int size = wc_asset_size(path, (unsigned int)path_len);
    if (size < 0) Py_RETURN_NONE;
    PyObject *buf = PyBytes_FromStringAndSize(NULL, size);
    if (!buf) return NULL;
    int loaded = wc_load_asset(path, (unsigned int)path_len,
                               PyBytes_AS_STRING(buf), size);
    if (loaded < 0) { Py_DECREF(buf); Py_RETURN_NONE; }
    return buf;
}

/* Switch to GL mode — zeroes fb_ptr so host provides a GL context */
static PyObject *py_set_gl_mode(PyObject *self, PyObject *args) {
    wc_info.fb_ptr = 0;
    Py_RETURN_NONE;
}

/* Update cart resolution — called when pygame.display.set_mode is called */
static PyObject *py_set_resolution(PyObject *self, PyObject *args) {
    int w, h;
    if (!PyArg_ParseTuple(args, "ii", &w, &h)) return NULL;
    if (w > 0 && w <= MAX_WIDTH && h > 0 && h <= MAX_HEIGHT) {
        cart_width = w;
        cart_height = h;
        wc_info.width = w;
        wc_info.height = h;
        SDL_WASMCART_SetFramebuffer(wc_framebuffer, w, h);
    }
    Py_RETURN_NONE;
}

static PyObject *py_clear_err(PyObject *self, PyObject *args) {
    if (PyErr_Occurred()) PyErr_Clear();
    Py_RETURN_NONE;
}

/*
 * _wasmcart.load_image(asset_path) -> pygame.Surface
 * Load an image from .wasc assets via SDL_RWFromConstMem + IMG_Load_RW.
 * Bypasses Python file I/O — goes straight from WASM memory to SDL surface.
 */
#include <SDL_image.h>

/*
 * _wasmcart.load_image(asset_path) -> pygame.Surface
 *
 * Decodes PNG/JPG from .wasc asset using stb_image, creates pygame.Surface
 * via pygame.image.frombuffer(). Bypasses SDL_image entirely.
 */
/* STBI_ONLY_GIF: GIF is not an exotic format for a pygame game -- it is what
 * anything written before PNG-with-alpha became universal uses for sprites
 * with a colorkey. SolarWolf ships ten of them (HUD, starfield, menu badges),
 * and without a GIF decoder each one raised "unknown image type" at load and
 * the game died during resource loading. SDL_image is linked but its
 * emscripten port compiles in only the formats named by SDL2_IMAGE_FORMATS,
 * so it was no help either; stb has a GIF decoder already and enabling it
 * costs a few KB. */
#define STB_IMAGE_IMPLEMENTATION
#define STBI_NO_STDIO
#define STBI_ONLY_PNG
#define STBI_ONLY_JPEG
#define STBI_ONLY_BMP
#define STBI_ONLY_GIF
#include "stb_image.h"

static PyObject *py_load_image(PyObject *self, PyObject *args) {
    const char *path;
    Py_ssize_t path_len;
    if (!PyArg_ParseTuple(args, "s#", &path, &path_len))
        return NULL;

    int size = wc_asset_size(path, (unsigned int)path_len);
    if (size < 0) {
        PyErr_Format(PyExc_FileNotFoundError, "Asset not found: %s", path);
        return NULL;
    }

    unsigned char *buf = malloc(size);
    if (!buf) return PyErr_NoMemory();
    wc_load_asset(path, (unsigned int)path_len, buf, size);

    /* Decode with stb_image */
    int w, h, channels;
    unsigned char *pixels = stbi_load_from_memory(buf, size, &w, &h, &channels, 4);
    free(buf);
    if (!pixels) {
        PyErr_Format(PyExc_RuntimeError, "Failed to decode image: %s (%s)",
                     path, stbi_failure_reason());
        return NULL;
    }

    /* Create pygame.Surface via frombuffer */
    PyObject *pixel_bytes = PyBytes_FromStringAndSize((char*)pixels, w * h * 4);
    stbi_image_free(pixels);
    if (!pixel_bytes) return NULL;

    PyObject *pg_image = PyImport_ImportModule("pygame.image");
    if (!pg_image) { Py_DECREF(pixel_bytes); return NULL; }

    PyObject *size_tuple = Py_BuildValue("(ii)", w, h);
    PyObject *result = PyObject_CallMethod(pg_image, "frombuffer", "OOs",
        pixel_bytes, size_tuple, "RGBA");

    Py_DECREF(pixel_bytes);
    Py_DECREF(size_tuple);
    Py_DECREF(pg_image);
    if (PyErr_Occurred()) PyErr_Clear();
    return result;
}

static PyObject *py_log(PyObject *self, PyObject *args) {
    const char *msg; Py_ssize_t msg_len;
    if (!PyArg_ParseTuple(args, "s#", &msg, &msg_len)) return NULL;
    wc_log(msg, (unsigned int)msg_len);
    Py_RETURN_NONE;
}

/*
 * Sound loading via SDL_mixer — bypasses pygame's file I/O.
 * Returns a lightweight Python wrapper that delegates to Mix_* functions.
 */
static PyObject *py_load_sound(PyObject *self, PyObject *args) {
    const char *path;
    Py_ssize_t path_len;
    if (!PyArg_ParseTuple(args, "s#", &path, &path_len))
        return NULL;

    int size = wc_asset_size(path, (unsigned int)path_len);
    if (size < 0) {
        PyErr_Format(PyExc_FileNotFoundError, "Sound not found: %s", path);
        return NULL;
    }

    /* Load into persistent buffer (Mix_Chunk references it) */
    void *buf = malloc(size);
    if (!buf) return PyErr_NoMemory();
    wc_load_asset(path, (unsigned int)path_len, buf, size);

    SDL_RWops *rw = SDL_RWFromConstMem(buf, size);
    if (!rw) { free(buf); PyErr_SetString(PyExc_RuntimeError, SDL_GetError()); return NULL; }

    Mix_Chunk *chunk = Mix_LoadWAV_RW(rw, 1);
    /* Don't free buf — Mix_Chunk may reference it internally */
    if (!chunk) {
        PyErr_Format(PyExc_RuntimeError, "Mix_LoadWAV failed: %s", Mix_GetError());
        return NULL;
    }

    /* Return the chunk pointer as a Python int — the Python wrapper uses it */
    return PyLong_FromUnsignedLongLong((unsigned long long)(uintptr_t)chunk);
}

static PyObject *py_snd_play(PyObject *self, PyObject *args) {
    unsigned long long ptr; int loops = 0;
    if (!PyArg_ParseTuple(args, "K|i", &ptr, &loops)) return NULL;
    Mix_Chunk *chunk = (Mix_Chunk*)(uintptr_t)ptr;
    int ch = Mix_PlayChannel(-1, chunk, loops);
    return PyLong_FromLong(ch);
}

static PyObject *py_snd_stop(PyObject *self, PyObject *args) {
    unsigned long long ptr;
    if (!PyArg_ParseTuple(args, "K", &ptr)) return NULL;
    /* Can't stop a specific chunk easily — stop all would be too aggressive */
    Py_RETURN_NONE;
}

static PyObject *py_snd_vol(PyObject *self, PyObject *args) {
    unsigned long long ptr; float vol;
    if (!PyArg_ParseTuple(args, "Kf", &ptr, &vol)) return NULL;
    Mix_Chunk *chunk = (Mix_Chunk*)(uintptr_t)ptr;
    Mix_VolumeChunk(chunk, (int)(vol * MIX_MAX_VOLUME));
    Py_RETURN_NONE;
}

/*
 * Streaming music (pygame.mixer.music).
 *
 * pygame's own music.load() goes through SDL_RWFromFile, which is C and never
 * sees the Python-level asset shim, so it cannot reach a file inside the
 * .wasc. It used to be patched to a no-op -- every cart was silent and no
 * error said so. These load the bytes out of the asset and hand SDL_mixer an
 * RWops over them.
 *
 * The buffer must outlive the Mix_Music: SDL_mixer streams from it rather
 * than decoding up front, which matters most for the tracker formats where
 * the whole module stays resident. Only one music track plays at a time, so
 * the previous track's buffer is freed on the next load.
 */
static Mix_Music *current_music = NULL;
static void *current_music_buf = NULL;

static PyObject *py_music_load(PyObject *self, PyObject *args) {
    const char *path;
    Py_ssize_t path_len;
    if (!PyArg_ParseTuple(args, "s#", &path, &path_len)) return NULL;

    int size = wc_asset_size(path, (unsigned int)path_len);
    if (size < 0) {
        PyErr_Format(PyExc_FileNotFoundError, "Music not found: %s", path);
        return NULL;
    }

    void *buf = malloc(size);
    if (!buf) return PyErr_NoMemory();
    wc_load_asset(path, (unsigned int)path_len, buf, size);

    SDL_RWops *rw = SDL_RWFromConstMem(buf, size);
    if (!rw) { free(buf); PyErr_SetString(PyExc_RuntimeError, SDL_GetError()); return NULL; }

    Mix_Music *mus = Mix_LoadMUS_RW(rw, 1);
    if (!mus) {
        free(buf);
        PyErr_Format(PyExc_RuntimeError, "Mix_LoadMUS failed: %s", Mix_GetError());
        return NULL;
    }

    if (current_music) Mix_FreeMusic(current_music);
    if (current_music_buf) free(current_music_buf);
    current_music = mus;
    current_music_buf = buf;
    Py_RETURN_NONE;
}

static PyObject *py_music_play(PyObject *self, PyObject *args) {
    int loops = 0;
    double start = 0.0;
    if (!PyArg_ParseTuple(args, "|id", &loops, &start)) return NULL;
    if (!current_music) Py_RETURN_NONE;
    /* pygame: loops=-1 is forever, loops=n repeats n extra times.
     * SDL_mixer: loops=-1 is forever, loops=n plays n times total. */
    int mix_loops = (loops < 0) ? -1 : loops + 1;
    if (Mix_PlayMusic(current_music, mix_loops) < 0) {
        PyErr_Format(PyExc_RuntimeError, "Mix_PlayMusic failed: %s", Mix_GetError());
        return NULL;
    }
    Py_RETURN_NONE;
}

static PyObject *py_music_stop(PyObject *self, PyObject *args) {
    Mix_HaltMusic();
    Py_RETURN_NONE;
}

static PyObject *py_music_fadeout(PyObject *self, PyObject *args) {
    int ms = 0;
    if (!PyArg_ParseTuple(args, "i", &ms)) return NULL;
    Mix_FadeOutMusic(ms);
    Py_RETURN_NONE;
}

static PyObject *py_music_vol(PyObject *self, PyObject *args) {
    float vol;
    if (!PyArg_ParseTuple(args, "f", &vol)) return NULL;
    if (vol < 0.0f) vol = 0.0f;
    if (vol > 1.0f) vol = 1.0f;
    Mix_VolumeMusic((int)(vol * MIX_MAX_VOLUME));
    Py_RETURN_NONE;
}

static PyObject *py_music_get_vol(PyObject *self, PyObject *args) {
    return PyFloat_FromDouble((double)Mix_VolumeMusic(-1) / MIX_MAX_VOLUME);
}

static PyObject *py_music_busy(PyObject *self, PyObject *args) {
    return PyBool_FromLong(Mix_PlayingMusic() && !Mix_PausedMusic());
}

static PyObject *py_music_pause(PyObject *self, PyObject *args) {
    Mix_PauseMusic();
    Py_RETURN_NONE;
}

static PyObject *py_music_unpause(PyObject *self, PyObject *args) {
    Mix_ResumeMusic();
    Py_RETURN_NONE;
}

static PyMethodDef wasmcart_methods[] = {
    {"get_fb_info", py_get_fb_info, METH_NOARGS,  NULL},
    {"set_pixel",   py_set_pixel,   METH_VARARGS, NULL},
    {"fill_rect",   py_fill_rect,   METH_VARARGS, NULL},
    {"clear",       py_clear,       METH_VARARGS, NULL},
    {"get_pad",     py_get_pad,     METH_VARARGS, NULL},
    {"pad_has_rumble", py_pad_has_rumble, METH_VARARGS, NULL},
    {"pad_rumble",  py_pad_rumble,  METH_VARARGS, NULL},
    {"pad_rumble_stop", py_pad_rumble_stop, METH_VARARGS, NULL},
    {"get_time",    py_get_time,    METH_NOARGS,  NULL},
    {"asset_size",  py_asset_size,  METH_VARARGS, NULL},
    {"load_asset",  py_load_asset,  METH_VARARGS, NULL},
    {"log",         py_log,         METH_VARARGS, NULL},
    {"_clear_err",  py_clear_err,   METH_NOARGS,  NULL},
    {"_set_res",    py_set_resolution, METH_VARARGS, NULL},
    {"_set_gl_mode", py_set_gl_mode, METH_NOARGS, NULL},
    {"load_image",  py_load_image,  METH_VARARGS, NULL},
    {"load_sound",  py_load_sound,  METH_VARARGS, NULL},
    {"_snd_play",   py_snd_play,    METH_VARARGS, NULL},
    {"_snd_stop",   py_snd_stop,    METH_VARARGS, NULL},
    {"_snd_vol",    py_snd_vol,     METH_VARARGS, NULL},
    {"_mus_load",   py_music_load,  METH_VARARGS, NULL},
    {"_mus_play",   py_music_play,  METH_VARARGS, NULL},
    {"_mus_stop",   py_music_stop,  METH_NOARGS,  NULL},
    {"_mus_fadeout",py_music_fadeout, METH_VARARGS, NULL},
    {"_mus_vol",    py_music_vol,   METH_VARARGS, NULL},
    {"_mus_get_vol",py_music_get_vol, METH_NOARGS, NULL},
    {"_mus_busy",   py_music_busy,  METH_NOARGS,  NULL},
    {"_mus_pause",  py_music_pause, METH_NOARGS,  NULL},
    {"_mus_unpause",py_music_unpause, METH_NOARGS, NULL},
    {NULL, NULL, 0, NULL}
};

static struct PyModuleDef wasmcart_module = {
    PyModuleDef_HEAD_INIT, "_wasmcart", NULL, -1, wasmcart_methods
};

PyMODINIT_FUNC PyInit__wasmcart(void) {
    return PyModule_Create(&wasmcart_module);
}

/* ── SDL clock override ──────────────────────────────────────────── */

/*
 * SDL_GetTicks/SDL_GetTicks64 report wall-clock time, which is the wrong
 * clock for a cart. The host owns the frame cadence -- it decides when
 * wc_render is called, and it may run frames faster than real time (a
 * headless --frames screenshot run) or slower (a paused debugger). SDL's
 * wall clock tracks none of that.
 *
 * The visible damage is anything a game times in milliseconds. Everything
 * that reads the clock does so through here:
 *
 *   pygame.time.get_ticks()      -> SDL_GetTicks
 *   pygame.time.Clock.tick(fps)  -> SDL_GetTicks deltas + SDL_Delay
 *   Clock.get_fps()
 *
 * In a headless run wc_render is called back-to-back, so wall time barely
 * moves: after 300 frames get_ticks() read 384 ms instead of 7500. Every
 * timed transition stalled -- SolarWolf's splash waits 1200 ms before
 * handing off to the menu and simply never did -- and Clock.tick(40)
 * returned 0 or 1 ms, so every game that scales movement by the frame delta
 * stood still while rendering perfectly. A cart that looks like it is
 * running and is frozen in game-time is exactly the failure that reads as
 * success.
 *
 * So the tick source becomes the host's frame clock. wc_time.time_ms
 * advances one frame's worth per wc_render regardless of how fast the host
 * chooses to call it, which makes game time a function of frames rendered.
 * A game paced this way behaves identically headless and in a window, and a
 * screenshot at frame N shows what frame N should show.
 */
/* Game-time accumulator, advanced once per wc_render.
 *
 * The rule is one frame of game time per frame rendered. Not "however long
 * that frame took": a host may run frames far faster than real time (a
 * headless --frames screenshot pass) or far slower (a window being dragged,
 * a backgrounded tab, a debugger), and in both cases the game should see the
 * same steady cadence. That is what makes a screenshot at frame N
 * reproducible, and what stops a slow frame from teleporting everything that
 * moves.
 *
 * Deriving it from wc_time.delta_ms with a floor was tried first and is
 * subtly wrong: a host that renders a heavy frame in 1.7 ms of wall time
 * passes any floor below that and the clock advances 1.7 ms, so the game
 * still runs ~10x slow while looking correct frame to frame. The nominal
 * step is unconditional for that reason.
 *
 * The host's real delta is still honoured for one thing -- audio pumping,
 * further down -- because that has to match the sample rate of the wall
 * clock the speaker runs on, not game time. */
static double frame_clock_ms = 0.0;
#define FRAME_STEP_MS (1000.0 / 60.0)

static uint64_t sdl_ticks_ms(void) {
    return (uint64_t)frame_clock_ms;
}

uint32_t __wrap_SDL_GetTicks(void) {
    return (uint32_t)sdl_ticks_ms();
}

uint64_t __wrap_SDL_GetTicks64(void) {
    return sdl_ticks_ms();
}

/* ── SDL_Delay override (ASYNCIFY yield point) ───────────────────── */

void __wrap_SDL_Delay(uint32_t ms) {
    (void)ms;
#ifdef __EMSCRIPTEN__
    if (audio_rate > 0) {
        uint32_t delta = (uint32_t)wc_time.delta_ms;
        if (delta == 0) delta = 16;
        wasmcart_audio_pump(wc_audio_ring, AUDIO_CAP,
                            &wc_audio_write_cursor, audio_rate, delta);
    }
    emscripten_sleep(0);
#endif
}

/* ── Boot script ─────────────────────────────────────────────────── */

/* Part 1: just the import hook */
static const char *boot_script_hook =
    "import sys\n"
    "import _wasmcart\n"
    "from _frozen_importlib import ModuleSpec\n"
    "\n"
    "class _WascLoader:\n"
    "    def __init__(self, src_path):\n"
    "        self._src_path = src_path\n"
    "    def create_module(self, spec):\n"
    "        return None\n"
    "    def exec_module(self, module):\n"
    "        data = _wasmcart.load_asset(self._src_path)\n"
    "        if data is None:\n"
    "            raise ImportError(f'Asset not found: {self._src_path}')\n"
    "        # Strip 'assets/' prefix so path.dirname(__file__) works naturally\n"
    "        f = self._src_path\n"
    "        if f.startswith('assets/'):\n"
    "            f = f[7:]\n"
    "        module.__file__ = f\n"
    "        source = data.decode('utf-8')\n"
    "        code = compile(source, self._src_path, 'exec')\n"
    "        exec(code, module.__dict__)\n"
    "\n"
    "class _WascFinder:\n"
    "    def find_spec(self, fullname, path, target=None):\n"
    "        parts = fullname.replace('.', '/')\n"
    "        for prefix in ('assets/', 'stdlib/'):\n"
    "            pkg_path = f'{prefix}{parts}/__init__.py'\n"
    "            mod_path = f'{prefix}{parts}.py'\n"
    "            if _wasmcart.asset_size(pkg_path) >= 0:\n"
    "                loader = _WascLoader(pkg_path)\n"
    "                spec = ModuleSpec(fullname, loader, origin=pkg_path, is_package=True)\n"
    "                spec.submodule_search_locations = [f'{prefix}{parts}']\n"
    "                return spec\n"
    "            if _wasmcart.asset_size(mod_path) >= 0:\n"
    "                loader = _WascLoader(mod_path)\n"
    "                return ModuleSpec(fullname, loader, origin=mod_path)\n"
    "        return None\n"
    "\n"
    "sys.meta_path.insert(0, _WascFinder())\n"
    "_wasmcart.log('wasc importer registered')\n"
;

/* Part 2: load the game */
/* Part 2: load the game */
static const char *boot_script = "import main\n";

/* ── wc_init ─────────────────────────────────────────────────────── */

__attribute__((export_name("wc_init")))
void wc_init(void) {
    /* Resolution from host */
    if (wc_host_info.preferred_width > 0 && wc_host_info.preferred_height > 0) {
        cart_width  = wc_host_info.preferred_width;
        cart_height = wc_host_info.preferred_height;
        if (cart_width > MAX_WIDTH)   cart_width = MAX_WIDTH;
        if (cart_height > MAX_HEIGHT) cart_height = MAX_HEIGHT;
        wc_info.width  = cart_width;
        wc_info.height = cart_height;
    }

    /* Wire up sdl2_wc backends and init SDL BEFORE pygame */
    SDL_WASMCART_SetFramebuffer(wc_framebuffer, cart_width, cart_height);
    SDL_WASMCART_SetPads(wc_pads);
    SDL_WASMCART_SetKeys(wc_keys);
    /* The joystick driver enumerates from this array at subsystem init, so it
     * has to be pointed at the pads before SDL_Init, not after. */
    SDL_WASMCART_SetJoystickPads(wc_pads);
    SDL_WASMCART_SetGLBlit(1);  /* All carts render through GL now */
    /* SDL_INIT_JOYSTICK so pygame.joystick works against real devices --
     * axes, buttons, hat and rumble -- rather than raising "SDL not built with
     * joystick support". pygame.joystick.init() is a no-op once SDL has the
     * subsystem up, so a game that calls it still behaves as upstream. */
    SDL_Init(SDL_INIT_VIDEO | SDL_INIT_AUDIO | SDL_INIT_EVENTS | SDL_INIT_JOYSTICK);
    TTF_Init();
    IMG_Init(IMG_INIT_PNG | IMG_INIT_JPG);
    /* Open audio device BEFORE pygame init — sdl2_wc backend hooks into
     * SDL's audio callback. wasmcart_audio_pump() in wc_render drives
     * the ring buffer. Format: 44100Hz stereo S16 (sdl2_wc handles
     * format negotiation with the host). */
    if (Mix_OpenAudio(44100, AUDIO_F32SYS, 2, 2048) < 0) {
        WC_LOG("WARN: Mix_OpenAudio failed");
    }
    Mix_AllocateChannels(16);

    /* Register built-in C extension modules */
    PyImport_AppendInittab("_wasmcart", PyInit__wasmcart);
    PyImport_AppendInittab("_opengl_gl", PyInit__opengl_gl);
    /* Register pygame as built-in. When Python does 'import pygame',
     * it calls PyInit_base() which in BUILD_STATIC mode calls
     * PyInit_pygame_static() to register all submodules. */
    PyImport_AppendInittab("pygame", _pygame_init_wrapper);

    /* Extend frozen module table with our stdlib + OpenGL */
    {
        const struct _frozen *existing = PyImport_FrozenModules;
        int existing_count = 0;
        while (existing[existing_count].name != NULL) existing_count++;

        int custom_count = 0;
        while (custom_frozen_modules[custom_count].name != NULL) custom_count++;

        int opengl_count = 0;
        while (frozen_opengl_modules[opengl_count].name != NULL) opengl_count++;

        int total = existing_count + custom_count + opengl_count + 1;
        struct _frozen *combined = malloc(total * sizeof(struct _frozen));
        memcpy(combined, existing, existing_count * sizeof(struct _frozen));
        memcpy(combined + existing_count, custom_frozen_modules,
               custom_count * sizeof(struct _frozen));
        memcpy(combined + existing_count + custom_count, frozen_opengl_modules,
               (opengl_count + 1) * sizeof(struct _frozen));
        PyImport_FrozenModules = combined;
    }

    /* Configure CPython */
    PyPreConfig preconfig;
    PyPreConfig_InitIsolatedConfig(&preconfig);
    preconfig.utf8_mode = 1;
    Py_PreInitialize(&preconfig);

    PyConfig config;
    PyConfig_InitPythonConfig(&config);
    config.site_import = 0;
    config.write_bytecode = 0;
    config.user_site_directory = 0;
    config.install_signal_handlers = 0;
    config.pathconfig_warnings = 0;
    config.parse_argv = 0;
    config.configure_c_stdio = 1;
    config.buffered_stdio = 0;  /* unbuffered so print() appears immediately */
    PyConfig_SetString(&config, &config.home, L"/");
    PyConfig_SetString(&config, &config.program_name, L"/wasmcart");
    config.module_search_paths_set = 1;
    PyWideStringList_Append(&config.module_search_paths, L"/");

    PyStatus status = Py_InitializeFromConfig(&config);
    PyConfig_Clear(&config);
    if (PyStatus_Exception(status)) {
        if (status.err_msg) wc_log(status.err_msg, strlen(status.err_msg));
        WC_LOG("ERROR: Py_Initialize failed");
        return;
    }

    WC_LOG("Python initialized");

    /* Set up sys.stdout/stderr if they're None (isolated config issue) */
    PyRun_SimpleString(
        "import sys\n"
        "if sys.stdout is None or sys.stderr is None:\n"
        "    import _io\n"
        "    if sys.stderr is None:\n"
        "        sys.stderr = _io.open(2, 'w', buffering=1, closefd=False)\n"
        "    if sys.stdout is None:\n"
        "        sys.stdout = _io.open(1, 'w', buffering=1, closefd=False)\n"
    );

    /* Register import hook */
    PyRun_SimpleString(boot_script_hook);

    /* Initialize pygame and export submodule APIs at package level */
    WC_LOG("importing pygame...");
    PyRun_SimpleString(
        "import _wasmcart, sys\n"
        "try:\n"
        "    import pygame\n"
        "    # Export submodule APIs to package level (normally done by __init__.py)\n"
        "    _submods = ['base', 'constants', 'rect', 'math', 'color',\n"
        "                'surface', 'display', 'draw', 'event', 'key',\n"
        "                'mouse', 'joystick', 'image', 'font', 'mixer',\n"
        "                'time', 'transform', 'mask', 'gfxdraw',\n"
        "                'pixelcopy', 'pixelarray', 'geometry', 'window']\n"
        "    # First: make submodules accessible as pygame.rect, pygame.display, etc.\n"
        "    for submod_name in _submods:\n"
        "        fqn = f'pygame.{submod_name}'\n"
        "        if fqn in sys.modules:\n"
        "            setattr(pygame, submod_name, sys.modules[fqn])\n"
        "    # Then: export public attrs from key modules (like constants, base, rect)\n"
        "    # but DON'T overwrite submodule references\n"
        "    for submod_name in ['base', 'constants', 'rect', 'surface']:\n"
        "        fqn = f'pygame.{submod_name}'\n"
        "        if fqn in sys.modules:\n"
        "            mod = sys.modules[fqn]\n"
        "            for attr in dir(mod):\n"
        "                if not attr.startswith('_') and attr not in _submods:\n"
        "                    if not hasattr(pygame, attr):\n"
        "                        setattr(pygame, attr, getattr(mod, attr))\n"
        "    # Import Python-based pygame submodules so pygame.sprite etc work\n"
        "    for pymod in ['sprite', 'colordict', 'cursors', 'locals',\n"
        "                  'version', 'sysfont', 'freetype', 'pkgdata',\n"
        "                  'surfarray']:\n"
        "        try:\n"
        "            mod = __import__(f'pygame.{pymod}', fromlist=[pymod])\n"
        "            setattr(pygame, pymod, mod)\n"
        "        except Exception as _e:\n"
        "            _wasmcart.log(f'  pygame.{pymod}: {_e}')\n"
        "    # Upstream pygame/__init__.py does `from pygame.version import *`,\n"
        "    # which is where pygame.ver / pygame.vernum / pygame.rev come from.\n"
        "    # BUILD_STATIC has no __init__.py, so the version module was\n"
        "    # imported and then never re-exported: `pygame.ver` raised\n"
        "    # AttributeError. Games version-gate on it (SolarWolf's txt.py does\n"
        "    # `if pygame.ver <= '1.6.1'` at import time), so a missing ver is a\n"
        "    # hard boot failure, not a cosmetic gap.\n"
        "    try:\n"
        "        _v = sys.modules.get('pygame.version')\n"
        "        if _v is not None:\n"
        "            for _a in getattr(_v, '__all__', ('ver', 'vernum', 'rev', 'SDL')):\n"
        "                if hasattr(_v, _a):\n"
        "                    setattr(pygame, _a, getattr(_v, _a))\n"
        "    except Exception as _e:\n"
        "        _wasmcart.log(f'  pygame.version export: {_e}')\n"
        "    # Wrap pygame.init to clear stale C exceptions after init\n"
        "    _orig_pg_init = pygame.init\n"
        "    def _safe_pg_init():\n"
        "        result = _orig_pg_init()\n"
        "        _wasmcart._clear_err()\n"
        "        return result\n"
        "    pygame.init = _safe_pg_init\n"
        "    _wasmcart.log('pygame ready')\n"
        "except Exception as e:\n"
        "    _wasmcart.log(f'pygame import error: {e}')\n"
    );

    /* Clear any stale C-level exceptions from BUILD_STATIC init */
    if (PyErr_Occurred()) PyErr_Clear();

    /* Run boot script — imports main.py
     * Also monkey-patch pygame.display.set_mode to clear exceptions */
    PyRun_SimpleString(
        "import _wasmcart\n"
        "try:\n"
        "    import pygame.display\n"
        "    _orig_set_mode = pygame.display.set_mode\n"
        "    def _safe_set_mode(*args, **kwargs):\n"
        "        result = _orig_set_mode(*args, **kwargs)\n"
        "        _wasmcart._clear_err()\n"
        "        # Update wasmcart framebuffer to match game's resolution\n"
        "        if args and hasattr(args[0], '__len__') and len(args[0]) >= 2:\n"
        "            _wasmcart._set_res(args[0][0], args[0][1])\n"
        "        return result\n"
        "    pygame.display.set_mode = _safe_set_mode\n"
        "    pygame.set_mode = _safe_set_mode\n"
        "except: pass\n"
    );
    if (PyErr_Occurred()) PyErr_Clear();

    /* Shim file I/O: pygame.image.load, pygame.mixer.Sound, etc.
     * redirect through _wasmcart.load_asset so games that use filesystem
     * paths work transparently with .wasc assets. */
    PyRun_SimpleString(
        "import _wasmcart, _io, sys\n"
        "\n"
        "def _wasc_open(path, mode='rb'):\n"
        "    \"\"\"Open a file from .wasc assets, falling back to real FS.\"\"\"\n"
        "    if isinstance(path, str):\n"
        "        # Normalize path\n"
        "        p = path.replace('\\\\', '/').lstrip('./')\n"
        "        # Try as-is, then under assets/\n"
        "        for prefix in ('', 'assets/'):\n"
        "            data = _wasmcart.load_asset(prefix + p)\n"
        "            if data is not None:\n"
        "                return _io.BytesIO(data)\n"
        "    return None\n"
        "\n"
        "# Patch pygame.image.load\n"
        "#\n"
        "# Two decoders, in this order:\n"
        "#\n"
        "#   1. pygame's own image.load over a BytesIO. That runs SDL_image,\n"
        "#      which returns the surface in the file's NATIVE format -- an\n"
        "#      8-bit indexed surface for a paletted PNG or a GIF, palette\n"
        "#      intact.\n"
        "#   2. _wasmcart.load_image (stb_image), which always decodes to RGBA.\n"
        "#\n"
        "# The order used to be the other way round, and the palette was the\n"
        "# casualty: every image arrived as 32-bit RGBA, so get_palette() raised\n"
        "# 'Surface has no palette to get' and set_palette() did nothing.\n"
        "# Palette-swap recolouring is not a fringe trick -- it is how a sprite\n"
        "# sheet from this era makes its variants (SolarWolf tints one box sheet\n"
        "# four ways, and died in resource loading on the first get_palette).\n"
        "# stb stays as the fallback for anything SDL_image refuses.\n"
        "try:\n"
        "    import pygame.image\n"
        "    _orig_img_load = pygame.image.load\n"
        "    def _wasc_img_load(path, namehint=''):\n"
        "        if isinstance(path, str):\n"
        "            p = path.replace('\\\\', '/').lstrip('./')\n"
        "            for try_path in (f'assets/{p}', p):\n"
        "                if _wasmcart.asset_size(try_path) >= 0:\n"
        "                    data = _wasmcart.load_asset(try_path)\n"
        "                    if data is not None:\n"
        "                        try:\n"
        "                            _wasmcart._clear_err()\n"
        "                            surf = _orig_img_load(_io.BytesIO(data),\n"
        "                                                  namehint or p)\n"
        "                            _wasmcart._clear_err()\n"
        "                            return surf\n"
        "                        except Exception:\n"
        "                            _wasmcart._clear_err()\n"
        "                    _wasmcart._clear_err()\n"
        "                    return _wasmcart.load_image(try_path)\n"
        "        _wasmcart._clear_err()\n"
        "        return _orig_img_load(path, namehint)\n"
        "    pygame.image.load = _wasc_img_load\n"
        "except: pass\n"
        "\n"
        "# Patch pygame.mixer.Sound — load from .wasc via Mix_LoadWAV_RW in C\n"
        "try:\n"
        "    import pygame.mixer\n"
        "    class _WascSound:\n"
        "        def __init__(self, path=None, **kwargs):\n"
        "            self._ptr = 0\n"
        "            if isinstance(path, str):\n"
        "                p = path.replace('\\\\', '/').lstrip('./')\n"
        "                for try_path in (f'assets/{p}', p):\n"
        "                    if _wasmcart.asset_size(try_path) >= 0:\n"
        "                        self._ptr = _wasmcart.load_sound(try_path)\n"
        "                        return\n"
        "        def play(self, loops=0, maxtime=0, fade_ms=0):\n"
        "            # Upstream Sound.play() returns the Channel it grabbed, and\n"
        "            # games use it: `chan = snd.play(); chan.set_volume(l, r)` is\n"
        "            # how stereo panning is done. Returning None made every such\n"
        "            # call site fall into its own error path or crash.\n"
        "            if not self._ptr:\n"
        "                return None\n"
        "            ch = _wasmcart._snd_play(self._ptr, loops)\n"
        "            if ch is None or ch < 0:\n"
        "                return None\n"
        "            try:\n"
        "                return pygame.mixer.Channel(ch)\n"
        "            except Exception:\n"
        "                return None\n"
        "        def stop(self):\n"
        "            if self._ptr: _wasmcart._snd_stop(self._ptr)\n"
        "        def fadeout(self, ms):\n"
        "            self.stop()\n"
        "        def set_volume(self, vol):\n"
        "            if self._ptr: _wasmcart._snd_vol(self._ptr, vol)\n"
        "        def get_volume(self): return 1.0\n"
        "        def get_length(self): return 0.0\n"
        "        def get_num_channels(self): return 0\n"
        "    pygame.mixer.Sound = _WascSound\n"
        "    pygame.Sound = _WascSound\n"
        "except: pass\n"
        "\n"
        "# Patch pygame.mixer.music to stream from .wasc assets.\n"
        "#\n"
        "# pygame's music.load() resolves the path through SDL_RWFromFile, which\n"
        "# is C and never sees the asset shim, so it cannot open anything inside\n"
        "# the cart. This used to be patched to a silent no-op: music.load()\n"
        "# succeeded, music.play() did nothing, and no error was raised -- every\n"
        "# cart was silently mute. These route through Mix_LoadMUS_RW on bytes\n"
        "# pulled out of the .wasc instead.\n"
        "try:\n"
        "    _mus = pygame.mixer.music\n"
        "    def _wasc_music_load(path, *args, **kwargs):\n"
        "        if isinstance(path, str):\n"
        "            p = path.replace('\\\\', '/').lstrip('./')\n"
        "            for try_path in (f'assets/{p}', p):\n"
        "                if _wasmcart.asset_size(try_path) >= 0:\n"
        "                    _wasmcart._mus_load(try_path)\n"
        "                    _wasmcart._clear_err()\n"
        "                    return\n"
        "        raise pygame.error(f'music file not found: {path}')\n"
        "    _mus.load = _wasc_music_load\n"
        "    _mus.play = lambda loops=0, start=0.0, fade_ms=0: _wasmcart._mus_play(loops, start)\n"
        "    _mus.stop = lambda: _wasmcart._mus_stop()\n"
        "    _mus.fadeout = lambda ms: _wasmcart._mus_fadeout(ms)\n"
        "    _mus.set_volume = lambda v: _wasmcart._mus_vol(v)\n"
        "    _mus.get_volume = lambda: _wasmcart._mus_get_vol()\n"
        "    _mus.get_busy = lambda: _wasmcart._mus_busy()\n"
        "    _mus.pause = lambda: _wasmcart._mus_pause()\n"
        "    _mus.unpause = lambda: _wasmcart._mus_unpause()\n"
        "    _mus.unload = lambda: _wasmcart._mus_stop()\n"
        "    _mus.rewind = lambda: None\n"
        "    # set_endevent posts a user event when a track finishes. Nothing\n"
        "    # drives SDL_mixer's finished-music hook into pygame's event queue\n"
        "    # here, so accept and ignore it rather than raising: games use it\n"
        "    # for playlist advance, which degrades to the track just looping.\n"
        "    _mus.set_endevent = lambda *a: None\n"
        "    _mus.get_endevent = lambda: 0\n"
        "except Exception as _e:\n"
        "    _wasmcart.log(f'music shim: {_e}')\n"
        "\n"
        "# Patch pygame.font.Font to load from assets.\n"
        "#\n"
        "# Font(None, size) is the common case and the one that matters most:\n"
        "# pygame resolves the default font through SDL_RWFromFile, which is C\n"
        "# and never sees the asset shim, so on this platform it raises rather\n"
        "# than falling back. The bundled freesansbold.ttf travels in the cart\n"
        "# under stdlib/pygame/, so resolve None to that and hand pygame a file\n"
        "# object, which its RWops layer accepts directly.\n"
        "try:\n"
        "    import pygame.font\n"
        "    _orig_Font = pygame.font.Font\n"
        "    _DEFAULT_FONTS = ('stdlib/pygame/freesansbold.ttf',\n"
        "                      'pygame/freesansbold.ttf',\n"
        "                      'freesansbold.ttf')\n"
        "    def _wasc_open_font(path):\n"
        "        if path is None or path == 'None':\n"
        "            for cand in _DEFAULT_FONTS:\n"
        "                f = _wasc_open(cand)\n"
        "                if f:\n"
        "                    return f\n"
        "            return None\n"
        "        if isinstance(path, str):\n"
        "            return _wasc_open(path)\n"
        "        return None\n"
        "    class _WascFont(_orig_Font):\n"
        "        def __init__(self, path=None, size=20, **kw):\n"
        "            f = _wasc_open_font(path)\n"
        "            if f is not None:\n"
        "                _wasmcart._clear_err()\n"
        "                super().__init__(f, size, **kw)\n"
        "                _wasmcart._clear_err()\n"
        "                return\n"
        "            _wasmcart._clear_err()\n"
        "            super().__init__(path, size, **kw)\n"
        "    pygame.font.Font = _WascFont\n"
        "    pygame.font.SysFont = lambda name, size, bold=False, italic=False: _WascFont(None, size)\n"
        "except: pass\n"
        "\n"
        "# Patch builtins.open for general file access (e.g. json.load)\n"
        "import builtins\n"
        "_orig_open = builtins.open\n"
        "def _wasc_builtin_open(path, mode='r', **kwargs):\n"
        "    if isinstance(path, str) and ('r' in mode) and not path.startswith('/dev'):\n"
        "        f = _wasc_open(path, mode)\n"
        "        if f:\n"
        "            if 'b' not in mode:\n"
        "                return _io.TextIOWrapper(f)\n"
        "            return f\n"
        "    return _orig_open(path, mode, **kwargs)\n"
        "builtins.open = _wasc_builtin_open\n"
        "\n"
        "# Shim os.listdir and os.path.isfile for .wasc assets\n"
        "import os, os.path\n"
        "# Load the asset file list once\n"
        "_wasc_file_list = set()\n"
        "_fl_data = _wasmcart.load_asset('_filelist.txt')\n"
        "if _fl_data:\n"
        "    _wasc_file_list = set(_fl_data.decode('utf-8').strip().split('\\n'))\n"
        "\n"
        "_orig_listdir = os.listdir\n"
        "def _wasc_listdir(path):\n"
        "    p = path.replace('\\\\', '/').rstrip('/')\n"
        "    # Try with and without assets/ prefix\n"
        "    results = set()\n"
        "    for prefix in ('assets/', ''):\n"
        "        full = prefix + p\n"
        "        for f in _wasc_file_list:\n"
        "            if f.startswith(full + '/'):\n"
        "                rest = f[len(full)+1:]\n"
        "                entry = rest.split('/')[0]\n"
        "                if entry:\n"
        "                    results.add(entry)\n"
        "    if results:\n"
        "        return sorted(results)\n"
        "    try:\n"
        "        return _orig_listdir(path)\n"
        "    except:\n"
        "        return []\n"
        "os.listdir = _wasc_listdir\n"
        "\n"
        "_orig_isfile = os.path.isfile\n"
        "def _wasc_isfile(path):\n"
        "    if isinstance(path, str):\n"
        "        p = path.replace('\\\\', '/').lstrip('./')\n"
        "        if p in _wasc_file_list or ('assets/' + p) in _wasc_file_list:\n"
        "            return True\n"
        "    try:\n"
        "        return _orig_isfile(path)\n"
        "    except:\n"
        "        return False\n"
        "os.path.isfile = _wasc_isfile\n"
        "\n"
        "_orig_isdir = os.path.isdir\n"
        "def _wasc_isdir(path):\n"
        "    if isinstance(path, str):\n"
        "        p = path.replace('\\\\', '/').rstrip('/')\n"
        "        for prefix in ('assets/', ''):\n"
        "            full = prefix + p\n"
        "            for f in _wasc_file_list:\n"
        "                if f.startswith(full + '/'):\n"
        "                    return True\n"
        "    try:\n"
        "        return _orig_isdir(path)\n"
        "    except:\n"
        "        return False\n"
        "os.path.isdir = _wasc_isdir\n"
    );
    if (PyErr_Occurred()) PyErr_Clear();

    /* Cooperative threading.
     *
     * WASM here is single-threaded, so _thread.start_new_thread raises
     * RuntimeError('can't start new thread') and Thread.start() propagates
     * it. That is not a niche API: the common pygame idiom for a loading
     * screen is to run the resource loader on a background thread and poll
     * is_alive() from the draw loop, which is exactly what SolarWolf's
     * GameInit does. Without this the game raises before drawing a frame.
     *
     * So start() runs the target inline and returns a thread that is already
     * finished. Semantics a caller can rely on:
     *   - the target runs exactly once, on start()
     *   - is_alive() is False from the first poll, so a progress bar snaps to
     *     done rather than animating; correctness over cosmetics
     *   - an exception in the target propagates out of start(), where a real
     *     thread would print it and keep going. Callers that already wrap the
     *     target body in try/except (SolarWolf does) see no difference.
     *   - join() is a no-op that returns immediately
     * A game that instead expects a thread to run CONCURRENTLY with the draw
     * loop -- streaming, a watchdog, a producer -- is not served by this and
     * cannot be until the runtime grows real threads. */
    PyRun_SimpleString(
        "import _wasmcart\n"
        "try:\n"
        "    import threading\n"
        "    def _wasc_thread_start(self):\n"
        "        if self._started.is_set():\n"
        "            raise RuntimeError('threads can only be started once')\n"
        "        self._started.set()\n"
        "        try:\n"
        "            # Thread.run() already drops _target/_args/_kwargs in its\n"
        "            # own finally, so do not delete them again here.\n"
        "            self.run()\n"
        "        finally:\n"
        "            with threading._active_limbo_lock:\n"
        "                threading._limbo.pop(self, None)\n"
        "    def _wasc_thread_join(self, timeout=None):\n"
        "        if not self._started.is_set():\n"
        "            raise RuntimeError('cannot join thread before it is started')\n"
        "        return None\n"
        "    def _wasc_thread_is_alive(self):\n"
        "        return False\n"
        "    threading.Thread.start = _wasc_thread_start\n"
        "    threading.Thread.join = _wasc_thread_join\n"
        "    threading.Thread.is_alive = _wasc_thread_is_alive\n"
        "except Exception as _e:\n"
        "    _wasmcart.log(f'threading shim: {_e}')\n"
    );
    if (PyErr_Occurred()) PyErr_Clear();

    int rc = PyRun_SimpleString(boot_script);
    if (rc != 0) {
        WC_LOG("ERROR: boot script failed");
        PyRun_SimpleString(
            "import sys, _wasmcart\n"
            "if hasattr(sys, 'last_type') and sys.last_type:\n"
            "    _wasmcart.log(f'{sys.last_type.__name__}: {sys.last_value}')\n"
        );
        return;
    }

    /* Detect game loop mode */
    PyObject *main_mod = PyImport_ImportModule("main");
    if (main_mod && PyObject_HasAttrString(main_mod, "_wc_frame")) {
        use_callback = 1;
    }
    Py_XDECREF(main_mod);

    /* Query audio after pygame.mixer.init() */
    int rate = 0, channels = 0, is_float = 0;
    wasmcart_audio_get_spec(&rate, &channels, &is_float);
    if (rate > 0) {
        audio_rate = rate;
        wc_info.audio_sample_rate = rate;
        char msg[80];
        snprintf(msg, sizeof(msg), "audio: %dHz %s %dch", rate,
                 is_float ? "F32" : "S16", channels);
        wc_log(msg, strlen(msg));
    } else {
        WC_LOG("audio: not initialized (rate=0)");
    }

    initialized = 1;
    WC_LOG("pygame cart initialized");
}

/* ── wc_render ───────────────────────────────────────────────────── */

__attribute__((export_name("wc_render")))
void wc_render(void) {
    if (!initialized) return;

    /* Advance the game clock by one frame. See sdl_ticks_ms above: this, not
     * wall time, is what SDL_GetTicks reports, so pygame.time.get_ticks() and
     * Clock.tick() measure frames rendered rather than seconds elapsed on
     * whatever machine happens to be hosting. */
    frame_clock_ms += FRAME_STEP_MS;

    if (use_callback) {
        /* Pump audio — write enough samples to cover this frame plus a small
         * buffer to prevent underruns. The sdl2_wc audio backend handles
         * leftover callback bytes between frames. */
        if (audio_rate > 0) {
            uint32_t delta = (uint32_t)wc_time.delta_ms;
            if (delta < 8) delta = 17;  /* avoid tiny pumps, aim for ~1 frame */
            wasmcart_audio_pump(wc_audio_ring, AUDIO_CAP,
                                &wc_audio_write_cursor, audio_rate, delta);
        }
        /* Call main._wc_frame() */
        PyObject *main_mod = PyImport_ImportModule("main");
        if (main_mod) {
            PyObject *result = PyObject_CallMethod(main_mod, "_wc_frame", NULL);
            Py_XDECREF(result);
            Py_DECREF(main_mod);
        }
    } else {
#ifdef __EMSCRIPTEN__
        /* ASYNCIFY: resume the suspended game stack */
        emscripten_sleep(0);
#endif
    }

    if (PyErr_Occurred()) {
        PyErr_Print();
        PyErr_Clear();
    }
}
