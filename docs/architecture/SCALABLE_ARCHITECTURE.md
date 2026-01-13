# Scalable Architecture - PostgreSQL as Source of Truth

**Created:** 2026-01-13
**Scale Target:** 1000+ sources, 100+ publications

---

## Core Principle

> **PostgreSQL IS the source of truth. Everything else is derived.**

```
┌─────────────────────────────────────────────────────────────────┐
│                      PostgreSQL                                  │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ datawarp.tbl_data_sources      (dataset registry)          │ │
│  │ datawarp.tbl_load_events       (audit trail)               │ │
│  │ staging.tbl_*                  (actual data - 1000+ tables)│ │
│  └────────────────────────────────────────────────────────────┘ │
│                           │                                      │
│              ┌────────────┼────────────┐                        │
│              ▼            ▼            ▼                        │
│         ┌────────┐  ┌────────┐  ┌────────────┐                 │
│         │  MCP   │  │ Export │  │   Backfill │                 │
│         │ Server │  │ Script │  │   Script   │                 │
│         └────────┘  └────────┘  └────────────┘                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## What This Means

### NO catalog.parquet
- Dataset discovery queries `datawarp.tbl_data_sources` directly
- MCP `list_datasets` = `SELECT * FROM datawarp.tbl_data_sources`

### NO per-source parquet files (for queries)
- MCP `query` = `SELECT * FROM staging.tbl_adhd_summary WHERE ...`
- Parquet export only for Cloudflare upload (separate workflow)

### NO per-period manifest files
- Single config per publication: `config/publications.yaml`
- Schema stored in database (column metadata in registry)

---

## Database Schema (Enhanced)

```sql
-- Dataset Registry (replaces catalog.parquet)
CREATE TABLE datawarp.tbl_data_sources (
    id SERIAL PRIMARY KEY,
    code VARCHAR(100) UNIQUE NOT NULL,       -- adhd_summary_open_referrals
    name VARCHAR(255),                        -- ADHD Summary - Open Referrals
    publication VARCHAR(100),                 -- adhd
    table_name VARCHAR(100) NOT NULL,        -- tbl_adhd_summary_open_referrals
    schema_name VARCHAR(50) DEFAULT 'staging',

    -- Metadata for discovery
    description TEXT,
    domain VARCHAR(50),                       -- mental_health, primary_care
    frequency VARCHAR(20),                    -- monthly, quarterly

    -- Stats (updated on each load)
    row_count INTEGER DEFAULT 0,
    column_count INTEGER DEFAULT 0,
    last_load_at TIMESTAMP,
    first_period VARCHAR(20),
    last_period VARCHAR(20),

    -- Schema info (JSON for flexibility)
    columns JSONB,  -- [{name, type, description}, ...]

    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Load Audit Trail
CREATE TABLE datawarp.tbl_load_events (
    id SERIAL PRIMARY KEY,
    source_code VARCHAR(100) NOT NULL,
    period VARCHAR(20),
    url TEXT,
    rows_loaded INTEGER,
    columns_added TEXT[],
    status VARCHAR(20),  -- success, failed, partial
    error_message TEXT,
    duration_ms INTEGER,
    loaded_at TIMESTAMP DEFAULT NOW()
);

-- Indexes for fast queries
CREATE INDEX idx_sources_publication ON datawarp.tbl_data_sources(publication);
CREATE INDEX idx_sources_domain ON datawarp.tbl_data_sources(domain);
CREATE INDEX idx_load_events_source ON datawarp.tbl_load_events(source_code);
CREATE INDEX idx_load_events_period ON datawarp.tbl_load_events(period);
```

---

## MCP Server (PostgreSQL-Native)

```python
# mcp_server/server.py - Key changes

def list_datasets(domain: str = None, publication: str = None) -> List[Dict]:
    """List datasets from PostgreSQL registry."""
    with get_connection() as conn:
        cur = conn.cursor()

        query = """
        SELECT code, name, publication, domain, row_count,
               last_load_at, first_period, last_period, description
        FROM datawarp.tbl_data_sources
        WHERE 1=1
        """
        params = []

        if domain:
            query += " AND domain = %s"
            params.append(domain)
        if publication:
            query += " AND publication = %s"
            params.append(publication)

        query += " ORDER BY publication, code"

        cur.execute(query, params)
        return [dict(zip([d[0] for d in cur.description], row))
                for row in cur.fetchall()]


def query_dataset(source_code: str, sql: str = None, limit: int = 1000) -> Dict:
    """Query dataset directly from PostgreSQL."""
    with get_connection() as conn:
        # Get table info from registry
        cur = conn.cursor()
        cur.execute("""
            SELECT schema_name, table_name, columns
            FROM datawarp.tbl_data_sources
            WHERE code = %s
        """, (source_code,))
        row = cur.fetchone()

        if not row:
            raise ValueError(f"Dataset not found: {source_code}")

        schema, table, columns = row
        full_table = f"{schema}.{table}"

        if sql:
            # User-provided SQL (with safety checks)
            safe_sql = validate_sql(sql, full_table)
            cur.execute(safe_sql)
        else:
            # Default: SELECT * with limit
            cur.execute(f"SELECT * FROM {full_table} LIMIT %s", (limit,))

        results = cur.fetchall()
        col_names = [d[0] for d in cur.description]

        return {
            "columns": col_names,
            "rows": [dict(zip(col_names, row)) for row in results],
            "row_count": len(results),
            "total_rows": get_table_count(conn, full_table)
        }
```

---

## File Organization (Minimal)

```
datawarp-v2.1/
├── config/
│   └── publications.yaml        # Publication definitions ONLY
│
├── data/                        # Runtime data (NOT in git)
│   ├── logs/                    # Event logs (7-day retention)
│   └── exports/                 # Parquet exports (for Cloudflare only)
│
├── docker/
│   ├── Dockerfile
│   └── docker-compose.yml
│
└── scripts/
    ├── backfill.py              # Main ingestion
    ├── export_to_cloudflare.py  # Export parquet → R2
    └── analyze_logs.py          # Operational tools
```

**That's it.** No manifest files in git. No parquet files for queries.

---

## Workflow at Scale

### 1. Add New Publication
```yaml
# config/publications.yaml
publications:
  new_publication:
    name: "New NHS Publication"
    domain: mental_health
    frequency: monthly
    landing_page: https://digital.nhs.uk/...
    urls:
      - period: jan26
        url: https://...
```

### 2. Run Backfill
```bash
docker-compose exec datawarp python scripts/backfill.py --pub new_publication
```

This:
- Downloads Excel from URL
- Extracts structure (FileExtractor)
- Creates/updates table in PostgreSQL
- Registers source in `tbl_data_sources`
- Logs event to `tbl_load_events`

### 3. Query via MCP
```
Agent: "List mental health datasets"
MCP: SELECT * FROM datawarp.tbl_data_sources WHERE domain = 'mental_health'

Agent: "Show ADHD referrals by age"
MCP: SELECT * FROM staging.tbl_adhd_summary_open_referrals_age LIMIT 100
```

### 4. Export for Cloudflare (Separate Workflow)
```bash
# Weekly/monthly export for public API
docker-compose exec datawarp python scripts/export_to_cloudflare.py
```

---

## Scale Characteristics

| Metric | Current | Scalable |
|--------|---------|----------|
| Manifest files | 480/year | 0 (config only) |
| Parquet files | 1000+ | Optional exports |
| Database tables | 1000+ | 1000+ (same) |
| MCP query speed | Read parquet | Direct SQL |
| Discovery | Scan files | Index query |

---

## Implementation Changes

### High Priority
1. **Update MCP server** to query PostgreSQL directly
2. **Enhance tbl_data_sources** with metadata columns
3. **Update backfill.py** to register sources properly

### Medium Priority
4. **Remove catalog.parquet** dependency
5. **Add domain/publication tagging** on load
6. **Create export_to_cloudflare.py** for external sharing

### Low Priority
7. **Add column-level metadata** to registry
8. **Add search/filter endpoints** to MCP
9. **Add SQL validation** for user queries

---

## Migration Path

### Step 1: Enhance Registry Table
```sql
-- Add missing columns
ALTER TABLE datawarp.tbl_data_sources
ADD COLUMN IF NOT EXISTS publication VARCHAR(100),
ADD COLUMN IF NOT EXISTS domain VARCHAR(50),
ADD COLUMN IF NOT EXISTS description TEXT,
ADD COLUMN IF NOT EXISTS columns JSONB;

-- Update existing sources
UPDATE datawarp.tbl_data_sources
SET publication = SPLIT_PART(code, '_', 1),
    domain = CASE
        WHEN code LIKE 'adhd%' THEN 'mental_health'
        WHEN code LIKE 'gp%' THEN 'primary_care'
        WHEN code LIKE 'pcn%' THEN 'workforce'
        ELSE 'other'
    END;
```

### Step 2: Update MCP Server
Replace parquet reads with PostgreSQL queries (keep backward compatibility).

### Step 3: Test at Scale
Load 100+ sources, verify MCP queries work.

### Step 4: Remove Parquet Dependencies
Once PostgreSQL queries work, remove catalog.parquet requirement.

---

## Summary

**Before:** Files everywhere (manifests, parquet, catalog)
**After:** PostgreSQL + config + logs

**MCP Before:** Load parquet → query pandas
**MCP After:** Query PostgreSQL directly

**Scale:** 1000+ sources with minimal file overhead

---

**Ready to implement?**
