# Asset licensing for the examples and ports

**Everything in `examples/` and `ports/` is freely redistributable.** Nothing
ships under a non-commercial or no-derivatives licence, nothing is a
screenshot or extract of a commercial game, and nothing here requires
permission to fork or republish.

Three examples originally shipped ~68 MB of third-party art with no
provenance -- Doom wall textures, a licensed cat model, photographic
skyboxes. None of it could be redistributed, so all of it was replaced.

## Kenney (CC0, public domain)

From the *Kenney Game Assets All-in-1* bundle. CC0 waives copyright
entirely: no attribution is required, and redistribution is unrestricted.
Kenney asks that the **bundle** not be redistributed but that individual
packs and assets may be -- which is what this repo does.

| Example | Asset | Pack |
|---|---|---|
| `3d_engine` | cat model + colormap | Cube Pets |
| `3d_engine` | wall / floor textures | Pattern Pack (tiled + tinted by `tools/make_3d_engine_textures.py`) |
| `doom_py` | NPC sprites (3 monsters) | Monster Builder Pack |
| `doom_py` | weapon + impact sounds | Retro Sounds 1, Impact Sounds |
| `doom_py` | music | Music Loops |
| `spaceshooter` | ships, rocks, UI | Space Shooter (CC-BY 3.0, credited in `main.py`) |
| `spaceshooter` | music | Music Loops |

## Generated for this project (MIT, same as the repo)

Built by scripts in `tools/`, so they can be regenerated and audited:

| Example | Asset | Generator |
|---|---|---|
| `3d_engine` | skybox cubemap (6 faces) | `tools_make_skybox.py` |
| `doom_py` | 5 tiling brick wall textures | `tools/make_doom_assets.py` |
| `doom_py` | sky, HUD digits, overlays | `tools/make_doom_assets.py` |
| `doom_py` | weapon frames, lights, scenery | `tools/make_doom_assets.py` |

Regenerating is deterministic -- the scripts seed their RNG -- so a rebuild
produces byte-identical output.

## Upstream code

The example *code* keeps its own licence. `spaceshooter` is derived from
tasdik's MIT-licensed Space Shooter, credited in its header. `3d_engine`,
`doom_py` and `threepy` are ports of community tutorial projects, rewritten
here against the wasmcart runtime.

## Removed

`threepy` shipped 5.5 MB of textures (earth, moon, sun, lava…) that no code
path loads -- it renders an untextured spinning cube. Deleted rather than
replaced.

## `ports/solarwolf`

SolarWolf is Pete Shinners' own game, LGPL, and its art and music ship under
that licence: graphics by Eero Tamminen, music by "theGREENzebra". All of it
is redistributable and all of it is here byte-identical to upstream, except
for one file.

| Excluded | Why | Replaced by |
|---|---|---|
| `data/oldsolarfox.png` | a screenshot of the Atari 2600 commercial game, referenced once from `gamecreds.py` | `tools/make_solarwolf_assets.py` -- an original stylised retro console at the same 235x210 |

The generator uses no RNG, so a rebuild is byte-identical. The upstream
screenshot is not in this repo's history.

`ports/solarwolf/lgpl.txt` is upstream's own licence text, kept so the LGPL
attribution travels with the code it covers.
