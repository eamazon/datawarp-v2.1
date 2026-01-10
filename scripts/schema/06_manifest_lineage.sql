-- Manifest Lineage Tracking
-- Auto-discover reference manifests and track enrichment lineage across periods
-- Enables bulletproof tracking and agentic discovery

CREATE TABLE IF NOT EXISTS datawarp.tbl_manifest_lineage (
    id SERIAL PRIMARY KEY,

    -- Identification
    publication VARCHAR(100) NOT NULL,  -- e.g., "gp_practice", "adhd", "workforce"
    period VARCHAR(20) NOT NULL,         -- e.g., "mar25", "2025-03", "2025-Q1"
    manifest_path VARCHAR(500) NOT NULL, -- Full path to manifest file

    -- Lineage
    reference_manifest_path VARCHAR(500), -- What it was enriched from (NULL for first period)
    reference_period VARCHAR(20),          -- Period of reference manifest

    -- Enrichment metadata
    enriched_at TIMESTAMP DEFAULT NOW(),
    source_count INTEGER,                  -- Total sources in manifest
    llm_calls_made INTEGER DEFAULT 0,      -- How many sources enriched by LLM
    reference_matches INTEGER DEFAULT 0,    -- How many matched reference deterministically

    -- Observability
    enrichment_run_id UUID,                -- Links to tbl_enrichment_runs
    created_by VARCHAR(100),               -- User/agent who created this

    UNIQUE(publication, period)
);

-- Indexes for auto-discovery queries
CREATE INDEX IF NOT EXISTS idx_lineage_publication ON datawarp.tbl_manifest_lineage(publication);
CREATE INDEX IF NOT EXISTS idx_lineage_pub_period ON datawarp.tbl_manifest_lineage(publication, period DESC);
CREATE INDEX IF NOT EXISTS idx_lineage_enriched_at ON datawarp.tbl_manifest_lineage(enriched_at DESC);

-- Comments
COMMENT ON TABLE datawarp.tbl_manifest_lineage IS 'Tracks enrichment lineage across periods for auto-discovery';
COMMENT ON COLUMN datawarp.tbl_manifest_lineage.publication IS 'Publication name extracted from URL or manifest name';
COMMENT ON COLUMN datawarp.tbl_manifest_lineage.reference_manifest_path IS 'Most recent manifest used as reference (enables chaining)';
COMMENT ON COLUMN datawarp.tbl_manifest_lineage.llm_calls_made IS 'Sources enriched by LLM (excludes reference matches)';

-- Query helper: Get most recent manifest for a publication
-- Usage: SELECT * FROM datawarp.get_most_recent_manifest('gp_practice');
CREATE OR REPLACE FUNCTION datawarp.get_most_recent_manifest(pub_name VARCHAR)
RETURNS TABLE (
    manifest_path VARCHAR,
    period VARCHAR,
    enriched_at TIMESTAMP,
    source_count INTEGER
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        ml.manifest_path,
        ml.period,
        ml.enriched_at,
        ml.source_count
    FROM datawarp.tbl_manifest_lineage ml
    WHERE ml.publication = pub_name
    ORDER BY ml.enriched_at DESC
    LIMIT 1;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION datawarp.get_most_recent_manifest IS 'Helper for auto-discovering most recent reference manifest';

-- Manifest lineage tracking created successfully
