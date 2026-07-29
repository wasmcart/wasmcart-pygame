#!/usr/bin/env python3
"""
patch_pygame.py - make pygame-ce's BUILD_STATIC unit compile.

src_c/static.c is the aggregation unit for BUILD_STATIC. Through at least
2.5.7 it still references _sdl2/controller_old.c, which upstream deleted --
so the static build cannot compile as shipped. The deprecated `controller_old`
submodule is simply dropped; pygame._sdl2.controller is the supported one and
is included right above it.

Idempotent: re-running on a patched tree is a no-op, so build.sh can call it
unconditionally.
"""
import re, sys, pathlib

src = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else 'vendor/pygame-ce/src_c/static.c')
text = src.read_text()

_static_done = 'wasmcart: controller_old dropped' in text
if _static_done:
    print('static.c already patched')

before = text if not _static_done else None
text = text.replace('#include "_sdl2/controller_old.c"',
                    '/* wasmcart: controller_old dropped (deleted upstream) */')
text = re.sub(r'^PyMODINIT_FUNC\nPyInit_controller_old\(void\);\n',
              '/* wasmcart: controller_old dropped (deleted upstream) */\n',
              text, flags=re.M)
text = re.sub(r'^\s*load_submodule_mphase\("pygame\._sdl2", PyInit_controller_old\(\), spec,\s*\n\s*"controller_old"\);\s*$\n',
              '', text, flags=re.M)

# pygame._sdl2 is Cython-generated: sdl2.c, mixer.c, audio.c and video.c are
# produced from .pyx at upstream build time and are absent from a source
# checkout. static.c calls their PyInit_* anyway, so the symbols stay
# unresolved -- and with -sERROR_ON_UNDEFINED_SYMBOLS=0 they become imports
# that TRAP the instant PyInit_pygame_static is entered, before its first
# statement. That is the "unreachable" this project has had since May.
#
# pygame._sdl2 is a niche API (raw SDL access); dropping it costs nothing for
# ordinary pygame games and makes the static build link honestly.
text = re.sub(r'^\s*load_submodule_mphase\("pygame\._sdl2", PyInit_(sdl2|mixer|audio|video)\(\), spec,?\s*\n?\s*"\1"\);\s*$\n',
              '', text, flags=re.M)
# Remove the WHOLE forward declaration -- "PyMODINIT_FUNC\nPyInit_x(void);" --
# not just the name line, or PyMODINIT_FUNC is left dangling and expands into
# a bare "PyObject*" statement.
text = re.sub(r'^PyMODINIT_FUNC\nPyInit_(sdl2|mixer|audio|video)\(void\);\n',
              '/* wasmcart: pygame._sdl2 \\1 dropped (Cython-generated, not in source) */\n',
              text, flags=re.M)

if text == before:
    print('nothing to patch (upstream may have fixed it)', file=sys.stderr)
else:
    src.write_text(text)
    print(f'patched {src}: dropped controller_old from the static build')


# ---------------------------------------------------------------------------
# rwobject.c: let a file object be a resource under Emscripten.
#
# pgRWops_FromObject has two branches. The ordinary one falls through to
# pgRWops_FromFileObject, so pygame accepts any Python file-like object. The
# __EMSCRIPTEN__ branch omits that call and raises "can't access resource on
# platform" instead, leaving SDL_RWFromFile as the only way in.
#
# A wasmcart cart has no real filesystem: assets live in the .wasc and reach
# Python through the asset shim, which hands back a BytesIO. With the fallback
# missing, every pygame.font.Font() fails -- including Font(None, size), since
# the bundled default font is itself an asset. Restoring the fallback is what
# the other branch already does.
rw = src.parent / 'rwobject.c'
if rw.exists():
    rtext = rw.read_text()
    if 'wasmcart: accept file objects' in rtext:
        print('rwobject.c already patched')
    else:
        anchor = """fail:
    if (retry)
        return RAISE(PyExc_RuntimeError, "can't access resource on platform");"""
        replacement = """fail:
    if (retry) {
        /* wasmcart: accept file objects here too, exactly as the non-Emscripten
         * branch below does. Cart assets arrive as file-like objects, not real
         * paths, so without this every resource load fails. */
        PyErr_Clear();
        return pgRWops_FromFileObject(obj);
    }"""
        if anchor not in rtext:
            print('rwobject.c: anchor not found (upstream may have changed)',
                  file=sys.stderr)
        else:
            rw.write_text(rtext.replace(anchor, replacement, 1))
            print(f'patched {rw}: file objects usable as resources')


# ---------------------------------------------------------------------------
# pixelcopy.c: give the channel-selector converter its own BUILD_STATIC copy.
#
# surface.c and pixelcopy.c each define `static int _view_kind(PyObject *,
# void *)` -- a PyArg converter that turns 'R'/'G'/'B'/'A' into an enum --
# and each has its OWN, DIFFERENT enum:
#
#   surface.c:  0D=0 1D=1 2D=2 3D=3 RED=4 GREEN=5 BLUE=6 ALPHA=7
#   pixelcopy:  RED=0 GREEN=1 BLUE=2 ALPHA=3 COLORKEY=4 RGB=5
#
# In an ordinary build these are separate translation units and the duplicate
# name is harmless. BUILD_STATIC #includes every .c into one unit, so upstream
# wraps pixelcopy's copy in `#if !defined(BUILD_STATIC)` to dodge the redefinition
# error. That silences the compiler but is semantically wrong: pixelcopy's call
# then binds to SURFACE.C's converter, which returns surface.c's enum values,
# and pixelcopy reads them as its own. Every channel selector is mistranslated:
#
#   'R' -> 4 -> COLORKEY : array_red() returns 255 everywhere (the opaque fill)
#   'G' -> 5 -> RGB      : routed to _copy_mapped, "target byte size of 4"
#   'B' -> 6, 'A' -> 7   : outside pixelcopy's enum -> default: -> the
#                          assertion at _copy_colorplane:309, which under wasm
#                          is an abort/unreachable, NOT a catchable exception
#
# So on a static build array_red/green/blue/alpha/colorkey and the pixels_*
# channel views are variously wrong or fatal. Confirmed live: 'R' gave all-255,
# 'G' raised the byte-size error, 'B' aborted the cart.
#
# The fix is to give pixelcopy a correctly-named converter that is compiled in
# BOTH configurations, and point its own call at it.
pc = src.parent / 'pixelcopy.c'
if pc.exists():
    ptext = pc.read_text()
    if 'wasmcart: pixelcopy needs its OWN' in ptext:
        print('pixelcopy.c already patched')
    else:
        converter = '''
/* wasmcart: pixelcopy needs its OWN view-kind converter under BUILD_STATIC.
 *
 * Upstream excludes the one above via `#if !defined(BUILD_STATIC)` so it does
 * not clash with the identically named function in surface.c. But surface.c's
 * converter yields SURFACE.C's enum (RED=4, GREEN=5, BLUE=6, ALPHA=7), while
 * the code below indexes pixelcopy's (RED=0 ... COLORKEY=4, RGB=5). Sharing it
 * silently mistranslates every channel: 'R' becomes COLORKEY, 'G' becomes RGB,
 * and 'B'/'A' fall off the end into an assertion failure.
 *
 * This copy is always compiled and always used by pixelcopy, so the mapping is
 * correct in both build configurations. */
static int
_pc_view_kind_arg(PyObject *obj, void *view_kind_vptr)
{
    unsigned long ch;
    _pc_view_kind_t *view_kind_ptr = (_pc_view_kind_t *)view_kind_vptr;

    if (PyUnicode_Check(obj)) {
        if (PyUnicode_GET_LENGTH(obj) != 1) {
            PyErr_SetString(PyExc_TypeError,
                            "expected a length 1 string for argument 3");
            return 0;
        }
        ch = PyUnicode_READ_CHAR(obj, 0);
    }
    else if (PyBytes_Check(obj)) {
        if (PyBytes_GET_SIZE(obj) != 1) {
            PyErr_SetString(PyExc_TypeError,
                            "expected a length 1 string for argument 3");
            return 0;
        }
        ch = *PyBytes_AS_STRING(obj);
    }
    else {
        PyErr_Format(PyExc_TypeError,
                     "expected a length one string for argument 3: got '%s'",
                     Py_TYPE(obj)->tp_name);
        return 0;
    }
    switch (ch) {
        case 'R':
        case 'r':
            *view_kind_ptr = PXC_VIEWKIND_RED;
            break;
        case 'G':
        case 'g':
            *view_kind_ptr = PXC_VIEWKIND_GREEN;
            break;
        case 'B':
        case 'b':
            *view_kind_ptr = PXC_VIEWKIND_BLUE;
            break;
        case 'A':
        case 'a':
            *view_kind_ptr = PXC_VIEWKIND_ALPHA;
            break;
        case 'C':
        case 'c':
            *view_kind_ptr = VIEWKIND_COLORKEY;
            break;
        case 'P':
        case 'p':
            *view_kind_ptr = VIEWKIND_RGB;
            break;
        default:
            PyErr_Format(PyExc_TypeError,
                         "unrecognized view kind '%c' for argument 3",
                         (int)ch);
            return 0;
    }
    return 1;
}

typedef union {'''

        anchor = '\ntypedef union {'
        if anchor not in ptext:
            print('pixelcopy.c: anchor not found (upstream may have changed)',
                  file=sys.stderr)
        else:
            new = ptext.replace(anchor, converter, 1)
            # Point pixelcopy's own PyArg call at the new converter. It is
            # passed as a bare function pointer, with no parentheses.
            call_old = '&surfobj, _view_kind, (void *)&view_kind'
            call_new = '&surfobj, _pc_view_kind_arg, (void *)&view_kind'
            if call_old not in new:
                print('pixelcopy.c: converter call site not found',
                      file=sys.stderr)
            else:
                new = new.replace(call_old, call_new, 1)
                pc.write_text(new)
                print(f'patched {pc}: added _pc_view_kind_arg and pointed '
                      f'surface_to_array at it')
