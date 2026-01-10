# DataWarp Production Database Management Framework

**Updated: 2026-01-10 17:00 UTC**

## Executive Summary

Production-grade database management framework for DataWarp v2.1, treating the database with production seriousness even in pre-live stage. Implements strict lifecycle rules, monitoring, cleanup procedures, and governance to prevent "junk accumulation" and ensure data quality.

---

## 🎯 Core Principles

### 1. **Every Load Has Purpose**
- No test loads in production database
- Every source must have metadata justification
- Clear owner and use case documented

### 2. **Immutable Audit Trail**
- Never delete load history
- Track every schema change
- Maintain lineage for all data

### 3. **Zero Tolerance for Drift Junk**
- Failed loads cleaned up immediately
- Orphaned tables archived, not left
- Schema changes reviewed, not auto-applied

### 4. **Observable Operations**
- Every load monitored and logged
- Failures trigger alerts
- Success metrics tracked

---

## 📋 Source Lifecycle Management

### Stage 1: Source Registration

**BEFORE any data can be loaded:**

```bash
# Register source with metadata
datawarp register SOURCE_CODE \
  --publication "ADHD Management Information" \
  --domain "Clinical - Mental Health" \
  --owner "your.email@nhs.uk" \
  --purpose "Track ADHD referral waiting times" \
  --retention-days 365 \
  --load-mode REPLACE \
  --validation-required true
```

**Required Metadata:**
- `source_code` - Unique identifier (lowercase, underscores)
- `publication` - NHS publication name
- `domain` - Clinical/Operational/Workforce/etc.
- `owner` - Email of data owner
- `purpose` - Why we're loading this (max 500 chars)
- `retention_days` - How long to keep data (default 365)
- `load_mode` - APPEND or REPLACE
- `validation_required` - Run post-load checks?

**Registry Entry Created:**
```sql
INSERT INTO datawarp.tbl_data_sources (
  source_code, publication, domain, owner, purpose,
  retention_days, load_mode, validation_required,
  status, created_at, created_by
) VALUES (...);
```

**Status Values:**
- `registered` - Initial state
- `active` - Loaded successfully at least once
- `deprecated` - No longer being loaded
- `archived` - Moved to archive schema

### Stage 2: Data Loading

**Load with Validation:**

```bash
# Load with automatic pre/post validation
datawarp load-batch manifest.yaml --validate

# What happens:
# 1. Pre-load validation (manifest structure, URLs reachable)
# 2. Data extraction and type inference
# 3. Schema evolution check (if needed)
# 4. Data load with transaction
# 5. Post-load validation (row counts, data quality)
# 6. Load event logged
# 7. Metrics updated
```

**Load Event Tracking:**
```sql
INSERT INTO datawarp.tbl_load_events (
  source_code, load_id, rows_loaded, columns_added,
  load_status, started_at, completed_at, error_message
) VALUES (...);
```

**Status Values:**
- `in_progress` - Load started
- `completed` - Success
- `failed` - Error occurred
- `rolled_back` - Transaction reverted

### Stage 3: Validation Gates

**Automatic Checks (on every load):**

1. **Row Count Sanity**
   - Alert if rows < 10 (likely extraction issue)
   - Alert if rows > 10M (performance concern)
   - Alert if 50%+ change from previous load

2. **Schema Drift Detection**
   - Log all column additions
   - Alert if >10 columns added in single load
   - Alert if column types change

3. **Data Quality**
   - Check for all-NULL columns (extraction bug)
   - Check for duplicate primary keys
   - Check date ranges (warn if dates in future/past 10 years)

4. **Metadata Completeness**
   - Warn if <50% columns have descriptions
   - Warn if search terms missing

**Validation Report:**
```
✓ Row count: 1,234 (within 10% of previous: 1,150)
✓ Schema: 12 columns (no changes)
✓ Data quality: No NULL columns, 0 duplicates
⚠ Metadata: 8/12 columns have descriptions (67%)
```

### Stage 4: Monitoring

**Key Metrics (dashboarded):**

- **Load Health:**
  - Success rate (last 7 days)
  - Average load duration
  - Failed loads by source

- **Data Freshness:**
  - Days since last load per source
  - Sources with stale data (>30 days)

- **Storage:**
  - Table sizes (top 20)
  - Row counts by source
  - Staging schema total size

- **Schema Evolution:**
  - Columns added (last 30 days)
  - Tables created (last 30 days)
  - Sources with high drift (>5 changes)

**Alert Thresholds:**
- 🔴 Critical: Load failed 3+ times in row
- 🟠 Warning: Load slower than 2x average
- 🟡 Info: New table created

### Stage 5: Deprecation & Archival

**When to Deprecate:**
- Publication no longer updated by NHS
- Source replaced by better version
- No queries against table in 90 days

**Deprecation Workflow:**

```bash
# 1. Mark as deprecated
datawarp deprecate SOURCE_CODE \
  --reason "Replaced by SOURCE_CODE_V2" \
  --archive-date "2026-02-01"

# 2. Grace period (30 days)
# - Status: deprecated
# - Still queryable
# - Warning shown on access

# 3. Archive (after grace period)
datawarp archive SOURCE_CODE

# What happens:
# - Table moved to `archive` schema
# - Renamed with timestamp: tbl_SOURCE_CODE_archived_20260201
# - Export to Parquet for long-term storage
# - Entry in registry marked `archived`
# - Load history preserved
```

**Archive Schema Structure:**
```
archive.tbl_SOURCE_CODE_archived_YYYYMMDD
archive.tbl_metadata_SOURCE_CODE_archived_YYYYMMDD
```

---

## 🧹 Database Hygiene Rules

### Rule 1: No Test Data in Production

**Problem:** Test loads pollute production database

**Solution:**
- Dedicated `staging_test` schema for experiments
- Test schema wiped weekly
- Never load to `staging` schema without registered source

**Enforcement:**
```python
# In loader/pipeline.py
if source_code not in registry:
    if not allow_test_load:
        raise ValueError(f"Source {source_code} not registered. Use --test flag for experiments.")
    target_schema = 'staging_test'
else:
    target_schema = 'staging'
```

### Rule 2: Failed Loads = Immediate Cleanup

**Problem:** Partial loads leave junk data

**Solution:**
- All loads wrapped in transaction
- On failure: ROLLBACK
- Log failure reason
- Notify owner

**Implementation:**
```python
try:
    with transaction():
        load_data()
        validate_data()
        log_success()
except Exception as e:
    # Transaction auto-rolled back
    log_failure(source_code, error=str(e))
    notify_owner(source_code, error=str(e))
    raise
```

### Rule 3: Orphaned Tables = Archive

**Problem:** Tables exist but not in registry

**Detection:**
```sql
-- Find orphaned tables
SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'staging'
  AND table_name NOT IN (
    SELECT table_name FROM datawarp.tbl_data_sources
  );
```

**Action:**
1. Alert DBAs
2. Investigate ownership
3. Either register or archive within 7 days

### Rule 4: Schema Changes = Review + Approval

**Problem:** Auto-ALTER TABLE can cause issues

**Current (automated):**
```sql
ALTER TABLE staging.tbl_source ADD COLUMN new_col VARCHAR(255);
```

**Proposed (with review):**
```python
# If schema change detected
if columns_to_add:
    if auto_approve_threshold(columns_to_add):  # <5 columns
        alter_table()
        log_auto_approved()
    else:
        create_schema_change_request()
        notify_dba()
        # Load continues with existing columns only
        # New columns ignored until approved
```

---

## 📊 Monitoring Dashboard Requirements

### Dashboard 1: Load Health

**Metrics:**
- Load success rate (7d rolling)
- Average load duration by source
- Failed loads (with error messages)
- Load frequency by source

**Queries:**
```sql
-- Success rate last 7 days
SELECT
  COUNT(*) FILTER (WHERE load_status = 'completed') * 100.0 / COUNT(*) as success_rate
FROM datawarp.tbl_load_events
WHERE started_at > NOW() - INTERVAL '7 days';

-- Slowest loads
SELECT source_code, AVG(completed_at - started_at) as avg_duration
FROM datawarp.tbl_load_events
WHERE load_status = 'completed'
GROUP BY source_code
ORDER BY avg_duration DESC
LIMIT 10;
```

### Dashboard 2: Data Freshness

**Metrics:**
- Days since last load
- Sources with stale data (>30 days)
- Load frequency by source

**Queries:**
```sql
-- Stale sources
SELECT
  s.source_code,
  s.publication,
  MAX(e.completed_at) as last_loaded,
  NOW() - MAX(e.completed_at) as days_stale
FROM datawarp.tbl_data_sources s
LEFT JOIN datawarp.tbl_load_events e ON s.source_code = e.source_code
WHERE s.status = 'active'
GROUP BY s.source_code, s.publication
HAVING NOW() - MAX(e.completed_at) > INTERVAL '30 days'
ORDER BY days_stale DESC;
```

### Dashboard 3: Storage & Growth

**Metrics:**
- Table sizes (top 20)
- Total storage by domain
- Row count growth trends

**Queries:**
```sql
-- Table sizes
SELECT
  schemaname,
  tablename,
  pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables
WHERE schemaname IN ('staging', 'archive')
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC
LIMIT 20;
```

### Dashboard 4: Schema Evolution

**Metrics:**
- Columns added (last 30 days)
- Tables created (last 30 days)
- High-drift sources

**Queries:**
```sql
-- Schema changes last 30 days
SELECT
  source_code,
  SUM(columns_added) as total_columns_added,
  COUNT(*) as load_count
FROM datawarp.tbl_load_events
WHERE started_at > NOW() - INTERVAL '30 days'
  AND columns_added > 0
GROUP BY source_code
ORDER BY total_columns_added DESC;
```

---

## 🔧 Maintenance Procedures

### Weekly Maintenance (Automated)

```bash
#!/bin/bash
# weekly_maintenance.sh

# 1. Vacuum and analyze
psql -c "VACUUM ANALYZE staging.*;"
psql -c "VACUUM ANALYZE datawarp.*;"

# 2. Update statistics
psql -c "ANALYZE;"

# 3. Check for orphaned tables
python scripts/detect_orphaned_tables.py --action alert

# 4. Check for failed loads
python scripts/check_failed_loads.py --days 7 --action alert

# 5. Generate health report
python scripts/generate_health_report.py --email dba@nhs.uk
```

### Monthly Maintenance (Manual)

1. **Review Deprecated Sources**
   - Archive sources past grace period
   - Export to Parquet
   - Update registry

2. **Capacity Planning**
   - Review storage growth trends
   - Forecast next 3 months
   - Plan retention policy updates

3. **Schema Review**
   - Review schema changes from last month
   - Identify optimization opportunities
   - Document intentional drift

### Quarterly Maintenance

1. **Audit Trail Review**
   - Verify load history integrity
   - Archive old load events (>1 year)
   - Compliance check

2. **Performance Tuning**
   - Identify slow queries
   - Add indexes if needed
   - Review table partitioning needs

---

## 🚨 Incident Response

### Scenario 1: Failed Load

**Detection:** `tbl_load_events` shows `load_status = 'failed'`

**Response:**
1. Check error message in `error_message` column
2. Review source URL (is it still available?)
3. Check manifest YAML (valid structure?)
4. Attempt reload with `--verbose` flag
5. If still failing: Mark source as `deprecated` temporarily
6. Notify owner

### Scenario 2: Orphaned Table

**Detection:** Table exists in `staging.*` but not in registry

**Response:**
1. Identify when table was created (pg_class.relcreated)
2. Search load history for clues
3. If <7 days old: Contact recent DBAs
4. If >7 days old: Archive immediately
5. Update registry or move to archive

### Scenario 3: Duplicate Data

**Detection:** Row hashes show duplicates across periods

**Response:**
1. Identify affected source
2. Check `load_mode` (should be REPLACE, not APPEND)
3. If APPEND: Change to REPLACE, reload data
4. If REPLACE: Investigate why duplicates exist
5. Run deduplication query if needed

### Scenario 4: Runaway Storage

**Detection:** Storage growing >20% per week

**Response:**
1. Identify largest tables
2. Check if retention policy is applied
3. Review if data needs to be in database vs Parquet
4. Archive old periods to Parquet
5. Update retention policies

---

## 📐 Database Schema Enhancements

### New Registry Fields

```sql
ALTER TABLE datawarp.tbl_data_sources ADD COLUMN IF NOT EXISTS
  owner VARCHAR(255),
  purpose TEXT,
  retention_days INTEGER DEFAULT 365,
  load_mode VARCHAR(20) DEFAULT 'replace',
  validation_required BOOLEAN DEFAULT true,
  last_validated_at TIMESTAMP,
  deprecation_reason TEXT,
  archived_at TIMESTAMP;
```

### New Validation Table

```sql
CREATE TABLE datawarp.tbl_validation_results (
  validation_id SERIAL PRIMARY KEY,
  load_id INTEGER REFERENCES datawarp.tbl_load_events(load_id),
  source_code VARCHAR(100),
  validation_type VARCHAR(50),  -- row_count, schema, quality, metadata
  status VARCHAR(20),  -- pass, warn, fail
  message TEXT,
  validated_at TIMESTAMP DEFAULT NOW()
);
```

### New Metrics Table

```sql
CREATE TABLE datawarp.tbl_source_metrics (
  metric_id SERIAL PRIMARY KEY,
  source_code VARCHAR(100),
  metric_date DATE DEFAULT CURRENT_DATE,
  row_count BIGINT,
  column_count INTEGER,
  table_size_bytes BIGINT,
  load_duration_seconds INTEGER,
  validation_pass_rate NUMERIC(5,2)
);
```

---

## 🔒 Access Control

### Role-Based Permissions

```sql
-- Read-only analysts
GRANT SELECT ON staging.* TO role_analyst;
GRANT SELECT ON datawarp.* TO role_analyst;

-- Data engineers (load data)
GRANT SELECT, INSERT, UPDATE ON staging.* TO role_engineer;
GRANT SELECT, INSERT, UPDATE ON datawarp.* TO role_engineer;

-- DBAs (full control)
GRANT ALL ON staging.* TO role_dba;
GRANT ALL ON datawarp.* TO role_dba;
GRANT ALL ON archive.* TO role_dba;
```

### Audit Logging

```sql
-- Enable audit logging on registry tables
ALTER TABLE datawarp.tbl_data_sources
  ENABLE ROW LEVEL SECURITY;

CREATE POLICY audit_policy ON datawarp.tbl_data_sources
  FOR ALL
  USING (true)
  WITH CHECK (
    current_user IN (SELECT user_email FROM datawarp.tbl_authorized_users)
  );
```

---

## 🎯 Implementation Plan

### Phase 1: Foundation (Week 1)
- [ ] Add new registry fields
- [ ] Create validation_results table
- [ ] Create metrics table
- [ ] Implement load validation framework

### Phase 2: Monitoring (Week 2)
- [ ] Build health dashboard queries
- [ ] Implement alerting system
- [ ] Create weekly maintenance script
- [ ] Document incident response procedures

### Phase 3: Lifecycle Management (Week 3)
- [ ] Implement source registration workflow
- [ ] Add deprecation/archival commands
- [ ] Create orphan detection script
- [ ] Implement schema change review

### Phase 4: Automation (Week 4)
- [ ] Automated weekly maintenance
- [ ] Automated health reports
- [ ] Automated archival process
- [ ] Integration with monitoring tools

---

## Success Criteria

### Operational Excellence
- ✓ 95%+ load success rate
- ✓ <5% orphaned tables
- ✓ Zero undocumented sources
- ✓ All loads validated
- ✓ Failures resolved within 24 hours

### Data Quality
- ✓ 90%+ metadata coverage
- ✓ Zero duplicate data
- ✓ All tables have owners
- ✓ Stale data <5% of sources

### Observability
- ✓ Real-time load monitoring
- ✓ Weekly health reports
- ✓ Trend analysis dashboards
- ✓ Proactive alerting

---

**This framework transforms DataWarp from development tool to production-grade data platform.**
