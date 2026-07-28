"""
Minimal PyGLM shim for wasmcart — provides vec2/vec3/mat3/mat4 and common
matrix operations. Backed by pure Python math, no C extension needed.
"""

import math


class vec2:
    def __init__(self, x=0.0, y=0.0):
        if isinstance(x, (tuple, list)):
            self.x, self.y = float(x[0]), float(x[1])
        elif isinstance(x, vec2):
            self.x, self.y = x.x, x.y
        else:
            self.x, self.y = float(x), float(y)

    def __iter__(self):
        yield self.x; yield self.y

    def __repr__(self):
        return f"vec2({self.x}, {self.y})"

    def to_bytes(self):
        import struct
        return struct.pack('<2f', self.x, self.y)

    def write(self):
        return self.to_bytes()


class vec3:
    __slots__ = ('x', 'y', 'z')

    def __init__(self, x=0.0, y=0.0, z=0.0):
        if isinstance(x, (tuple, list, vec3)):
            vals = list(x) if not isinstance(x, vec3) else [x.x, x.y, x.z]
            self.x, self.y, self.z = float(vals[0]), float(vals[1]), float(vals[2])
        else:
            self.x, self.y, self.z = float(x), float(y), float(z)

    def __iter__(self):
        yield self.x; yield self.y; yield self.z

    # Swizzles: real glm supports v.xyz, v.xy, v.zyx and so on, both to read
    # and to assign. __slots__ means an unknown attribute raises with the
    # unhelpful "no __dict__ for setting new attributes", so handle any
    # combination of x/y/z here rather than enumerate them.
    def __getattr__(self, name):
        if name and len(name) <= 3 and all(c in 'xyz' for c in name):
            vals = tuple(getattr(self, c) for c in name)
            return vec3(*vals) if len(name) == 3 else vals
        raise AttributeError(name)

    def __setattr__(self, name, value):
        # Only a MULTI-character swizzle unpacks a sequence. "y" is a plain
        # component assignment and must not try to iterate a float.
        if len(name) > 1 and len(name) <= 3 and all(c in 'xyz' for c in name):
            # glm broadcasts a scalar across a swizzle: v.xyz = 1.5 sets all
            # three. Only a sequence is unpacked component-wise.
            try:
                vals = list(value)
            except TypeError:
                vals = [value] * len(name)
            for c, v in zip(name, vals):
                object.__setattr__(self, c, float(v))
            return
        object.__setattr__(self, name, value)

    def __add__(self, o):
        if isinstance(o, vec3):
            return vec3(self.x+o.x, self.y+o.y, self.z+o.z)
        return vec3(self.x+o, self.y+o, self.z+o)

    def __sub__(self, o):
        if isinstance(o, vec3):
            return vec3(self.x-o.x, self.y-o.y, self.z-o.z)
        return vec3(self.x-o, self.y-o, self.z-o)

    def __mul__(self, o):
        if isinstance(o, (int, float)):
            return vec3(self.x*o, self.y*o, self.z*o)
        if isinstance(o, vec3):
            return vec3(self.x*o.x, self.y*o.y, self.z*o.z)
        return NotImplemented

    def __rmul__(self, o):
        return self.__mul__(o)

    def __neg__(self):
        return vec3(-self.x, -self.y, -self.z)

    def __repr__(self):
        return f"vec3({self.x}, {self.y}, {self.z})"

    def __getitem__(self, i):
        return (self.x, self.y, self.z)[i]

    def to_bytes(self):
        import struct
        return struct.pack('<3f', self.x, self.y, self.z)

    def write(self):
        return self.to_bytes()


class mat3:
    """3x3 column-major matrix"""
    __slots__ = ('data',)

    def __init__(self, *args):
        if len(args) == 0:
            self.data = [1,0,0, 0,1,0, 0,0,1]
        elif len(args) == 1 and isinstance(args[0], mat4):
            m = args[0].data
            self.data = [m[0],m[1],m[2], m[4],m[5],m[6], m[8],m[9],m[10]]
        elif len(args) == 9:
            self.data = [float(x) for x in args]
        else:
            self.data = [1,0,0, 0,1,0, 0,0,1]

    def to_bytes(self):
        import struct
        return struct.pack('<9f', *self.data)

    def write(self):
        return self.to_bytes()


class mat4:
    """4x4 column-major matrix"""
    __slots__ = ('data',)

    def __init__(self, *args):
        if len(args) == 0 or (len(args) == 1 and args[0] == 1):
            self.data = [1,0,0,0, 0,1,0,0, 0,0,1,0, 0,0,0,1]
        elif len(args) == 1 and isinstance(args[0], (list, tuple)):
            self.data = [float(x) for x in args[0]]
        elif len(args) == 1 and isinstance(args[0], mat4):
            self.data = list(args[0].data)
        elif len(args) == 16:
            self.data = [float(x) for x in args]
        else:
            self.data = [1,0,0,0, 0,1,0,0, 0,0,1,0, 0,0,0,1]

    def __mul__(self, other):
        if isinstance(other, mat4):
            return _mat4_mul(self, other)
        if isinstance(other, vec3):
            return _mat4_mul_vec3(self, other)
        return NotImplemented

    def __getitem__(self, i):
        # Column access
        c = i * 4
        return [self.data[c], self.data[c+1], self.data[c+2], self.data[c+3]]

    def to_bytes(self):
        import struct
        return struct.pack('<16f', *self.data)

    def write(self):
        return self.to_bytes()

    def __repr__(self):
        d = self.data
        return f"mat4([{d[0]:.2f},{d[4]:.2f},{d[8]:.2f},{d[12]:.2f}],[{d[1]:.2f},{d[5]:.2f},{d[9]:.2f},{d[13]:.2f}],[{d[2]:.2f},{d[6]:.2f},{d[10]:.2f},{d[14]:.2f}],[{d[3]:.2f},{d[7]:.2f},{d[11]:.2f},{d[15]:.2f}])"


def _mat4_mul(a, b):
    r = [0.0] * 16
    for c in range(4):
        for row in range(4):
            s = 0.0
            for k in range(4):
                s += a.data[k*4+row] * b.data[c*4+k]
            r[c*4+row] = s
    return mat4(r)


def _mat4_mul_vec3(m, v):
    d = m.data
    x = d[0]*v.x + d[4]*v.y + d[8]*v.z + d[12]
    y = d[1]*v.x + d[5]*v.y + d[9]*v.z + d[13]
    z = d[2]*v.x + d[6]*v.y + d[10]*v.z + d[14]
    return vec3(x, y, z)


def radians(deg):
    return math.radians(deg)

def sin(x):
    return math.sin(x)

def cos(x):
    return math.cos(x)


def normalize(v):
    if isinstance(v, vec3):
        l = math.sqrt(v.x*v.x + v.y*v.y + v.z*v.z)
        if l < 1e-10:
            return vec3(0, 0, 0)
        return vec3(v.x/l, v.y/l, v.z/l)
    return v


def cross(a, b):
    return vec3(
        a.y*b.z - a.z*b.y,
        a.z*b.x - a.x*b.z,
        a.x*b.y - a.y*b.x
    )


def dot(a, b):
    return a.x*b.x + a.y*b.y + a.z*b.z


def inverse(m):
    if isinstance(m, mat4):
        return _mat4_inverse(m)
    return m


def perspective(fovy, aspect, near, far):
    f = 1.0 / math.tan(fovy / 2.0)
    d = near - far
    return mat4([
        f/aspect, 0, 0, 0,
        0, f, 0, 0,
        0, 0, (far+near)/d, -1,
        0, 0, (2*far*near)/d, 0
    ])


def lookAt(eye, center, up):
    f = normalize(vec3(center.x-eye.x, center.y-eye.y, center.z-eye.z))
    s = normalize(cross(f, up))
    u = cross(s, f)
    return mat4([
        s.x, u.x, -f.x, 0,
        s.y, u.y, -f.y, 0,
        s.z, u.z, -f.z, 0,
        -dot(s,eye), -dot(u,eye), dot(f,eye), 1
    ])


def _v3(v):
    """Accept a vec3 OR any (x, y, z) sequence.

    Real glm takes both -- glm.translate(m, (x, y, z)) is ordinary usage --
    and this shim only handled objects with .x/.y/.z, so a plain tuple raised
    "'tuple' object has no attribute 'x'".
    """
    if hasattr(v, 'x'):
        return v
    return vec3(v[0], v[1], v[2])


def translate(m, v):
    v = _v3(v)
    result = mat4(m.data[:])
    d = result.data
    d[12] += d[0]*v.x + d[4]*v.y + d[8]*v.z
    d[13] += d[1]*v.x + d[5]*v.y + d[9]*v.z
    d[14] += d[2]*v.x + d[6]*v.y + d[10]*v.z
    return result


def scale(m, v):
    v = _v3(v)
    result = mat4(m.data[:])
    d = result.data
    d[0]*=v.x; d[1]*=v.x; d[2]*=v.x; d[3]*=v.x
    d[4]*=v.y; d[5]*=v.y; d[6]*=v.y; d[7]*=v.y
    d[8]*=v.z; d[9]*=v.z; d[10]*=v.z; d[11]*=v.z
    return result


def rotate(m, angle, axis):
    axis = _v3(axis)
    c = math.cos(angle)
    s = math.sin(angle)
    a = normalize(axis)
    t = 1.0 - c

    rot = mat4([
        t*a.x*a.x+c, t*a.x*a.y+s*a.z, t*a.x*a.z-s*a.y, 0,
        t*a.x*a.y-s*a.z, t*a.y*a.y+c, t*a.y*a.z+s*a.x, 0,
        t*a.x*a.z+s*a.y, t*a.y*a.z-s*a.x, t*a.z*a.z+c, 0,
        0, 0, 0, 1
    ])
    return _mat4_mul(m, rot)


def _mat4_inverse(m):
    d = m.data
    inv = [0.0] * 16

    inv[0] = d[5]*d[10]*d[15] - d[5]*d[11]*d[14] - d[9]*d[6]*d[15] + d[9]*d[7]*d[14] + d[13]*d[6]*d[11] - d[13]*d[7]*d[10]
    inv[4] = -d[4]*d[10]*d[15] + d[4]*d[11]*d[14] + d[8]*d[6]*d[15] - d[8]*d[7]*d[14] - d[12]*d[6]*d[11] + d[12]*d[7]*d[10]
    inv[8] = d[4]*d[9]*d[15] - d[4]*d[11]*d[13] - d[8]*d[5]*d[15] + d[8]*d[7]*d[13] + d[12]*d[5]*d[11] - d[12]*d[7]*d[9]
    inv[12] = -d[4]*d[9]*d[14] + d[4]*d[10]*d[13] + d[8]*d[5]*d[14] - d[8]*d[6]*d[13] - d[12]*d[5]*d[10] + d[12]*d[6]*d[9]
    inv[1] = -d[1]*d[10]*d[15] + d[1]*d[11]*d[14] + d[9]*d[2]*d[15] - d[9]*d[3]*d[14] - d[13]*d[2]*d[11] + d[13]*d[3]*d[10]
    inv[5] = d[0]*d[10]*d[15] - d[0]*d[11]*d[14] - d[8]*d[2]*d[15] + d[8]*d[3]*d[14] + d[12]*d[2]*d[11] - d[12]*d[3]*d[10]
    inv[9] = -d[0]*d[9]*d[15] + d[0]*d[11]*d[13] + d[8]*d[1]*d[15] - d[8]*d[3]*d[13] - d[12]*d[1]*d[11] + d[12]*d[3]*d[9]
    inv[13] = d[0]*d[9]*d[14] - d[0]*d[10]*d[13] - d[8]*d[1]*d[14] + d[8]*d[2]*d[13] + d[12]*d[1]*d[10] - d[12]*d[2]*d[9]
    inv[2] = d[1]*d[6]*d[15] - d[1]*d[7]*d[14] - d[5]*d[2]*d[15] + d[5]*d[3]*d[14] + d[13]*d[2]*d[7] - d[13]*d[3]*d[6]
    inv[6] = -d[0]*d[6]*d[15] + d[0]*d[7]*d[14] + d[4]*d[2]*d[15] - d[4]*d[3]*d[14] - d[12]*d[2]*d[7] + d[12]*d[3]*d[6]
    inv[10] = d[0]*d[5]*d[15] - d[0]*d[7]*d[13] - d[4]*d[1]*d[15] + d[4]*d[3]*d[13] + d[12]*d[1]*d[7] - d[12]*d[3]*d[5]
    inv[14] = -d[0]*d[5]*d[14] + d[0]*d[6]*d[13] + d[4]*d[1]*d[14] - d[4]*d[2]*d[13] - d[12]*d[1]*d[6] + d[12]*d[2]*d[5]
    inv[3] = -d[1]*d[6]*d[11] + d[1]*d[7]*d[10] + d[5]*d[2]*d[11] - d[5]*d[3]*d[10] - d[9]*d[2]*d[7] + d[9]*d[3]*d[6]
    inv[7] = d[0]*d[6]*d[11] - d[0]*d[7]*d[10] - d[4]*d[2]*d[11] + d[4]*d[3]*d[10] + d[8]*d[2]*d[7] - d[8]*d[3]*d[6]
    inv[11] = -d[0]*d[5]*d[11] + d[0]*d[7]*d[9] + d[4]*d[1]*d[11] - d[4]*d[3]*d[9] - d[8]*d[1]*d[7] + d[8]*d[3]*d[5]
    inv[15] = d[0]*d[5]*d[10] - d[0]*d[6]*d[9] - d[4]*d[1]*d[10] + d[4]*d[2]*d[9] + d[8]*d[1]*d[6] - d[8]*d[2]*d[5]

    det = d[0]*inv[0] + d[1]*inv[4] + d[2]*inv[8] + d[3]*inv[12]
    if abs(det) < 1e-10:
        return mat4()
    inv_det = 1.0 / det
    return mat4([x * inv_det for x in inv])
