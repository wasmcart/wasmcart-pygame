/*
 * pystubs.c — Stubs for CPython Emscripten-specific imports
 *
 * CPython's emscripten build references these functions which are normally
 * provided by Emscripten's JS glue. In STANDALONE_WASM mode we need C stubs.
 */

#include <stdint.h>
#include <stddef.h>

/* CPython emscripten signal handling — no-op in wasmcart */
int _Py_emscripten_runtime(void) {
    return 0;  /* 0 = not in browser */
}

int _Py_CheckEmscriptenSignals_Helper(void) {
    return 0;
}

/* Network stubs — not available in wasmcart sandbox */
void *getprotobyname(const char *name) {
    return NULL;
}

int getaddrinfo(const char *node, const char *service,
                const void *hints, void **res) {
    return -1;  /* EAI_FAIL */
}

int getnameinfo(const void *sa, unsigned int salen,
                char *host, unsigned int hostlen,
                char *serv, unsigned int servlen,
                int flags) {
    return -1;
}

void freeaddrinfo(void *res) {}

/* Emscripten memory growth notification */
void emscripten_notify_memory_growth(int idx) {
    (void)idx;
}

/* System call — no shell in sandbox */
int _emscripten_system(const char *cmd) {
    return -1;
}

/* DNS lookup */
int _emscripten_lookup_name(const char *name) {
    return 0;
}

/* mmap sync */
int _msync_js(int addr, int len, int prot, int flags, int fd, int64_t offset) {
    return 0;
}

/* Syscall stubs that CPython's posixmodule needs.
 * CartHost already stubs these via JS, but if the linker resolves them
 * at compile time we need C definitions too. */
int __syscall_faccessat(int dirfd, const char *path, int mode, int flags) { return -1; }
int __syscall_chdir(const char *path) { return -1; }
int __syscall_chmod(const char *path, int mode) { return -1; }
int __syscall_fchownat(int dirfd, const char *path, int owner, int group, int flags) { return -1; }
int __syscall_dup3(int oldfd, int newfd, int flags) { return -1; }
int __syscall_fchdir(int fd) { return -1; }
int __syscall_fchmod(int fd, int mode) { return -1; }
int __syscall_fchmodat2(int dirfd, const char *path, int mode, int flags) { return -1; }
int __syscall_fchown32(int fd, int owner, int group) { return -1; }
int __syscall_fdatasync(int fd) { return -1; }
int __syscall_ftruncate64(int fd, int64_t length) { return -1; }
int __syscall_getcwd(char *buf, int size) {
    /* Return "/" as current directory */
    if (buf && size >= 2) {
        buf[0] = '/';
        buf[1] = '\0';
        return 2;
    }
    return -1;
}
int __syscall_pipe(int *fds) { return -1; }
int __syscall_poll(void *fds, int nfds, int timeout) { return -1; }
int __syscall_fadvise64(int fd, int64_t offset, int64_t len, int advice) { return 0; }
int __syscall_fallocate(int fd, int mode, int64_t offset, int64_t len) { return -1; }
int __syscall_getdents64(int fd, void *buf, int count) { return -1; }
int __syscall_readlinkat(int dirfd, const char *path, char *buf, int bufsiz) { return -1; }
int __syscall_renameat(int olddirfd, const char *oldpath, int newdirfd, const char *newpath) { return -1; }
int __syscall_rmdir(const char *path) { return -1; }
int __syscall_statfs64(const char *path, int size) { return -1; }
int __syscall_fstatfs64(int fd, int size) { return -1; }
int __syscall_symlinkat(const char *target, int newdirfd, const char *linkpath) { return -1; }
int __syscall_truncate64(const char *path, int64_t length) { return -1; }
int __syscall_unlinkat(int dirfd, const char *path, int flags) { return -1; }
int __syscall_utimensat(int dirfd, const char *path, const void *times, int flags) { return -1; }

/* Socket syscalls — not available */
int __syscall_accept4(int fd, void *addr, void *addrlen, int flags, int a5, int a6) { return -1; }
int __syscall_bind(int fd, const void *addr, int addrlen, int a4, int a5, int a6) { return -1; }
int __syscall_connect(int fd, const void *addr, int addrlen, int a4, int a5, int a6) { return -1; }
int __syscall_getpeername(int fd, void *addr, void *addrlen, int a4, int a5, int a6) { return -1; }
int __syscall_getsockname(int fd, void *addr, void *addrlen, int a4, int a5, int a6) { return -1; }
int __syscall_getsockopt(int fd, int level, int optname, void *optval, void *optlen, int a6) { return -1; }
int __syscall_listen(int fd, int backlog, int a3, int a4, int a5, int a6) { return -1; }
int __syscall_recvfrom(int fd, void *buf, int len, int flags, void *addr, void *addrlen) { return -1; }
int __syscall_recvmsg(int fd, void *msg, int flags, int a4, int a5, int a6) { return -1; }
int __syscall_sendmsg(int fd, const void *msg, int flags, int a4, int a5, int a6) { return -1; }
int __syscall_sendto(int fd, const void *buf, int len, int flags, const void *addr, int addrlen) { return -1; }
int __syscall_socket(int domain, int type, int protocol, int a4, int a5, int a6) { return -1; }
