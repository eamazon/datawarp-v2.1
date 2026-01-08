-- DataWarp v2 Index Creation
-- Run: psql -d datawarp -f 03_create_indexes.sql

-- Indexes on tbl_data_sources
CREATE INDEX IF NOT EXISTS idx_data_sources_code 
    ON datawarp.tbl_data_sources(code);
CREATE INDEX IF NOT EXISTS idx_data_sources_last_load 
    ON datawarp.tbl_data_sources(last_load_at DESC);

-- Indexes on tbl_load_history
CREATE INDEX IF NOT EXISTS idx_load_history_source 
    ON datawarp.tbl_load_history(source_id);
CREATE INDEX IF NOT EXISTS idx_load_history_loaded_at 
    ON datawarp.tbl_load_history(loaded_at DESC);
CREATE INDEX IF NOT EXISTS idx_load_history_source_loaded 
    ON datawarp.tbl_load_history(source_id, loaded_at DESC);

\echo 'Indexes created successfully'