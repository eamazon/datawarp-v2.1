---
description: Initialize DataWarp v2.1 session
---

# DataWarp v2.1 Session Init

**Status:** ✅ **Production-Ready with Testing Infrastructure**
**Architecture:** Clean, validated, tested foundations in place
**Last Updated:** 2026-01-10 11:30 UTC

---

## 🚨 Current Status (2026-01-10 11:30)

| Component | Status | Notes |
|-----------|--------|-------|
| Testing Infrastructure | ✅ Complete | validate_manifest.py, run_tests.sh, golden_datasets.yaml |
| Manifest Organization | ✅ Complete | production/test/archive structure, 5 prod manifests |
| Validation Scripts | ✅ Complete | 100% pass on production manifests |
| Canonical Workflow | ✅ Documented | CLAUDE.md with decision tree |
| Agent-Ready Data | ✅ Complete | 65 datasets, catalog.parquet, CATALOG_README.md |
| Git Status | ✅ Clean | All committed (commits: 83a2cee, 5baa3c0) |
| Database | ✅ Connected | 147 sources, ADHD/GP/PCN/Waiting Times loaded |

**Latest Handover:** `docs/TASKS.md` (2026-01-10 session summary)

---

## ⚡ Next Session Should Start With

1. **Read Core Docs** (5-10 minutes):
   - `docs/TASKS.md` - Current status and next steps
   - `CLAUDE.md` - Canonical workflow section (lines 136-211)
   - `docs/TESTING_STRATEGY.md` - Testing approach

2. **Verify State:**
   ```bash
   git status                              # Should be clean
   git log -n 3 --oneline                  # See recent commits
   python scripts/validate_manifest.py manifests/production/*/*.yaml
   ```

3. **Choose Next Priority:**
   - **Option 1:** Build validation scripts (validate_loaded_data.py, validate_parquet_export.py)
   - **Option 2:** Write first unit tests (test_schema.py, test_extractor.py)
   - **Option 3:** MCP prototype (Task D - agent querying)

---

## 📚 Core Documentation (Read These Only)

**Essential (Read Every Session):**
1. `CLAUDE.md` - Project instructions, workflows, rules
2. `docs/TASKS.md` - Current status, session history, next steps
3. This file - Quick reference

**Architecture (Read Once, Reference Often):**
4. `docs/architecture/system_overview_20260110.md` - Complete system
5. `docs/architecture/cross_period_solution_20260110.md` - Cross-period patterns

**Testing (For Current Work):**
6. `docs/TESTING_STRATEGY.md` - Testing framework
7. `docs/TESTING_IMPLEMENTATION_PLAN.md` - Implementation plan

**Data Catalog:**
8. `output/CATALOG_README.md` - How to use exported datasets

**Ignore:** Everything else (old handovers, archive/, LLM JSONs, etc.)

## Session Start Checklist

### 1. Activate Virtual Environment

```bash
cd /Users/speddi/projectx/datawarp-v2.1
source .venv/bin/activate && which python
# Should return: /Users/speddi/projectx/datawarp-v2.1/.venv/bin/python
```

### 2. Check Recent Changes

```bash
git status
git log -5 --oneline
```

### 3. Verify Database Connection

```bash
datawarp list-sources
```

### 4. Key Capabilities

**✅ Complete Features:**
- Deterministic column naming (no LLM variance)
- Collision detection with suffix
- Wide date pattern detection
- Optional unpivot transformation (`--unpivot`)
- Excel/CSV extraction with smart header detection
- Automatic schema evolution (drift detection)
- Row-level lineage tracking (`_load_id`, `_loaded_at`)
- Batch loading from YAML manifests
- Full audit trail

### 5. Key Files to Know

**Schema & Naming:**
- `src/datawarp/utils/schema.py` - Deterministic naming, collision detection

**Transform:**
- `src/datawarp/transform/unpivot.py` - Wide→Long transformation

**Core Pipeline:**
- `src/datawarp/loader/pipeline.py` - Main orchestration
- `src/datawarp/loader/batch.py` - Batch loading
- `src/datawarp/loader/ddl.py` - Table creation

**CLI:**
- `src/datawarp/cli/commands.py` - CLI interface

**Manifests:**
- `manifests/*.yaml` - Batch loading configurations

### 6. Database Schema

**Registry Tables:**
- `datawarp.tbl_data_sources` - Source registrations
- `datawarp.tbl_load_history` - Load audit trail
- `datawarp.tbl_manifest_files` - Batch loading tracker

**Data Tables:**
- `staging.*` - Auto-created from loads
- All include `_load_id`, `_loaded_at`, `_period`, `_manifest_file_id`

---

## Known Issues / Blockers

1. **LLM Enrichment Timeouts**: Gemini enrichment sometimes times out. Fallback to non-enriched manifest works.
2. **Model Deprecation**: `gemini-1.5-flash` deprecated, use `gemini-2.0-flash-exp` or `gemini-2.5-flash-lite`

## Next Steps (Optional)

1. **Parquet Export**: Add `datawarp export` command for Parquet output
2. **Auto-unpivot in Manifest**: Add `unpivot: true` option to manifest YAML
3. **LLM Model Update**: Update LLM client to use non-deprecated models
