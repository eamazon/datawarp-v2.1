# SQL Coding Standards

**Version:** 1.0
**Based On:** ANSI SQL + Microsoft SQL Server Best Practices
**Last Updated:** 2026-01-07

---

## Core Principles

1. **ANSI SQL Compliant** - Use standard SQL where possible
2. **PostgreSQL Specific** - When needed, document why
3. **Readable** - Code is read more than written
4. **Consistent** - Follow these rules always
5. **Maintainable** - Future developers should understand

---

## Naming Conventions

### Tables

**Format:** `{schema}.tbl_{entity_name}`

```sql
-- ✅ GOOD
CREATE TABLE datawarp.tbl_canonical_sources (...);
CREATE TABLE staging.tbl_adhd_summary_waiting_age (...);

-- ❌ BAD
CREATE TABLE CanonicalSources (...);  -- No prefix, mixed case
CREATE TABLE tblSources (...);        -- No schema
CREATE TABLE sources (...);           -- No prefix
```

**Rules:**
- Always specify schema
- Always use `tbl_` prefix
- Lowercase with underscores (snake_case)
- Singular or plural based on content (be consistent)
- Descriptive names (no abbreviations unless obvious)

### Columns

**Format:** `{column_name}` (snake_case)

```sql
-- ✅ GOOD
canonical_code VARCHAR(100)
load_timestamp TIMESTAMP
match_confidence FLOAT

-- ❌ BAD
CanonicalCode VARCHAR(100)   -- Mixed case
loadTimestamp TIMESTAMP       -- camelCase
match_conf FLOAT              -- Unclear abbreviation
```

**Rules:**
- Lowercase with underscores
- No abbreviations (use `identifier` not `id`, unless very common like `id`)
- Descriptive (column purpose should be obvious)
- Avoid reserved words (don't use `user`, `order`, `group` as column names)

### Indexes

**Format:** `idx_{table}_{columns}`

```sql
-- ✅ GOOD
CREATE INDEX idx_canonical_publication
  ON datawarp.tbl_canonical_sources(publication_id);

CREATE INDEX idx_mapping_canonical_period
  ON datawarp.tbl_source_mappings(canonical_code, period);

-- ❌ BAD
CREATE INDEX index1 ON ...;           -- Not descriptive
CREATE INDEX CanonicalIdx ON ...;     -- Mixed case
```

### Primary Keys

**Format:** `pk_{table}`

```sql
-- ✅ GOOD
CONSTRAINT pk_canonical_sources PRIMARY KEY (canonical_code)

-- ❌ BAD
PRIMARY KEY (canonical_code)  -- Unnamed constraint
```

### Foreign Keys

**Format:** `fk_{table}_{referenced_table}`

```sql
-- ✅ GOOD
CONSTRAINT fk_mappings_canonical_sources
  FOREIGN KEY (canonical_code)
  REFERENCES datawarp.tbl_canonical_sources(canonical_code)

-- ❌ BAD
FOREIGN KEY (canonical_code) REFERENCES tbl_canonical_sources(canonical_code)  -- Unnamed
```

---

## Formatting

### Indentation

**Use 2 spaces** (not tabs)

```sql
-- ✅ GOOD
CREATE TABLE datawarp.tbl_load_events (
  id SERIAL PRIMARY KEY,
  source_code VARCHAR(100) NOT NULL,
  load_timestamp TIMESTAMP DEFAULT NOW(),
  rows_loaded INTEGER,
  status VARCHAR(20)
);

-- ❌ BAD
CREATE TABLE datawarp.tbl_load_events (
id SERIAL PRIMARY KEY,
    source_code VARCHAR(100) NOT NULL,  -- Inconsistent indentation
        load_timestamp TIMESTAMP DEFAULT NOW());
```

### Keywords

**UPPERCASE for SQL keywords**

```sql
-- ✅ GOOD
SELECT
  canonical_code,
  COUNT(*) as period_count
FROM datawarp.tbl_source_mappings
WHERE match_confidence > 0.80
GROUP BY canonical_code
ORDER BY period_count DESC;

-- ❌ BAD
select canonical_code, count(*) as period_count
from datawarp.tbl_source_mappings
where match_confidence > 0.80
group by canonical_code
order by period_count desc;
```

### Line Length

**Maximum 100 characters per line**

```sql
-- ✅ GOOD
SELECT
  canonical_code,
  COUNT(DISTINCT period) as period_count,
  MIN(period) as first_period,
  MAX(period) as last_period
FROM datawarp.tbl_source_mappings
GROUP BY canonical_code;

-- ❌ BAD
SELECT canonical_code, COUNT(DISTINCT period) as period_count, MIN(period) as first_period, MAX(period) as last_period FROM datawarp.tbl_source_mappings GROUP BY canonical_code;
```

### Commas

**Leading commas** (Microsoft style)

```sql
-- ✅ GOOD
SELECT
  canonical_code
  , match_confidence
  , period
FROM datawarp.tbl_source_mappings;

-- ❌ BAD
SELECT
  canonical_code,
  match_confidence,
  period
FROM datawarp.tbl_source_mappings;
```

**Rationale:** Makes adding/removing columns easier, clearer diffs.

---

## Data Types

### String Types

```sql
-- ✅ GOOD - Specify length
source_code VARCHAR(100)
description TEXT  -- For unlimited length
status VARCHAR(20)

-- ❌ BAD
source_code VARCHAR  -- No length (PostgreSQL allows, but bad practice)
description VARCHAR(MAX)  -- Use TEXT instead
```

### Numeric Types

```sql
-- ✅ GOOD
rows_loaded INTEGER
match_confidence FLOAT
total_rows_loaded BIGINT

-- ❌ BAD
rows_loaded INT  -- Use full name INTEGER
match_confidence REAL  -- Use FLOAT or NUMERIC
```

### Temporal Types

```sql
-- ✅ GOOD
created_at TIMESTAMP DEFAULT NOW()
load_date DATE

-- ❌ BAD
created_at DATETIME  -- Not ANSI SQL (use TIMESTAMP)
load_date VARCHAR(20)  -- Should be DATE type
```

### Boolean Types

```sql
-- ✅ GOOD
active BOOLEAN DEFAULT TRUE
notified BOOLEAN DEFAULT FALSE

-- ❌ BAD
active INT  -- 0/1, use BOOLEAN
notified VARCHAR(1)  -- 'Y'/'N', use BOOLEAN
```

---

## Table Design

### Primary Keys

**Every table MUST have a primary key**

```sql
-- ✅ GOOD
CREATE TABLE datawarp.tbl_load_events (
  id SERIAL PRIMARY KEY,
  ...
);

-- Or natural key
CREATE TABLE datawarp.tbl_canonical_sources (
  canonical_code VARCHAR(100) PRIMARY KEY,
  ...
);
```

### Timestamps

**Every table SHOULD have created_at and updated_at**

```sql
-- ✅ GOOD
CREATE TABLE datawarp.tbl_data_sources (
  ...
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
);

-- Trigger for updated_at
CREATE TRIGGER set_updated_at
  BEFORE UPDATE ON datawarp.tbl_data_sources
  FOR EACH ROW
  EXECUTE FUNCTION update_updated_at_column();
```

### NULL vs NOT NULL

**Be explicit**

```sql
-- ✅ GOOD
source_code VARCHAR(100) NOT NULL,
description TEXT,  -- NULL allowed (implicit)
active BOOLEAN NOT NULL DEFAULT TRUE

-- ❌ BAD
source_code VARCHAR(100),  -- Unclear if NULL allowed
```

### Defaults

**Specify defaults for non-nullable columns**

```sql
-- ✅ GOOD
active BOOLEAN NOT NULL DEFAULT TRUE,
created_at TIMESTAMP DEFAULT NOW(),
retry_count INTEGER DEFAULT 0

-- ❌ BAD
active BOOLEAN NOT NULL,  -- Should have default
```

---

## Query Standards

### SELECT Statements

**Always specify columns** (never SELECT *)

```sql
-- ✅ GOOD
SELECT
  source_code
  , source_name
  , table_name
FROM datawarp.tbl_data_sources;

-- ❌ BAD
SELECT * FROM datawarp.tbl_data_sources;
```

### JOIN Syntax

**Use explicit JOIN keywords**

```sql
-- ✅ GOOD
SELECT
  s.source_code
  , s.source_name
  , e.rows_loaded
FROM datawarp.tbl_data_sources s
INNER JOIN datawarp.tbl_load_events e
  ON s.source_code = e.source_code;

-- ❌ BAD
SELECT s.source_code, s.source_name, e.rows_loaded
FROM datawarp.tbl_data_sources s, datawarp.tbl_load_events e
WHERE s.source_code = e.source_code;  -- Old-style join
```

### Table Aliases

**Use meaningful aliases**

```sql
-- ✅ GOOD
FROM datawarp.tbl_canonical_sources cs
INNER JOIN datawarp.tbl_source_mappings sm
  ON cs.canonical_code = sm.canonical_code

-- ❌ BAD
FROM datawarp.tbl_canonical_sources a
INNER JOIN datawarp.tbl_source_mappings b ON a.canonical_code = b.canonical_code
```

### WHERE Clauses

**One condition per line for complex queries**

```sql
-- ✅ GOOD
WHERE
  status = 'failed'
  AND load_timestamp > NOW() - INTERVAL '7 days'
  AND source_code LIKE 'adhd%'

-- Simple queries can be single line
WHERE status = 'success'
```

### Aggregations

**Use meaningful column aliases**

```sql
-- ✅ GOOD
SELECT
  canonical_code
  , COUNT(DISTINCT period) as period_count
  , MIN(period) as first_period
  , MAX(period) as last_period
FROM datawarp.tbl_source_mappings
GROUP BY canonical_code;

-- ❌ BAD
SELECT
  canonical_code
  , COUNT(DISTINCT period)  -- No alias
  , MIN(period) as col1      -- Unclear alias
FROM ...;
```

---

## Comments

### Table Comments

```sql
-- ✅ GOOD
CREATE TABLE datawarp.tbl_canonical_sources (
  canonical_code VARCHAR(100) PRIMARY KEY,
  ...
);

COMMENT ON TABLE datawarp.tbl_canonical_sources IS
  'Registry of canonical source codes for cross-period data consolidation';

COMMENT ON COLUMN datawarp.tbl_canonical_sources.fingerprint IS
  'MD5 hash of sorted column names for structural matching';
```

### Inline Comments

```sql
-- ✅ GOOD
SELECT
  canonical_code
  , match_confidence
FROM datawarp.tbl_source_mappings
WHERE match_confidence < 0.80  -- Low confidence matches need review
ORDER BY match_confidence ASC;
```

---

## Transactions

### Always Use Transactions for Multiple Operations

```sql
-- ✅ GOOD
BEGIN;

INSERT INTO datawarp.tbl_canonical_sources (...) VALUES (...);
INSERT INTO datawarp.tbl_source_mappings (...) VALUES (...);
UPDATE datawarp.tbl_drift_events SET notified = TRUE WHERE ...;

COMMIT;

-- ❌ BAD
INSERT INTO datawarp.tbl_canonical_sources (...) VALUES (...);
INSERT INTO datawarp.tbl_source_mappings (...) VALUES (...);
-- No transaction - partial failure possible
```

### Error Handling

```sql
-- ✅ GOOD
BEGIN;

-- Operation that might fail
INSERT INTO ...;

EXCEPTION
  WHEN unique_violation THEN
    -- Log and rollback
    ROLLBACK;
    RAISE NOTICE 'Duplicate key detected';
END;
```

---

## Performance

### Indexes

**Create indexes for:**
- Foreign keys
- Frequently filtered columns (WHERE)
- Frequently joined columns
- Frequently sorted columns (ORDER BY)

```sql
-- ✅ GOOD
CREATE INDEX idx_load_events_source
  ON datawarp.tbl_load_events(source_code);

CREATE INDEX idx_load_events_timestamp
  ON datawarp.tbl_load_events(load_timestamp);
```

### Query Optimization

**Avoid:**
- SELECT * (retrieve only needed columns)
- OR in WHERE clause (use UNION if needed)
- Functions on indexed columns in WHERE clause

```sql
-- ❌ BAD
SELECT * FROM datawarp.tbl_load_events
WHERE UPPER(status) = 'FAILED';  -- Function prevents index use

-- ✅ GOOD
SELECT
  source_code
  , load_timestamp
  , status
FROM datawarp.tbl_load_events
WHERE status = 'failed';  -- Assumes lowercase storage
```

---

## Schema Files Organization

```
scripts/schema/
├── 01_create_schemas.sql       # CREATE SCHEMA statements
├── 02_create_tables.sql        # Core tables (tbl_data_sources, etc.)
├── 03_create_indexes.sql       # Indexes for core tables
├── 04_create_registry_tables.sql  # Phase 1 tables
├── 05_create_publication_tracking.sql  # Phase 2 tables
└── functions/
    └── update_updated_at.sql   # Shared functions
```

**Each file should:**
- Be idempotent (IF NOT EXISTS where supported)
- Include comments explaining purpose
- Be numbered for execution order

---

## Examples

### Full Table Creation (Good)

```sql
-- Phase 1: Canonical source registry
-- Tracks unique source identifiers across time periods

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
```

---

## Checklist for New SQL Files

- [ ] All keywords UPPERCASE
- [ ] All table/column names lowercase snake_case
- [ ] All tables have schema prefix
- [ ] All tables have primary key
- [ ] All tables have created_at/updated_at
- [ ] All constraints are named
- [ ] All indexes are named with idx_ prefix
- [ ] Leading commas in SELECT
- [ ] Comments for complex logic
- [ ] IF NOT EXISTS for idempotency
- [ ] Proper indentation (2 spaces)
- [ ] Line length <100 characters

---

**Enforcement:** Add SQL linting to pre-commit hook (future)
**Reference:** Point to this doc when reviewing SQL changes
**Updates:** Increment version number when standards change
