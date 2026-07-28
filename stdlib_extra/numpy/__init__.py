"""
Minimal numpy shim for three.py — provides only the array/matrix/vector
operations the 3D engine actually uses. Not real numpy.
"""

import math

float64 = float
float32 = float
int32 = int

class ndarray(list):
    """Minimal ndarray — a list that supports element-wise math."""

    def __init__(self, data=None, dtype=None):
        if data is None:
            data = []
        if isinstance(data, ndarray):
            data = list(data)
        super().__init__(data)
        self.dtype = dtype

    @property
    def shape(self):
        if len(self) == 0:
            return (0,)
        if isinstance(self[0], (list, ndarray)):
            return (len(self), len(self[0]))
        return (len(self),)

    @property
    def T(self):
        s = self.shape
        if len(s) == 2:
            rows, cols = s
            result = [[self[r][c] for r in range(rows)] for c in range(cols)]
            return array(result)
        return self

    def reshape(self, *shape):
        if len(shape) == 1 and isinstance(shape[0], (tuple, list)):
            shape = shape[0]
        flat = list(self.flatten())
        if len(shape) == 1:
            return array(flat)
        if len(shape) == 2:
            rows, cols = shape
            if cols == -1: cols = len(flat) // rows
            if rows == -1: rows = len(flat) // cols
            return array([flat[r*cols:(r+1)*cols] for r in range(rows)])
        return array(flat)

    def ravel(self):
        return self.flatten()

    def flatten(self):
        result = []
        for item in self:
            if isinstance(item, (list, ndarray)):
                result.extend(item)
            else:
                result.append(item)
        return array(result)

    def copy(self, order=None):
        if len(self) > 0 and isinstance(self[0], (list, ndarray)):
            return array([list(row) for row in self])
        return array(list(self))

    def __add__(self, other):
        if isinstance(other, (list, ndarray)):
            return array([a + b for a, b in zip(self, other)])
        return array([a + other for a in self])

    def __radd__(self, other):
        return self.__add__(other)

    def __sub__(self, other):
        if isinstance(other, (list, ndarray)):
            return array([a - b for a, b in zip(self, other)])
        return array([a - other for a in self])

    def __rsub__(self, other):
        if isinstance(other, (list, ndarray)):
            return array([b - a for a, b in zip(self, other)])
        return array([other - a for a in self])

    def __mul__(self, other):
        if isinstance(other, (list, ndarray)):
            return array([a * b for a, b in zip(self, other)])
        return array([a * other for a in self])

    def __rmul__(self, other):
        return self.__mul__(other)

    def __truediv__(self, other):
        if isinstance(other, (list, ndarray)):
            return array([a / b for a, b in zip(self, other)])
        return array([a / other for a in self])

    def __neg__(self):
        return array([-a for a in self])

    def __matmul__(self, other):
        return matmul(self, other)

    def __getitem__(self, key):
        result = super().__getitem__(key)
        if isinstance(result, list) and not isinstance(result, ndarray):
            return ndarray(result)
        return result

    def __setitem__(self, key, value):
        super().__setitem__(key, value)

    def astype(self, dtype):
        return self.copy()

    def tobytes(self):
        """Convert to bytes (float32 little-endian)."""
        import struct
        flat = []
        for item in self:
            if isinstance(item, (list, ndarray)):
                flat.extend(item)
            else:
                flat.append(item)
        return struct.pack(f'<{len(flat)}f', *[float(x) for x in flat])

    def __bytes__(self):
        return self.tobytes()

    def __len_hint__(self):
        return len(self.tobytes())

    def item(self, *args):
        if len(args) == 1 and isinstance(args[0], tuple):
            r, c = args[0]
            return self[r][c]
        if len(args) == 2:
            return self[args[0]][args[1]]
        if len(args) == 1:
            return list.__getitem__(self, args[0])
        raise IndexError(f"invalid index {args}")

    def itemset(self, *args):
        if len(args) == 2 and isinstance(args[0], tuple):
            r, c = args[0]
            self[r][c] = args[1]
        elif len(args) == 3:
            self[args[0]][args[1]] = args[2]
        else:
            raise IndexError(f"invalid index {args}")

    def tolist(self):
        return [list(row) if isinstance(row, (list, ndarray)) else row for row in self]


def array(data, dtype=None):
    if isinstance(data, ndarray):
        return data.copy()
    if isinstance(data, (list, tuple)):
        if len(data) > 0 and isinstance(data[0], (list, tuple, ndarray)):
            return ndarray([ndarray(list(row)) for row in data], dtype=dtype)
        return ndarray(list(data), dtype=dtype)
    return ndarray([data], dtype=dtype)


def asarray(data, dtype=None):
    if isinstance(data, ndarray):
        return data
    return array(data, dtype=dtype)


def identity(n, dtype=None):
    result = [[1.0 if i == j else 0.0 for j in range(n)] for i in range(n)]
    return array(result, dtype=dtype)


def zeros(shape, dtype=None):
    if isinstance(shape, int):
        return array([0.0] * shape)
    if len(shape) == 1:
        return array([0.0] * shape[0])
    return array([[0.0] * shape[1] for _ in range(shape[0])])


def ones(shape, dtype=None):
    if isinstance(shape, int):
        return array([1.0] * shape)
    if len(shape) == 1:
        return array([1.0] * shape[0])
    return array([[1.0] * shape[1] for _ in range(shape[0])])


def dot(a, b):
    a = asarray(a)
    b = asarray(b)
    if len(a.shape) == 1 and len(b.shape) == 1:
        return sum(x * y for x, y in zip(a, b))
    return matmul(a, b)


def cross(a, b):
    a = asarray(a)
    b = asarray(b)
    # Flatten nested arrays to get 3-element vectors
    if hasattr(a, 'flatten'):
        a = a.flatten()
    if hasattr(b, 'flatten'):
        b = b.flatten()
    al = [float(x) for x in a]
    bl = [float(x) for x in b]
    if len(al) < 3 or len(bl) < 3:
        print(f"cross error: a={al} b={bl}")
        return array([0.0, 0.0, 0.0])
    return array([
        al[1] * bl[2] - al[2] * bl[1],
        al[2] * bl[0] - al[0] * bl[2],
        al[0] * bl[1] - al[1] * bl[0]
    ])


def matmul(a, b):
    a = asarray(a)
    b = asarray(b)
    sa = a.shape
    sb = b.shape
    if len(sa) == 2 and len(sb) == 2:
        rows_a, cols_a = sa
        rows_b, cols_b = sb
        result = [[sum(a[i][k] * b[k][j] for k in range(cols_a))
                    for j in range(cols_b)] for i in range(rows_a)]
        return array(result)
    if len(sa) == 2 and len(sb) == 1:
        rows_a, cols_a = sa
        return array([sum(a[i][k] * b[k] for k in range(cols_a))
                       for i in range(rows_a)])
    return dot(a, b)


def multiply(a, b):
    a = asarray(a)
    if isinstance(b, (int, float)):
        return a * b
    b = asarray(b)
    if len(b) == 1:
        return a * float(b[0])
    return a * b


def divide(a, b):
    a = asarray(a)
    if isinstance(b, (int, float)):
        return a / b
    b = asarray(b)
    if len(b) == 1:
        return a / float(b[0])
    return a / b


def subtract(a, b):
    a = asarray(a)
    if isinstance(b, (int, float)):
        return a - b
    b = asarray(b)
    return a - b


def hstack(arrays):
    """Horizontally stack arrays."""
    result = []
    for a in arrays:
        a = asarray(a)
        if len(a.shape) == 2:
            if not result:
                result = [list(row) for row in a]
            else:
                for i, row in enumerate(a):
                    if i < len(result):
                        result[i].extend(row)
        else:
            result.extend(a)
    if result and isinstance(result[0], list):
        return array(result)
    return array(result)


def vstack(arrays):
    """Vertically stack arrays."""
    result = []
    for a in arrays:
        a = asarray(a)
        if len(a.shape) == 2:
            result.extend([list(row) for row in a])
        else:
            result.append(list(a))
    return array(result)


def concatenate(arrays, axis=0):
    if axis == 0:
        return vstack(arrays)
    return hstack(arrays)


def flip(a, axis=None):
    a = asarray(a)
    if len(a.shape) == 2:
        if axis == 0 or axis is None:
            return array([list(row) for row in reversed(a)])
        elif axis == 1:
            return array([list(reversed(row)) for row in a])
    return array(list(reversed(a)))


def arange(start, stop=None, step=1):
    if stop is None:
        stop = start
        start = 0
    result = []
    v = start
    while v < stop:
        result.append(v)
        v += step
    return array(result)


def linspace(start, stop, num=50):
    if num <= 1:
        return array([start])
    step = (stop - start) / (num - 1)
    return array([start + i * step for i in range(num)])


def searchsorted(a, v):
    a = list(a)
    if isinstance(v, (int, float)):
        for i, val in enumerate(a):
            if val >= v:
                return i
        return len(a)
    return [searchsorted(a, x) for x in v]


class _linalg:
    @staticmethod
    def norm(v):
        v = asarray(v)
        return math.sqrt(sum(x * x for x in v))

    @staticmethod
    def inv(m):
        m = asarray(m)
        s = m.shape
        if s == (4, 4):
            return _inv4x4(m)
        if s == (3, 3):
            return _inv3x3(m)
        if s == (2, 2):
            det = m[0][0] * m[1][1] - m[0][1] * m[1][0]
            if abs(det) < 1e-10:
                raise ValueError("Singular matrix")
            inv_det = 1.0 / det
            return array([
                [m[1][1] * inv_det, -m[0][1] * inv_det],
                [-m[1][0] * inv_det, m[0][0] * inv_det]
            ])
        raise ValueError(f"Can't invert matrix with shape {s}")

linalg = _linalg()


def _inv4x4(m):
    """4x4 matrix inverse"""
    a = [m[i][j] for i in range(4) for j in range(4)]

    inv = [0.0] * 16
    inv[0] = a[5]*a[10]*a[15] - a[5]*a[11]*a[14] - a[9]*a[6]*a[15] + a[9]*a[7]*a[14] + a[13]*a[6]*a[11] - a[13]*a[7]*a[10]
    inv[4] = -a[4]*a[10]*a[15] + a[4]*a[11]*a[14] + a[8]*a[6]*a[15] - a[8]*a[7]*a[14] - a[12]*a[6]*a[11] + a[12]*a[7]*a[10]
    inv[8] = a[4]*a[9]*a[15] - a[4]*a[11]*a[13] - a[8]*a[5]*a[15] + a[8]*a[7]*a[13] + a[12]*a[5]*a[11] - a[12]*a[7]*a[9]
    inv[12] = -a[4]*a[9]*a[14] + a[4]*a[10]*a[13] + a[8]*a[5]*a[14] - a[8]*a[6]*a[13] - a[12]*a[5]*a[10] + a[12]*a[6]*a[9]
    inv[1] = -a[1]*a[10]*a[15] + a[1]*a[11]*a[14] + a[9]*a[2]*a[15] - a[9]*a[3]*a[14] - a[13]*a[2]*a[11] + a[13]*a[3]*a[10]
    inv[5] = a[0]*a[10]*a[15] - a[0]*a[11]*a[14] - a[8]*a[2]*a[15] + a[8]*a[3]*a[14] + a[12]*a[2]*a[11] - a[12]*a[3]*a[10]
    inv[9] = -a[0]*a[9]*a[15] + a[0]*a[11]*a[13] + a[8]*a[1]*a[15] - a[8]*a[3]*a[13] - a[12]*a[1]*a[11] + a[12]*a[3]*a[9]
    inv[13] = a[0]*a[9]*a[14] - a[0]*a[10]*a[13] - a[8]*a[1]*a[14] + a[8]*a[2]*a[13] + a[12]*a[1]*a[10] - a[12]*a[2]*a[9]
    inv[2] = a[1]*a[6]*a[15] - a[1]*a[7]*a[14] - a[5]*a[2]*a[15] + a[5]*a[3]*a[14] + a[13]*a[2]*a[7] - a[13]*a[3]*a[6]
    inv[6] = -a[0]*a[6]*a[15] + a[0]*a[7]*a[14] + a[4]*a[2]*a[15] - a[4]*a[3]*a[14] - a[12]*a[2]*a[7] + a[12]*a[3]*a[6]
    inv[10] = a[0]*a[5]*a[15] - a[0]*a[7]*a[13] - a[4]*a[1]*a[15] + a[4]*a[3]*a[13] + a[12]*a[1]*a[7] - a[12]*a[3]*a[5]
    inv[14] = -a[0]*a[5]*a[14] + a[0]*a[6]*a[13] + a[4]*a[1]*a[14] - a[4]*a[2]*a[13] - a[12]*a[1]*a[6] + a[12]*a[2]*a[5]
    inv[3] = -a[1]*a[6]*a[11] + a[1]*a[7]*a[10] + a[5]*a[2]*a[11] - a[5]*a[3]*a[10] - a[9]*a[2]*a[7] + a[9]*a[3]*a[6]
    inv[7] = a[0]*a[6]*a[11] - a[0]*a[7]*a[10] - a[4]*a[2]*a[11] + a[4]*a[3]*a[10] + a[8]*a[2]*a[7] - a[8]*a[3]*a[6]
    inv[11] = -a[0]*a[5]*a[11] + a[0]*a[7]*a[9] + a[4]*a[1]*a[11] - a[4]*a[3]*a[9] - a[8]*a[1]*a[7] + a[8]*a[3]*a[5]
    inv[15] = a[0]*a[5]*a[10] - a[0]*a[6]*a[9] - a[4]*a[1]*a[10] + a[4]*a[2]*a[9] + a[8]*a[1]*a[6] - a[8]*a[2]*a[5]

    det = a[0]*inv[0] + a[1]*inv[4] + a[2]*inv[8] + a[3]*inv[12]
    if abs(det) < 1e-10:
        raise ValueError("Singular matrix")
    inv_det = 1.0 / det
    return array([[inv[i*4+j] * inv_det for j in range(4)] for i in range(4)])


def _inv3x3(m):
    """3x3 matrix inverse"""
    a, b, c = m[0][0], m[0][1], m[0][2]
    d, e, f = m[1][0], m[1][1], m[1][2]
    g, h, i = m[2][0], m[2][1], m[2][2]
    det = a*(e*i - f*h) - b*(d*i - f*g) + c*(d*h - e*g)
    if abs(det) < 1e-10:
        raise ValueError("Singular matrix")
    inv_det = 1.0 / det
    return array([
        [(e*i - f*h)*inv_det, (c*h - b*i)*inv_det, (b*f - c*e)*inv_det],
        [(f*g - d*i)*inv_det, (a*i - c*g)*inv_det, (c*d - a*f)*inv_det],
        [(d*h - e*g)*inv_det, (b*g - a*h)*inv_det, (a*e - b*d)*inv_det]
    ])
