/*
 * opengl_module.c — PyOpenGL-compatible GL module backed by wasmcart GL ABI
 *
 * Provides `_opengl_gl` built-in module. Frozen Python packages make it
 * available as `from OpenGL.GL import *` — same API as PyOpenGL.
 *
 * GL functions are declared as WASM imports from the "gl" module.
 * CartHost provides the implementations (WebGL2/GLES3).
 */

#include <Python.h>
#include <stdint.h>

/* ── GL WASM imports from wasmcart host ──────────────────────────── */

#ifdef __wasm__
#define GL_IMPORT(name) \
    __attribute__((import_module("gl"), import_name(#name))) \
    extern
#else
#define GL_IMPORT(name) extern
#endif

/* State */
GL_IMPORT(glEnable) void _glEnable(unsigned int cap);
GL_IMPORT(glDisable) void _glDisable(unsigned int cap);
GL_IMPORT(glClear) void _glClear(unsigned int mask);
GL_IMPORT(glClearColor) void _glClearColor(float r, float g, float b, float a);
GL_IMPORT(glClearDepthf) void _glClearDepthf(float d);
GL_IMPORT(glClearStencil) void _glClearStencil(int s);
GL_IMPORT(glColorMask) void _glColorMask(unsigned int r, unsigned int g, unsigned int b, unsigned int a);
GL_IMPORT(glDepthFunc) void _glDepthFunc(unsigned int func);
GL_IMPORT(glDepthMask) void _glDepthMask(unsigned int flag);
GL_IMPORT(glDepthRangef) void _glDepthRangef(float n, float f);
GL_IMPORT(glBlendFunc) void _glBlendFunc(unsigned int sfactor, unsigned int dfactor);
GL_IMPORT(glBlendFuncSeparate) void _glBlendFuncSeparate(unsigned int sr, unsigned int dr, unsigned int sa, unsigned int da);
GL_IMPORT(glBlendEquation) void _glBlendEquation(unsigned int mode);
GL_IMPORT(glBlendEquationSeparate) void _glBlendEquationSeparate(unsigned int modeRGB, unsigned int modeA);
GL_IMPORT(glBlendColor) void _glBlendColor(float r, float g, float b, float a);
GL_IMPORT(glCullFace) void _glCullFace(unsigned int mode);
GL_IMPORT(glFrontFace) void _glFrontFace(unsigned int mode);
GL_IMPORT(glLineWidth) void _glLineWidth(float width);
GL_IMPORT(glPolygonOffset) void _glPolygonOffset(float factor, float units);
GL_IMPORT(glScissor) void _glScissor(int x, int y, int w, int h);
GL_IMPORT(glViewport) void _glViewport(int x, int y, int w, int h);
GL_IMPORT(glStencilFunc) void _glStencilFunc(unsigned int func, int ref, unsigned int mask);
GL_IMPORT(glStencilMask) void _glStencilMask(unsigned int mask);
GL_IMPORT(glStencilOp) void _glStencilOp(unsigned int sfail, unsigned int dpfail, unsigned int dppass);
GL_IMPORT(glPixelStorei) void _glPixelStorei(unsigned int pname, int param);
GL_IMPORT(glHint) void _glHint(unsigned int target, unsigned int mode);
GL_IMPORT(glFlush) void _glFlush(void);
GL_IMPORT(glFinish) void _glFinish(void);
GL_IMPORT(glGetError) unsigned int _glGetError(void);
GL_IMPORT(glGetIntegerv) void _glGetIntegerv(unsigned int pname, int *data);
GL_IMPORT(glGetFloatv) void _glGetFloatv(unsigned int pname, float *data);
GL_IMPORT(glGetString) const unsigned char* _glGetString(unsigned int name);
GL_IMPORT(glIsEnabled) unsigned int _glIsEnabled(unsigned int cap);

/* Shaders */
GL_IMPORT(glCreateShader) unsigned int _glCreateShader(unsigned int type);
GL_IMPORT(glDeleteShader) void _glDeleteShader(unsigned int shader);
GL_IMPORT(glShaderSource) void _glShaderSource(unsigned int shader, int count, const char **string, const int *length);
GL_IMPORT(glCompileShader) void _glCompileShader(unsigned int shader);
GL_IMPORT(glGetShaderiv) void _glGetShaderiv(unsigned int shader, unsigned int pname, int *params);
GL_IMPORT(glGetShaderInfoLog) void _glGetShaderInfoLog(unsigned int shader, int maxLen, int *length, char *infoLog);
GL_IMPORT(glCreateProgram) unsigned int _glCreateProgram(void);
GL_IMPORT(glDeleteProgram) void _glDeleteProgram(unsigned int program);
GL_IMPORT(glAttachShader) void _glAttachShader(unsigned int program, unsigned int shader);
GL_IMPORT(glDetachShader) void _glDetachShader(unsigned int program, unsigned int shader);
GL_IMPORT(glLinkProgram) void _glLinkProgram(unsigned int program);
GL_IMPORT(glUseProgram) void _glUseProgram(unsigned int program);
GL_IMPORT(glGetProgramiv) void _glGetProgramiv(unsigned int program, unsigned int pname, int *params);
GL_IMPORT(glGetProgramInfoLog) void _glGetProgramInfoLog(unsigned int program, int maxLen, int *length, char *infoLog);
GL_IMPORT(glGetAttribLocation) int _glGetAttribLocation(unsigned int program, const char *name);
GL_IMPORT(glGetUniformLocation) int _glGetUniformLocation(unsigned int program, const char *name);
GL_IMPORT(glBindAttribLocation) void _glBindAttribLocation(unsigned int program, unsigned int index, const char *name);
GL_IMPORT(glValidateProgram) void _glValidateProgram(unsigned int program);

/* Uniforms */
GL_IMPORT(glUniform1i) void _glUniform1i(int loc, int v0);
GL_IMPORT(glUniform2i) void _glUniform2i(int loc, int v0, int v1);
GL_IMPORT(glUniform3i) void _glUniform3i(int loc, int v0, int v1, int v2);
GL_IMPORT(glUniform4i) void _glUniform4i(int loc, int v0, int v1, int v2, int v3);
GL_IMPORT(glUniform1f) void _glUniform1f(int loc, float v0);
GL_IMPORT(glUniform2f) void _glUniform2f(int loc, float v0, float v1);
GL_IMPORT(glUniform3f) void _glUniform3f(int loc, float v0, float v1, float v2);
GL_IMPORT(glUniform4f) void _glUniform4f(int loc, float v0, float v1, float v2, float v3);
GL_IMPORT(glUniform1fv) void _glUniform1fv(int loc, int count, const float *value);
GL_IMPORT(glUniform2fv) void _glUniform2fv(int loc, int count, const float *value);
GL_IMPORT(glUniform3fv) void _glUniform3fv(int loc, int count, const float *value);
GL_IMPORT(glUniform4fv) void _glUniform4fv(int loc, int count, const float *value);
GL_IMPORT(glUniformMatrix2fv) void _glUniformMatrix2fv(int loc, int count, unsigned int transpose, const float *value);
GL_IMPORT(glUniformMatrix3fv) void _glUniformMatrix3fv(int loc, int count, unsigned int transpose, const float *value);
GL_IMPORT(glUniformMatrix4fv) void _glUniformMatrix4fv(int loc, int count, unsigned int transpose, const float *value);

/* Buffers */
GL_IMPORT(glGenBuffers) void _glGenBuffers(int n, unsigned int *buffers);
GL_IMPORT(glDeleteBuffers) void _glDeleteBuffers(int n, const unsigned int *buffers);
GL_IMPORT(glBindBuffer) void _glBindBuffer(unsigned int target, unsigned int buffer);
GL_IMPORT(glBufferData) void _glBufferData(unsigned int target, int size, const void *data, unsigned int usage);
GL_IMPORT(glBufferSubData) void _glBufferSubData(unsigned int target, int offset, int size, const void *data);

/* VAO */
GL_IMPORT(glGenVertexArrays) void _glGenVertexArrays(int n, unsigned int *arrays);
GL_IMPORT(glDeleteVertexArrays) void _glDeleteVertexArrays(int n, const unsigned int *arrays);
GL_IMPORT(glBindVertexArray) void _glBindVertexArray(unsigned int array);
GL_IMPORT(glEnableVertexAttribArray) void _glEnableVertexAttribArray(unsigned int index);
GL_IMPORT(glDisableVertexAttribArray) void _glDisableVertexAttribArray(unsigned int index);
GL_IMPORT(glVertexAttribPointer) void _glVertexAttribPointer(unsigned int index, int size, unsigned int type, unsigned int normalized, int stride, const void *pointer);

/* Textures */
GL_IMPORT(glGenTextures) void _glGenTextures(int n, unsigned int *textures);
GL_IMPORT(glDeleteTextures) void _glDeleteTextures(int n, const unsigned int *textures);
GL_IMPORT(glBindTexture) void _glBindTexture(unsigned int target, unsigned int texture);
GL_IMPORT(glActiveTexture) void _glActiveTexture(unsigned int texture);
GL_IMPORT(glTexParameteri) void _glTexParameteri(unsigned int target, unsigned int pname, int param);
GL_IMPORT(glTexParameterf) void _glTexParameterf(unsigned int target, unsigned int pname, float param);
GL_IMPORT(glTexImage2D) void _glTexImage2D(unsigned int target, int level, int internalformat, int width, int height, int border, unsigned int format, unsigned int type, const void *pixels);
GL_IMPORT(glTexSubImage2D) void _glTexSubImage2D(unsigned int target, int level, int xoffset, int yoffset, int width, int height, unsigned int format, unsigned int type, const void *pixels);
GL_IMPORT(glGenerateMipmap) void _glGenerateMipmap(unsigned int target);

/* FBO */
GL_IMPORT(glGenFramebuffers) void _glGenFramebuffers(int n, unsigned int *framebuffers);
GL_IMPORT(glDeleteFramebuffers) void _glDeleteFramebuffers(int n, const unsigned int *framebuffers);
GL_IMPORT(glBindFramebuffer) void _glBindFramebuffer(unsigned int target, unsigned int framebuffer);
GL_IMPORT(glFramebufferTexture2D) void _glFramebufferTexture2D(unsigned int target, unsigned int attachment, unsigned int textarget, unsigned int texture, int level);
GL_IMPORT(glCheckFramebufferStatus) unsigned int _glCheckFramebufferStatus(unsigned int target);
GL_IMPORT(glGenRenderbuffers) void _glGenRenderbuffers(int n, unsigned int *renderbuffers);
GL_IMPORT(glDeleteRenderbuffers) void _glDeleteRenderbuffers(int n, const unsigned int *renderbuffers);
GL_IMPORT(glBindRenderbuffer) void _glBindRenderbuffer(unsigned int target, unsigned int renderbuffer);
GL_IMPORT(glRenderbufferStorage) void _glRenderbufferStorage(unsigned int target, unsigned int internalformat, int width, int height);
GL_IMPORT(glFramebufferRenderbuffer) void _glFramebufferRenderbuffer(unsigned int target, unsigned int attachment, unsigned int renderbuffertarget, unsigned int renderbuffer);

/* Draw */
GL_IMPORT(glDrawArrays) void _glDrawArrays(unsigned int mode, int first, int count);
GL_IMPORT(glDrawElements) void _glDrawElements(unsigned int mode, int count, unsigned int type, const void *indices);

/* Read */
GL_IMPORT(glReadPixels) void _glReadPixels(int x, int y, int width, int height, unsigned int format, unsigned int type, void *pixels);

/* ── Python wrappers ─────────────────────────────────────────────── */

/* Macros to reduce boilerplate */

/* void func(uint) */
#define PY_GL_VOID_U(name) \
    static PyObject *py_##name(PyObject *self, PyObject *args) { \
        unsigned int a; \
        if (!PyArg_ParseTuple(args, "I", &a)) return NULL; \
        _##name(a); Py_RETURN_NONE; }

/* void func(uint, uint) */
#define PY_GL_VOID_UU(name) \
    static PyObject *py_##name(PyObject *self, PyObject *args) { \
        unsigned int a, b; \
        if (!PyArg_ParseTuple(args, "II", &a, &b)) return NULL; \
        _##name(a, b); Py_RETURN_NONE; }

/* void func(uint, uint, uint, uint) */
#define PY_GL_VOID_UUUU(name) \
    static PyObject *py_##name(PyObject *self, PyObject *args) { \
        unsigned int a, b, c, d; \
        if (!PyArg_ParseTuple(args, "IIII", &a, &b, &c, &d)) return NULL; \
        _##name(a, b, c, d); Py_RETURN_NONE; }

/* void func(int, int, int, int) */
#define PY_GL_VOID_IIII(name) \
    static PyObject *py_##name(PyObject *self, PyObject *args) { \
        int a, b, c, d; \
        if (!PyArg_ParseTuple(args, "iiii", &a, &b, &c, &d)) return NULL; \
        _##name(a, b, c, d); Py_RETURN_NONE; }

/* void func(float, float, float, float) */
#define PY_GL_VOID_FFFF(name) \
    static PyObject *py_##name(PyObject *self, PyObject *args) { \
        float a, b, c, d; \
        if (!PyArg_ParseTuple(args, "ffff", &a, &b, &c, &d)) return NULL; \
        _##name(a, b, c, d); Py_RETURN_NONE; }

/* void func(void) */
#define PY_GL_VOID_V(name) \
    static PyObject *py_##name(PyObject *self, PyObject *args) { \
        _##name(); Py_RETURN_NONE; }

/* uint func(void) */
#define PY_GL_UINT_V(name) \
    static PyObject *py_##name(PyObject *self, PyObject *args) { \
        return PyLong_FromUnsignedLong(_##name()); }

/* uint func(uint) */
#define PY_GL_UINT_U(name) \
    static PyObject *py_##name(PyObject *self, PyObject *args) { \
        unsigned int a; \
        if (!PyArg_ParseTuple(args, "I", &a)) return NULL; \
        return PyLong_FromUnsignedLong(_##name(a)); }

/* State */
PY_GL_VOID_U(glEnable)
PY_GL_VOID_U(glDisable)
PY_GL_VOID_U(glClear)
PY_GL_VOID_FFFF(glClearColor)
PY_GL_VOID_UUUU(glColorMask)
PY_GL_VOID_U(glDepthFunc)
PY_GL_VOID_U(glDepthMask)
PY_GL_VOID_UU(glBlendFunc)
PY_GL_VOID_UUUU(glBlendFuncSeparate)
PY_GL_VOID_U(glBlendEquation)
PY_GL_VOID_UU(glBlendEquationSeparate)
PY_GL_VOID_FFFF(glBlendColor)
PY_GL_VOID_U(glCullFace)
PY_GL_VOID_U(glFrontFace)
PY_GL_VOID_IIII(glScissor)
PY_GL_VOID_IIII(glViewport)
PY_GL_VOID_UU(glHint)
PY_GL_VOID_V(glFlush)
PY_GL_VOID_V(glFinish)
PY_GL_UINT_V(glGetError)
PY_GL_UINT_U(glIsEnabled)

static PyObject *py_glClearDepthf(PyObject *self, PyObject *args) {
    float d; if (!PyArg_ParseTuple(args, "f", &d)) return NULL;
    _glClearDepthf(d); Py_RETURN_NONE;
}
static PyObject *py_glClearStencil(PyObject *self, PyObject *args) {
    int s; if (!PyArg_ParseTuple(args, "i", &s)) return NULL;
    _glClearStencil(s); Py_RETURN_NONE;
}
static PyObject *py_glDepthRangef(PyObject *self, PyObject *args) {
    float n, f; if (!PyArg_ParseTuple(args, "ff", &n, &f)) return NULL;
    _glDepthRangef(n, f); Py_RETURN_NONE;
}
static PyObject *py_glLineWidth(PyObject *self, PyObject *args) {
    float w; if (!PyArg_ParseTuple(args, "f", &w)) return NULL;
    _glLineWidth(w); Py_RETURN_NONE;
}
static PyObject *py_glPolygonOffset(PyObject *self, PyObject *args) {
    float f, u; if (!PyArg_ParseTuple(args, "ff", &f, &u)) return NULL;
    _glPolygonOffset(f, u); Py_RETURN_NONE;
}
static PyObject *py_glStencilFunc(PyObject *self, PyObject *args) {
    unsigned int func, mask; int ref;
    if (!PyArg_ParseTuple(args, "IiI", &func, &ref, &mask)) return NULL;
    _glStencilFunc(func, ref, mask); Py_RETURN_NONE;
}
static PyObject *py_glStencilMask(PyObject *self, PyObject *args) {
    unsigned int mask; if (!PyArg_ParseTuple(args, "I", &mask)) return NULL;
    _glStencilMask(mask); Py_RETURN_NONE;
}
static PyObject *py_glStencilOp(PyObject *self, PyObject *args) {
    unsigned int a, b, c;
    if (!PyArg_ParseTuple(args, "III", &a, &b, &c)) return NULL;
    _glStencilOp(a, b, c); Py_RETURN_NONE;
}
static PyObject *py_glPixelStorei(PyObject *self, PyObject *args) {
    unsigned int pname; int param;
    if (!PyArg_ParseTuple(args, "Ii", &pname, &param)) return NULL;
    _glPixelStorei(pname, param); Py_RETURN_NONE;
}

/* Shaders */
PY_GL_UINT_U(glCreateShader)
PY_GL_VOID_U(glDeleteShader)
PY_GL_VOID_U(glCompileShader)
PY_GL_UINT_V(glCreateProgram)
PY_GL_VOID_U(glDeleteProgram)
PY_GL_VOID_UU(glAttachShader)
PY_GL_VOID_UU(glDetachShader)
PY_GL_VOID_U(glLinkProgram)
PY_GL_VOID_U(glUseProgram)
PY_GL_VOID_U(glValidateProgram)

static PyObject *py_glShaderSource(PyObject *self, PyObject *args) {
    unsigned int shader;
    const char *source;
    if (!PyArg_ParseTuple(args, "Is", &shader, &source)) return NULL;
    const char *sources[] = { source };
    _glShaderSource(shader, 1, sources, NULL);
    Py_RETURN_NONE;
}

static PyObject *py_glGetShaderiv(PyObject *self, PyObject *args) {
    unsigned int shader, pname; int result = 0;
    if (!PyArg_ParseTuple(args, "II", &shader, &pname)) return NULL;
    _glGetShaderiv(shader, pname, &result);
    return PyLong_FromLong(result);
}

static PyObject *py_glGetShaderInfoLog(PyObject *self, PyObject *args) {
    unsigned int shader;
    if (!PyArg_ParseTuple(args, "I", &shader)) return NULL;
    int len = 0;
    _glGetShaderiv(shader, 0x8B84 /*GL_INFO_LOG_LENGTH*/, &len);
    if (len <= 0) return PyUnicode_FromString("");
    char *buf = malloc(len + 1);
    _glGetShaderInfoLog(shader, len + 1, NULL, buf);
    PyObject *s = PyUnicode_FromString(buf);
    free(buf);
    return s;
}

static PyObject *py_glGetProgramiv(PyObject *self, PyObject *args) {
    unsigned int program, pname; int result = 0;
    if (!PyArg_ParseTuple(args, "II", &program, &pname)) return NULL;
    _glGetProgramiv(program, pname, &result);
    return PyLong_FromLong(result);
}

static PyObject *py_glGetProgramInfoLog(PyObject *self, PyObject *args) {
    unsigned int program;
    if (!PyArg_ParseTuple(args, "I", &program)) return NULL;
    int len = 0;
    _glGetProgramiv(program, 0x8B84, &len);
    if (len <= 0) return PyUnicode_FromString("");
    char *buf = malloc(len + 1);
    _glGetProgramInfoLog(program, len + 1, NULL, buf);
    PyObject *s = PyUnicode_FromString(buf);
    free(buf);
    return s;
}

static PyObject *py_glGetAttribLocation(PyObject *self, PyObject *args) {
    unsigned int program; const char *name;
    if (!PyArg_ParseTuple(args, "Is", &program, &name)) return NULL;
    return PyLong_FromLong(_glGetAttribLocation(program, name));
}

static PyObject *py_glGetUniformLocation(PyObject *self, PyObject *args) {
    unsigned int program; const char *name;
    if (!PyArg_ParseTuple(args, "Is", &program, &name)) return NULL;
    return PyLong_FromLong(_glGetUniformLocation(program, name));
}

static PyObject *py_glBindAttribLocation(PyObject *self, PyObject *args) {
    unsigned int program, index; const char *name;
    if (!PyArg_ParseTuple(args, "IIs", &program, &index, &name)) return NULL;
    _glBindAttribLocation(program, index, name); Py_RETURN_NONE;
}

/* Uniforms */
static PyObject *py_glUniform1i(PyObject *s, PyObject *a) { int l,v; if(!PyArg_ParseTuple(a,"ii",&l,&v))return NULL; _glUniform1i(l,v); Py_RETURN_NONE; }
static PyObject *py_glUniform2i(PyObject *s, PyObject *a) { int l,v0,v1; if(!PyArg_ParseTuple(a,"iii",&l,&v0,&v1))return NULL; _glUniform2i(l,v0,v1); Py_RETURN_NONE; }
static PyObject *py_glUniform3i(PyObject *s, PyObject *a) { int l,v0,v1,v2; if(!PyArg_ParseTuple(a,"iiii",&l,&v0,&v1,&v2))return NULL; _glUniform3i(l,v0,v1,v2); Py_RETURN_NONE; }
static PyObject *py_glUniform4i(PyObject *s, PyObject *a) { int l,v0,v1,v2,v3; if(!PyArg_ParseTuple(a,"iiiii",&l,&v0,&v1,&v2,&v3))return NULL; _glUniform4i(l,v0,v1,v2,v3); Py_RETURN_NONE; }
static PyObject *py_glUniform1f(PyObject *s, PyObject *a) { int l; float v; if(!PyArg_ParseTuple(a,"if",&l,&v))return NULL; _glUniform1f(l,v); Py_RETURN_NONE; }
static PyObject *py_glUniform2f(PyObject *s, PyObject *a) { int l; float v0,v1; if(!PyArg_ParseTuple(a,"iff",&l,&v0,&v1))return NULL; _glUniform2f(l,v0,v1); Py_RETURN_NONE; }
static PyObject *py_glUniform3f(PyObject *s, PyObject *a) { int l; float v0,v1,v2; if(!PyArg_ParseTuple(a,"ifff",&l,&v0,&v1,&v2))return NULL; _glUniform3f(l,v0,v1,v2); Py_RETURN_NONE; }
static PyObject *py_glUniform4f(PyObject *s, PyObject *a) { int l; float v0,v1,v2,v3; if(!PyArg_ParseTuple(a,"iffff",&l,&v0,&v1,&v2,&v3))return NULL; _glUniform4f(l,v0,v1,v2,v3); Py_RETURN_NONE; }

/* Uniform array/matrix — accept Python list of floats */
static PyObject *py_glUniformMatrix4fv(PyObject *self, PyObject *args) {
    int loc, count; unsigned int transpose; PyObject *list;
    if (!PyArg_ParseTuple(args, "iIIO", &loc, &count, &transpose, &list)) return NULL;
    Py_ssize_t n = PyList_Size(list);
    float *vals = malloc(n * sizeof(float));
    for (Py_ssize_t i = 0; i < n; i++)
        vals[i] = (float)PyFloat_AsDouble(PyList_GetItem(list, i));
    _glUniformMatrix4fv(loc, count, transpose, vals);
    free(vals);
    Py_RETURN_NONE;
}

static PyObject *py_glUniformMatrix3fv(PyObject *self, PyObject *args) {
    int loc, count; unsigned int transpose; PyObject *list;
    if (!PyArg_ParseTuple(args, "iIIO", &loc, &count, &transpose, &list)) return NULL;
    Py_ssize_t n = PyList_Size(list);
    float *vals = malloc(n * sizeof(float));
    for (Py_ssize_t i = 0; i < n; i++)
        vals[i] = (float)PyFloat_AsDouble(PyList_GetItem(list, i));
    _glUniformMatrix3fv(loc, count, transpose, vals);
    free(vals);
    Py_RETURN_NONE;
}

/* Buffers */
static PyObject *py_glGenBuffers(PyObject *self, PyObject *args) {
    int n; if (!PyArg_ParseTuple(args, "i", &n)) return NULL;
    if (n == 1) { unsigned int buf; _glGenBuffers(1, &buf); return PyLong_FromUnsignedLong(buf); }
    unsigned int *bufs = malloc(n * sizeof(unsigned int));
    _glGenBuffers(n, bufs);
    PyObject *list = PyList_New(n);
    for (int i = 0; i < n; i++) PyList_SetItem(list, i, PyLong_FromUnsignedLong(bufs[i]));
    free(bufs);
    return list;
}

static PyObject *py_glDeleteBuffers(PyObject *self, PyObject *args) {
    unsigned int buf;
    if (PyArg_ParseTuple(args, "I", &buf)) { _glDeleteBuffers(1, &buf); Py_RETURN_NONE; }
    Py_RETURN_NONE;
}

PY_GL_VOID_UU(glBindBuffer)

static PyObject *py_glBufferData(PyObject *self, PyObject *args) {
    unsigned int target, usage; PyObject *data_obj;
    if (!PyArg_ParseTuple(args, "IOI", &target, &data_obj, &usage)) return NULL;
    Py_buffer view;
    if (PyObject_GetBuffer(data_obj, &view, PyBUF_SIMPLE) == -1) return NULL;
    _glBufferData(target, (int)view.len, view.buf, usage);
    PyBuffer_Release(&view);
    Py_RETURN_NONE;
}

static PyObject *py_glBufferSubData(PyObject *self, PyObject *args) {
    unsigned int target; int offset; PyObject *data_obj;
    if (!PyArg_ParseTuple(args, "IiO", &target, &offset, &data_obj)) return NULL;
    Py_buffer view;
    if (PyObject_GetBuffer(data_obj, &view, PyBUF_SIMPLE) == -1) return NULL;
    _glBufferSubData(target, offset, (int)view.len, view.buf);
    PyBuffer_Release(&view);
    Py_RETURN_NONE;
}

/* VAO */
static PyObject *py_glGenVertexArrays(PyObject *self, PyObject *args) {
    int n; if (!PyArg_ParseTuple(args, "i", &n)) return NULL;
    if (n == 1) { unsigned int vao; _glGenVertexArrays(1, &vao); return PyLong_FromUnsignedLong(vao); }
    unsigned int *vaos = malloc(n * sizeof(unsigned int));
    _glGenVertexArrays(n, vaos);
    PyObject *list = PyList_New(n);
    for (int i = 0; i < n; i++) PyList_SetItem(list, i, PyLong_FromUnsignedLong(vaos[i]));
    free(vaos);
    return list;
}

PY_GL_VOID_U(glBindVertexArray)
PY_GL_VOID_U(glEnableVertexAttribArray)
PY_GL_VOID_U(glDisableVertexAttribArray)

static PyObject *py_glVertexAttribPointer(PyObject *self, PyObject *args) {
    unsigned int index, type, normalized; int size, stride; long offset;
    if (!PyArg_ParseTuple(args, "IiIIil", &index, &size, &type, &normalized, &stride, &offset)) return NULL;
    _glVertexAttribPointer(index, size, type, normalized, stride, (const void*)(uintptr_t)offset);
    Py_RETURN_NONE;
}

/* Textures */
static PyObject *py_glGenTextures(PyObject *self, PyObject *args) {
    int n; if (!PyArg_ParseTuple(args, "i", &n)) return NULL;
    if (n == 1) { unsigned int tex; _glGenTextures(1, &tex); return PyLong_FromUnsignedLong(tex); }
    unsigned int *texs = malloc(n * sizeof(unsigned int));
    _glGenTextures(n, texs);
    PyObject *list = PyList_New(n);
    for (int i = 0; i < n; i++) PyList_SetItem(list, i, PyLong_FromUnsignedLong(texs[i]));
    free(texs);
    return list;
}

PY_GL_VOID_UU(glBindTexture)
PY_GL_VOID_U(glActiveTexture)
PY_GL_VOID_U(glGenerateMipmap)

static PyObject *py_glTexParameteri(PyObject *self, PyObject *args) {
    unsigned int target, pname; int param;
    if (!PyArg_ParseTuple(args, "IIi", &target, &pname, &param)) return NULL;
    _glTexParameteri(target, pname, param); Py_RETURN_NONE;
}

static PyObject *py_glTexImage2D(PyObject *self, PyObject *args) {
    unsigned int target, format, type; int level, ifmt, width, height, border;
    PyObject *data_obj;
    /* 9 specifiers for 9 variables: the border argument was missing its
     * 'i', so every call raised "function takes exactly 8 arguments". */
    if (!PyArg_ParseTuple(args, "IiiiiiIIO", &target, &level, &ifmt, &width, &height, &border, &format, &type, &data_obj)) return NULL;
    if (data_obj == Py_None) {
        _glTexImage2D(target, level, ifmt, width, height, border, format, type, NULL);
    } else {
        Py_buffer view;
        if (PyObject_GetBuffer(data_obj, &view, PyBUF_SIMPLE) == -1) return NULL;
        _glTexImage2D(target, level, ifmt, width, height, border, format, type, view.buf);
        PyBuffer_Release(&view);
    }
    Py_RETURN_NONE;
}

/* FBO */
static PyObject *py_glGenFramebuffers(PyObject *self, PyObject *args) {
    int n; if (!PyArg_ParseTuple(args, "i", &n)) return NULL;
    if (n == 1) { unsigned int fbo; _glGenFramebuffers(1, &fbo); return PyLong_FromUnsignedLong(fbo); }
    unsigned int *fbos = malloc(n * sizeof(unsigned int));
    _glGenFramebuffers(n, fbos);
    PyObject *list = PyList_New(n);
    for (int i = 0; i < n; i++) PyList_SetItem(list, i, PyLong_FromUnsignedLong(fbos[i]));
    free(fbos);
    return list;
}

PY_GL_VOID_UU(glBindFramebuffer)
PY_GL_UINT_U(glCheckFramebufferStatus)

static PyObject *py_glFramebufferTexture2D(PyObject *self, PyObject *args) {
    unsigned int target, attachment, textarget, texture; int level;
    if (!PyArg_ParseTuple(args, "IIIIi", &target, &attachment, &textarget, &texture, &level)) return NULL;
    _glFramebufferTexture2D(target, attachment, textarget, texture, level); Py_RETURN_NONE;
}

static PyObject *py_glRenderbufferStorage(PyObject *self, PyObject *args) {
    unsigned int target, ifmt; int w, h;
    if (!PyArg_ParseTuple(args, "IIii", &target, &ifmt, &w, &h)) return NULL;
    _glRenderbufferStorage(target, ifmt, w, h); Py_RETURN_NONE;
}

/* Draw */
static PyObject *py_glDrawArrays(PyObject *self, PyObject *args) {
    unsigned int mode; int first, count;
    if (!PyArg_ParseTuple(args, "Iii", &mode, &first, &count)) return NULL;
    _glDrawArrays(mode, first, count); Py_RETURN_NONE;
}

static PyObject *py_glDrawElements(PyObject *self, PyObject *args) {
    unsigned int mode, type; int count; long offset;
    if (!PyArg_ParseTuple(args, "IiIl", &mode, &count, &type, &offset)) return NULL;
    _glDrawElements(mode, count, type, (const void*)(uintptr_t)offset); Py_RETURN_NONE;
}

/* GetString */
static PyObject *py_glGetString(PyObject *self, PyObject *args) {
    unsigned int name; if (!PyArg_ParseTuple(args, "I", &name)) return NULL;
    const unsigned char *s = _glGetString(name);
    return PyUnicode_FromString(s ? (const char*)s : "");
}

/* Desktop GL compat stubs */
static PyObject *py_glPolygonMode(PyObject *s, PyObject *a) { Py_RETURN_NONE; }
static PyObject *py_glPointSize(PyObject *s, PyObject *a) { Py_RETURN_NONE; }

/* ── Method table ────────────────────────────────────────────────── */

#define M(name) {#name, py_##name, METH_VARARGS, #name}
#define M0(name) {#name, py_##name, METH_NOARGS, #name}

static PyMethodDef opengl_methods[] = {
    /* State */
    M(glEnable), M(glDisable), M(glClear), M(glClearColor), M(glClearDepthf),
    M(glClearStencil), M(glColorMask), M(glDepthFunc), M(glDepthMask),
    M(glDepthRangef), M(glBlendFunc), M(glBlendFuncSeparate), M(glBlendEquation),
    M(glBlendEquationSeparate), M(glBlendColor), M(glCullFace), M(glFrontFace),
    M(glLineWidth), M(glPolygonOffset), M(glScissor), M(glViewport),
    M(glStencilFunc), M(glStencilMask), M(glStencilOp), M(glPixelStorei),
    M(glHint), M0(glFlush), M0(glFinish), M0(glGetError), M(glIsEnabled),
    M(glGetString),

    /* Shaders */
    M(glCreateShader), M(glDeleteShader), M(glShaderSource), M(glCompileShader),
    M(glGetShaderiv), M(glGetShaderInfoLog), M0(glCreateProgram), M(glDeleteProgram),
    M(glAttachShader), M(glDetachShader), M(glLinkProgram), M(glUseProgram),
    M(glGetProgramiv), M(glGetProgramInfoLog), M(glGetAttribLocation),
    M(glGetUniformLocation), M(glBindAttribLocation), M(glValidateProgram),

    /* Uniforms */
    M(glUniform1i), M(glUniform2i), M(glUniform3i), M(glUniform4i),
    M(glUniform1f), M(glUniform2f), M(glUniform3f), M(glUniform4f),
    M(glUniformMatrix3fv), M(glUniformMatrix4fv),

    /* Buffers */
    M(glGenBuffers), M(glDeleteBuffers), M(glBindBuffer), M(glBufferData),
    M(glBufferSubData),

    /* VAO */
    M(glGenVertexArrays), M(glBindVertexArray), M(glEnableVertexAttribArray),
    M(glDisableVertexAttribArray), M(glVertexAttribPointer),

    /* Textures */
    M(glGenTextures), M(glBindTexture), M(glActiveTexture), M(glTexParameteri),
    M(glTexImage2D), M(glGenerateMipmap),

    /* FBO */
    M(glGenFramebuffers), M(glBindFramebuffer), M(glCheckFramebufferStatus),
    M(glFramebufferTexture2D), M(glRenderbufferStorage),

    /* Draw */
    M(glDrawArrays), M(glDrawElements),

    /* Desktop GL compat stubs (no-ops on GLES3) */
    {"glPolygonMode", (PyCFunction)(void(*)(void))py_glPolygonMode, METH_VARARGS, "no-op"},
    {"glPointSize", (PyCFunction)(void(*)(void))py_glPointSize, METH_VARARGS, "no-op"},

    {NULL, NULL, 0, NULL}
};

#undef M
#undef M0

/* ── GL constants ────────────────────────────────────────────────── */

static int add_gl_constants(PyObject *module) {
#define C(name, val) PyModule_AddIntConstant(module, #name, val)
    /* Clear bits */
    C(GL_COLOR_BUFFER_BIT, 0x00004000);
    C(GL_DEPTH_BUFFER_BIT, 0x00000100);
    C(GL_STENCIL_BUFFER_BIT, 0x00000400);
    /* Primitive types */
    C(GL_POINTS, 0x0000); C(GL_LINES, 0x0001); C(GL_LINE_LOOP, 0x0002);
    C(GL_LINE_STRIP, 0x0003); C(GL_TRIANGLES, 0x0004);
    C(GL_TRIANGLE_STRIP, 0x0005); C(GL_TRIANGLE_FAN, 0x0006);
    /* Enable caps */
    C(GL_BLEND, 0x0BE2); C(GL_CULL_FACE, 0x0B44); C(GL_DEPTH_TEST, 0x0B71);
    C(GL_DITHER, 0x0BD0); C(GL_POLYGON_OFFSET_FILL, 0x8037);
    C(GL_SAMPLE_ALPHA_TO_COVERAGE, 0x809E); C(GL_SAMPLE_COVERAGE, 0x80A0);
    C(GL_SCISSOR_TEST, 0x0C11); C(GL_STENCIL_TEST, 0x0B90);
    /* Blend */
    C(GL_ZERO, 0); C(GL_ONE, 1); C(GL_SRC_COLOR, 0x0300); C(GL_ONE_MINUS_SRC_COLOR, 0x0301);
    C(GL_SRC_ALPHA, 0x0302); C(GL_ONE_MINUS_SRC_ALPHA, 0x0303);
    C(GL_DST_ALPHA, 0x0304); C(GL_ONE_MINUS_DST_ALPHA, 0x0305);
    C(GL_DST_COLOR, 0x0306); C(GL_ONE_MINUS_DST_COLOR, 0x0307);
    C(GL_FUNC_ADD, 0x8006); C(GL_FUNC_SUBTRACT, 0x800A); C(GL_FUNC_REVERSE_SUBTRACT, 0x800B);
    /* Depth */
    C(GL_NEVER, 0x0200); C(GL_LESS, 0x0201); C(GL_EQUAL, 0x0202);
    C(GL_LEQUAL, 0x0203); C(GL_GREATER, 0x0204); C(GL_NOTEQUAL, 0x0205);
    C(GL_GEQUAL, 0x0206); C(GL_ALWAYS, 0x0207);
    /* Cull */
    C(GL_FRONT, 0x0404); C(GL_BACK, 0x0405); C(GL_FRONT_AND_BACK, 0x0408);
    C(GL_CW, 0x0900); C(GL_CCW, 0x0901);
    /* Data types */
    C(GL_BYTE, 0x1400); C(GL_UNSIGNED_BYTE, 0x1401);
    C(GL_SHORT, 0x1402); C(GL_UNSIGNED_SHORT, 0x1403);
    C(GL_INT, 0x1404); C(GL_UNSIGNED_INT, 0x1405); C(GL_FLOAT, 0x1406);
    /* Pixel formats */
    C(GL_ALPHA, 0x1906); C(GL_RGB, 0x1907); C(GL_RGBA, 0x1908);
    C(GL_LUMINANCE, 0x1909); C(GL_LUMINANCE_ALPHA, 0x190A);
    C(GL_RED, 0x1903);
    /* Texture targets */
    C(GL_TEXTURE_2D, 0x0DE1); C(GL_TEXTURE_CUBE_MAP, 0x8513);
    C(GL_TEXTURE0, 0x84C0);
    /* Texture params */
    C(GL_TEXTURE_MIN_FILTER, 0x2801); C(GL_TEXTURE_MAG_FILTER, 0x2800);
    C(GL_TEXTURE_WRAP_S, 0x2802); C(GL_TEXTURE_WRAP_T, 0x2803);
    C(GL_NEAREST, 0x2600); C(GL_LINEAR, 0x2601);
    C(GL_NEAREST_MIPMAP_NEAREST, 0x2700); C(GL_LINEAR_MIPMAP_NEAREST, 0x2701);
    C(GL_NEAREST_MIPMAP_LINEAR, 0x2702); C(GL_LINEAR_MIPMAP_LINEAR, 0x2703);
    C(GL_CLAMP_TO_EDGE, 0x812F); C(GL_REPEAT, 0x2901); C(GL_MIRRORED_REPEAT, 0x8370);
    /* Buffer targets */
    C(GL_ARRAY_BUFFER, 0x8892); C(GL_ELEMENT_ARRAY_BUFFER, 0x8893);
    C(GL_UNIFORM_BUFFER, 0x8A11);
    /* Buffer usage */
    C(GL_STATIC_DRAW, 0x88E4); C(GL_DYNAMIC_DRAW, 0x88E8); C(GL_STREAM_DRAW, 0x88E0);
    /* Shader types */
    C(GL_VERTEX_SHADER, 0x8B31); C(GL_FRAGMENT_SHADER, 0x8B30);
    /* Shader params */
    C(GL_COMPILE_STATUS, 0x8B81); C(GL_LINK_STATUS, 0x8B82);
    C(GL_INFO_LOG_LENGTH, 0x8B84); C(GL_VALIDATE_STATUS, 0x8B83);
    /* FBO */
    C(GL_FRAMEBUFFER, 0x8D40); C(GL_RENDERBUFFER, 0x8D41);
    C(GL_COLOR_ATTACHMENT0, 0x8CE0); C(GL_DEPTH_ATTACHMENT, 0x8D00);
    C(GL_STENCIL_ATTACHMENT, 0x8D20); C(GL_DEPTH_STENCIL_ATTACHMENT, 0x821A);
    C(GL_FRAMEBUFFER_COMPLETE, 0x8CD5);
    /* The unsized base format, needed as glTexImage2D's `format` argument
     * when allocating a depth texture. Its absence is what pushed the
     * moderngl shim into passing GL_DEPTH_BUFFER_BIT there -- a clear-mask
     * bit, not a pixel format -- which left shadow maps unreadable and the
     * whole scene shadowed. */
    C(GL_DEPTH_COMPONENT, 0x1902);
    /* Depth comparison, required by sampler2DShadow. A depth texture sampled
     * through a shadow sampler with comparison left off returns 0 for every
     * lookup in GLES3, which reads as "fully shadowed" and turns a lit scene
     * uniformly black. */
    C(GL_TEXTURE_COMPARE_MODE, 0x884C); C(GL_TEXTURE_COMPARE_FUNC, 0x884D);
    C(GL_COMPARE_REF_TO_TEXTURE, 0x884E); C(GL_NONE, 0);
    C(GL_DEPTH_COMPONENT16, 0x81A5); C(GL_DEPTH_COMPONENT24, 0x81A6);
    C(GL_DEPTH24_STENCIL8, 0x88F0);
    C(GL_DEPTH_STENCIL, 0x84F9); C(GL_UNSIGNED_INT_24_8, 0x84FA);
    /* GetString */
    C(GL_VENDOR, 0x1F00); C(GL_RENDERER, 0x1F01); C(GL_VERSION, 0x1F02);
    C(GL_SHADING_LANGUAGE_VERSION, 0x8B8C); C(GL_EXTENSIONS, 0x1F03);
    /* Bool */
    C(GL_TRUE, 1); C(GL_FALSE, 0);
    /* Desktop GL compat (not in GLES3 but used by three.py) */
    C(GL_FILL, 0x1B02); C(GL_LINE, 0x1B01); C(GL_POINT, 0x1B00);
    C(GL_FRONT_AND_BACK, 0x0408);
    /* Internal formats */
    C(GL_RGBA8, 0x8058); C(GL_RGB8, 0x8051);
    C(GL_R8, 0x8229); C(GL_RG8, 0x822B);
#undef C
    return 0;
}

/* ── Module definition ───────────────────────────────────────────── */

static struct PyModuleDef opengl_module_def = {
    PyModuleDef_HEAD_INIT, "_opengl_gl",
    "OpenGL ES 3.0 bindings backed by wasmcart GL ABI", -1, opengl_methods
};

PyMODINIT_FUNC PyInit__opengl_gl(void) {
    PyObject *m = PyModule_Create(&opengl_module_def);
    if (m) add_gl_constants(m);
    return m;
}
