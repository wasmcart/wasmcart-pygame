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
