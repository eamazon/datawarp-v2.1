# DataWarp Deployment Starter Guide

**For developers new to containerized deployment**

---

## What You're Deploying

```
┌─────────────────────────────────────────────────────────┐
│                    Your WSL Machine                      │
│                                                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │  PostgreSQL  │  │   DataWarp   │  │  MCP Server  │  │
│  │  (Database)  │◄─│   (Python)   │  │  (API)       │  │
│  │  Port 5432   │  │              │  │  Port 8080   │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  │
│         │                                     │         │
│         └─────────── Docker Network ──────────┘         │
└─────────────────────────────────────────────────────────┘
```

---

## Prerequisites

### 1. Install Docker Desktop (Windows)

1. Download from: https://www.docker.com/products/docker-desktop/
2. Install and restart Windows
3. Open Docker Desktop → Settings → Resources → WSL Integration
4. Enable integration with your WSL distro (e.g., Ubuntu)
5. Click "Apply & Restart"

### 2. Verify Docker in WSL

Open your WSL terminal:

```bash
# Check Docker is working
docker --version
docker-compose --version

# You should see version numbers, not errors
```

---

## Deployment Steps

### Step 1: Navigate to Project

```bash
cd /path/to/datawarp-v2.1
```

### Step 2: Create Environment File

```bash
# Copy the example file
cp .env.example .env

# Edit with your settings
nano .env
```

**Required settings in `.env`:**

```bash
# Database credentials (change the password!)
POSTGRES_DB=datawarp
POSTGRES_USER=datawarp
POSTGRES_PASSWORD=your_secure_password_here

# Keep these as-is
POSTGRES_PORT=5432
DATABASE_TYPE=postgres

# Optional: For LLM enrichment
GEMINI_API_KEY=your_gemini_key_here
```

### Step 3: Start Everything

```bash
# Build and start all containers
docker-compose up -d

# Check they're running
docker-compose ps
```

You should see:
```
NAME              STATUS
datawarp-db       Up (healthy)
datawarp-app      Up
datawarp-mcp      Up
```

### Step 4: Initialize Database

```bash
# Run database setup
docker-compose exec datawarp python scripts/reset_db.py
```

---

## Daily Operations

### Run a Backfill

```bash
# Dry run first (see what would happen)
docker-compose exec datawarp python scripts/backfill.py \
  --config config/publications.yaml --dry-run

# Actually run it
docker-compose exec datawarp python scripts/backfill.py \
  --config config/publications.yaml
```

### Check Load Status

```bash
# View recent loads
docker-compose exec datawarp python scripts/analyze_logs.py --all

# See errors only
docker-compose exec datawarp python scripts/analyze_logs.py --errors

# Get restart commands for failed loads
docker-compose exec datawarp python scripts/analyze_logs.py --restart
```

### Query via MCP

```bash
# Test MCP is working
curl http://localhost:8080/

# List datasets
curl -X POST http://localhost:8080/mcp \
  -H "Content-Type: application/json" \
  -d '{"method": "list_datasets", "params": {}}'
```

---

## Common Commands Cheatsheet

| What you want | Command |
|---------------|---------|
| Start everything | `docker-compose up -d` |
| Stop everything | `docker-compose down` |
| View logs | `docker-compose logs -f` |
| Enter datawarp shell | `docker-compose exec datawarp bash` |
| Restart a service | `docker-compose restart datawarp` |
| Rebuild after code changes | `docker-compose build && docker-compose up -d` |
| Check disk usage | `docker system df` |
| Clean unused images | `docker system prune` |

---

## Troubleshooting

### "Cannot connect to Docker daemon"

Docker Desktop isn't running. Open Docker Desktop on Windows.

### "Port 5432 already in use"

Another PostgreSQL is running. Either:
- Stop it: `sudo service postgresql stop`
- Or change port in `.env`: `POSTGRES_PORT=5433`

### "Permission denied"

```bash
# Add yourself to docker group
sudo usermod -aG docker $USER

# Log out and back in, or run:
newgrp docker
```

### Container keeps restarting

```bash
# Check what's wrong
docker-compose logs datawarp

# Common fix: rebuild
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

### Database connection failed

```bash
# Check PostgreSQL is healthy
docker-compose ps

# If not healthy, check logs
docker-compose logs postgres

# Recreate the database
docker-compose down -v  # WARNING: Deletes all data!
docker-compose up -d
```

---

## Data Persistence

Your data is stored in:

| Data | Location | Persists across restarts? |
|------|----------|---------------------------|
| PostgreSQL data | Docker volume `datawarp-postgres-data` | ✅ Yes |
| Manifests | `./manifests/` | ✅ Yes (on disk) |
| Exports | `./data/exports/` | ✅ Yes (on disk) |
| Logs | `./data/logs/` | ✅ Yes (on disk) |

**To backup the database:**

```bash
docker-compose exec postgres pg_dump -U datawarp datawarp > backup.sql
```

**To restore:**

```bash
cat backup.sql | docker-compose exec -T postgres psql -U datawarp datawarp
```

---

## Next Steps

1. **Test locally first** - Run a small backfill, verify data loads
2. **Set up monitoring** - Check logs regularly with `analyze_logs.py`
3. **Schedule backfills** - Add cron job for automated runs
4. **Export for Cloudflare** - When ready, export parquet and upload to R2

---

## Quick Validation

Run this to verify everything works:

```bash
# 1. Check containers
docker-compose ps

# 2. Check database
docker-compose exec datawarp python -c "
from datawarp.storage.connection import get_connection
with get_connection() as conn:
    cur = conn.cursor()
    cur.execute('SELECT COUNT(*) FROM datawarp.tbl_data_sources')
    print(f'Datasets in database: {cur.fetchone()[0]}')
"

# 3. Check MCP
curl -s http://localhost:8080/ | python -m json.tool
```

If all three work, you're deployed! 🎉

---

**Created:** 2026-01-13
