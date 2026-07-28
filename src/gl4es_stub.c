/*
 * gl4es_stub.c — satisfy the two gl4es symbols sdl2_wc's video backend
 * references unconditionally.
 *
 * SDL_wasmcart_video.c declares gl4es_bridge_set_size and
 * wc_gl4es_GetProcAddress extern and calls them behind runtime guards, so they
 * must RESOLVE even for a cart that never takes a gl4es path. They come from
 * gl4es itself, which only GL1.x ports link.
 *
 * pygame does not: it renders through SDL surfaces, and carts wanting GL use
 * the OpenGL ES 3.0 module directly. Without these stubs the link "succeeded"
 * only because -sERROR_ON_UNDEFINED_SYMBOLS=0 turned them into imports, and
 * pygame's display init then trapped on `unreachable` the moment SDL created
 * a window — a blank screen with no diagnostic.
 *
 * See wasmcart-sdl2/PORTING_GUIDE.md, "Link fails: undefined ...".
 */
void gl4es_bridge_set_size(int w, int h) { (void)w; (void)h; }
void *wc_gl4es_GetProcAddress(const char *p) { (void)p; return 0; }
