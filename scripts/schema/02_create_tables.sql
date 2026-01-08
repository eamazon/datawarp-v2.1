-- DataWarp v2 Table Creation
-- Purpose: Create all DataWarp registry tables
-- Run: psql -d datawarp -f 02_create_tables.sql
-- DataWarp v2 Table Creation
-- Run: psql -d datawarp -f 02_create_tables.sql

-- Table 1: Data Sources Registry
CREATE TABLE IF NOT EXISTS datawarp.tbl_data_sources (
    id SERIAL PRIMARY KEY,
    code VARCHAR(100) UNIQUE NOT NULL,
    name VARCHAR(255),
    table_name VARCHAR(100) NOT NULL,
    schema_name VARCHAR(50) DEFAULT 'staging',
    default_sheet VARCHAR(100),
    created_at TIMESTAMP DEFAULT NOW(),
    last_load_at TIMESTAMP
);

COMMENT ON TABLE datawarp.tbl_data_sources IS 'Registry of configured data sources';
COMMENT ON COLUMN datawarp.tbl_data_sources.code IS 'Unique source identifier';

-- Table 2: Load History (Phase 4 Audit Trail)
CREATE TABLE IF NOT EXISTS datawarp.tbl_load_history (
    id SERIAL PRIMARY KEY,
    source_id INTEGER NOT NULL REFERENCES datawarp.tbl_data_sources(id),
    file_url VARCHAR(500) NOT NULL,
    rows_loaded INTEGER NOT NULL,
    columns_added TEXT[],
    load_mode VARCHAR(20) DEFAULT 'append',
    loaded_at TIMESTAMP DEFAULT NOW()
);

COMMENT ON TABLE datawarp.tbl_load_history IS 'Complete audit trail of all load operations';
COMMENT ON COLUMN datawarp.tbl_load_history.load_mode IS 'Load strategy: append or replace';
COMMENT ON COLUMN datawarp.tbl_load_history.columns_added IS 'Array of column names added during drift';

-- Table 3: Pipeline Log (Observability)
CREATE TABLE IF NOT EXISTS datawarp.tbl_pipeline_log (
    id SERIAL PRIMARY KEY,
    manifest_name VARCHAR(100),
    source_code VARCHAR(100),
    period VARCHAR(20),
    file_url VARCHAR(500),
    category VARCHAR(20) NOT NULL,  -- 'dq', 'perf', 'schema', 'op'
    event_type VARCHAR(50) NOT NULL,
    severity VARCHAR(20) DEFAULT 'info',  -- 'info', 'warning', 'error'
    message TEXT,
    metadata JSONB,
    duration_ms NUMERIC(10,2),
    user_name VARCHAR(50),
    command TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

COMMENT ON TABLE datawarp.tbl_pipeline_log IS 'Real-time pipeline events for observability and troubleshooting';
COMMENT ON COLUMN datawarp.tbl_pipeline_log.category IS 'Event category: dq (data quality), perf (performance), schema, op (operation)';
COMMENT ON COLUMN datawarp.tbl_pipeline_log.severity IS 'Event severity: info, warning, error';

-- Table 4: Manifest File Tracking (Batch Loading)
CREATE TABLE IF NOT EXISTS datawarp.tbl_manifest_files (
    id SERIAL PRIMARY KEY,
    manifest_name VARCHAR(100) NOT NULL,
    manifest_file_path VARCHAR(255),
    source_code VARCHAR(100) NOT NULL,
    file_url VARCHAR(500) NOT NULL,
    period VARCHAR(10),
    status VARCHAR(20) NOT NULL,
    error_details JSONB,
    rows_loaded INTEGER,
    columns_added JSONB,
    loaded_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(manifest_name, file_url)
);

COMMENT ON TABLE datawarp.tbl_manifest_files IS 'Tracks individual file loads from YAML manifests';
COMMENT ON COLUMN datawarp.tbl_manifest_files.manifest_file_path IS 'Path to the YAML manifest file (e.g., manifests/output.yaml)';
COMMENT ON COLUMN datawarp.tbl_manifest_files.error_details IS 'JSON structure with error_type, error_message, traceback, context';
COMMENT ON COLUMN datawarp.tbl_manifest_files.status IS 'pending, loaded, failed, or skipped';

-- ============================================================================
-- EXAMPLE STAGING TABLE SCHEMA (Reference for Production Deployment)
-- ============================================================================
-- Staging tables created dynamically by DataWarp when you run:
--   datawarp load-batch <manifest.yaml>
--
-- Schema structure:
--   - Business columns (dynamic, from source file)
--   - _load_id INTEGER           → tbl_load_history.id
--   - _loaded_at TIMESTAMP        → insertion time
--   - _period VARCHAR(20)         → time period (e.g., "2025-01")
--   - _manifest_file_id INTEGER   → tbl_manifest_files.id
-- ============================================================================

\echo 'Tables created successfully'