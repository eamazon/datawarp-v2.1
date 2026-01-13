---
description: Initialize DataWarp v2.1 session
---

# DataWarp v2.1 Session Init

**Status:** 🎉 **PRIMARY OBJECTIVE COMPLETE - Agent Querying Proven!**
**Architecture:** Full pipeline validated + MCP server operational + Autonomous Supervisor designed
**Last Updated:** 2026-01-12 12:00 UTC

---

## 🤖 Agent Team (Say "run team" or "catch me up")

When user starts a session or asks for status, **automatically run parallel checks**:

| Agent | Check | Report |
|-------|-------|--------|
| Pipeline Guardian | `python scripts/backfill.py --status` | URLs processed/pending |
| Data Validator | Query `tbl_load_events` for recent loads | Failures, warnings |
| Cleanup Crew | `python scripts/cleanup_orphans.py` | Orphan counts |
| Test Runner | `pytest tests/ -q` | Pass/fail counts |
| MCP Quality | Check catalog.parquet exists | MCP readiness |

**Output format:**
```
## TEAM STANDUP

### CRITICAL (Fix Now)
- [issues] → [commands]

### WARNING (Fix Soon)
- [issues] → [recommendations]

### INFO (All Good)
- ✅ Component statuses

### RECOMMENDED NEXT ACTION
> Single most important thing
```

**Triggers:** "run team", "catch me up", "morning", "what's the status", "health check"

See: `.agent/workflows/team_lead.md` for full coordination logic
See: `config/agents.yaml` for individual agent prompts

---

## 🚨 Current Status (2026-01-12 12:00)

| Component | Status | Notes |
|-----------|--------|-------|
| **PRIMARY OBJECTIVE** | ✅ **COMPLETE** | **Agent querying proven! MCP server operational.** |
| **Autonomous Supervisor** | 📐 **DESIGNED** | **Architecture + 7-phase plan ready for implementation** |
| MCP Server | ✅ Complete | FastAPI server, 3 endpoints, natural language queries working |
| Error Pattern Discovery | ✅ Complete | 5 patterns: 404, no files, type mismatch, partial success, low row count |
| Validation Infrastructure | ✅ Complete | validate_manifest.py (URL checks), validate_loaded_data.py, compare_manifests.py |
| Fiscal Year Testing | ✅ Validated | +69 columns detected in April boundary, March→April→May tested |
| Load Mode Classifier | ✅ Complete | LoadModeClassifier with 95% confidence, 6 patterns detected |
| End-to-End Pipeline | ✅ Tested | Manifest→Enrich→Load→Export→Validation (211K rows exported) |
| Agent-Ready Data | ✅ Complete | 181 datasets, 75.8M rows, catalog.parquet operational |
| Session Logging | ✅ Enabled | Auto-logging to docs/sessions/session_YYYYMMDD.md |
| Git Status | ⚠️ Uncommitted | New: docs/design/*.md, docs/sessions/*.md |

**Latest Handover:** `docs/TASKS.md` (Session 14: Autonomous Supervisor Design)
**Next Priority:** **Option A: Implement Supervisor Phase 1 (Event System)** OR **Option B: MCP Quick Wins**

---

## ⚡ Next Session Priorities (Ordered A → B → C)

### **PRIORITY A: Implement Autonomous Supervisor Phase 1** ⭐ (USER'S VISION)

**Why:** User wants "mini Claude Code" - LLM that runs backfill, detects errors, investigates, fixes manifests, resumes

**Design Docs:**
- `docs/design/autonomous_supervisor_architecture.md` - Full architecture
- `docs/design/autonomous_supervisor_patterns.md` - Error patterns discovered

**Phase 1: Event System (2 hours):**
1. **Create event module:**
   ```bash
   mkdir -p src/datawarp/supervisor
   touch src/datawarp/supervisor/__init__.py
   touch src/datawarp/supervisor/events.py
   ```

2. **Implement EventStore:**
   - Event dataclass (run_id, timestamp, event_type, publication, period, source, stage, context)
   - JSONL writer to `logs/events/YYYY-MM-DD/run_*.jsonl`
   - Event types: run_started, source_started, error, warning, success, run_completed

3. **Integrate into backfill.py:**
   - Emit events at each stage (manifest, enrich, load, export)
   - Capture error context (stack trace, relevant state)
   - Test: `python scripts/backfill.py --config config/publications_test.yaml`

**Goal:** Structured event logging as foundation for LLM supervisor

---

### **PRIORITY B: MCP Quick Wins** (30 min)

**Why:** Fix critical bug + usability improvements

**Tasks:**
1. Fix get_metadata JSON serialization error (5 min)
2. Add get_schema() MCP tool (20 min)
3. Add dataset discovery tags to catalog (5 min)

**Goal:** get_metadata works, 95% first-time query success

---

### **PRIORITY C: Continue Backfill** (Expand NHS data)

**Why:** More data for conversational analytics

**Commands:**
```bash
# Edit config/publications.yaml (add URLs)
python scripts/backfill.py --dry-run  # Preview
python scripts/backfill.py            # Execute
```

**Goal:** Expand NHS data coverage

---

## 📚 Core Documentation (Read These Only)

**Essential (Read Every Session):**
1. `CLAUDE.md` - Project instructions, workflows, rules
2. `docs/TASKS.md` - Current status, session history, next steps
3. This file - Quick reference

**Vision & Strategy (Read When Planning):**
4. `docs/plans/features.md` ⭐ - **THE PRIMARY OBJECTIVE** (MCP, agent-ready data, Track A journal)
5. `docs/plans/AGENTIC_SOLUTION.md` - Cross-period solution design, NHS research

**Architecture (Reference):**
6. `docs/architecture/system_overview_20260110.md` - Complete system
7. `docs/architecture/cross_period_solution_20260110.md` - Cross-period patterns

**Testing (For Current Work):**
8. `docs/TESTING_STRATEGY.md` - Testing framework
9. `docs/TESTING_IMPLEMENTATION_PLAN.md` - Implementation plan

**Data Catalog:**
10. `output/CATALOG_README.md` - How to use exported datasets

**Note:** docs/plans/ is gitignored but contains critical vision docs - don't delete!

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
