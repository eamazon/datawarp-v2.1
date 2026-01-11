# DataWarp Pipeline Visuals

**Created:** 2026-01-11 UTC
**Purpose:** Collection of ASCII pipeline diagrams for quick reference

---

## Index

| Pipeline | File | Purpose |
|----------|------|---------|
| **E2E Data Pipeline** | `01_e2e_data_pipeline.md` | NHS Excel → Agent Querying |
| **MCP Architecture** | `02_mcp_architecture.md` | Multi-dataset MCP server design |
| **File Lifecycle** | `03_file_lifecycle.md` | File states, cleanup, archival |
| **Database Schema** | `04_database_schema.md` | Tables, relationships, audit trail |
| **Manifest Lifecycle** | `05_manifest_lifecycle.md` | Draft → Enriched → Loaded → Archived |
| **Backfill & Monitor** | `06_backfill_monitor.md` | Automated historical processing |

---

## Quick Reference: Core E2E Pipeline

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        DataWarp E2E Pipeline                                 │
└─────────────────────────────────────────────────────────────────────────────┘

  NHS Publication URL
         │
         ▼
  ┌──────────────┐     url_to_manifest.py
  │   Download   │     (~50ms per file)
  │  NHS Excel   │     Detects headers, merged cells, types
  └──────┬───────┘
         │
         ▼
  ┌──────────────┐     enrich_manifest.py
  │   Generate   │     First: LLM enrichment
  │   Manifest   │     Later: --reference for consistency
  └──────┬───────┘
         │
         ▼
  ┌──────────────┐     datawarp load-batch
  │    Load      │     Schema evolution, deduplication
  │  PostgreSQL  │     Row-level lineage (_load_id, _period)
  └──────┬───────┘
         │
         ▼
  ┌──────────────┐     export_to_parquet.py
  │   Export     │     Columnar format, metadata .md
  │   Parquet    │     rebuild_catalog.py
  └──────┬───────┘
         │
         ▼
  ┌──────────────┐     mcp_server/stdio_server.py
  │  MCP Server  │     list_datasets, get_metadata, query
  │   (stdio)    │     Official MCP SDK v1.25.0
  └──────┬───────┘
         │
         ▼
  ┌──────────────┐
  │   Claude     │     Natural language querying
  │   Desktop    │     75.8M rows accessible
  └──────────────┘
```

---

## How to Use These Diagrams

1. **Copy into docs** - Paste relevant diagrams into documentation
2. **Reference in PRs** - Link to specific pipeline when explaining changes
3. **Onboarding** - New team members start with E2E pipeline
4. **Debugging** - Find which stage has issues

---

*See individual files for detailed diagrams.*
