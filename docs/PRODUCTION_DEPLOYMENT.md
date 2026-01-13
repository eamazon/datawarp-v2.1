# DataWarp Production Deployment Guide

**Target:** Mac with Docker PostgreSQL
**Time Required:** 15-20 minutes
**Version:** DataWarp v2.1

---

## Prerequisites

Before starting, verify:

1. **Docker Desktop running** with PostgreSQL container
2. **Python 3.10+** installed
3. **Git** installed
4. **Gemini API key** (for LLM enrichment)

```bash
# Verify prerequisites
docker ps | grep postgres    # Should show databot-postgres
python3 --version            # Should show 3.10+
git --version                # Should show git version
```

---

## Quick Deployment (Recommended)

Use the automated nuke and rebuild script:

```bash
cd /Users/speddi/projectx/datawarp-v2.1

# Nuke and rebuild prod
./scripts/nuke_and_rebuild_prod.sh /Users/speddi/projectx/datawarp-prod
```

**What it does:**
1. Backs up .env file
2. Deletes all files in datawarp-prod
3. Pulls latest code from git
4. Creates virtual environment
5. Installs all packages
6. Drops and recreates datawarp_prod database
7. Initializes clean schema

**After script completes:**

```bash
cd /Users/speddi/projectx/datawarp-prod
source .venv/bin/activate

# Verify environment
which python
# Should show: /Users/speddi/projectx/datawarp-prod/.venv/bin/python

datawarp list
# Should show: (empty - fresh database)
```

---

## Manual Deployment

If you need to set up from scratch without the script:

### 1. Create Production Directory

```bash
mkdir -p /Users/speddi/projectx/datawarp-prod
cd /Users/speddi/projectx/datawarp-prod

# Clone repository
git clone https://github.com/eamazon/datawarp-v2.1.git .

# Create data directories
mkdir -p logs output state manifests/production config
```

### 2. Create Virtual Environment

```bash
cd /Users/speddi/projectx/datawarp-prod

# Create venv
python3 -m venv .venv

# Activate
source .venv/bin/activate

# Install DataWarp
pip install --upgrade pip
pip install -e .

# Install MCP dependencies
pip install fastapi uvicorn httpx jsonschema pydantic-settings
pip install beautifulsoup4 lxml python-dotenv duckdb pyarrow mcp
```

### 3. Create Production Database

```bash
# Drop existing database (if any)
docker exec databot-postgres psql -U databot -c "DROP DATABASE IF EXISTS datawarp_prod;"

# Create fresh database
docker exec databot-postgres psql -U databot -c "CREATE DATABASE datawarp_prod OWNER databot;"

# Verify
docker exec databot-postgres psql -U databot -l | grep datawarp_prod
```

### 4. Configure Environment

Create `.env` file:

```bash
cd /Users/speddi/projectx/datawarp-prod
nano .env
```

**Contents:**

```bash
# Production Database (Docker PostgreSQL)
DATABASE_TYPE=postgres
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=datawarp_prod
POSTGRES_USER=databot
POSTGRES_PASSWORD=databot_dev_password
POSTGRES_SCHEMA=datawarp
DEFAULT_SCHEMA=datawarp

# LLM Provider (for manifest enrichment)
LLM_PROVIDER=gemini
LLM_MODEL=gemini-2.5-flash-lite
GEMINI_API_KEY=YOUR_GEMINI_API_KEY_HERE
LLM_MAX_OUTPUT_TOKENS=15000
LLM_TEMPERATURE=0.1
LLM_TIMEOUT=600

# Production Mode
DEV_MODE=false
DATAWARP_ENABLE_ENRICHMENT=true

# Paths
DATAWARP_TEMP_DIR=./temp
DATAWARP_ARCHIVE_ROOT=./archive
```

### 5. Initialize Database Schema

```bash
cd /Users/speddi/projectx/datawarp-prod
source .venv/bin/activate

# Initialize schema
python scripts/reset_db.py
# Type 'yes' when prompted

# Verify tables created
python -c "
from dotenv import load_dotenv
load_dotenv()
from datawarp.storage.connection import get_connection

with get_connection() as conn:
    cur = conn.cursor()
    cur.execute(\"\"\"
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'datawarp'
        ORDER BY table_name
    \"\"\")
    print('Tables created:')
    for row in cur.fetchall():
        print(f'  - {row[0]}')
"
```

### 6. Create State File

```bash
mkdir -p state
echo '{"processed": {}, "failed": {}}' > state/state.json
```

---

## Configuration

### Publications Config

Edit `config/publications.yaml`:

```bash
cd /Users/speddi/projectx/datawarp-prod
nano config/publications.yaml
```

**Example:**

```yaml
# Production NHS Data Sources
# Format: backfill.py reads this to process URLs

publications:
  adhd:
    name: "ADHD Management Information"
    frequency: quarterly
    landing_page: https://digital.nhs.uk/data-and-information/publications/statistical/mi-adhd
    urls:
      - period: may25
        url: https://digital.nhs.uk/data-and-information/publications/statistical/mi-adhd/may-2025
        enabled: true
      - period: aug25
        url: https://digital.nhs.uk/data-and-information/publications/statistical/mi-adhd/august-2025
        enabled: true
      - period: nov25
        url: https://digital.nhs.uk/data-and-information/publications/statistical/mi-adhd/november-2025
        enabled: true

  online_consultation:
    name: "Online Consultation Systems in General Practice"
    frequency: monthly
    landing_page: https://digital.nhs.uk/data-and-information/publications/statistical/submissions-via-online-consultation-systems-in-general-practice
    urls:
      - period: oct25
        url: https://digital.nhs.uk/.../october-2025
        enabled: true
```

**URL Control:**
- `enabled: true` - Process this URL
- `enabled: false` - Skip permanently (even with --force)

---

## Loading Data

### Basic Commands

```bash
cd /Users/speddi/projectx/datawarp-prod
source .venv/bin/activate

# Load all publications
python scripts/backfill.py

# Load specific publication
python scripts/backfill.py --pub adhd

# Check status (what would be processed)
python scripts/backfill.py --status

# Force reload (ignore state.json)
python scripts/backfill.py --pub adhd --force

# Dry run (don't actually load)
python scripts/backfill.py --dry-run
```

### Reference Manifest Logic

Backfill automatically finds reference manifests using fiscal year logic:

**Priority:**
1. Manual `--reference` flag (if provided)
2. April reference for fiscal year (e.g., nov25 uses apr25)
3. Most recent enriched manifest
4. Fresh LLM enrichment (no reference)

**April is always fresh** (never references another manifest)

```bash
# Use specific reference
python scripts/backfill.py --pub adhd --reference manifests/production/adhd/adhd_apr25_enriched.yaml

# Force fresh LLM (ignore all references)
python scripts/backfill.py --pub adhd --no-reference
```

### What Backfill Does

For each URL:
1. **Generate manifest** - Downloads file, extracts structure
2. **Enrich with LLM** - Calls Gemini to generate semantic names
3. **Load to PostgreSQL** - Inserts data with metadata
4. **Export to Parquet** - Creates .parquet files in output/

**Output locations:**
- Manifests: `manifests/backfill/{publication}/`
- Logs: `logs/backfill_*.log`
- Events: `logs/events/{date}/backfill_*.jsonl`
- Parquet: `output/{source_code}.parquet`

---

## MCP Server

DataWarp provides two MCP server modes:

### HTTP Server (Port 8000)

For testing and direct API access:

```bash
cd /Users/speddi/projectx/datawarp-prod
source .venv/bin/activate

# Start server
python mcp_server/server.py

# In another terminal, test:
curl -s http://localhost:8000/ | python -m json.tool

# List datasets
curl -s -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{"method": "list_datasets", "params": {"limit": 5}}' | python -m json.tool

# Get metadata
curl -s -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{"method": "get_metadata", "params": {"dataset": "adhd"}}' | python -m json.tool

# Query data
curl -s -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{"method": "query", "params": {"dataset": "adhd", "question": "how many rows"}}' | python -m json.tool
```

### STDIO Server (Claude Desktop)

For Claude Desktop integration:

**1. Find paths:**

```bash
cd /Users/speddi/projectx/datawarp-prod
source .venv/bin/activate

which python
# Copy this path

pwd
# This is your working directory
```

**2. Edit Claude Desktop config:**

Location: `~/Library/Application Support/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "datawarp-prod": {
      "command": "/Users/speddi/projectx/datawarp-prod/.venv/bin/python",
      "args": [
        "/Users/speddi/projectx/datawarp-prod/mcp_server/stdio_server.py"
      ],
      "env": {
        "POSTGRES_HOST": "localhost",
        "POSTGRES_PORT": "5432",
        "POSTGRES_DB": "datawarp_prod",
        "POSTGRES_USER": "databot",
        "POSTGRES_PASSWORD": "databot_dev_password"
      }
    }
  }
}
```

**3. Restart Claude Desktop completely**
- Quit app
- Reopen
- Start new conversation

---

## CLI Commands

### DataWarp CLI

```bash
# List all registered sources
datawarp list

# Check specific source status
datawarp status adhd

# Load single file (rarely used - use backfill instead)
datawarp load <url> <source_code> --sheet "Sheet Name"

# Load from manifest
datawarp load-batch manifests/production/adhd/adhd_nov25_enriched.yaml

# Register source manually (auto-done by load-batch)
datawarp register <code> --name "Name" --table "tbl_name"
```

### Database Queries

```bash
# Connect to production database
python -c "
from dotenv import load_dotenv
load_dotenv()
import os
print(f'psql -h {os.getenv(\"POSTGRES_HOST\")} -U {os.getenv(\"POSTGRES_USER\")} -d {os.getenv(\"POSTGRES_DB\")}')
"

# Count sources
python -c "
from dotenv import load_dotenv
load_dotenv()
from datawarp.storage.connection import get_connection

with get_connection() as conn:
    cur = conn.cursor()
    cur.execute('SELECT COUNT(*) FROM datawarp.tbl_data_sources')
    print(f'Sources: {cur.fetchone()[0]}')
"

# Database size
python -c "
from dotenv import load_dotenv
load_dotenv()
from datawarp.storage.connection import get_connection

with get_connection() as conn:
    cur = conn.cursor()
    cur.execute(\"\"\"
        SELECT pg_size_pretty(pg_database_size('datawarp_prod'))
    \"\"\")
    print(f'Database size: {cur.fetchone()[0]}')
"
```

---

## Troubleshooting

### "datawarp: command not found"

**Cause:** Virtual environment not activated

**Fix:**
```bash
cd /Users/speddi/projectx/datawarp-prod
source .venv/bin/activate
```

**Add alias to shell:**
```bash
echo 'alias prod="cd /Users/speddi/projectx/datawarp-prod && source .venv/bin/activate"' >> ~/.zshrc
source ~/.zshrc

# Now just type: prod
```

---

### "ModuleNotFoundError: No module named 'datawarp'"

**Cause:** Package not installed or wrong venv active

**Fix:**
```bash
# Check which Python
which python
# Should show: /Users/speddi/projectx/datawarp-prod/.venv/bin/python

# If not, activate correct venv
cd /Users/speddi/projectx/datawarp-prod
source .venv/bin/activate

# Reinstall
pip install -e .
```

---

### "connection to server at localhost failed: fe_sendauth: no password supplied"

**Cause:** `.env` file not loaded or missing

**Fix:**
```bash
# Check .env exists
ls -la /Users/speddi/projectx/datawarp-prod/.env

# Verify contents
cat /Users/speddi/projectx/datawarp-prod/.env | grep POSTGRES

# Should show:
# POSTGRES_HOST=localhost
# POSTGRES_DB=datawarp_prod
# POSTGRES_USER=databot
# POSTGRES_PASSWORD=databot_dev_password
```

---

### "database 'datawarp_prod' does not exist"

**Cause:** Database not created

**Fix:**
```bash
# Check database exists
docker exec databot-postgres psql -U databot -l | grep datawarp

# If not listed, create it
docker exec databot-postgres psql -U databot -c "CREATE DATABASE datawarp_prod OWNER databot;"

# Verify
docker exec databot-postgres psql -U databot -l | grep datawarp_prod
```

---

### "Port 8000 already in use"

**Cause:** MCP server still running from previous session

**Fix:**
```bash
# Find process
lsof -ti :8000

# Kill it
lsof -ti :8000 | xargs kill -9

# Verify port is free
lsof -ti :8000
# Should return nothing
```

---

### "Docker container not found"

**Cause:** PostgreSQL container not running

**Fix:**
```bash
# Check if running
docker ps | grep postgres

# If not running, start it
docker start databot-postgres

# Verify
docker ps | grep postgres
# Should show: databot-postgres
```

---

### "Gemini API error: Invalid API key"

**Cause:** Wrong or missing Gemini API key

**Fix:**
```bash
# Check .env has API key
grep GEMINI_API_KEY /Users/speddi/projectx/datawarp-prod/.env

# Should show:
# GEMINI_API_KEY=AIzaSy...

# If missing or wrong, edit .env
nano /Users/speddi/projectx/datawarp-prod/.env

# Test API key works
python -c "
import os
from dotenv import load_dotenv
load_dotenv()

api_key = os.getenv('GEMINI_API_KEY')
if api_key:
    print(f'API Key: {api_key[:20]}...')
else:
    print('ERROR: No API key found')
"
```

---

### MCP Server Not Showing in Claude Desktop

**Fix:**

1. **Verify paths in config:**
   ```bash
   # Get Python path
   cd /Users/speddi/projectx/datawarp-prod && source .venv/bin/activate && which python

   # Get stdio_server.py path
   ls /Users/speddi/projectx/datawarp-prod/mcp_server/stdio_server.py
   ```

2. **Update `claude_desktop_config.json` with exact paths**

3. **Check file permissions:**
   ```bash
   chmod +x /Users/speddi/projectx/datawarp-prod/mcp_server/stdio_server.py
   ```

4. **Test manually:**
   ```bash
   cd /Users/speddi/projectx/datawarp-prod
   source .venv/bin/activate
   python mcp_server/stdio_server.py
   # Should start without errors (Ctrl+C to stop)
   ```

5. **Restart Claude Desktop COMPLETELY:**
   - Quit all windows
   - Cmd+Q to quit app
   - Check Activity Monitor - no Claude processes running
   - Reopen Claude Desktop
   - Start NEW conversation (not existing one)

---

### "Low row count" warnings during backfill

**This is normal** for NHS summary tables that have 5-13 rows per period.

Not an error - just a validation warning. Data loaded successfully.

---

### Stale venv (wrong Python after running nuke script)

**Cause:** The nuke script was activating prod venv, polluting your shell

**Fix:**
```bash
# Exit terminal completely
exit

# Open new terminal
cd /Users/speddi/projectx/datawarp-v2.1
source .venv/bin/activate

# Verify correct venv
which python
# Should show: /Users/speddi/projectx/datawarp-v2.1/.venv/bin/python
```

**This is now fixed** in the latest nuke script - it no longer activates venv.

---

## FAQ

### How do I switch between dev and prod?

**Dev:**
```bash
cd /Users/speddi/projectx/datawarp-v2.1
source .venv/bin/activate
# All commands use datawarp-v2.1 database
```

**Prod:**
```bash
cd /Users/speddi/projectx/datawarp-prod
source .venv/bin/activate
# All commands use datawarp_prod database
```

**Check which you're in:**
```bash
pwd
which python
echo $POSTGRES_DB
```

---

### How do I add a new NHS publication?

1. **Edit publications.yaml:**
   ```bash
   nano config/publications.yaml
   ```

2. **Add entry using template:**
   ```yaml
   your_publication:
     name: "Publication Name"
     frequency: monthly
     landing_page: https://...
     urls:
       - period: jan26
         url: https://...
         enabled: true
   ```

3. **Run backfill:**
   ```bash
   python scripts/backfill.py --pub your_publication
   ```

---

### How do I reprocess a URL?

**Force reload (ignores state.json):**
```bash
python scripts/backfill.py --pub adhd --force
```

**Delete from state.json:**
```bash
nano state/state.json
# Remove URL from "processed" section
```

---

### How do I disable a URL without deleting it?

**Set enabled flag:**
```yaml
urls:
  - period: jan26
    url: https://...
    enabled: false  # Permanently skip
```

Backfill will skip this URL even with `--force`.

---

### Where are the logs?

```bash
# Backfill logs
ls -lh logs/backfill_*.log
tail -f logs/backfill_*.log

# Event logs (JSONL)
ls -lh logs/events/*/
cat logs/events/2026-01-13/backfill_*.jsonl | jq .

# MCP logs
ls -lh logs/mcp.log
tail -f logs/mcp.log
```

---

### How do I clean up and start fresh?

**Option 1: Nuke and rebuild (recommended):**
```bash
cd /Users/speddi/projectx/datawarp-v2.1
./scripts/nuke_and_rebuild_prod.sh /Users/speddi/projectx/datawarp-prod
```

**Option 2: Just reset database:**
```bash
cd /Users/speddi/projectx/datawarp-prod
source .venv/bin/activate

# Drop and recreate
docker exec databot-postgres psql -U databot -c "DROP DATABASE datawarp_prod;"
docker exec databot-postgres psql -U databot -c "CREATE DATABASE datawarp_prod OWNER databot;"

# Reinitialize schema
python scripts/reset_db.py

# Clear state
echo '{"processed": {}, "failed": {}}' > state/state.json

# Clear logs
rm -rf logs/* output/*
```

---

### How do I check if enrichment metadata was captured?

```bash
python -c "
from dotenv import load_dotenv
load_dotenv()
from datawarp.storage.connection import get_connection

with get_connection() as conn:
    cur = conn.cursor()
    cur.execute(\"\"\"
        SELECT
            code,
            description,
            domain,
            tags,
            metadata IS NOT NULL as has_metadata
        FROM datawarp.tbl_data_sources
        LIMIT 5
    \"\"\")
    print('Sources with metadata:')
    for row in cur.fetchall():
        code, desc, domain, tags, has_meta = row
        print(f'  {code}:')
        print(f'    Description: {desc}')
        print(f'    Domain: {domain}')
        print(f'    Tags: {tags}')
        print(f'    Has metadata: {has_meta}')
        print()
"
```

---

### How do I backup production database?

```bash
# Create backup directory
mkdir -p ~/datawarp-backups

# Backup (using Docker)
docker exec databot-postgres pg_dump -U databot datawarp_prod > ~/datawarp-backups/datawarp_prod_$(date +%Y%m%d_%H%M%S).sql

# Compress
gzip ~/datawarp-backups/datawarp_prod_*.sql

# List backups
ls -lh ~/datawarp-backups/
```

**Restore:**
```bash
# Uncompress
gunzip ~/datawarp-backups/datawarp_prod_20260113_120000.sql.gz

# Restore (using Docker)
docker exec -i databot-postgres psql -U databot datawarp_prod < ~/datawarp-backups/datawarp_prod_20260113_120000.sql
```

---

### How do I update prod to latest code?

```bash
cd /Users/speddi/projectx/datawarp-prod
git pull origin main
source .venv/bin/activate
pip install -e .
```

**If you want clean slate with latest code:**
```bash
cd /Users/speddi/projectx/datawarp-v2.1
./scripts/nuke_and_rebuild_prod.sh /Users/speddi/projectx/datawarp-prod
```

---

### What files should never be in git?

These are .gitignored (won't be committed):
- `output/` - Parquet files
- `logs/` - Log files
- `state/` - State tracking
- `manifests/backfill/` - Generated manifests
- `manifests/production/` - Generated manifests
- `.env` - Credentials

Only source code is in git.

---

### How do I monitor production health?

**Quick check:**
```bash
cd /Users/speddi/projectx/datawarp-prod
source .venv/bin/activate

echo "Sources: $(datawarp list | wc -l)"
echo "Database: $(python -c 'from dotenv import load_dotenv; load_dotenv(); import os; print(os.getenv(\"POSTGRES_DB\"))')"
echo "Last log: $(ls -t logs/backfill_*.log 2>/dev/null | head -1)"
```

---

## Quick Reference

### Essential Commands

| Task | Command |
|------|---------|
| Activate prod | `cd /Users/speddi/projectx/datawarp-prod && source .venv/bin/activate` |
| Load all data | `python scripts/backfill.py` |
| Load one publication | `python scripts/backfill.py --pub adhd` |
| Check status | `python scripts/backfill.py --status` |
| List sources | `datawarp list` |
| Start MCP HTTP | `python mcp_server/server.py` |
| Test MCP | `curl -s http://localhost:8000/ \| python -m json.tool` |
| Reset database | `python scripts/reset_db.py` |
| Nuke and rebuild | `./scripts/nuke_and_rebuild_prod.sh /path/to/prod` |

### File Locations

| What | Path |
|------|------|
| Prod directory | `/Users/speddi/projectx/datawarp-prod/` |
| Config | `/Users/speddi/projectx/datawarp-prod/.env` |
| Publications | `/Users/speddi/projectx/datawarp-prod/config/publications.yaml` |
| Logs | `/Users/speddi/projectx/datawarp-prod/logs/` |
| Output | `/Users/speddi/projectx/datawarp-prod/output/` |
| State | `/Users/speddi/projectx/datawarp-prod/state/state.json` |
| Manifests | `/Users/speddi/projectx/datawarp-prod/manifests/backfill/` |

### Database

- **Host:** localhost
- **Port:** 5432
- **Database:** datawarp_prod
- **User:** databot
- **Password:** databot_dev_password
- **Container:** databot-postgres

---

**Updated:** 2026-01-13
**Version:** 2.0 (Mac/Docker)
