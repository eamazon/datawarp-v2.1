# Production Architecture - Container + Cloud Deployment

**Created:** 2026-01-13
**Status:** PROPOSAL

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                        INGESTION LAYER                              │
│                    (Local/WSL or Cheap VPS)                         │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐             │
│  │  DataWarp   │───▶│ PostgreSQL  │───▶│   Export    │             │
│  │  Container  │    │  Container  │    │  to Parquet │             │
│  └─────────────┘    └─────────────┘    └──────┬──────┘             │
│         │                                      │                    │
│         ▼                                      ▼                    │
│  ┌─────────────┐                      ┌─────────────┐              │
│  │ EventStore  │                      │   Upload    │              │
│  │    Logs     │                      │   to R2     │              │
│  └─────────────┘                      └──────┬──────┘              │
└──────────────────────────────────────────────┼──────────────────────┘
                                               │
                                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         HOSTING LAYER                               │
│                    (Cloudflare - FREE tier)                         │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────┐       │
│  │                   Cloudflare R2                          │       │
│  │              (S3-compatible storage)                     │       │
│  │                                                          │       │
│  │   /datasets/                                             │       │
│  │     ├── catalog.parquet          (dataset registry)     │       │
│  │     ├── adhd_summary.parquet     (ADHD data)           │       │
│  │     ├── gp_practice.parquet      (GP data)             │       │
│  │     └── ...                                             │       │
│  └─────────────────────────────────────────────────────────┘       │
│                              │                                      │
│                              ▼                                      │
│  ┌─────────────────────────────────────────────────────────┐       │
│  │               Cloudflare Workers                         │       │
│  │            (Serverless REST API)                         │       │
│  │                                                          │       │
│  │   GET /api/datasets          → List all datasets        │       │
│  │   GET /api/datasets/:id      → Get dataset metadata     │       │
│  │   GET /api/query             → Query with DuckDB-WASM   │       │
│  └─────────────────────────────────────────────────────────┘       │
│                              │                                      │
└──────────────────────────────┼──────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        CONSUMER LAYER                               │
│                                                                     │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐             │
│  │   Claude    │    │   Custom    │    │    Web      │             │
│  │   Desktop   │    │   Agents    │    │   Browser   │             │
│  │   (MCP)     │    │   (API)     │    │   (REST)    │             │
│  └─────────────┘    └─────────────┘    └─────────────┘             │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Component Breakdown

### 1. Ingestion Layer (Docker Compose)

**Purpose:** Process NHS data, load to PostgreSQL, export to Parquet

**Runs:** Locally on WSL, or on cheap VPS ($5/month)

**Components:**
- DataWarp container (Python app)
- PostgreSQL container (data storage)
- Shared volumes for manifests, exports, logs

```yaml
# docker-compose.yml
version: '3.8'

services:
  postgres:
    image: postgres:15
    environment:
      POSTGRES_DB: datawarp
      POSTGRES_USER: datawarp
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./scripts/schema:/docker-entrypoint-initdb.d
    ports:
      - "5432:5432"

  datawarp:
    build: .
    depends_on:
      - postgres
    environment:
      POSTGRES_HOST: postgres
      POSTGRES_DB: datawarp
      POSTGRES_USER: datawarp
      POSTGRES_PASSWORD: ${DB_PASSWORD}
      GEMINI_API_KEY: ${GEMINI_API_KEY}
    volumes:
      - ./config:/app/config
      - ./manifests:/app/manifests
      - ./data:/app/data
    command: ["python", "scripts/backfill.py"]

volumes:
  postgres_data:
```

### 2. Hosting Layer (Cloudflare FREE)

**Cloudflare R2 Storage:**
- 10 GB free storage
- 1 million requests/month free
- S3-compatible API
- No egress fees (!)

**Cloudflare Workers:**
- 100,000 requests/day free
- Serverless, scales automatically
- Can use DuckDB-WASM for queries

**Cost:** $0/month for moderate usage

### 3. Consumer Layer

**MCP Server:** Points to R2 or local PostgreSQL
**REST API:** Cloudflare Workers serving JSON
**Web UI:** Optional static site on Cloudflare Pages

---

## File Organization (Revised for Cloud)

```
datawarp-v2.1/
├── config/
│   ├── publications.yaml        # What to load
│   └── r2_sync.yaml             # What to upload to R2
│
├── manifests/
│   └── canonical/               # Schema definitions (git tracked)
│
├── data/                        # Local working data (NOT in git)
│   ├── exports/                 # Parquet files (sync to R2)
│   │   ├── catalog.parquet
│   │   └── *.parquet
│   ├── logs/                    # Event logs (local only)
│   └── state/                   # Processing state
│
├── docker/
│   ├── Dockerfile               # DataWarp container
│   ├── docker-compose.yml       # Full stack
│   └── docker-compose.dev.yml   # Development only
│
├── cloudflare/
│   ├── worker/                  # REST API worker
│   │   ├── src/index.ts
│   │   └── wrangler.toml
│   └── r2_upload.py             # Sync script
│
└── scripts/
    ├── backfill.py              # Main ingestion
    ├── export_and_sync.py       # Export + upload to R2
    └── analyze_logs.py          # Operational tools
```

---

## Deployment Workflows

### Initial Setup (One-time)

```bash
# 1. Clone repo
git clone <repo> datawarp
cd datawarp

# 2. Create .env
cp .env.example .env
# Edit with your credentials

# 3. Start containers
docker-compose up -d

# 4. Initialize database
docker-compose exec datawarp python scripts/reset_db.py

# 5. Setup Cloudflare (one-time)
# - Create R2 bucket: datawarp-nhs-data
# - Create Worker: nhs-data-api
# - Get R2 credentials for sync
```

### Daily Ingestion (Automated)

```bash
# Run via cron or manually
docker-compose exec datawarp python scripts/backfill.py

# Check results
docker-compose exec datawarp python scripts/analyze_logs.py

# Export and sync to Cloudflare
docker-compose exec datawarp python scripts/export_and_sync.py
```

### Cloudflare Worker (REST API)

```typescript
// cloudflare/worker/src/index.ts
import { DuckDB } from '@duckdb/duckdb-wasm';

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const url = new URL(request.url);

    if (url.pathname === '/api/datasets') {
      // List datasets from catalog.parquet
      const catalog = await env.R2_BUCKET.get('datasets/catalog.parquet');
      // Parse with DuckDB-WASM and return JSON
      return new Response(JSON.stringify(datasets));
    }

    if (url.pathname.startsWith('/api/query')) {
      // Execute query against parquet files
      const query = url.searchParams.get('sql');
      // Use DuckDB-WASM to query R2 parquet files
      return new Response(JSON.stringify(results));
    }

    return new Response('Not found', { status: 404 });
  }
};
```

---

## Cost Analysis

### Option A: Fully Local (WSL)
| Component | Cost |
|-----------|------|
| WSL | Free |
| PostgreSQL (Docker) | Free |
| Storage | Local disk |
| **Total** | **$0/month** |

Limitations: Only accessible locally

### Option B: Local + Cloudflare
| Component | Cost |
|-----------|------|
| WSL ingestion | Free |
| Cloudflare R2 (10GB) | Free |
| Cloudflare Workers | Free |
| **Total** | **$0/month** |

Benefits: Public API, global CDN, no egress fees

### Option C: VPS + Cloudflare (Production)
| Component | Cost |
|-----------|------|
| Hetzner VPS (CX11) | €4.50/month |
| Cloudflare R2 | Free |
| Cloudflare Workers | Free |
| **Total** | **~$5/month** |

Benefits: 24/7 ingestion, reliable, public API

---

## MCP Server Options

### Option 1: Local MCP → PostgreSQL
```python
# Current approach
# MCP server queries local PostgreSQL
# Works with Claude Desktop locally
```

### Option 2: Local MCP → R2 Parquet
```python
# MCP server fetches parquet from R2
# Uses DuckDB to query
# Works anywhere with internet
```

### Option 3: Remote MCP via Cloudflare
```typescript
// MCP protocol over Cloudflare Workers
// Claude Desktop connects to remote MCP
// Fully cloud-native
```

---

## Implementation Phases

### Phase 1: Dockerize (1-2 hours)
- [ ] Create Dockerfile
- [ ] Create docker-compose.yml
- [ ] Test local deployment
- [ ] Document setup steps

### Phase 2: Cloudflare Setup (1-2 hours)
- [ ] Create R2 bucket
- [ ] Create upload script
- [ ] Test sync workflow
- [ ] Create basic Worker API

### Phase 3: Production Workflow (2-3 hours)
- [ ] Automate daily ingestion
- [ ] Automate R2 sync
- [ ] Add monitoring/alerts
- [ ] Document operational procedures

### Phase 4: Enhanced API (Optional)
- [ ] DuckDB-WASM in Worker
- [ ] Query endpoint
- [ ] Rate limiting
- [ ] API documentation

---

## Quick Start Commands

```bash
# Start everything
docker-compose up -d

# Run backfill
docker-compose exec datawarp python scripts/backfill.py --dry-run
docker-compose exec datawarp python scripts/backfill.py

# Check status
docker-compose exec datawarp python scripts/analyze_logs.py

# Export to Cloudflare
docker-compose exec datawarp python scripts/export_and_sync.py

# View logs
docker-compose logs -f datawarp

# Stop everything
docker-compose down
```

---

## Decision Points

1. **Start with Docker Compose locally?** (Recommended)
2. **When to add Cloudflare?** (After Docker works)
3. **Need VPS or WSL-only?** (WSL fine for start)
4. **DuckDB-WASM in Workers?** (Nice to have, not required)

---

**Next Step:** Create Dockerfile and docker-compose.yml?
