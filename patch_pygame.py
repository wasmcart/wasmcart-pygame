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

if 'wasmcart: controller_old dropped' in text:
    print('static.c already patched')
    raise SystemExit(0)

before = text
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
    raise SystemExit(0)

src.write_text(text)
print(f'patched {src}: dropped controller_old from the static build')
