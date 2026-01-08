-- Enrichment Observability Tables
-- Track LLM API calls, costs, and lineage for manifest enrichment

-- Enrichment Run Tracking (Normalized)
CREATE TABLE IF NOT EXISTS datawarp.tbl_enrichment_runs (
    id SERIAL PRIMARY KEY,
    run_id UUID DEFAULT gen_random_uuid(),
    started_at TIMESTAMP DEFAULT NOW(),
    completed_at TIMESTAMP,
    
    -- Link to Manifest (normalized - avoid storing full paths)
    manifest_name VARCHAR(200) NOT NULL,  -- Links to tbl_manifest_files.manifest_name
    
    -- Processing Stats
    total_sources INTEGER,
    data_sources INTEGER,          -- Sent to LLM
    noise_sources INTEGER,          -- Auto-filtered
    reference_matched INTEGER,      -- Matched from reference (skipped LLM)
    total_columns_enriched INTEGER,
    
    -- Validation
    validation_status VARCHAR(20),
    validation_errors TEXT,
    
    -- Outcome
    status VARCHAR(20),             -- 'running', 'success', 'failed'
    error_message TEXT,
    
    -- Performance
    duration_ms INTEGER,
    total_api_calls INTEGER DEFAULT 0,
    total_input_tokens INTEGER DEFAULT 0,
    total_output_tokens INTEGER DEFAULT 0,
    total_cost NUMERIC(10,6) DEFAULT 0.00,
    
    -- Environment (for reproducibility)
    model_name VARCHAR(100),
    git_commit VARCHAR(40),
    
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_enrichment_runs_started ON datawarp.tbl_enrichment_runs(started_at DESC);
CREATE INDEX idx_enrichment_runs_run_id ON datawarp.tbl_enrichment_runs(run_id);
CREATE INDEX idx_enrichment_runs_manifest_name ON datawarp.tbl_enrichment_runs(manifest_name);
CREATE INDEX idx_enrichment_runs_status ON datawarp.tbl_enrichment_runs(status, started_at DESC);

-- API Call Metrics
CREATE TABLE IF NOT EXISTS datawarp.tbl_enrichment_api_calls (
    id SERIAL PRIMARY KEY,
    run_id UUID NOT NULL,
    call_timestamp TIMESTAMP DEFAULT NOW(),
    
    -- Request
    prompt TEXT,
    prompt_length INTEGER,
    prompt_hash VARCHAR(64),
    
    -- Response
    response_text TEXT,
    response_json JSONB,
    response_length INTEGER,
    
    -- Token Usage
    input_tokens INTEGER,
    output_tokens INTEGER,
    total_tokens INTEGER,
    
    -- Cost
    input_cost NUMERIC(10,6),
    output_cost NUMERIC(10,6),
    total_cost NUMERIC(10,6),
    
    -- Performance
    latency_ms INTEGER,
    
    -- Outcome
    status VARCHAR(20),
    error_message TEXT,
    parse_error TEXT,
    
    -- Model
    model_name VARCHAR(100),
    temperature NUMERIC(3,2),
    max_output_tokens INTEGER
);

CREATE INDEX idx_api_calls_run_id ON datawarp.tbl_enrichment_api_calls(run_id);
CREATE INDEX idx_api_calls_timestamp ON datawarp.tbl_enrichment_api_calls(call_timestamp DESC);
CREATE INDEX idx_api_calls_prompt_hash ON datawarp.tbl_enrichment_api_calls(prompt_hash);

-- Add enrichment lineage to manifest files
ALTER TABLE datawarp.tbl_manifest_files 
ADD COLUMN IF NOT EXISTS enrichment_run_id UUID;

CREATE INDEX IF NOT EXISTS idx_manifest_files_enrichment_run 
ON datawarp.tbl_manifest_files(enrichment_run_id);

-- LINEAGE VIEW: Complete traceability
CREATE OR REPLACE VIEW datawarp.v_enrichment_to_loads AS
SELECT 
    e.run_id as enrichment_run_id,
    e.manifest_name,
    e.started_at as enriched_at,
    e.total_cost as enrichment_cost,
    e.total_columns_enriched,
    
    m.id as manifest_file_id,
    m.source_code,
    m.file_url,
    m.period,
    m.status as load_status,
    m.rows_loaded,
    
    h.id as load_id,
    s.table_name,
    s.schema_name,
    h.loaded_at,
    h.load_mode
    
FROM datawarp.tbl_enrichment_runs e
LEFT JOIN datawarp.tbl_manifest_files m ON e.manifest_name = m.manifest_name
LEFT JOIN datawarp.tbl_data_sources s ON m.source_code = s.code
LEFT JOIN datawarp.tbl_load_history h ON s.id = h.source_id
WHERE e.status = 'success'
ORDER BY e.started_at DESC, m.id, h.id;

-- Cost Tracking View
CREATE OR REPLACE VIEW datawarp.v_enrichment_costs AS
SELECT
    DATE_TRUNC('day', started_at) as date,
    COUNT(*) as enrichment_runs,
    SUM(total_api_calls) as total_api_calls,
    SUM(total_input_tokens) as total_input_tokens,
    SUM(total_output_tokens) as total_output_tokens,
    SUM(total_cost) as total_cost,
    AVG(duration_ms) as avg_duration_ms,
    SUM(total_columns_enriched) as total_columns_enriched
FROM datawarp.tbl_enrichment_runs
WHERE status = 'success'
GROUP BY DATE_TRUNC('day', started_at)
ORDER BY date DESC;

-- Prompt Reuse View
CREATE OR REPLACE VIEW datawarp.v_prompt_reuse AS
SELECT
    prompt_hash,
    COUNT(*) as reuse_count,
    MIN(call_timestamp) as first_used,
    MAX(call_timestamp) as last_used,
    AVG(total_cost) as avg_cost,
    SUM(total_cost) as cumulative_cost
FROM datawarp.tbl_enrichment_api_calls
WHERE prompt_hash IS NOT NULL
GROUP BY prompt_hash
HAVING COUNT(*) > 1
ORDER BY reuse_count DESC;
