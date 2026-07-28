/*
 * cart_shim_minimal.c — Minimal proof-of-concept: CPython in a wasmcart
 *
 * No pygame, no SDL. Just proves:
 *   1. CPython boots inside a wasmcart
 *   2. Python scripts load from .wasc assets via wc_load_asset()
 *   3. Python code writes pixels to the wasmcart framebuffer
 *   4. Relative imports work (main.py imports helper.py)
 */

#include <stdint.h>
#include <string.h>
#include <stdlib.h>
#include <stdio.h>
#include <sys/stat.h>
#include <Python.h>

/* Frozen stdlib modules (encodings, codecs, io, abc) */
#include "frozen_stdlib.c"

/* Frozen OpenGL package shims */
#include "frozen_opengl.c"

/* OpenGL C extension */
extern PyMODINIT_FUNC PyInit__opengl_gl(void);
#include "wasmcart.h"

/* ── Cart configuration ──────────────────────────────────────────── */

#define WIDTH  320
#define HEIGHT 240
#define AUDIO_CAP 1024

/* ── Static buffers ──────────────────────────────────────────────── */

static uint32_t     framebuffer[WIDTH * HEIGHT];
static float        audio_ring[AUDIO_CAP * 2];
static uint32_t     audio_write_cursor;
static wc_pad_t     pads[4];
static wc_time_t    time_info;
static wc_info_t    info;
static wc_host_info_t host_info;
static wc_pointer_t pointers[10];
static uint8_t      keys[32];

static int initialized = 0;

/* ── wc_get_info ─────────────────────────────────────────────────── */

__attribute__((export_name("wc_get_info")))
wc_info_t *wc_get_info(void) {
    info.version         = WC_ABI_VERSION;
    info.width           = WIDTH;
    info.height          = HEIGHT;
    info.fb_ptr          = (uint32_t)(uintptr_t)framebuffer;
    info.audio_ptr       = (uint32_t)(uintptr_t)audio_ring;
    info.audio_cap       = AUDIO_CAP;
    info.audio_write_ptr = (uint32_t)(uintptr_t)&audio_write_cursor;
    info.input_ptr       = (uint32_t)(uintptr_t)pads;
    info.save_ptr        = 0;
    info.save_size       = 0;
    info.time_ptr        = (uint32_t)(uintptr_t)&time_info;
    info.host_info_ptr   = (uint32_t)(uintptr_t)&host_info;
    info.flags           = WC_FLAG_AUDIO_F32;
    info.audio_sample_rate = 0;
    info.pointer_ptr     = (uint32_t)(uintptr_t)pointers;
    info.keys_ptr        = (uint32_t)(uintptr_t)keys;
    return &info;
}

/* ── _wasmcart C extension module ────────────────────────────────── */

/* Expose framebuffer pointer and dimensions to Python */
static PyObject *py_get_fb_info(PyObject *self, PyObject *args) {
    return Py_BuildValue("(KII)",
        (unsigned long long)(uintptr_t)framebuffer, WIDTH, HEIGHT);
}

/* Set a pixel in the framebuffer: set_pixel(x, y, argb) */
static PyObject *py_set_pixel(PyObject *self, PyObject *args) {
    int x, y;
    uint32_t color;
    if (!PyArg_ParseTuple(args, "iiI", &x, &y, &color))
        return NULL;
    if (x >= 0 && x < WIDTH && y >= 0 && y < HEIGHT)
        framebuffer[y * WIDTH + x] = color;
    Py_RETURN_NONE;
}

/* Fill a rect: fill_rect(x, y, w, h, argb) */
static PyObject *py_fill_rect(PyObject *self, PyObject *args) {
    int x, y, w, h;
    uint32_t color;
    if (!PyArg_ParseTuple(args, "iiiiI", &x, &y, &w, &h, &color))
        return NULL;
    for (int row = y; row < y + h && row < HEIGHT; row++) {
        if (row < 0) continue;
        for (int col = x; col < x + w && col < WIDTH; col++) {
            if (col < 0) continue;
            framebuffer[row * WIDTH + col] = color;
        }
    }
    Py_RETURN_NONE;
}

/* Clear framebuffer: clear(argb) */
static PyObject *py_clear(PyObject *self, PyObject *args) {
    uint32_t color;
    if (!PyArg_ParseTuple(args, "I", &color))
        return NULL;
    for (int i = 0; i < WIDTH * HEIGHT; i++)
        framebuffer[i] = color;
    Py_RETURN_NONE;
}

/* Get pad state: get_pad(index) -> (buttons, lx, ly, rx, ry, lt, rt, connected) */
static PyObject *py_get_pad(PyObject *self, PyObject *args) {
    int idx;
    if (!PyArg_ParseTuple(args, "i", &idx))
        return NULL;
    if (idx < 0 || idx >= 4)
        Py_RETURN_NONE;
    wc_pad_t *p = &pads[idx];
    return Py_BuildValue("(Hhhhhbbi)",
        p->buttons, p->left_x, p->left_y, p->right_x, p->right_y,
        p->left_trigger, p->right_trigger, p->connected);
}

/* Get time: get_time() -> (time_ms, delta_ms, frame) */
static PyObject *py_get_time(PyObject *self, PyObject *args) {
    return Py_BuildValue("(ddI)", time_info.time_ms, time_info.delta_ms, time_info.frame);
}

/* Asset loading */
static PyObject *py_asset_size(PyObject *self, PyObject *args) {
    const char *path;
    Py_ssize_t path_len;
    if (!PyArg_ParseTuple(args, "s#", &path, &path_len))
        return NULL;
    return PyLong_FromLong(wc_asset_size(path, (unsigned int)path_len));
}

static PyObject *py_load_asset(PyObject *self, PyObject *args) {
    const char *path;
    Py_ssize_t path_len;
    if (!PyArg_ParseTuple(args, "s#", &path, &path_len))
        return NULL;
    int size = wc_asset_size(path, (unsigned int)path_len);
    if (size < 0)
        Py_RETURN_NONE;
    PyObject *buf = PyBytes_FromStringAndSize(NULL, size);
    if (!buf)
        return NULL;
    int loaded = wc_load_asset(path, (unsigned int)path_len,
                               PyBytes_AS_STRING(buf), size);
    if (loaded < 0) {
        Py_DECREF(buf);
        Py_RETURN_NONE;
    }
    return buf;
}

static PyObject *py_log(PyObject *self, PyObject *args) {
    const char *msg;
    Py_ssize_t msg_len;
    if (!PyArg_ParseTuple(args, "s#", &msg, &msg_len))
        return NULL;
    wc_log(msg, (unsigned int)msg_len);
    Py_RETURN_NONE;
}

static PyMethodDef wasmcart_methods[] = {
    {"get_fb_info", py_get_fb_info, METH_NOARGS,  "Get (fb_ptr, width, height)"},
    {"set_pixel",   py_set_pixel,   METH_VARARGS, "set_pixel(x, y, argb)"},
    {"fill_rect",   py_fill_rect,   METH_VARARGS, "fill_rect(x, y, w, h, argb)"},
    {"clear",       py_clear,       METH_VARARGS, "clear(argb)"},
    {"get_pad",     py_get_pad,     METH_VARARGS, "get_pad(index) -> pad tuple"},
    {"get_time",    py_get_time,    METH_NOARGS,  "get_time() -> (time_ms, delta_ms, frame)"},
    {"asset_size",  py_asset_size,  METH_VARARGS, "asset_size(path) -> int"},
    {"load_asset",  py_load_asset,  METH_VARARGS, "load_asset(path) -> bytes or None"},
    {"log",         py_log,         METH_VARARGS, "log(message)"},
    {NULL, NULL, 0, NULL}
};

static struct PyModuleDef wasmcart_module = {
    PyModuleDef_HEAD_INIT, "_wasmcart", NULL, -1, wasmcart_methods
};

PyMODINIT_FUNC PyInit__wasmcart(void) {
    return PyModule_Create(&wasmcart_module);
}

/* ── Boot script ─────────────────────────────────────────────────── */

static const char *boot_script =
    "import sys\n"
    "import _wasmcart\n"
    "from _frozen_importlib import ModuleSpec\n"
    "_ModuleType = type(sys)\n"
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
    "        source = data.decode('utf-8')\n"
    "        code = compile(source, self._src_path, 'exec')\n"
    "        exec(code, module.__dict__)\n"
    "\n"
    "class _WascFinder:\n"
    "    def find_spec(self, fullname, path, target=None):\n"
    "        parts = fullname.replace('.', '/')\n"
    "        # Search order: game assets first, then stdlib\n"
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
    "        mod.__file__ = src_path\n"
    "        mod.__loader__ = self\n"
    "        if is_pkg:\n"
    "            mod.__package__ = fullname\n"
    "            mod.__path__ = [f'assets/{parts}']\n"
    "        else:\n"
    "            mod.__package__ = fullname.rpartition('.')[0]\n"
    "        sys.modules[fullname] = mod\n"
    "        code = compile(source, src_path, 'exec')\n"
    "        exec(code, mod.__dict__)\n"
    "        return mod\n"
    "\n"
    "sys.meta_path.insert(0, _WascFinder())\n"
    "_wasmcart.log('wasc importer registered')\n"
    "import main\n"
;

/* ── wc_init ─────────────────────────────────────────────────────── */

__attribute__((export_name("wc_init")))
void wc_init(void) {
    PyImport_AppendInittab("_wasmcart", PyInit__wasmcart);
    PyImport_AppendInittab("_opengl_gl", PyInit__opengl_gl);

    /*
     * Extend CPython's frozen module table with our stdlib modules.
     * This allows Py_Initialize to find encodings, codecs, io, abc
     * without any filesystem access.
     */
    {
        /* Count existing frozen modules */
        const struct _frozen *existing = PyImport_FrozenModules;
        int existing_count = 0;
        while (existing[existing_count].name != NULL)
            existing_count++;

        /* Count our custom frozen modules */
        int custom_count = 0;
        while (custom_frozen_modules[custom_count].name != NULL)
            custom_count++;

        /* Count OpenGL frozen modules */
        int opengl_count = 0;
        while (frozen_opengl_modules[opengl_count].name != NULL)
            opengl_count++;

        /* Allocate combined table */
        int total = existing_count + custom_count + opengl_count + 1;
        struct _frozen *combined = malloc(total * sizeof(struct _frozen));

        /* Copy existing frozen modules first */
        memcpy(combined, existing, existing_count * sizeof(struct _frozen));

        /* Append stdlib modules */
        memcpy(combined + existing_count, custom_frozen_modules,
               custom_count * sizeof(struct _frozen));

        /* Append OpenGL modules */
        memcpy(combined + existing_count + custom_count, frozen_opengl_modules,
               (opengl_count + 1) * sizeof(struct _frozen));  /* +1 for sentinel */

        /* Replace the frozen table */
        PyImport_FrozenModules = combined;
    }

    /* Configure CPython for embedded use */
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
    config.configure_c_stdio = 0;
    config.buffered_stdio = 0;

    /* Point Python home at our virtual filesystem stdlib */
    PyConfig_SetString(&config, &config.home, L"/");
    PyConfig_SetString(&config, &config.program_name, L"/wasmcart");

    /* Set module search paths */
    config.module_search_paths_set = 1;
    PyWideStringList_Append(&config.module_search_paths, L"/lib/python3.13");

    PyStatus status = Py_InitializeFromConfig(&config);
    PyConfig_Clear(&config);
    if (PyStatus_Exception(status)) {
        if (status.err_msg) {
            wc_log(status.err_msg, strlen(status.err_msg));
        }
        WC_LOG("ERROR: Py_Initialize failed");
        return;
    }

    WC_LOG("Python initialized, running boot script...");

    int rc = PyRun_SimpleString(boot_script);
    if (rc != 0) {
        WC_LOG("ERROR: boot script failed");
        /* Try to capture the error with minimal imports */
        PyRun_SimpleString(
            "import sys, _wasmcart\n"
            "ei = sys.exc_info()\n"
            "if ei[0]:\n"
            "    _wasmcart.log(f'{ei[0].__name__}: {ei[1]}')\n"
            "elif hasattr(sys, 'last_type') and sys.last_type:\n"
            "    _wasmcart.log(f'{sys.last_type.__name__}: {sys.last_value}')\n"
        );
        return;
    }

    initialized = 1;
    WC_LOG("python cart initialized");
}

/* ── wc_render ───────────────────────────────────────────────────── */

__attribute__((export_name("wc_render")))
void wc_render(void) {
    if (!initialized)
        return;

    PyObject *main_mod = PyImport_ImportModule("main");
    if (main_mod) {
        PyObject *result = PyObject_CallMethod(main_mod, "_wc_frame", NULL);
        Py_XDECREF(result);
        Py_DECREF(main_mod);
    }

    if (PyErr_Occurred()) {
        PyErr_Print();
        PyErr_Clear();
    }
}
