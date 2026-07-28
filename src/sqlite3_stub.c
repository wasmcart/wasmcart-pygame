/*
 * sqlite3_stub.c — resolve CPython's _sqlite3 module without an sqlite3 build.
 *
 * The emscripten CPython build compiles Modules/_sqlite/*.o into
 * libpython3.13.a but does not build or link libsqlite3, so every sqlite3_*
 * symbol is left undefined. A cart never imports sqlite3 (there is no
 * database to open), but the objects are in the archive, so the linker still
 * demands the symbols.
 *
 * These stubs abort if ever called, which cannot happen: importing sqlite3
 * fails at the module level first. Previously ERROR_ON_UNDEFINED_SYMBOLS=0
 * hid all of this by turning them into imports.
 */
extern void abort(void);

void sqlite3_aggregate_context(void) { abort(); }
void sqlite3_backup_finish(void) { abort(); }
void sqlite3_backup_init(void) { abort(); }
void sqlite3_backup_pagecount(void) { abort(); }
void sqlite3_backup_remaining(void) { abort(); }
void sqlite3_backup_step(void) { abort(); }
void sqlite3_bind_blob(void) { abort(); }
void sqlite3_bind_double(void) { abort(); }
void sqlite3_bind_int64(void) { abort(); }
void sqlite3_bind_null(void) { abort(); }
void sqlite3_bind_parameter_count(void) { abort(); }
void sqlite3_bind_parameter_name(void) { abort(); }
void sqlite3_bind_text(void) { abort(); }
void sqlite3_blob_bytes(void) { abort(); }
void sqlite3_blob_close(void) { abort(); }
void sqlite3_blob_open(void) { abort(); }
void sqlite3_blob_read(void) { abort(); }
void sqlite3_blob_write(void) { abort(); }
void sqlite3_busy_timeout(void) { abort(); }
void sqlite3_changes(void) { abort(); }
void sqlite3_close(void) { abort(); }
void sqlite3_close_v2(void) { abort(); }
void sqlite3_column_blob(void) { abort(); }
void sqlite3_column_bytes(void) { abort(); }
void sqlite3_column_count(void) { abort(); }
void sqlite3_column_decltype(void) { abort(); }
void sqlite3_column_double(void) { abort(); }
void sqlite3_column_int64(void) { abort(); }
void sqlite3_column_name(void) { abort(); }
void sqlite3_column_text(void) { abort(); }
void sqlite3_column_type(void) { abort(); }
void sqlite3_complete(void) { abort(); }
void sqlite3_context_db_handle(void) { abort(); }
void sqlite3_create_collation_v2(void) { abort(); }
void sqlite3_create_function_v2(void) { abort(); }
void sqlite3_create_window_function(void) { abort(); }
void sqlite3_data_count(void) { abort(); }
void sqlite3_db_config(void) { abort(); }
void sqlite3_db_handle(void) { abort(); }
void sqlite3_deserialize(void) { abort(); }
void sqlite3_errcode(void) { abort(); }
void sqlite3_errmsg(void) { abort(); }
void sqlite3_errstr(void) { abort(); }
void sqlite3_exec(void) { abort(); }
void sqlite3_expanded_sql(void) { abort(); }
void sqlite3_extended_errcode(void) { abort(); }
void sqlite3_finalize(void) { abort(); }
void sqlite3_free(void) { abort(); }
void sqlite3_get_autocommit(void) { abort(); }
void sqlite3_initialize(void) { abort(); }
void sqlite3_interrupt(void) { abort(); }
void sqlite3_last_insert_rowid(void) { abort(); }
void sqlite3_libversion(void) { abort(); }
void sqlite3_libversion_number(void) { abort(); }
void sqlite3_limit(void) { abort(); }
void sqlite3_malloc64(void) { abort(); }
void sqlite3_open_v2(void) { abort(); }
void sqlite3_prepare_v2(void) { abort(); }
void sqlite3_progress_handler(void) { abort(); }
void sqlite3_reset(void) { abort(); }
void sqlite3_result_blob(void) { abort(); }
void sqlite3_result_double(void) { abort(); }
void sqlite3_result_error(void) { abort(); }
void sqlite3_result_error_nomem(void) { abort(); }
void sqlite3_result_error_toobig(void) { abort(); }
void sqlite3_result_int64(void) { abort(); }
void sqlite3_result_null(void) { abort(); }
void sqlite3_result_text(void) { abort(); }
void sqlite3_serialize(void) { abort(); }
void sqlite3_set_authorizer(void) { abort(); }
void sqlite3_shutdown(void) { abort(); }
void sqlite3_sleep(void) { abort(); }
void sqlite3_step(void) { abort(); }
void sqlite3_stmt_busy(void) { abort(); }
void sqlite3_stmt_readonly(void) { abort(); }
void sqlite3_stricmp(void) { abort(); }
void sqlite3_threadsafe(void) { abort(); }
void sqlite3_total_changes(void) { abort(); }
void sqlite3_trace_v2(void) { abort(); }
void sqlite3_user_data(void) { abort(); }
void sqlite3_value_blob(void) { abort(); }
void sqlite3_value_bytes(void) { abort(); }
void sqlite3_value_double(void) { abort(); }
void sqlite3_value_int64(void) { abort(); }
void sqlite3_value_text(void) { abort(); }
void sqlite3_value_type(void) { abort(); }
