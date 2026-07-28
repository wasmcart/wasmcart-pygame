/* Fix PG_VERSION_TAG for wasmcart build — shell quoting breaks "" literal */
#ifdef PG_VERSION_TAG_EMPTY
#undef PG_VERSION_TAG
#define PG_VERSION_TAG ""
#endif
