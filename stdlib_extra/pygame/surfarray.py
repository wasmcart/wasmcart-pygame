"""pygame.surfarray for wasmcart -- the numpy bridge, without numpy.

Why this is not upstream's surfarray.py
---------------------------------------
Upstream src_py/surfarray.py is a thin wrapper whose reference functions all
funnel through one line:

    numpy_array(surface.get_view("3"), copy=False)

That asks numpy to alias a foreign, strided C buffer with zero copying. The
wasmcart numpy shim (stdlib_extra/numpy/) is a `list` subclass, and a Python
list fundamentally cannot alias someone else's memory. Bundling upstream and
"extending the shim until it works" would therefore have produced `pixels3d`
returning a COPY -- and a copy is worse than nothing here, because every game
that mutates pixels in place would silently render an unchanged surface while
reporting a perfect frame count. That is precisely the failure mode that made
mixer.music a silent `pass` and every cart mute.

So the reference (`pixels*`) side is implemented natively against the real
buffer, and the copying side delegates to the pixelcopy C extension, which is
already compiled into cart.wasm.

What makes true live views possible
-----------------------------------
Surface.get_view("3") returns a BufferProxy exporting a genuine 3D strided
PEP-3118 buffer, and CPython's memoryview writes straight through it:

    mv = memoryview(surf.get_view("3"))
    mv[0, 0, 0] = 200        -> surf.get_at((0, 0)) becomes (200, ...)

That is verified live, not assumed. Note the last axis carries a NEGATIVE
stride (BGR byte order in a little-endian pixel), which full-index memoryview
access handles correctly.

Two CPython memoryview limits shape the code below:
  * multi-dimensional SUB-views are not implemented, so `mv[x, y]` raises.
    Partial indexing is therefore rebuilt here on top of full indexing.
  * format "=I" (the 2D pixel view) is not indexable by memoryview at all,
    so pixels2d exposes its elements through an explicit unpack instead.

Both are worked around honestly; neither is papered over.
"""

from pygame.pixelcopy import (
    array_to_surface,
    surface_to_array,
    map_array as pix_map_array,
    make_surface as pix_make_surface,
)

import array as _array

__all__ = [
    "array2d",
    "array3d",
    "array_alpha",
    "array_blue",
    "array_colorkey",
    "array_green",
    "array_red",
    "array_to_surface",
    "blit_array",
    "get_arraytype",
    "get_arraytypes",
    "make_surface",
    "map_array",
    "pixels2d",
    "pixels3d",
    "pixels_alpha",
    "pixels_blue",
    "pixels_green",
    "pixels_red",
    "surface_to_array",
    "use_arraytype",
]

# Pixel sizes permissible for 2D reference arrays, as upstream.
_pixel2d_bitdepths = {8, 16, 32}


def _normalize_index(idx, length):
    if idx < 0:
        idx += length
    if idx < 0 or idx >= length:
        raise IndexError("index out of range")
    return idx


class _ArrayBase:
    """Common indexing/shape behaviour for the array objects returned here.

    Subclasses supply _get(coords) and _set(coords, value) for FULL
    coordinate tuples; this class layers partial indexing, slicing, iteration
    and whole-array assignment on top, which is what game code actually uses
    (`arr[x, y] = (r, g, b)`, `arr[x][y][0] = v`, `arr[:] = other`).
    """

    __slots__ = ("shape", "dtype")

    # -- to be provided by subclasses ------------------------------------
    def _get(self, coords):
        raise NotImplementedError

    def _set(self, coords, value):
        raise NotImplementedError

    # -- shape helpers ----------------------------------------------------
    @property
    def ndim(self):
        return len(self.shape)

    @property
    def size(self):
        n = 1
        for d in self.shape:
            n *= d
        return n

    def __len__(self):
        return self.shape[0]

    def _key_to_coords(self, key):
        if not isinstance(key, tuple):
            key = (key,)
        if len(key) > len(self.shape):
            raise IndexError(
                f"too many indices: array is {len(self.shape)}-dimensional"
            )
        return key

    def __getitem__(self, key):
        coords = self._key_to_coords(key)
        if any(isinstance(c, slice) for c in coords):
            return _SubArray(self, coords)
        if len(coords) == len(self.shape):
            return self._get(tuple(
                _normalize_index(c, d) for c, d in zip(coords, self.shape)
            ))
        # Partial index -> a view onto the remaining axes. CPython memoryview
        # refuses this ("multi-dimensional sub-views are not implemented"), so
        # it is rebuilt here rather than surfaced as a crash.
        return _SubArray(self, coords)

    def __setitem__(self, key, value):
        coords = self._key_to_coords(key)
        if (len(coords) == len(self.shape)
                and not any(isinstance(c, slice) for c in coords)):
            self._set(tuple(
                _normalize_index(c, d) for c, d in zip(coords, self.shape)
            ), value)
            return
        _SubArray(self, coords)._assign(value)

    def __iter__(self):
        for i in range(self.shape[0]):
            yield self[i]

    def tolist(self):
        if len(self.shape) == 1:
            return [self._get((i,)) for i in range(self.shape[0])]
        return [self[i].tolist() for i in range(self.shape[0])]

    def __eq__(self, other):
        if isinstance(other, _ArrayBase):
            return self.shape == other.shape and self.tolist() == other.tolist()
        if isinstance(other, (list, tuple)):
            return self.tolist() == list(other)
        return NotImplemented

    def __repr__(self):
        return f"{type(self).__name__}(shape={self.shape}, dtype={self.dtype})"


class _SubArray(_ArrayBase):
    """A view produced by partial indexing or slicing of another array.

    Holds a reference to its parent, so writes propagate all the way back to
    the Surface when the root is a live view. This is what keeps
    `pixels3d(s)[10, 20] = (255, 0, 0)` and `pixels3d(s)[5][5][0] = 128`
    honest rather than writing into a throwaway copy.
    """

    __slots__ = ("_parent", "_prefix", "_ranges")

    def __init__(self, parent, coords):
        self._parent = parent
        prefix = []
        ranges = []
        pshape = parent.shape
        for axis, c in enumerate(coords):
            if isinstance(c, slice):
                idxs = list(range(*c.indices(pshape[axis])))
                prefix.append(None)
                ranges.append(idxs)
            else:
                prefix.append(_normalize_index(c, pshape[axis]))
                ranges.append(None)
        # remaining axes are taken whole
        for axis in range(len(coords), len(pshape)):
            prefix.append(None)
            ranges.append(list(range(pshape[axis])))
        self._prefix = prefix
        self._ranges = ranges
        self.shape = tuple(len(r) for r in ranges if r is not None)
        self.dtype = parent.dtype

    def _map(self, coords):
        """Map this view's coords onto the parent's full coordinate tuple."""
        out = []
        it = iter(coords)
        for fixed, rng in zip(self._prefix, self._ranges):
            if rng is None:
                out.append(fixed)
            else:
                out.append(rng[next(it)])
        return tuple(out)

    def _get(self, coords):
        return self._parent._get(self._map(coords))

    def _set(self, coords, value):
        self._parent._set(self._map(coords), value)

    def _assign(self, value):
        """Broadcast-ish assignment: scalar, nested sequence, or array."""
        shape = self.shape
        if not shape:
            self._parent._set(self._map(()), value)
            return
        if isinstance(value, _ArrayBase):
            value = value.tolist()
        if isinstance(value, (list, tuple)):
            if len(value) != shape[0]:
                # A flat colour tuple assigned across the minor axis, e.g.
                # arr[x, y] = (r, g, b) where shape == (3,)
                raise ValueError(
                    f"cannot assign sequence of length {len(value)} "
                    f"to axis of length {shape[0]}"
                )
            for i, v in enumerate(value):
                if len(shape) == 1:
                    self._set((i,), v)
                else:
                    self[i]._assign(v)
            return
        # scalar fill
        if len(shape) == 1:
            for i in range(shape[0]):
                self._set((i,), value)
        else:
            for i in range(shape[0]):
                self[i]._assign(value)


class _BufferArray(_ArrayBase):
    """A LIVE array over a Surface's exported buffer.

    Every read and write goes straight to the memoryview, so mutations land in
    the Surface's own pixels. The Surface is kept locked (and referenced) for
    the lifetime of this object, matching upstream's documented contract.
    """

    __slots__ = ("_mv", "_surface", "_locked")

    def __init__(self, surface, view, dtype):
        self._mv = memoryview(view)
        self._surface = surface
        self.shape = tuple(self._mv.shape)
        self.dtype = dtype
        surface.lock()
        self._locked = True

    def _get(self, coords):
        return self._mv[coords]

    def _set(self, coords, value):
        self._mv[coords] = value

    def unlock(self):
        if self._locked:
            self._locked = False
            try:
                self._mv.release()
            except Exception:
                pass
            self._surface.unlock()

    def __del__(self):
        try:
            self.unlock()
        except Exception:
            pass


class _Pixels2D(_ArrayBase):
    """Live 2D pixel-value array.

    Two CPython memoryview limits collide on this one view, so it is built by
    hand rather than by casting:

      * Surface.get_view("2") exports format "=I", which memoryview refuses to
        index at all ("unsupported format =I").
      * The view is pitch-strided, not C-contiguous, so .cast("B") is also
        refused ("casts are restricted to C-contiguous views").

    The bytes themselves are perfectly addressable, so this takes a flat
    byte-level view of the SAME memory and does the stride arithmetic itself.
    Writes still land in the Surface's pixels, which is the whole point of
    pixels2d.

    get_view("0") is the flat byte view, but pygame grants it only when the
    surface pitch has no row padding. Padding is common (8- and 16-bit surfaces
    round their rows up to 4 bytes), so when the flat view is refused this
    falls back to Surface.get_buffer(), which always covers the whole pixel
    block including the padding. The stride arithmetic below is driven by the
    2-D view's own strides either way, so both paths address identically.
    """

    __slots__ = ("_mv", "_surface", "_locked", "_itemsize", "_strides",
                 "_byteorder")

    def __init__(self, surface):
        view = surface.get_view("2")
        mv = memoryview(view)
        self.shape = tuple(mv.shape)
        self._strides = tuple(mv.strides)
        self._itemsize = mv.itemsize
        self._byteorder = "little"
        mv.release()
        try:
            self._mv = memoryview(surface.get_view("0")).cast("B")
        except (ValueError, TypeError):
            # Padded pitch. get_buffer() is the whole pixel block as bytes,
            # padding included, so the 2-D strides index into it correctly.
            self._mv = memoryview(surface.get_buffer()).cast("B")
        self._surface = surface
        self.dtype = "uint32"
        surface.lock()
        self._locked = True

    def _offset(self, coords):
        off = 0
        for c, s in zip(coords, self._strides):
            off += c * s
        return off

    def _get(self, coords):
        off = self._offset(coords)
        return int.from_bytes(
            self._mv[off:off + self._itemsize], self._byteorder
        )

    def _set(self, coords, value):
        off = self._offset(coords)
        # Mask into the unsigned range: pygame's map_rgb() hands back a signed
        # int for pixel values with the top bit set (a full-alpha 32-bit pixel
        # is routinely negative), and to_bytes() rejects those outright.
        value = int(value) & ((1 << (self._itemsize * 8)) - 1)
        self._mv[off:off + self._itemsize] = value.to_bytes(
            self._itemsize, self._byteorder
        )

    def unlock(self):
        if self._locked:
            self._locked = False
            try:
                self._mv.release()
            except Exception:
                pass
            self._surface.unlock()

    def __del__(self):
        try:
            self.unlock()
        except Exception:
            pass


class _CopyArray(_ArrayBase):
    """An owned, contiguous array -- what the copying array*() calls return.

    Backed by array.array so it exports a real buffer, which is what lets it
    be handed straight back to pixelcopy (blit_array, map_array, make_surface)
    without any conversion step.
    """

    __slots__ = ("_buf", "_mv", "_strides", "_typecode")

    def __init__(self, shape, typecode, dtype, fill=0):
        n = 1
        for d in shape:
            n *= d
        self._typecode = typecode
        self._buf = _array.array(typecode, [fill]) * n
        self.shape = tuple(shape)
        self.dtype = dtype
        strides = [0] * len(shape)
        acc = 1
        for i in range(len(shape) - 1, -1, -1):
            strides[i] = acc
            acc *= shape[i]
        self._strides = tuple(strides)
        self._mv = memoryview(self._buf)

    def _index(self, coords):
        off = 0
        for c, s in zip(coords, self._strides):
            off += c * s
        return off

    def _get(self, coords):
        return self._buf[self._index(coords)]

    def _set(self, coords, value):
        self._buf[self._index(coords)] = int(value)

    def buffer(self):
        """A correctly-shaped memoryview, for handing to pixelcopy.

        The cast goes via "B" deliberately: memoryview refuses to cast
        directly between two non-byte formats, so array("i") -> ("i", shape)
        raises TypeError. Bytes are the only legal intermediate.
        """
        return memoryview(self._buf).cast("B").cast(self._typecode, self.shape)

    def __buffer__(self, flags):
        return self.buffer()


def _as_pixelcopy_arg(array):
    """Coerce whatever a caller passed into something pixelcopy accepts."""
    if isinstance(array, _CopyArray):
        return array.buffer()
    if isinstance(array, _BufferArray):
        return array._mv
    if isinstance(array, _Pixels2D):
        return memoryview(array._surface.get_view("2"))
    if isinstance(array, _SubArray):
        # A sliced/partial view is not contiguous; materialize it.
        return _from_nested(array.tolist()).buffer()
    if isinstance(array, (list, tuple)):
        return _from_nested(array).buffer()
    return array


def _nested_shape(seq):
    shape = []
    cur = seq
    while isinstance(cur, (list, tuple)):
        shape.append(len(cur))
        if not cur:
            break
        cur = cur[0]
    return tuple(shape)


def _flatten(seq, out):
    for item in seq:
        if isinstance(item, (list, tuple)):
            _flatten(item, out)
        else:
            out.append(int(item))


def _from_nested(seq):
    shape = _nested_shape(seq)
    flat = []
    _flatten(seq, flat)
    if len(shape) >= 3:
        arr = _CopyArray(shape, "B", "uint8")
    else:
        arr = _CopyArray(shape, "i", "int32")
    for i, v in enumerate(flat):
        arr._buf[i] = v
    return arr


# ---------------------------------------------------------------------------
# Reference (live) arrays -- writes land in the Surface.
# ---------------------------------------------------------------------------

def pixels3d(surface):
    """Reference pixels into a live 3D array (x, y, RGB).

    Writes go straight through to the Surface. Only 24- and 32-bit Surfaces
    can be referenced, as upstream.
    """
    return _BufferArray(surface, surface.get_view("3"), "uint8")


def pixels2d(surface):
    """Reference pixels into a live 2D array of mapped pixel values."""
    if surface.get_bitsize() not in _pixel2d_bitdepths:
        raise ValueError("unsupported bit depth for 2D reference array")
    return _Pixels2D(surface)


def pixels_alpha(surface):
    """Reference pixel alpha into a live 2D array."""
    return _BufferArray(surface, surface.get_view("A"), "uint8")


def pixels_red(surface):
    """Reference pixel red into a live 2D array."""
    return _BufferArray(surface, surface.get_view("R"), "uint8")


def pixels_green(surface):
    """Reference pixel green into a live 2D array."""
    return _BufferArray(surface, surface.get_view("G"), "uint8")


def pixels_blue(surface):
    """Reference pixel blue into a live 2D array."""
    return _BufferArray(surface, surface.get_view("B"), "uint8")


# ---------------------------------------------------------------------------
# Copying arrays -- snapshots, safe to mutate without touching the Surface.
# ---------------------------------------------------------------------------

def array3d(surface):
    """Copy pixels into a 3D array (x, y, RGB)."""
    width, height = surface.get_size()
    arr = _CopyArray((width, height, 3), "B", "uint8")
    surface_to_array(arr.buffer(), surface)
    return arr


def array2d(surface):
    """Copy pixels into a 2D array of mapped pixel values."""
    bpp = surface.get_bytesize()
    try:
        typecode, dtype = (
            ("B", "uint8"),
            ("H", "uint16"),
            ("i", "int32"),
            ("i", "int32"),
        )[bpp - 1]
    except IndexError:
        raise ValueError(f"unsupported bit depth {bpp * 8} for 2D array")
    width, height = surface.get_size()
    arr = _CopyArray((width, height), typecode, dtype)
    surface_to_array(arr.buffer(), surface)
    return arr


def _array_channel(surface, channel):
    width, height = surface.get_size()
    arr = _CopyArray((width, height), "B", "uint8")
    surface_to_array(arr.buffer(), surface, channel)
    return arr


def array_alpha(surface):
    """Copy pixel alpha into a 2D array."""
    return _array_channel(surface, "A")


def array_red(surface):
    """Copy pixel red into a 2D array."""
    return _array_channel(surface, "R")


def array_green(surface):
    """Copy pixel green into a 2D array."""
    return _array_channel(surface, "G")


def array_blue(surface):
    """Copy pixel blue into a 2D array."""
    return _array_channel(surface, "B")


def array_colorkey(surface):
    """Copy the colorkey transparency values into a 2D array."""
    return _array_channel(surface, "C")


# ---------------------------------------------------------------------------
# Array -> Surface
# ---------------------------------------------------------------------------

def blit_array(surface, array):
    """Blit directly from an array of values onto a Surface."""
    return array_to_surface(surface, _as_pixelcopy_arg(array))


def make_surface(array):
    """Copy an array to a new Surface."""
    return pix_make_surface(_as_pixelcopy_arg(array))


def map_array(surface, array):
    """Map a 3D array of colour components into a 2D array of pixel values."""
    if isinstance(array, (list, tuple)):
        array = _from_nested(array)
    shape = tuple(array.shape)
    if not shape:
        raise ValueError("array must have at least 1 dimension")
    if shape[-1] != 3:
        raise ValueError("array must be a 3d array of 3-value color data")
    target = _CopyArray(shape[:-1], "i", "int32")
    pix_map_array(target.buffer(), _as_pixelcopy_arg(array), surface)
    return target


# ---------------------------------------------------------------------------
# Deprecated arraytype selectors, kept for source compatibility.
# ---------------------------------------------------------------------------

def use_arraytype(arraytype):
    """DEPRECATED - only one array type is supported."""
    if arraytype.lower() != "numpy":
        raise ValueError("invalid array type")


def get_arraytype():
    """DEPRECATED - only one array type is supported."""
    return "numpy"


def get_arraytypes():
    """DEPRECATED - only one array type is supported."""
    return ("numpy",)
