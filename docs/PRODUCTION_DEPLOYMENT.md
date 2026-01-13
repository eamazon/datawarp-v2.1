# DataWarp Production Deployment Guide

**Target Audience:** Solo developer deploying to WSL (Windows Subsystem for Linux)
**Expertise Level:** Beginner-friendly with detailed explanations
**Time Required:** 45-60 minutes
**Version:** DataWarp v2.2

---

## 📋 What You'll Have When Done

```
Your WSL Machine:
├── Dev Environment (existing)
│   └── /mnt/c/Users/.../datawarp-v2.1/
│       ├── PostgreSQL: datawarp2
│       ├── .venv/ (dev Python)
│       └── logs/output/state/ (dev data)
│
└── Production Environment (NEW)
    └── /home/yourusername/datawarp-prod/
        ├── PostgreSQL: datawarp_prod
        ├── .venv/ (prod Python)
        ├── logs/ (prod logs)
        ├── output/ (prod exports)
        ├── state/ (prod state)
        ├── manifests/ (prod config)
        └── MCP Server (prod API)
```

**Result:** Two completely isolated environments that don't interfere with each other.

---

## ✅ Prerequisites Check

Before starting, verify you have:

### 1. WSL Installed and Working

```bash
# Check WSL version
wsl --version

# If not installed, run in Windows PowerShell (Admin):
wsl --install -d Ubuntu-22.04
# Then restart computer
```

### 2. PostgreSQL Installed

```bash
# Check if PostgreSQL is installed
psql --version

# If not installed:
sudo apt update
sudo apt install -y postgresql postgresql-contrib

# Start PostgreSQL
sudo service postgresql start

# Make it auto-start
echo "sudo service postgresql start" >> ~/.bashrc
```

### 3. Python 3.10+

```bash
# Check Python version
python3 --version

# Should show 3.10 or higher. If not:
sudo apt install -y python3.10 python3.10-venv python3-pip
```

### 4. Git Installed

```bash
# Check git
git --version

# If not installed:
sudo apt install -y git
```

**✅ Once all four pass, continue to setup.**

---

## 🚀 Part 1: Create Production Directory

**Concept:** We'll install a fresh copy of DataWarp in a separate directory.

```bash
# Step 1: Go to your Linux home directory (not Windows /mnt/c/)
cd ~
pwd
# Should show: /home/yourusername

# Step 2: Create production directory
mkdir -p datawarp-prod
cd datawarp-prod
pwd
# Should show: /home/yourusername/datawarp-prod

# Step 3: Clone the repository
git clone https://github.com/eamazon/datawarp-v2.1.git .
# Note the dot (.) at the end - clones INTO current directory

# Step 4: Verify files are there
ls -la
# Should see: src/ scripts/ docs/ .git/ setup.py etc.

# Step 5: Create production folders
mkdir -p logs output state manifests/production config

# Step 6: Verify structure
tree -L 1 -d
# Should see both code folders (src/, scripts/) and data folders (logs/, output/)
```

**Why Linux home (~) not Windows (/mnt/c/)?**
- Faster file I/O (native Linux filesystem)
- Proper Unix permissions
- No Windows/Linux path issues

---

## 🐍 Part 2: Set Up Production Python Environment

**Concept:** Create a separate virtual environment so production doesn't share packages with dev.

```bash
# Ensure you're in production directory
cd ~/datawarp-prod

# Step 1: Create virtual environment
python3 -m venv .venv
# Creates .venv/ folder with isolated Python

# Step 2: Activate it
source .venv/bin/activate

# Step 3: Verify you're in the venv
which python
# Should show: /home/yourusername/datawarp-prod/.venv/bin/python

python --version
# Should show: Python 3.10+ (YOUR production Python)

# Step 4: Upgrade pip
pip install --upgrade pip

# Step 5: Install DataWarp
pip install -e .
# The -e means "editable" - code changes apply immediately

# Step 6: Install MCP dependencies
pip install fastapi uvicorn httpx jsonschema pydantic-settings

# Step 7: Verify DataWarp CLI is available
datawarp --help
# Should show commands: register, load, list, load-batch, etc.

# Step 8: Save installed packages for reference
pip freeze > requirements-prod.txt
```

**What just happened?**
- Created isolated Python environment
- Installed DataWarp and all dependencies
- CLI command `datawarp` now works in this environment

---

## 🗄️ Part 3: Create Production PostgreSQL Database

**Concept:** Create a separate database so production data doesn't mix with dev data.

```bash
# Step 1: Check PostgreSQL is running
sudo service postgresql status
# Should say: "Running"

# If not running:
sudo service postgresql start

# Step 2: Connect as superuser
sudo -u postgres psql
# You're now in PostgreSQL prompt (postgres=#)
```

**In the PostgreSQL prompt, run these SQL commands:**

```sql
-- Create production user
CREATE USER datawarp_prod_user WITH PASSWORD 'your_secure_prod_password_123';

-- Create production database
CREATE DATABASE datawarp_prod OWNER datawarp_prod_user;

-- Grant privileges
GRANT ALL PRIVILEGES ON DATABASE datawarp_prod TO datawarp_prod_user;

-- Exit PostgreSQL
\q
```

```bash
# Step 3: Test the new database connection
psql -h localhost -U datawarp_prod_user -d datawarp_prod
# Enter password when prompted: your_secure_prod_password_123

# In psql, run:
SELECT current_database();
# Should show: datawarp_prod

\q
```

**What just happened?**
- Created new user: `datawarp_prod_user`
- Created new database: `datawarp_prod`
- Tested connection works

**Your databases now:**
- `datawarp2` ← Dev database (existing)
- `datawarp_prod` ← Production database (NEW)

---

## ⚙️ Part 4: Configure Production Environment

**Concept:** Create `.env` file with production database credentials.

```bash
# Ensure you're in production directory
cd ~/datawarp-prod

# Step 1: Create .env file
nano .env
# Or use: vi .env or code .env
```

**Copy this template into .env:**

```bash
# ============================================================================
# PRODUCTION ENVIRONMENT CONFIGURATION
# ============================================================================

# Production Database
DATABASE_TYPE=postgres
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=datawarp_prod
POSTGRES_USER=datawarp_prod_user
POSTGRES_PASSWORD=your_secure_prod_password_123
POSTGRES_SCHEMA=datawarp
DEFAULT_SCHEMA=datawarp

# LLM Provider (for manifest enrichment)
LLM_PROVIDER=gemini
LLM_MODEL=gemini-2.5-flash-lite
GEMINI_API_KEY=your_gemini_api_key_here
LLM_MAX_OUTPUT_TOKENS=15000
LLM_TEMPERATURE=0.1
LLM_TIMEOUT=600

# Production Mode
DEV_MODE=false
DATAWARP_ENABLE_ENRICHMENT=true

# Temp/Archive Paths (relative to this installation)
DATAWARP_TEMP_DIR=./temp
DATAWARP_ARCHIVE_ROOT=./archive
```

**Save and exit:**
- If using nano: Ctrl+X, then Y, then Enter
- If using vi: Esc, then :wq, then Enter

```bash
# Step 2: Secure the .env file (only you can read it)
chmod 600 .env

# Step 3: Verify permissions
ls -lh .env
# Should show: -rw------- (only owner can read/write)

# Step 4: Test environment variables are loaded
source .venv/bin/activate  # Activate venv if not already
python -c "import os; print('DB:', os.getenv('POSTGRES_DB', 'NOT LOADED'))"
```

**⚠️ Important:** The `.env` file should show `POSTGRES_DB=datawarp_prod` when you print it.

**If it shows "NOT LOADED":**
The python-dotenv library loads .env automatically when DataWarp runs. The test above might show "NOT LOADED" - that's OK. DataWarp CLI commands will load it.

---

## 🏗️ Part 5: Initialize Database Schema

**Concept:** Create tables in the production database.

```bash
# Ensure you're in production directory with venv active
cd ~/datawarp-prod
source .venv/bin/activate

# Step 1: Check if reset_db.py exists
ls scripts/reset_db.py
# Should show: scripts/reset_db.py

# Step 2: Initialize database
python scripts/reset_db.py

# You should see output like:
# Dropping existing tables...
# Creating schemas...
# Creating tables...
# Creating indexes...
# Database initialized successfully!

# Step 3: Verify schema created
psql -h localhost -U datawarp_prod_user -d datawarp_prod
```

**In psql, run these verification commands:**

```sql
-- List schemas
\dn
-- Should see: datawarp | staging

-- List tables in datawarp schema
\dt datawarp.*
-- Should see:
--   tbl_data_sources
--   tbl_load_history
--   tbl_manifest_files

-- Count sources (should be 0 for fresh install)
SELECT COUNT(*) FROM datawarp.tbl_data_sources;
-- Should show: 0

-- Exit
\q
```

**What just happened?**
- Created `datawarp` schema (for registry tables)
- Created `staging` schema (for data tables)
- Created registry tables (tbl_data_sources, tbl_load_history, etc.)

---

## 🎯 Part 6: Set Up MCP Server for Production

**Concept:** Configure Claude Desktop to connect to production database via MCP.

```bash
# Step 1: Verify MCP server file exists
ls ~/datawarp-prod/mcp_server/stdio_server.py
# Should show the file

# Step 2: Test MCP server manually (optional)
cd ~/datawarp-prod
source .venv/bin/activate
python mcp_server/stdio_server.py
# Press Ctrl+C to stop
```

### Configure Claude Desktop

**Location of config file:**
- **Windows:** `%APPDATA%\Claude\claude_desktop_config.json`
- **Mac:** `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Linux:** `~/.config/Claude/claude_desktop_config.json`

**How to edit (Windows):**
1. Press Windows+R
2. Type: `%APPDATA%\Claude`
3. Open `claude_desktop_config.json` in Notepad

**Add this configuration:**

```json
{
  "mcpServers": {
    "datawarp-production": {
      "command": "/home/yourusername/datawarp-prod/.venv/bin/python",
      "args": ["/home/yourusername/datawarp-prod/mcp_server/stdio_server.py"],
      "env": {
        "POSTGRES_HOST": "localhost",
        "POSTGRES_DB": "datawarp_prod",
        "POSTGRES_USER": "datawarp_prod_user",
        "POSTGRES_PASSWORD": "your_secure_prod_password_123",
        "POSTGRES_PORT": "5432"
      }
    }
  }
}
```

**⚠️ Replace `yourusername` with your actual username!**

```bash
# Find your username:
whoami
# Use the output in the paths above
```

**If you want BOTH dev and prod MCP servers:**

```json
{
  "mcpServers": {
    "datawarp-dev": {
      "command": "/mnt/c/Users/.../datawarp-v2.1/.venv/bin/python",
      "args": ["/mnt/c/Users/.../datawarp-v2.1/mcp_server/stdio_server.py"],
      "env": {
        "POSTGRES_DB": "datawarp2"
      }
    },
    "datawarp-production": {
      "command": "/home/yourusername/datawarp-prod/.venv/bin/python",
      "args": ["/home/yourusername/datawarp-prod/mcp_server/stdio_server.py"],
      "env": {
        "POSTGRES_DB": "datawarp_prod",
        "POSTGRES_USER": "datawarp_prod_user",
        "POSTGRES_PASSWORD": "your_secure_prod_password_123"
      }
    }
  }
}
```

**After editing:**
1. Save the file
2. **Restart Claude Desktop** (completely quit and reopen)
3. Start a new conversation
4. MCP tools should now be available

---

## ✅ Part 7: Test Production Environment

```bash
# Ensure you're in production directory
cd ~/datawarp-prod
source .venv/bin/activate

# Verification Test 1: Database connection
datawarp list
# Should show: (empty list - no sources yet)
# If you see error "database not found", check .env file

# Verification Test 2: Generate a test manifest
python scripts/url_to_manifest.py \
  "https://digital.nhs.uk/data-and-information/publications/statistical/adult-adhd/august-2025" \
  manifests/production/test_adhd_aug25.yaml

# Verification Test 3: Check manifest was created
ls -lh manifests/production/
# Should see: test_adhd_aug25.yaml

# Verification Test 4: Verify database is empty (production isolation)
psql -h localhost -U datawarp_prod_user -d datawarp_prod -c \
  "SELECT COUNT(*) FROM datawarp.tbl_data_sources;"
# Should show: 0 (different from dev database!)

# Verification Test 5: Check logs directory is ready
ls -ld logs/
# Should show: drwxr-xr-x ... logs/

# Verification Test 6: Verify Python environment
which python
# Should show: /home/yourusername/datawarp-prod/.venv/bin/python
pip list | grep datawarp
# Should show: datawarp (editable install)
```

**All 6 tests passed? ✅ Production environment is ready!**

---

## 📦 Part 8: Load Your First Production Data

Let's test the full pipeline with real NHS data:

```bash
cd ~/datawarp-prod
source .venv/bin/activate

# Step 1: Create production publications config
nano config/publications.yaml
```

**Add this content:**

```yaml
# Production NHS Data Sources
adhd:
  name: "ADHD Management Information"
  landing_page: "https://digital.nhs.uk/data-and-information/publications/statistical/adult-adhd"
  urls:
    - "https://digital.nhs.uk/data-and-information/publications/statistical/adult-adhd/august-2025"
```

**Save and exit.**

```bash
# Step 2: Initialize state tracking
mkdir -p state
echo '{"processed": {}, "failed": {}}' > state/state.json

# Step 3: Check what would be processed (dry run)
python scripts/backfill.py --status

# Step 4: Run the backfill (actual load)
python scripts/backfill.py

# This will:
# 1. Download ADHD August 2025 Excel file
# 2. Generate manifest
# 3. Enrich with LLM (uses Gemini API key from .env)
# 4. Load to PostgreSQL (datawarp_prod database)
# 5. Export to Parquet

# Step 5: Check what was loaded
datawarp list
# Should show ADHD sources

# Step 6: Check logs
ls -lh logs/events/*/
# Should see JSONL event files

# Step 7: Analyze what happened
python scripts/analyze_logs.py --all

# Step 8: Check output files
ls -lh output/
# Should see .parquet files

# Step 9: Verify database has data
psql -h localhost -U datawarp_prod_user -d datawarp_prod -c \
  "SELECT source_code, table_name FROM datawarp.tbl_data_sources LIMIT 5;"
# Should show ADHD sources
```

**✅ If you see data, you successfully loaded your first production NHS dataset!**

---

## 🔄 Part 9: Daily Operations

### Switch Between Dev and Production

**To work in PRODUCTION:**
```bash
cd ~/datawarp-prod
source .venv/bin/activate
# Now all commands use production database
```

**To work in DEV:**
```bash
cd /mnt/c/Users/.../datawarp-v2.1
source .venv/bin/activate
# Now all commands use dev database
```

**How to tell which environment you're in:**
```bash
# Check database
python -c "from datawarp.storage.connection import get_connection; \
with get_connection() as conn: \
    cur = conn.cursor(); \
    cur.execute('SELECT current_database()'); \
    print('Database:', cur.fetchone()[0])"

# Check directory
pwd
```

### Common Production Tasks

**Check backfill status:**
```bash
cd ~/datawarp-prod && source .venv/bin/activate
python scripts/backfill.py --status
```

**Add new publication:**
```bash
cd ~/datawarp-prod && source .venv/bin/activate
nano config/publications.yaml  # Add new URL
python scripts/backfill.py --dry-run  # Preview
python scripts/backfill.py  # Run it
```

**Check recent loads:**
```bash
cd ~/datawarp-prod && source .venv/bin/activate
python scripts/analyze_logs.py --all
```

**Check for errors:**
```bash
cd ~/datawarp-prod && source .venv/bin/activate
python scripts/analyze_logs.py --errors
```

**Get restart commands for failures:**
```bash
cd ~/datawarp-prod && source .venv/bin/activate
python scripts/analyze_logs.py --restart
```

**Clean up orphaned data:**
```bash
cd ~/datawarp-prod && source .venv/bin/activate
python scripts/cleanup_orphans.py  # Dry run
python scripts/cleanup_orphans.py --execute  # Actually clean
```

**Export specific publication:**
```bash
cd ~/datawarp-prod && source .venv/bin/activate
python scripts/export_to_parquet.py --publication adhd output/
```

**Rebuild catalog for MCP:**
```bash
cd ~/datawarp-prod && source .venv/bin/activate
python scripts/rebuild_catalog.py
ls -lh output/catalog.parquet
```

---

## 🔧 Troubleshooting

### "datawarp: command not found"

**Cause:** Virtual environment not activated.

**Fix:**
```bash
cd ~/datawarp-prod
source .venv/bin/activate
```

**To auto-activate on login:**
```bash
echo 'alias prod="cd ~/datawarp-prod && source .venv/bin/activate"' >> ~/.bashrc
source ~/.bashrc
# Now just type: prod
```

---

### "FATAL: database 'datawarp_prod' does not exist"

**Cause:** Database wasn't created or .env has wrong name.

**Fix:**
```bash
# Check .env file
grep POSTGRES_DB ~/datawarp-prod/.env
# Should show: POSTGRES_DB=datawarp_prod

# Check database exists
psql -h localhost -U postgres -l | grep datawarp
# Should list: datawarp_prod

# If not listed, create it:
sudo -u postgres psql -c "CREATE DATABASE datawarp_prod OWNER datawarp_prod_user;"
```

---

### "permission denied for schema datawarp"

**Cause:** User doesn't have permissions.

**Fix:**
```bash
sudo -u postgres psql -d datawarp_prod << 'EOF'
GRANT ALL ON SCHEMA datawarp TO datawarp_prod_user;
GRANT ALL ON SCHEMA staging TO datawarp_prod_user;
GRANT ALL ON ALL TABLES IN SCHEMA datawarp TO datawarp_prod_user;
GRANT ALL ON ALL TABLES IN SCHEMA staging TO datawarp_prod_user;
EOF
```

---

### "ModuleNotFoundError: No module named 'datawarp'"

**Cause:** DataWarp not installed or wrong venv.

**Fix:**
```bash
cd ~/datawarp-prod
source .venv/bin/activate
pip install -e .
```

---

### "FileNotFoundError: [Errno 2] No such file or directory: '.env'"

**Cause:** .env file doesn't exist or you're in wrong directory.

**Fix:**
```bash
# Check you're in right place
pwd
# Should show: /home/yourusername/datawarp-prod

# Check .env exists
ls -la .env

# If missing, create it:
cp .env.example .env
nano .env  # Edit with your settings
```

---

### MCP Server Not Showing in Claude Desktop

**Fix:**
1. Check Claude Desktop config file has correct paths:
   ```bash
   # Get your username
   whoami

   # Get full path to Python
   cd ~/datawarp-prod && source .venv/bin/activate && which python

   # Get full path to MCP server
   cd ~/datawarp-prod && pwd
   # Combine: /home/USERNAME/datawarp-prod/mcp_server/stdio_server.py
   ```

2. Update `claude_desktop_config.json` with full paths

3. **Restart Claude Desktop completely:**
   - Close all windows
   - Quit from system tray (right-click Claude icon → Quit)
   - Reopen

4. Start a **new conversation** (MCP loads per conversation)

---

### PostgreSQL Not Starting

**Fix:**
```bash
# Start manually
sudo service postgresql start

# Check status
sudo service postgresql status

# If fails, check logs
sudo tail -f /var/log/postgresql/postgresql-*-main.log

# Nuclear option (reinstall)
sudo apt remove --purge postgresql postgresql-contrib
sudo apt install postgresql postgresql-contrib
```

---

## 🔒 Security Best Practices

### Secure Your .env File

```bash
# Only you should be able to read it
chmod 600 ~/datawarp-prod/.env

# Verify
ls -lh ~/datawarp-prod/.env
# Should show: -rw------- (600)
```

### Use Strong Database Password

```bash
# Generate random password
openssl rand -base64 32

# Update in PostgreSQL
sudo -u postgres psql << 'EOF'
ALTER USER datawarp_prod_user WITH PASSWORD 'new_strong_password_here';
EOF

# Update in .env
nano ~/datawarp-prod/.env
# Change POSTGRES_PASSWORD=new_strong_password_here
```

### Backup Production Database

```bash
# Create backup directory
mkdir -p ~/datawarp-backups

# Backup database
pg_dump -h localhost -U datawarp_prod_user -d datawarp_prod \
  > ~/datawarp-backups/datawarp_prod_$(date +%Y%m%d_%H%M%S).sql

# Compress it
gzip ~/datawarp-backups/datawarp_prod_*.sql

# List backups
ls -lh ~/datawarp-backups/
```

**Restore from backup:**
```bash
# Uncompress
gunzip ~/datawarp-backups/datawarp_prod_20260113_120000.sql.gz

# Restore
psql -h localhost -U datawarp_prod_user -d datawarp_prod \
  < ~/datawarp-backups/datawarp_prod_20260113_120000.sql
```

---

## 📊 Monitoring Production

### Set Up Daily Health Check

Create a health check script:

```bash
nano ~/check_datawarp.sh
```

**Add this content:**

```bash
#!/bin/bash
cd ~/datawarp-prod
source .venv/bin/activate

echo "=== DataWarp Production Health Check ==="
echo "Date: $(date)"
echo

echo "1. Database connection:"
datawarp list | head -5

echo -e "\n2. Disk usage:"
df -h ~ | tail -1

echo -e "\n3. Recent errors:"
python scripts/analyze_logs.py --errors | tail -10

echo -e "\n4. Backfill status:"
python scripts/backfill.py --status | tail -10

echo -e "\n5. Database size:"
psql -h localhost -U datawarp_prod_user -d datawarp_prod -c \
  "SELECT pg_size_pretty(pg_database_size('datawarp_prod'));"
```

**Make it executable:**
```bash
chmod +x ~/check_datawarp.sh
```

**Run it:**
```bash
~/check_datawarp.sh
```

**Schedule it daily:**
```bash
# Add to crontab
crontab -e

# Add this line (runs daily at 8 AM):
0 8 * * * ~/check_datawarp.sh >> ~/datawarp_health.log 2>&1
```

---

## 📚 Quick Reference

### Essential Commands

| What | Command |
|------|---------|
| **Switch to production** | `cd ~/datawarp-prod && source .venv/bin/activate` |
| **Check database** | `datawarp list` |
| **Run backfill** | `python scripts/backfill.py` |
| **Check status** | `python scripts/backfill.py --status` |
| **View errors** | `python scripts/analyze_logs.py --errors` |
| **Export data** | `python scripts/export_to_parquet.py --publication adhd output/` |
| **Rebuild catalog** | `python scripts/rebuild_catalog.py` |
| **Clean orphans** | `python scripts/cleanup_orphans.py --execute` |
| **Database backup** | `pg_dump -h localhost -U datawarp_prod_user -d datawarp_prod > backup.sql` |

### File Locations

| What | Location |
|------|----------|
| **Production install** | `~/datawarp-prod/` |
| **Virtual environment** | `~/datawarp-prod/.venv/` |
| **Configuration** | `~/datawarp-prod/.env` |
| **Publications config** | `~/datawarp-prod/config/publications.yaml` |
| **Logs** | `~/datawarp-prod/logs/events/YYYY-MM-DD/` |
| **Output files** | `~/datawarp-prod/output/` |
| **State tracking** | `~/datawarp-prod/state/state.json` |
| **Manifests** | `~/datawarp-prod/manifests/production/` |

### Database Credentials

**Write these down securely:**
- Database: `datawarp_prod`
- User: `datawarp_prod_user`
- Password: `[what you set in Part 3]`
- Host: `localhost`
- Port: `5432`

---

## 🎉 You're Done!

**What you accomplished:**
✅ Created isolated production environment
✅ Separate Python virtual environment
✅ Separate PostgreSQL database
✅ Configured environment variables
✅ Initialized database schema
✅ Set up MCP server
✅ Loaded first production NHS dataset
✅ Configured monitoring and health checks

**Next Steps:**
1. Add more NHS publications to `config/publications.yaml`
2. Run `python scripts/backfill.py` to process them
3. Use Claude Desktop with MCP to query your production data
4. Set up automated backups (daily recommended)
5. Monitor logs with `analyze_logs.py`

**Questions or Issues?**
Check the Troubleshooting section above or refer to:
- `docs/BACKFILL_WORKFLOW.md` - Detailed backfill guide
- `docs/architecture/system_overview_20260110.md` - System architecture
- `docs/TASKS.md` - Current development status

---

**Created:** 2026-01-13
**Version:** 1.0
**For:** DataWarp v2.2
