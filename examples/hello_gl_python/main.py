"""
hello_gl_python — OpenGL triangle from Python inside wasmcart

Uses `from OpenGL.GL import *` — same API as PyOpenGL.
Backed by wasmcart GL ABI under the hood.
"""

import _wasmcart
from OpenGL.GL import *

_wasmcart.log("OpenGL module loaded!")

# Shader sources
VERT_SRC = """#version 300 es
layout(location = 0) in vec2 aPos;
layout(location = 1) in vec3 aColor;
out vec3 vColor;
void main() {
    gl_Position = vec4(aPos, 0.0, 1.0);
    vColor = aColor;
}
"""

FRAG_SRC = """#version 300 es
precision mediump float;
in vec3 vColor;
out vec4 FragColor;
void main() {
    FragColor = vec4(vColor, 1.0);
}
"""

import math

# Pack floats manually (no struct/array module needed)
def _pack_floats(*vals):
    """Pack floats to bytes using ctypes-free approach."""
    import _wasmcart
    # Use _wasmcart to pack via C - or just use bytearray
    result = bytearray()
    for v in vals:
        # IEEE 754 float to 4 bytes, little-endian
        # Simple approach: use int.to_bytes with float bits
        import sys
        bits = 0
        if v == 0.0:
            bits = 0
        else:
            sign = 0
            if v < 0:
                sign = 1
                v = -v
            # Find exponent and mantissa
            exp = 0
            m = v
            if m >= 2.0:
                while m >= 2.0:
                    m /= 2.0
                    exp += 1
            elif m < 1.0:
                while m < 1.0:
                    m *= 2.0
                    exp -= 1
            # m is now 1.0 <= m < 2.0
            mantissa = int((m - 1.0) * (1 << 23))
            biased_exp = exp + 127
            bits = (sign << 31) | (biased_exp << 23) | mantissa
        result.extend(bits.to_bytes(4, 'little'))
    return bytes(result)

# Triangle vertices: x, y, r, g, b
vertex_data = _pack_floats(
     0.0,  0.5,  1.0, 0.0, 0.0,  # top - red
    -0.5, -0.5,  0.0, 1.0, 0.0,  # bottom left - green
     0.5, -0.5,  0.0, 0.0, 1.0,  # bottom right - blue
)

# Compile shaders
def compile_shader(source, shader_type):
    shader = glCreateShader(shader_type)
    glShaderSource(shader, source)
    glCompileShader(shader)
    status = glGetShaderiv(shader, GL_COMPILE_STATUS)
    if not status:
        log = glGetShaderInfoLog(shader)
        _wasmcart.log(f"Shader compile error: {log}")
    return shader

vs = compile_shader(VERT_SRC, GL_VERTEX_SHADER)
fs = compile_shader(FRAG_SRC, GL_FRAGMENT_SHADER)

program = glCreateProgram()
glAttachShader(program, vs)
glAttachShader(program, fs)
glLinkProgram(program)
status = glGetProgramiv(program, GL_LINK_STATUS)
if not status:
    log = glGetProgramInfoLog(program)
    _wasmcart.log(f"Program link error: {log}")

glDeleteShader(vs)
glDeleteShader(fs)

# Setup VAO/VBO
vao = glGenVertexArrays(1)
vbo = glGenBuffers(1)

glBindVertexArray(vao)
glBindBuffer(GL_ARRAY_BUFFER, vbo)
glBufferData(GL_ARRAY_BUFFER, vertex_data, GL_STATIC_DRAW)

# Position: location 0, 2 floats, stride 20, offset 0
glEnableVertexAttribArray(0)
glVertexAttribPointer(0, 2, GL_FLOAT, GL_FALSE, 20, 0)

# Color: location 1, 3 floats, stride 20, offset 8
glEnableVertexAttribArray(1)
glVertexAttribPointer(1, 3, GL_FLOAT, GL_FALSE, 20, 8)

glBindVertexArray(0)

_wasmcart.log("GL setup complete!")

angle = 0.0

def _wc_frame():
    global angle
    angle += 0.02

    # Pulsing background
    r = (math.sin(angle) + 1.0) * 0.15
    g = (math.sin(angle + 2.0) + 1.0) * 0.15
    b = (math.sin(angle + 4.0) + 1.0) * 0.15

    glClearColor(r, g, b, 1.0)
    glClear(GL_COLOR_BUFFER_BIT)

    glUseProgram(program)
    glBindVertexArray(vao)
    glDrawArrays(GL_TRIANGLES, 0, 3)
    glBindVertexArray(0)
    glUseProgram(0)
