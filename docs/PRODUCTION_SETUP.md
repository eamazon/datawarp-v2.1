# Production Deployment Guide

**Version:** 2.1.0
**Last Updated:** 2026-01-07
**Target:** Semi-production deployment with 10 NHS publications

---

## Prerequisites

- PostgreSQL 12+ running
- Python 3.10+
- 2GB RAM minimum
- Network access to digital.nhs.uk
- (Optional) Gemini API key OR Qwen model for enrichment

---

## Quick Start

### 1. Server Preparation

```bash
# Install dependencies (Ubuntu/Debian)
sudo apt update
sudo apt install python3.10 python3.10-venv postgresql-client

# Create datawarp user (optional, for dedicated deployment)
sudo useradd -m -s /bin/bash datawarp
sudo su - datawarp
```

### 2. Application Installation

```bash
# Clone repository
git clone <repo-url> datawarp-v2.1
cd datawarp-v2.1

# Create virtual environment
python3.10 -m venv .venv
source .venv/bin/activate

# Install application
pip install --upgrade pip
pip install -e .
```

### 3. Configuration

```bash
# Copy example environment file
cp .env.example .env

# Edit with production credentials
nano .env
```

**Production `.env` example:**
```bash
# Database (required)
POSTGRES_HOST=prod-db.internal
POSTGRES_PORT=5432
POSTGRES_DB=datawarp_prod
POSTGRES_USER=datawarp_user
POSTGRES_PASSWORD=<strong-password-here>
DATABASE_TYPE=postgres

# LLM Provider (required: "external" or "local")
LLM_PROVIDER=external

# Gemini API (if LLM_PROVIDER=external)
GEMINI_API_KEY=<your-api-key>

# Qwen Local (if LLM_PROVIDER=local)
QWEN_MODEL_PATH=/opt/models/qwen2.5-32b
```

### 4. Database Initialization

```bash
# Run schema creation scripts
python scripts/reset_db.py
```

**Verify tables created:**
```bash
psql -h $POSTGRES_HOST -U $POSTGRES_USER -d $POSTGRES_DB -c "\dt datawarp.*"
```

Expected output:
```
Schema   | Name                  | Type  | Owner
---------+-----------------------+-------+-------
datawarp | tbl_canonical_sources | table | ...
datawarp | tbl_data_sources      | table | ...
datawarp | tbl_drift_events      | table | ...
datawarp | tbl_load_events       | table | ...
datawarp | tbl_source_mappings   | table | ...
```

---

## Testing Installation

### Run End-to-End Test

```bash
# Activate virtual environment
source .venv/bin/activate

# Test with ADHD publication (if available)
python scripts/url_to_manifest.py \
  "https://digital.nhs.uk/data-and-information/publications/statistical/mi-adhd/november-2025" \
  manifests/test_adhd.yaml

# Enrich
python scripts/enrich.py \
  manifests/test_adhd.yaml \
  manifests/test_adhd_enriched.yaml

# Apply enrichment (Phase 1)
python scripts/apply_enrichment.py \
  manifests/test_adhd_enriched.yaml \
  manifests/test_adhd_enriched_llm_response.json \
  manifests/test_adhd_canonical.yaml

# Load
datawarp load-batch manifests/test_adhd_canonical.yaml

# Verify data loaded
psql -h $POSTGRES_HOST -U $POSTGRES_USER -d $POSTGRES_DB \
  -c "SELECT schemaname, tablename FROM pg_tables WHERE schemaname = 'staging';"
```

**Expected:** Several `tbl_adhd_*` tables in staging schema.

---

## Production Workflow

### Standard Data Loading

```bash
# 1. Generate manifest
python scripts/url_to_manifest.py <nhs-url> raw.yaml

# 2. Enrich
python scripts/enrich.py raw.yaml enriched.yaml

# 3. Canonicalize
python scripts/apply_enrichment.py \
  enriched.yaml \
  enriched_llm_response.json \
  canonical.yaml

# 4. Load
datawarp load-batch canonical.yaml
```

### Automated Cron Job (Future)

```bash
# /etc/cron.d/datawarp-daily
0 2 * * * datawarp /path/to/scripts/daily_load.sh >> /var/log/datawarp.log 2>&1
```

---

## Monitoring

### Check Recent Loads

```sql
-- Recent loads (last 20)
SELECT
  source_code,
  load_timestamp,
  rows_loaded,
  columns_added,
  status
FROM datawarp.tbl_load_events
ORDER BY load_timestamp DESC
LIMIT 20;
```

### Check Failed Loads

```sql
-- All failed loads
SELECT
  source_code,
  load_timestamp,
  error_message,
  status
FROM datawarp.tbl_load_events
WHERE status = 'failed'
ORDER BY load_timestamp DESC;
```

### Check Canonicalization

```sql
-- See LLM → canonical mappings
SELECT
  llm_generated_code,
  canonical_code,
  match_confidence,
  match_method,
  period
FROM datawarp.tbl_source_mappings
ORDER BY canonical_code, period;
```

### Check Cross-Period Consolidation

```sql
-- How many periods per canonical source?
SELECT
  canonical_code,
  COUNT(DISTINCT period) as period_count,
  MIN(period) as first_period,
  MAX(period) as last_period
FROM datawarp.tbl_source_mappings
GROUP BY canonical_code
ORDER BY period_count DESC;
```

**Expected:** Each canonical source should have multiple periods.

### Check Schema Drift

```sql
-- Recent drift events
SELECT
  canonical_code,
  drift_type,
  severity,
  details,
  detected_at
FROM datawarp.tbl_drift_events
ORDER BY detected_at DESC
LIMIT 20;
```

---

## Troubleshooting

### Problem: Database connection failed

**Check:**
```bash
# Can you connect?
psql -h $POSTGRES_HOST -U $POSTGRES_USER -d $POSTGRES_DB -c "SELECT 1"

# Credentials correct?
grep POSTGRES_ .env
```

**Common fixes:**
- Check PostgreSQL is running: `systemctl status postgresql`
- Check firewall allows port 5432
- Verify credentials in `.env`

### Problem: LLM enrichment timeout

**If using Gemini:**
```bash
# Test API key
curl -H "x-goog-api-key: $GEMINI_API_KEY" \
  https://generativelanguage.googleapis.com/v1beta/models
```

**If API key invalid:**
- Generate new key at https://aistudio.google.com/apikey
- Update `.env`: `GEMINI_API_KEY=new_key`

**Switch to local Qwen:**
```bash
# Edit .env
LLM_PROVIDER=local
QWEN_MODEL_PATH=/path/to/qwen-model
```

### Problem: Source codes changing every month

**This means `apply_enrichment.py` was skipped!**

**Solution:** Always run full workflow:
```bash
url_to_manifest → enrich → apply_enrichment → load
                                    ↑
                            DON'T SKIP THIS!
```

**Verify canonical.yaml has clean codes:**
```bash
grep "^  code:" canonical.yaml
# Should NOT see dates like "nov25", "2025-11"
```

### Problem: Duplicate tables for same source

**Check source mappings:**
```sql
SELECT canonical_code, COUNT(*)
FROM datawarp.tbl_source_mappings
GROUP BY canonical_code
HAVING COUNT(*) = 1;
```

**If many single-period sources:**
- Fingerprinting threshold too high (>0.80)
- Columns changed significantly between periods
- Manual review needed

**Manual fix:**
```sql
-- Force mapping
UPDATE datawarp.tbl_source_mappings
SET canonical_code = 'correct_canonical_code'
WHERE llm_generated_code = 'wrong_code';
```

### Problem: Tests fail

```bash
# Run specific test
pytest tests/test_extractor.py -v

# Check fixtures exist
ls tests/fixtures/

# Reinstall in editable mode
pip install -e .
```

---

## Backup Strategy

### Database Backup

```bash
# Daily backup (add to cron)
pg_dump -h $POSTGRES_HOST \
  -U $POSTGRES_USER \
  -d $POSTGRES_DB \
  -F c \
  -f /backups/datawarp_$(date +%Y%m%d).dump

# Restore
pg_restore -h $POSTGRES_HOST \
  -U $POSTGRES_USER \
  -d $POSTGRES_DB \
  -c \
  /backups/datawarp_20260107.dump
```

### Manifest Backup

```bash
# Archive processed manifests weekly
tar -czf /backups/manifests_$(date +%Y%m%d).tar.gz manifests/
```

---

## Scaling Considerations

**Current capacity:**
- 10 publications × 12 months = 120 loads/year
- ~5 minutes per publication (including enrichment)
- ~10 hours for full annual backfill

**If scaling needed:**
- Run parallel backfills (different publications)
- Use local Qwen to avoid API costs
- Increase PostgreSQL max_connections
- Add connection pooling (PgBouncer)

---

## Security

1. **Database credentials**
   - Use environment variables (`.env`)
   - Never commit `.env` to git
   - Rotate passwords quarterly

2. **API keys**
   - Rotate Gemini API key monthly
   - Use secrets manager in production (AWS Secrets Manager, etc.)

3. **Network**
   - Restrict PostgreSQL to internal network
   - Use SSL/TLS for database connections
   - Firewall rules: only port 5432 from app server

4. **Backups**
   - Encrypt backup files
   - Store offsite (S3, Azure Blob)
   - Test restore quarterly

5. **Logs**
   - Don't log sensitive data (PII from NHS)
   - Rotate logs weekly
   - Archive for 90 days

---

## Updating DataWarp

### Update to Latest Version

```bash
cd datawarp-v2.1
git pull origin main

# Activate venv
source .venv/bin/activate

# Reinstall
pip install -e .

# Run any new schema migrations
# (Check release notes for migration scripts)
```

### Schema Migrations

If database schema changes (new tables, columns):

```bash
# Example: Adding new Phase 2 tables
psql -h $POSTGRES_HOST -U $POSTGRES_USER -d $POSTGRES_DB \
  -f scripts/schema/05_create_publication_tracking.sql
```

**Always backup before migrations!**

---

## Phase 2 Deployment (Future)

Once Phase 2 is implemented:

### Register Publications

```bash
# Add 10 core publications
python scripts/init_publication.py \
  --id adhd \
  --name "ADHD Management Information" \
  --base-url "https://digital.nhs.uk/.../{period}" \
  --frequency monthly
```

### Backfill Historical Data

```bash
# Backfill 3 years
datawarp backfill adhd \
  --start-period 2022-01 \
  --end-period 2024-12 \
  --dry-run  # Test first

# Run for real
datawarp backfill adhd \
  --start-period 2022-01 \
  --end-period 2024-12
```

### Monitor Publications

```sql
-- Check publication status
SELECT
  publication_id,
  COUNT(*) as periods_loaded,
  MIN(period) as earliest,
  MAX(period) as latest
FROM datawarp.tbl_publication_periods
WHERE load_status = 'success'
GROUP BY publication_id;
```

---

## Support

**Issues:** Report at GitHub repository issues page

**Logs location:** Check console output or redirect to file:
```bash
datawarp load-batch manifest.yaml 2>&1 | tee datawarp.log
```

**Database issues:** Check PostgreSQL logs:
```bash
# Ubuntu/Debian
sudo tail -f /var/log/postgresql/postgresql-*.log
```

---

**END OF PRODUCTION_SETUP.MD - Keep under 300 lines**
