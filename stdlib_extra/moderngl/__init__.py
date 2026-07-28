"""
Minimal ModernGL shim for wasmcart — wraps OpenGL.GL functions to provide
the moderngl API (ctx.program, ctx.buffer, ctx.vertex_array, ctx.texture).

Games use: import moderngl as mgl; ctx = mgl.create_context()
"""

from OpenGL.GL import *
import struct

# Constants
DEPTH_TEST = GL_DEPTH_TEST
CULL_FACE = GL_CULL_FACE
BLEND = GL_BLEND
NEAREST = GL_NEAREST
LINEAR = GL_LINEAR
LINEAR_MIPMAP_LINEAR = GL_LINEAR_MIPMAP_LINEAR
TRIANGLE_STRIP = GL_TRIANGLE_STRIP
TRIANGLES = GL_TRIANGLES
LINES = GL_LINES
POINTS = GL_POINTS


def create_context():
    return Context()


class Uniform:
    """Wraps a GL uniform location for program['name'] = value syntax."""
    def __init__(self, program_id, name, location):
        self._prog = program_id
        self._name = name
        self._loc = location

    def write(self, value):
        """Write uniform value. Accepts glm types, bytes, or scalars."""
        glUseProgram(self._prog)
        if hasattr(value, 'to_bytes'):
            data = value.to_bytes()
            n = len(data) // 4
            if n == 16:
                glUniformMatrix4fv(self._loc, 1, GL_FALSE, list(struct.unpack(f'<{n}f', data)))
            elif n == 9:
                glUniformMatrix3fv(self._loc, 1, GL_FALSE, list(struct.unpack(f'<{n}f', data)))
            elif n == 4:
                vals = struct.unpack('<4f', data)
                glUniform4f(self._loc, *vals)
            elif n == 3:
                vals = struct.unpack('<3f', data)
                glUniform3f(self._loc, *vals)
            elif n == 2:
                vals = struct.unpack('<2f', data)
                glUniform2f(self._loc, *vals)
            elif n == 1:
                glUniform1f(self._loc, struct.unpack('<f', data)[0])
        elif isinstance(value, (int,)):
            glUniform1i(self._loc, value)
        elif isinstance(value, (float,)):
            glUniform1f(self._loc, value)
        elif isinstance(value, bytes):
            n = len(value) // 4
            vals = list(struct.unpack(f'<{n}f', value))
            if n == 16:
                glUniformMatrix4fv(self._loc, 1, GL_FALSE, vals)
            elif n == 9:
                glUniformMatrix3fv(self._loc, 1, GL_FALSE, vals)
            elif n == 4:
                glUniform4f(self._loc, *vals)
            elif n == 3:
                glUniform3f(self._loc, *vals)
            elif n == 2:
                glUniform2f(self._loc, *vals)

    @property
    def value(self):
        return self._loc

    @value.setter
    def value(self, val):
        self.write(val)


class Program:
    """Wraps a GL shader program."""
    def __init__(self, program_id):
        self._id = program_id
        self._uniforms = {}

    def __getitem__(self, name):
        if name not in self._uniforms:
            loc = glGetUniformLocation(self._id, name)
            self._uniforms[name] = Uniform(self._id, name, loc)
        return self._uniforms[name]

    def __setitem__(self, name, value):
        u = self[name]
        if isinstance(value, int):
            glUseProgram(self._id)
            glUniform1i(u._loc, value)
        elif isinstance(value, float):
            glUseProgram(self._id)
            glUniform1f(u._loc, value)
        else:
            u.write(value)

    @property
    def glo(self):
        return self._id

    def release(self):
        glDeleteProgram(self._id)


class Buffer:
    """Wraps a GL buffer object."""
    def __init__(self, buffer_id, size):
        self._id = buffer_id
        self.size = size

    def write(self, data, offset=0):
        glBindBuffer(GL_ARRAY_BUFFER, self._id)
        if offset == 0 and len(data) == self.size:
            glBufferData(GL_ARRAY_BUFFER, data, GL_DYNAMIC_DRAW)
        else:
            # glBufferSubData not in our shim yet, re-upload
            glBufferData(GL_ARRAY_BUFFER, data, GL_DYNAMIC_DRAW)

    def release(self):
        pass  # leak for now

    @property
    def glo(self):
        return self._id


class VertexArray:
    """Wraps a GL VAO."""
    def __init__(self, vao_id, program, mode=GL_TRIANGLES, num_vertices=0):
        self._id = vao_id
        self.program = program
        self._mode = mode
        self._num_vertices = num_vertices

    def render(self, mode=None):
        m = mode if mode is not None else self._mode
        glUseProgram(self.program._id)
        glBindVertexArray(self._id)
        glDrawArrays(m, 0, self._num_vertices)
        glBindVertexArray(0)

    def release(self):
        pass

    @property
    def glo(self):
        return self._id


# GL_TEXTURE_CUBE_MAP_POSITIVE_X .. NEGATIVE_Z are consecutive from 0x8515,
# so face N is simply base + N -- the order moderngl's `face` kwarg uses.
GL_TEXTURE_CUBE_MAP_POSITIVE_X = 0x8515


class Texture:
    """Wraps a GL texture (2D or cubemap)."""
    def __init__(self, tex_id, width, height, cube=False, components=4):
        self._id = tex_id
        self.width = width
        self.height = height
        self._cube = cube
        self._components = components
        # RGB vs RGBA matters: pygame hands over 3-component data for a
        # cubemap face, and uploading it as GL_RGBA misreads every row --
        # the skybox came out as diagonal stripes.
        self._fmt = GL_RGB if components == 3 else GL_RGBA
        self._target = GL_TEXTURE_CUBE_MAP if cube else GL_TEXTURE_2D

    def use(self, location=0):
        glActiveTexture(GL_TEXTURE0 + location)
        glBindTexture(self._target, self._id)

    def build_mipmaps(self):
        glBindTexture(self._target, self._id)
        glGenerateMipmap(self._target)

    def read(self):
        # Not implemented for wasmcart
        return b'\x00' * (self.width * self.height * 4)

    def write(self, data, viewport=None, face=0):
        """Upload pixels. `face` selects a cubemap face (moderngl's API);
        it is ignored for a 2D texture."""
        glBindTexture(self._target, self._id)
        target = (GL_TEXTURE_CUBE_MAP_POSITIVE_X + face) if self._cube else GL_TEXTURE_2D
        glTexImage2D(target, 0, self._fmt, self.width, self.height,
                     0, self._fmt, GL_UNSIGNED_BYTE, data)

    def release(self):
        pass

    @property
    def glo(self):
        return self._id


class Framebuffer:
    """Wraps a GL framebuffer object."""
    def __init__(self, fbo_id, width, height):
        self._id = fbo_id
        self.width = width
        self.height = height

    def use(self):
        glBindFramebuffer(GL_FRAMEBUFFER, self._id)
        glViewport(0, 0, self.width, self.height)

    def clear(self, color=None, depth=True):
        glBindFramebuffer(GL_FRAMEBUFFER, self._id)
        if color:
            glClearColor(*color, 1.0) if len(color) == 3 else glClearColor(*color)
        bits = GL_COLOR_BUFFER_BIT
        if depth:
            bits |= GL_DEPTH_BUFFER_BIT
        glClear(bits)

    def release(self):
        pass

    @property
    def glo(self):
        return self._id


class Context:
    """ModernGL context — wraps our OpenGL.GL functions."""

    def __init__(self):
        self.gc_mode = None
        self.screen = Framebuffer(0, 800, 600)
        self._fbo_stack = [self.screen]
        self.front_face = 'ccw'

    def enable(self, flags=0):
        if flags & DEPTH_TEST: glEnable(GL_DEPTH_TEST)
        if flags & CULL_FACE: glEnable(GL_CULL_FACE)
        if flags & BLEND: glEnable(GL_BLEND)

    def disable(self, flags=0):
        if flags & DEPTH_TEST: glDisable(GL_DEPTH_TEST)
        if flags & CULL_FACE: glDisable(GL_CULL_FACE)
        if flags & BLEND: glDisable(GL_BLEND)

    def clear(self, color=(0, 0, 0), depth=True):
        if isinstance(color, (tuple, list)):
            if len(color) == 3:
                glClearColor(color[0], color[1], color[2], 1.0)
            else:
                glClearColor(*color)
        bits = GL_COLOR_BUFFER_BIT
        if depth:
            bits |= GL_DEPTH_BUFFER_BIT
        glClear(bits)

    def program(self, vertex_shader='', fragment_shader=''):
        """Compile and link a shader program."""
        # Add GLES3 header if not present
        def fixup(code, is_frag):
            import re
            # Replace desktop GLSL version with GLES3
            code = re.sub(r'#version\s+\d+(\s+core)?', '#version 300 es', code)
            if '#version' not in code:
                code = '#version 300 es\n' + code
            # Add precision qualifier after version line
            if 'precision ' not in code:
                code = code.replace('#version 300 es', '#version 300 es\nprecision mediump float;', 1)
            # Fragment shader needs out variable
            if is_frag and 'out vec4' not in code and 'fragColor' not in code:
                # Insert after precision line
                code = code.replace('precision mediump float;', 'precision mediump float;\nout vec4 fragColor;', 1)
            # Replace gl_FragColor
            code = code.replace('gl_FragColor', 'fragColor')
            # texture2D -> texture
            code = code.replace('texture2D(', 'texture(')
            # GLES3 needs precision for sampler2DShadow
            if 'sampler2DShadow' in code and 'precision' not in code.split('sampler2DShadow')[0][-50:]:
                code = code.replace('precision mediump float;',
                    'precision mediump float;\nprecision mediump sampler2DShadow;', 1)
            # Fix int/float mismatches common in desktop GLSL
            # max(0, float) -> max(0.0, float)
            code = re.sub(r'\bmax\((\d+),', r'max(\1.0,', code)
            code = re.sub(r'\bmin\((\d+),', r'min(\1.0,', code)
            # int * float -> float * float
            code = re.sub(r'(\d+)\s*/\s*textureSize', r'\1.0 / textureSize', code)
            return code

        vs = fixup(vertex_shader, False)
        fs = fixup(fragment_shader, True)

        vs_id = glCreateShader(GL_VERTEX_SHADER)
        glShaderSource(vs_id, vs)
        glCompileShader(vs_id)
        if not glGetShaderiv(vs_id, GL_COMPILE_STATUS):
            err = glGetShaderInfoLog(vs_id)
            print(f"[moderngl] vertex shader error:\n{err}")

        fs_id = glCreateShader(GL_FRAGMENT_SHADER)
        glShaderSource(fs_id, fs)
        glCompileShader(fs_id)
        if not glGetShaderiv(fs_id, GL_COMPILE_STATUS):
            err = glGetShaderInfoLog(fs_id)
            print(f"[moderngl] fragment shader error:\n{err}")

        prog = glCreateProgram()
        glAttachShader(prog, vs_id)
        glAttachShader(prog, fs_id)
        glLinkProgram(prog)
        if not glGetProgramiv(prog, GL_LINK_STATUS):
            err = glGetProgramInfoLog(prog)
            print(f"[moderngl] link error:\n{err}")

        glDeleteShader(vs_id)
        glDeleteShader(fs_id)
        return Program(prog)

    def buffer(self, data=None, reserve=0, dynamic=False):
        """Create a GL buffer."""
        buf_id = glGenBuffers(1)
        if isinstance(data, (bytes, bytearray)):
            size = len(data)
            glBindBuffer(GL_ARRAY_BUFFER, buf_id)
            glBufferData(GL_ARRAY_BUFFER, data, GL_DYNAMIC_DRAW if dynamic else GL_STATIC_DRAW)
        elif hasattr(data, 'tobytes'):
            raw = data.tobytes()
            size = len(raw)
            glBindBuffer(GL_ARRAY_BUFFER, buf_id)
            glBufferData(GL_ARRAY_BUFFER, raw, GL_DYNAMIC_DRAW if dynamic else GL_STATIC_DRAW)
        else:
            size = reserve
            glBindBuffer(GL_ARRAY_BUFFER, buf_id)
            # Allocate empty buffer
            glBufferData(GL_ARRAY_BUFFER, bytes(size), GL_DYNAMIC_DRAW)
        return Buffer(buf_id, size)

    def vertex_array(self, program, content, index_buffer=None, skip_errors=False):
        """Create a VAO.
        content: list of (buffer, format_string, *attrib_names)
        format_string: e.g. '3f 2f' = 3 floats + 2 floats per vertex
        """
        vao_id = glGenVertexArrays(1)
        glBindVertexArray(vao_id)

        total_vertices = 0

        for item in content:
            buf = item[0]
            fmt = item[1]
            attrib_names = item[2:]

            glBindBuffer(GL_ARRAY_BUFFER, buf._id if isinstance(buf, Buffer) else buf)

            # Parse format: '3f 2f 3f' -> [(3, GL_FLOAT, 4), (2, GL_FLOAT, 4), ...]
            parts = fmt.split()
            attrs = []
            stride = 0
            for p in parts:
                # Handle formats like '3f', '2f', '1f', '4f', '3f/i' (instanced)
                p = p.rstrip('/i')
                count = int(p[:-1]) if len(p) > 1 else 1
                dtype = p[-1]
                if dtype == 'f':
                    gl_type = GL_FLOAT
                    byte_size = 4
                elif dtype == 'i':
                    gl_type = GL_INT if hasattr(GL_INT, '__int__') else 0x1404
                    byte_size = 4
                else:
                    gl_type = GL_FLOAT
                    byte_size = 4
                attrs.append((count, gl_type, byte_size * count))
                stride += byte_size * count

            if buf.size > 0 and stride > 0 and len(attrs) > 0:
                total_vertices = buf.size // stride

            offset = 0
            for idx, name in enumerate(attrib_names):
                if idx >= len(attrs):
                    break
                count, gl_type, size = attrs[idx]
                loc = glGetAttribLocation(program._id, name)
                if loc is not None and loc >= 0:
                    glEnableVertexAttribArray(loc)
                    glVertexAttribPointer(loc, count, gl_type, GL_FALSE, stride, offset)
                elif not skip_errors:
                    print(f"[moderngl] attrib '{name}' not found in program")
                offset += size

        glBindVertexArray(0)
        return VertexArray(vao_id, program, GL_TRIANGLES, total_vertices)

    def texture(self, size, components=4, data=None, samples=0, alignment=1, dtype='f1'):
        """Create a 2D texture."""
        w, h = size
        tex_id = glGenTextures(1)
        glBindTexture(GL_TEXTURE_2D, tex_id)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)

        fmt = GL_RGBA if components == 4 else GL_RGB
        ifmt = GL_RGBA if components == 4 else GL_RGB

        if data is not None:
            if isinstance(data, bytes):
                glTexImage2D(GL_TEXTURE_2D, 0, ifmt, w, h, 0, fmt, GL_UNSIGNED_BYTE, data)
            elif hasattr(data, 'tobytes'):
                glTexImage2D(GL_TEXTURE_2D, 0, ifmt, w, h, 0, fmt, GL_UNSIGNED_BYTE, data.tobytes())
            else:
                glTexImage2D(GL_TEXTURE_2D, 0, ifmt, w, h, 0, fmt, GL_UNSIGNED_BYTE, None)
        else:
            glTexImage2D(GL_TEXTURE_2D, 0, ifmt, w, h, 0, fmt, GL_UNSIGNED_BYTE, None)

        return Texture(tex_id, w, h, components=components)

    def depth_texture(self, size, samples=0):
        """Create a depth texture for shadow mapping."""
        w, h = size if isinstance(size, (tuple, list)) else (size, size)
        tex_id = glGenTextures(1)
        glBindTexture(GL_TEXTURE_2D, tex_id)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST)
        # format must be GL_DEPTH_COMPONENT, the base format matching the
        # DEPTH_COMPONENT16 internal format. It previously read
        # GL_DEPTH_BUFFER_BIT, which is a glClear mask bit that happens to be
        # a valid integer -- so the call failed silently and every shadow
        # lookup returned 0, shadowing the entire scene.
        glTexImage2D(GL_TEXTURE_2D, 0, GL_DEPTH_COMPONENT16, w, h, 0,
                     GL_DEPTH_COMPONENT, GL_UNSIGNED_SHORT, None)
        # Shaders read this through sampler2DShadow, which only works when
        # the texture carries a comparison mode. Without it GLES3 returns 0
        # for every lookup, so the scene renders as if everything were in
        # shadow -- a lit 3D scene comes out uniformly black.
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_COMPARE_MODE,
                        GL_COMPARE_REF_TO_TEXTURE)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_COMPARE_FUNC, GL_LEQUAL)
        return Texture(tex_id, w, h)

    def texture_cube(self, size, components=3, data=None):
        """Create a cubemap. Allocates all six faces so a later
        write(..., face=N) has storage to land in."""
        w, h = size if isinstance(size, (tuple, list)) else (size, size)
        fmt = GL_RGB if components == 3 else GL_RGBA
        tex_id = glGenTextures(1)
        glBindTexture(GL_TEXTURE_CUBE_MAP, tex_id)
        for face in range(6):
            glTexImage2D(GL_TEXTURE_CUBE_MAP_POSITIVE_X + face, 0, fmt,
                         w, h, 0, fmt, GL_UNSIGNED_BYTE, data)
        glTexParameteri(GL_TEXTURE_CUBE_MAP, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
        glTexParameteri(GL_TEXTURE_CUBE_MAP, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
        return Texture(tex_id, w, h, cube=True, components=components)

    def texture_array(self, size, components=3, data=None):
        """Stub for texture arrays."""
        tex_id = glGenTextures(1)
        return Texture(tex_id, size[0] if isinstance(size, tuple) else size, 0)

    def framebuffer(self, color_attachments=None, depth_attachment=None):
        """Create an FBO."""
        fbo_id = glGenFramebuffers(1)
        glBindFramebuffer(GL_FRAMEBUFFER, fbo_id)

        w, h = 800, 600
        if depth_attachment and isinstance(depth_attachment, Texture):
            w, h = depth_attachment.width, depth_attachment.height
            glFramebufferTexture2D(GL_FRAMEBUFFER, GL_DEPTH_ATTACHMENT,
                                   GL_TEXTURE_2D, depth_attachment._id, 0)

        if color_attachments:
            if isinstance(color_attachments, Texture):
                color_attachments = [color_attachments]
            for i, tex in enumerate(color_attachments):
                w, h = tex.width, tex.height
                glFramebufferTexture2D(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0 + i,
                                       GL_TEXTURE_2D, tex._id, 0)

        glBindFramebuffer(GL_FRAMEBUFFER, 0)
        return Framebuffer(fbo_id, w, h)

    def copy_framebuffer(self, dst, src):
        """Copy framebuffer — stub, would need glBlitFramebuffer."""
        pass
