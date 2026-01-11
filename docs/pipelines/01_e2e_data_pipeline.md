# E2E Data Pipeline

**Created:** 2026-01-11 UTC
**Purpose:** Complete data flow from NHS Excel to Agent Querying

---

## Complete Pipeline

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         DataWarp E2E Pipeline                               │
└─────────────────────────────────────────────────────────────────────────────┘

  NHS Publication URL
  https://digital.nhs.uk/...
         │
         ▼
  ┌──────────────┐     url_to_manifest.py
  │   Download   │     (~50ms per file)
  │  NHS Excel   │     Detects headers, merged cells, types
  └──────┬───────┘     Handles suppressed values (*, -, ..)
         │
         ▼
  ┌──────────────┐     enrich_manifest.py
  │   Generate   │     First: LLM enrichment (Gemini)
  │   Manifest   │     Later: --reference for consistency
  └──────┬───────┘     Output: source codes, column names
         │
         ▼
  ┌──────────────┐     datawarp load-batch
  │    Load      │     Schema evolution (auto-ALTER TABLE)
  │  PostgreSQL  │     Drift detection + validation
  └──────┬───────┘     Row-level lineage (_load_id, _period)
         │
         ▼
  ┌──────────────┐     export_to_parquet.py
  │   Export     │     Columnar format for fast querying
  │   Parquet    │     Metadata .md files
  └──────┬───────┘     rebuild_catalog.py
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

## Detailed Stage View

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              STAGE 1: EXTRACT                               │
└─────────────────────────────────────────────────────────────────────────────┘

NHS Excel File                           Output YAML Manifest
┌─────────────────────────┐             ┌───────────────────────────────┐
│ Sheet: "Main Data"      │             │ sheets:                       │
│ ┌─────────────────────┐ │             │   - name: Main Data           │
│ │     │ Q1  │ Q2  │Q3 │ │   ─────▶    │     columns:                  │
│ │     │2024 │2024 │..│  │ extractor   │       - name: Q1_2024         │
│ │─────┼─────┼─────┼───│ │     .py     │         type: INTEGER         │
│ │Age  │ 100 │ 150 │.. │ │             │       - name: Q2_2024         │
│ │Band │     │     │   │ │             │         type: INTEGER         │
│ └─────────────────────┘ │             │     row_count: 8149           │
│ [Merged cells detected] │             │     header_row: 2             │
└─────────────────────────┘             └───────────────────────────────┘


┌─────────────────────────────────────────────────────────────────────────────┐
│                              STAGE 2: ENRICH                                │
└─────────────────────────────────────────────────────────────────────────────┘

                      ┌─────────────────┐
                      │  Gemini API     │
                      │  (gemini-2.5-   │
                      │   flash-lite)   │
                      └────────┬────────┘
                               │ LLM generates
                               │ semantic names
                               ▼
Draft Manifest              Enriched Manifest
┌───────────────────┐       ┌───────────────────────────────┐
│ source:           │       │ source:                       │
│   code: sheet1    │  ──▶  │   code: adhd_prevalence_est   │
│   columns:        │       │   columns:                    │
│     - Q1_2024     │       │     - reporting_period        │
│     - Q2_2024     │       │       semantic: period_start  │
└───────────────────┘       │     - patient_count           │
                            │       semantic: adhd_patients │
                            └───────────────────────────────┘

For subsequent periods: --reference flag
┌───────────────────────────────────────────────────────────────────────────┐
│ python scripts/enrich_manifest.py nov25.yaml nov25_canonical.yaml \       │
│        --reference aug25_enriched.yaml                                    │
│                                                                           │
│ Result: Nov 2025 uses same codes as Aug 2025 → Cross-period consistency   │
└───────────────────────────────────────────────────────────────────────────┘


┌─────────────────────────────────────────────────────────────────────────────┐
│                              STAGE 3: LOAD                                  │
└─────────────────────────────────────────────────────────────────────────────┘

                    datawarp load-batch
Manifest                    │                      PostgreSQL
┌───────────────┐           │           ┌───────────────────────────┐
│ sources:      │           │           │ staging.tbl_adhd_prev     │
│   - adhd_prev │           │           │ ┌───────────────────────┐ │
│     columns:  │     ──────┼──────▶    │ │ age_band │ count │... │ │
│       - age   │           │           │ │──────────┼───────┼─── │ │
│       - count │           │           │ │ 0-17     │ 15000 │    │ │
│               │           │           │ │ 18-24    │ 8500  │    │ │
└───────────────┘           │           │ └───────────────────────┘ │
                            │           │                           │
                Schema Evolution        │ + _load_id (lineage)      │
                ┌───────────────────┐   │ + _source_file (audit)    │
                │ New column found? │   └───────────────────────────┘
                │ → ALTER TABLE ADD │
                │ Missing column?   │           datawarp.tbl_data_sources
                │ → INSERT NULL     │           ┌──────────────────────┐
                └───────────────────┘           │ id │ code    │ table │
                                                │ 1  │ adhd_pr │ adhd  │
                                                └──────────────────────┘


┌─────────────────────────────────────────────────────────────────────────────┐
│                              STAGE 4: EXPORT                                │
└─────────────────────────────────────────────────────────────────────────────┘

PostgreSQL Tables                        Parquet + Metadata
┌───────────────────────┐               ┌────────────────────────────────┐
│ staging.tbl_adhd_prev │               │ output/                        │
│ staging.tbl_pcn_wf    │    ──────▶    │ ├── adhd_prevalence.parquet    │
│ staging.tbl_gp_reg    │  export_to    │ ├── adhd_prevalence.md         │
│ ...                   │  _parquet.py  │ ├── pcn_wf_fte.parquet         │
└───────────────────────┘               │ ├── pcn_wf_fte.md              │
                                        │ ├── catalog.parquet  ← Index   │
                                        │ └── ...                        │
                                        └────────────────────────────────┘

catalog.parquet schema:
┌────────────────────────────────────────────────────────────────────────────┐
│ source_code │ domain │ description │ row_count │ col_count │ file_path     │
│─────────────┼────────┼─────────────┼───────────┼───────────┼───────────────│
│ adhd_prev   │ mental │ ADHD prev.. │ 8149      │ 11        │ output/ad..   │
│ pcn_wf_fte  │ workf. │ PCN staff.. │ 50000     │ 15        │ output/pc..   │
└────────────────────────────────────────────────────────────────────────────┘


┌─────────────────────────────────────────────────────────────────────────────┐
│                              STAGE 5: MCP                                   │
└─────────────────────────────────────────────────────────────────────────────┘

                    MCP Server (stdio)
                    ┌───────────────────────────────────────────────────┐
                    │                stdio_server.py                    │
                    │  ┌─────────────────────────────────────────────┐  │
                    │  │              Tools Available                │  │
                    │  │  ┌───────────────┐  ┌──────────────┐        │  │
                    │  │  │ list_datasets │  │ get_metadata │        │  │
                    │  │  │ search by     │  │ returns cols │        │  │
                    │  │  │ keyword/      │  │ types, desc  │        │  │
                    │  │  │ domain        │  │ sample data  │        │  │
                    │  │  └───────────────┘  └──────────────┘        │  │
                    │  │  ┌───────────────┐                          │  │
                    │  │  │    query      │                          │  │
                    │  │  │ SQL via       │                          │  │
                    │  │  │ DuckDB        │                          │  │
                    │  │  └───────────────┘                          │  │
                    │  └─────────────────────────────────────────────┘  │
                    └──────────────────────┬────────────────────────────┘
                                           │
                                           │ MCP Protocol (stdio)
                                           ▼
                    ┌───────────────────────────────────────────────────┐
                    │                Claude Desktop                     │
                    │  "What is the ADHD prevalence by age group?"      │
                    │                                                   │
                    │  1. list_datasets(keyword="adhd")                 │
                    │  2. get_metadata("adhd_prevalence_estimate")      │
                    │  3. query(dataset, "SELECT age_band, ...")        │
                    │  4. Return formatted answer to user               │
                    └───────────────────────────────────────────────────┘
```

---

## Quick Command Reference

```bash
# Full E2E pipeline for a new publication
python scripts/url_to_manifest.py <url> adhd_aug25.yaml
python scripts/enrich_manifest.py adhd_aug25.yaml adhd_aug25_enriched.yaml
datawarp load-batch adhd_aug25_enriched.yaml
python scripts/export_to_parquet.py --publication adhd output/
python scripts/rebuild_catalog.py

# For subsequent periods (use --reference)
python scripts/url_to_manifest.py <url> adhd_nov25.yaml
python scripts/enrich_manifest.py adhd_nov25.yaml adhd_nov25_canonical.yaml \
       --reference adhd_aug25_enriched.yaml
datawarp load-batch adhd_nov25_canonical.yaml
python scripts/export_to_parquet.py --publication adhd output/
```

---

## Current Stats

| Stage | Count | Notes |
|-------|-------|-------|
| Sources Registered | 182 | In datawarp.tbl_data_sources |
| Tables Created | 181 | In staging schema |
| Parquet Files | 179 | In output/ |
| Total Rows | 75.8M | Across all tables |
| Database Size | 15 GB | PostgreSQL |
| Parquet Size | 204 MB | Columnar compression |

---

*See E2E_PIPELINE_STATUS.md for detailed stage analysis and gap tracking.*
