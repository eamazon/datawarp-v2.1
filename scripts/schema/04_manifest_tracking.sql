-- Manifest File Tracking
-- Tracks batch loads from YAML manifests to ensure idempotency and detailed error logging

CREATE TABLE IF NOT EXISTS datawarp.tbl_manifest_files (
    id SERIAL PRIMARY KEY,
    manifest_name VARCHAR(100) NOT NULL,
    manifest_file_path VARCHAR(255),  -- Track which YAML file was used (e.g., manifests/output.yaml)
    source_code VARCHAR(100) NOT NULL,
    file_url VARCHAR(500) NOT NULL,
    period VARCHAR(10),
    status VARCHAR(20) NOT NULL,  -- pending, loaded, failed, skipped

    -- Rich error context for human/AI troubleshooting
    error_details JSONB,

    -- Success metadata
    rows_loaded INTEGER,
    columns_added JSONB,

    -- Timestamps
    loaded_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),

    -- Prevent duplicate tracking
    UNIQUE(manifest_name, file_url)
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_manifest_name ON datawarp.tbl_manifest_files(manifest_name);
CREATE INDEX IF NOT EXISTS idx_manifest_status ON datawarp.tbl_manifest_files(manifest_name, status);
CREATE INDEX IF NOT EXISTS idx_period ON datawarp.tbl_manifest_files(period);
CREATE INDEX IF NOT EXISTS idx_source_code ON datawarp.tbl_manifest_files(source_code);

-- Error queries support
CREATE INDEX IF NOT EXISTS idx_error_type ON datawarp.tbl_manifest_files USING gin(error_details);

-- Comments
COMMENT ON TABLE datawarp.tbl_manifest_files IS 'Tracks individual file loads from YAML manifests';
COMMENT ON COLUMN datawarp.tbl_manifest_files.manifest_file_path IS 'Path to the YAML manifest file (e.g., manifests/output.yaml)';
COMMENT ON COLUMN datawarp.tbl_manifest_files.error_details IS 'JSON structure with error_type, error_message, traceback, context for AI/human debugging';
COMMENT ON COLUMN datawarp.tbl_manifest_files.status IS 'pending: not yet loaded, loaded: success, failed: error occurred, skipped: already loaded';
