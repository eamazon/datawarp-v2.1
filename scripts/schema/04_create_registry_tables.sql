-- Phase 1: Canonical source registry tables
-- Tracks unique source identifiers across time periods

-- Canonical source registry
CREATE TABLE IF NOT EXISTS datawarp.tbl_canonical_sources (
  -- Primary key
  canonical_code VARCHAR(100) PRIMARY KEY,

  -- Relationships
  publication_id VARCHAR(50),

  -- Descriptive
  canonical_name TEXT NOT NULL,
  canonical_table VARCHAR(100) NOT NULL,

  -- Structural fingerprint for matching
  fingerprint JSONB NOT NULL,

  -- Period tracking
  first_seen_period VARCHAR(20),
  last_seen_period VARCHAR(20),

  -- Statistics
  total_loads INTEGER DEFAULT 0,
  total_rows_loaded BIGINT DEFAULT 0,

  -- Audit
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_canonical_publication
  ON datawarp.tbl_canonical_sources(publication_id);

CREATE INDEX IF NOT EXISTS idx_canonical_fingerprint
  ON datawarp.tbl_canonical_sources USING gin(fingerprint);

-- Comments
COMMENT ON TABLE datawarp.tbl_canonical_sources IS
  'Registry of canonical source codes for cross-period data consolidation';

COMMENT ON COLUMN datawarp.tbl_canonical_sources.fingerprint IS
  'JSONB structure: {column_names: [...], signature_hash: "md5..."}';

-- Source mapping history
CREATE TABLE IF NOT EXISTS datawarp.tbl_source_mappings (
  id SERIAL PRIMARY KEY,

  -- What the LLM generated
  llm_generated_code VARCHAR(100) NOT NULL,
  period VARCHAR(20),

  -- What it was mapped to
  canonical_code VARCHAR(100) REFERENCES datawarp.tbl_canonical_sources(canonical_code),

  -- Match quality
  match_confidence FLOAT NOT NULL,  -- 0.0 to 1.0
  match_method VARCHAR(50) NOT NULL,  -- 'exact', 'fingerprint', 'manual'

  -- Fingerprint at time of match
  source_fingerprint JSONB,

  -- Audit
  mapped_at TIMESTAMP DEFAULT NOW(),
  mapped_by VARCHAR(50) DEFAULT 'system',
  reviewed BOOLEAN DEFAULT FALSE,
  review_notes TEXT,

  UNIQUE(llm_generated_code, period)
);

CREATE INDEX IF NOT EXISTS idx_mapping_canonical
  ON datawarp.tbl_source_mappings(canonical_code);

CREATE INDEX IF NOT EXISTS idx_mapping_period
  ON datawarp.tbl_source_mappings(period);

CREATE INDEX IF NOT EXISTS idx_mapping_confidence
  ON datawarp.tbl_source_mappings(match_confidence);

COMMENT ON TABLE datawarp.tbl_source_mappings IS
  'Tracks mapping from LLM-generated codes to canonical codes';

-- Drift event log
CREATE TABLE IF NOT EXISTS datawarp.tbl_drift_events (
  id SERIAL PRIMARY KEY,
  canonical_code VARCHAR(100),
  period VARCHAR(20),

  drift_type VARCHAR(50) NOT NULL,  -- 'new_columns', 'missing_columns', 'type_change', 'wide_date_detected'
  severity VARCHAR(20) NOT NULL,     -- 'info', 'warning', 'error'

  details JSONB NOT NULL,

  -- Actions taken
  auto_resolved BOOLEAN DEFAULT FALSE,
  resolution_action TEXT,

  detected_at TIMESTAMP DEFAULT NOW(),
  notified BOOLEAN DEFAULT FALSE
);

CREATE INDEX IF NOT EXISTS idx_drift_code
  ON datawarp.tbl_drift_events(canonical_code);

CREATE INDEX IF NOT EXISTS idx_drift_severity
  ON datawarp.tbl_drift_events(severity);

CREATE INDEX IF NOT EXISTS idx_drift_notified
  ON datawarp.tbl_drift_events(notified) WHERE NOT notified;

COMMENT ON TABLE datawarp.tbl_drift_events IS
  'Logs schema drift events for monitoring and alerting';
