# 🤖 START HERE - Agentic Entry Point

**Last Updated: 2026-01-10 17:45 UTC**

---

## 🎯 Decision Tree: What Should I Read?

### New Session Starting?

```
1. Read TASKS.md (5 min)
   ↓
2. Check current epic → Read relevant docs
   ↓
3. Follow session start protocol (CLAUDE.md)
   ↓
4. Begin work
```

### Specific Question?

**"What does DataWarp do?"**
→ `architecture/system_overview_20260110.md` (Section 1-3)

**"How do I run the pipeline?"**
→ `implementation/WORKFLOW.md` + `CLAUDE.md` (Essential Commands)

**"How does [feature] work?"**
→ Use search tree below

**"What should I work on next?"**
→ `TASKS.md` → Current Epic → Next Steps

**"What's the long-term plan?"**
→ `IMPLEMENTATION_TASKS.md` (80+ tasks, 4 priorities)

---

## 📚 Documentation Map (Agentic Perspective)

### Layer 1: Context (Read FIRST)

**Essential (Every Session):**
1. **TASKS.md** - What's current? What's blocked? What's next?
2. **CLAUDE.md** - Project rules, workflows, commands

**Vision (When Planning):**
3. **plans/features.md** - PRIMARY OBJECTIVE, Track A journal
4. **plans/AGENTIC_SOLUTION.md** - Cross-period strategy

### Layer 2: Understanding (Read WHEN NEEDED)

**Architecture (How System Works):**
- `architecture/system_overview_20260110.md` - Complete system design
- `architecture/cross_period_solution_20260110.md` - Cross-period patterns
- `architecture/ARCHITECTURE.md` - Original design doc
- `architecture/CANONICAL_FIX_DESIGN.md` - Phase 1 design
- `architecture/PRODUCTION_SETUP.md` - Deployment guide
- `architecture/SQL_STANDARDS.md` - SQL conventions

**Implementation (How To Do Things):**
- `implementation/WORKFLOW.md` - Proven patterns for common tasks
- `implementation/DB_MANAGEMENT_FRAMEWORK.md` - Production DB management
- `implementation/LOAD_MODE_STRATEGY.md` - Append vs Replace logic

**Testing (How To Validate):**
- `testing/TESTING_STRATEGY.md` - Overall testing philosophy
- `testing/TESTING_GOALS_AND_EVIDENCE.md` - 8 S.M.A.R.T. goals
- `testing/TESTING_IMPLEMENTATION_PLAN.md` - How to implement testing

### Layer 3: Evidence (Read WHEN VALIDATING)

**Test Results:**
- `testing/ADHD_TEMPORAL_TESTING.md` - Temporal evolution testing
- `testing/E2E_FISCAL_TEST_RESULTS.md` - Fiscal boundary testing
- `testing/FISCAL_TESTING_FINDINGS.md` - Fiscal year insights
- `testing/AGENTIC_TEST_RESULTS.md` - MCP agentic tests (89% pass)
- `testing/MCP_PROTOTYPE_RESULTS.md` - MCP server validation
- `testing/VALIDATION_TEST_FINDINGS.md` - Validation infrastructure

### Layer 4: History (Read WHEN INVESTIGATING)

**Archive (Old Sessions):**
- `archive/SESSION_5_SUMMARY.md` - Session 5 notes
- `archive/PHASE1_SUMMARY.md` - Phase 1 completion
- `archive/test_results_phase1.md` - Phase 1 test results
- `archive/scratch.md` - Historical scratch notes

**Handovers:**
- `handovers/handover_YYYYMMDD_HHMM.md` - Session handoffs

---

## 🔍 Search Tree (Find Information Fast)

### "How do I...?"

**Load data:**
1. Check `CLAUDE.md` → "Essential Commands" → datawarp load-batch
2. For workflow: `implementation/WORKFLOW.md`
3. For issues: `TASKS.md` → Blockers

**Test the system:**
1. Check `testing/TESTING_STRATEGY.md` → Test Pyramid
2. For specific tests: `testing/TESTING_GOALS_AND_EVIDENCE.md`
3. Run tests: `pytest tests/`

**Understand schema drift:**
1. Read `architecture/cross_period_solution_20260110.md` → Schema Drift section
2. For strategy: `implementation/LOAD_MODE_STRATEGY.md`
3. For evidence: `testing/FISCAL_TESTING_FINDINGS.md`

**Set up environment:**
1. Check `CLAUDE.md` → "Development Setup"
2. For production: `architecture/PRODUCTION_SETUP.md`

### "What is...?"

**DataWarp:**
→ `architecture/system_overview_20260110.md` → Section 1 (Executive Summary)

**Primary Objective:**
→ `plans/features.md` → Track A (MCP server + agent querying)

**Phase 1:**
→ `architecture/CANONICAL_FIX_DESIGN.md` OR `archive/PHASE1_SUMMARY.md`

**LoadModeClassifier:**
→ `implementation/LOAD_MODE_STRATEGY.md`

**Fiscal Boundary:**
→ `testing/FISCAL_TESTING_FINDINGS.md` OR `testing/E2E_FISCAL_TEST_RESULTS.md`

### "Where is...?"

**Code locations:**
- Core pipeline: `src/datawarp/loader/pipeline.py`
- Extractor: `src/datawarp/core/extractor.py`
- Schema naming: `src/datawarp/utils/schema.py`
- LoadModeClassifier: `src/datawarp/utils/load_mode_classifier.py`

**Scripts:**
- Manifest generation: `scripts/url_to_manifest.py`
- Enrichment: `scripts/enrich_manifest.py`
- Export: `scripts/export_to_parquet.py`
- Validation: `scripts/validate_*.py`

**Tests:**
- Unit: `tests/test_*.py`
- Integration: `tests/e2e/`
- MCP agentic: `tests/test_mcp_agentic.py`

---

## ⚡ Common Workflows (Quick Reference)

### Workflow 1: Load New Publication (First Time)

```bash
# 1. Generate manifest
python scripts/url_to_manifest.py <url> manifests/production/{pub}/{pub}_PERIOD.yaml

# 2. Enrich with LLM (NO --reference for first time)
python scripts/enrich_manifest.py \
  manifests/production/{pub}/{pub}_PERIOD.yaml \
  manifests/production/{pub}/{pub}_PERIOD_enriched.yaml

# 3. Load to database
datawarp load-batch manifests/production/{pub}/{pub}_PERIOD_enriched.yaml

# 4. Export to Parquet
python scripts/export_to_parquet.py --publication {pub} output/

# 5. Validate
python scripts/validate_parquet_export.py output/{pub}_*.parquet
```

**Success:** 6/6 validation tests passing

### Workflow 2: Load Subsequent Period (Cross-Period)

```bash
# 1. Generate manifest
python scripts/url_to_manifest.py <url> manifests/production/{pub}/{pub}_PERIOD2.yaml

# 2. Enrich with reference (USE --reference for consistency)
python scripts/enrich_manifest.py \
  manifests/production/{pub}/{pub}_PERIOD2.yaml \
  manifests/production/{pub}/{pub}_PERIOD2_canonical.yaml \
  --reference manifests/production/{pub}/{pub}_PERIOD1_enriched.yaml

# 3. Load, export, validate (same as above)
```

**Success:** Code consistency 80%+, validation tests passing

### Workflow 3: Test Schema Drift

```bash
# Compare two periods
python scripts/compare_manifests.py \
  manifests/test/{pub}_PERIOD1.yaml \
  manifests/test/{pub}_PERIOD2.yaml \
  --fiscal-boundary  # If testing fiscal boundary
```

**Output:** Common sources, additions, removals, schema consistency %

---

## 🚨 Red Flags (When to STOP and ASK)

### Stop If:

- [ ] Documentation is unclear (don't guess!)
- [ ] Success criteria undefined (what does "done" mean?)
- [ ] About to skip a validation gate
- [ ] Tempted to create new documentation file
- [ ] About to commit without running tests
- [ ] Load fails 3+ times (investigate, don't retry blindly)
- [ ] Celebrating row counts instead of test pass rates

### Ask User:

- **Before creating new docs:** "Which existing doc should this update?"
- **Before skipping validation:** "Can I proceed without validation?"
- **Before pivoting strategy:** "URLs return 404, what should I do?"
- **Before large refactor:** "Should I enter plan mode?"

---

## 📊 Success Metrics (Am I On Track?)

### Current Goals (Session 6)

- **MCP Server:** 17/18 tests passing (94%) ✓ Target: 95%
- **Load Success:** 89% ⚠️ Target: 95%
- **Metadata Coverage:** 95% ✓ Target: 90%
- **Cross-Period Consistency:** 100% ✓ Target: 80%

See `testing/TESTING_GOALS_AND_EVIDENCE.md` for all 8 goals.

### How to Check:

```bash
# Load success rate (last 7 days)
psql -c "SELECT COUNT(*) FILTER (WHERE load_status='completed')*100.0/COUNT(*)
         FROM datawarp.tbl_load_events
         WHERE started_at > NOW() - INTERVAL '7 days';"

# Metadata coverage
psql -c "SELECT COUNT(*) FILTER (WHERE description IS NOT NULL)*100.0/COUNT(*)
         FROM datawarp.tbl_column_metadata;"

# Run MCP tests
pytest tests/test_mcp_agentic.py -v
```

---

## 🎯 Current State Snapshot

**Epic:** PRIMARY OBJECTIVE COMPLETE - Agent Querying Validated
**Session:** 6 (2026-01-10)
**Database:** 173 sources registered
**Agent-Ready Data:** 65 datasets + 12 PCN fiscal exports
**MCP Server:** Operational (94% test pass rate)

**Next Round:**
- DB Management Framework (80+ tasks in IMPLEMENTATION_TASKS.md)
- Testing Goals Framework
- Correct fiscal testing (March/April/May URLs needed)

---

## 🤔 Decision Heuristics (How Should I Think?)

### Mission Alignment

**Every action, ask:** "Does this move toward PRIMARY OBJECTIVE?"
- PRIMARY OBJECTIVE = Enable agents to query NHS data via MCP
- If NO → Reconsider, maybe it's not priority

### Validation-First Mindset

- ❌ "Loaded 3.4M rows" = NOT success
- ✅ "6/6 tests passing" = SUCCESS
- Always validate, never skip gates

### Documentation Discipline

- Max 5 docs in production (enforced by pre-commit hook)
- Update existing, don't create new
- Archive old docs, don't delete

### Conservative Defaults

- When uncertain: REPLACE mode (prevents duplicates)
- When failing: STOP and investigate (don't retry blindly)
- When blocked: ASK user (don't pivot silently)

---

## 📖 Reading Order (First Time)

**If you're completely new:**

1. **START_HERE.md** (this file, 10 min)
2. **CLAUDE.md** (project instructions, 20 min)
3. **TASKS.md** (current status, 10 min)
4. **architecture/system_overview_20260110.md** (Section 1-4, 30 min)
5. **plans/features.md** (PRIMARY OBJECTIVE, 15 min)

**Total:** ~90 minutes to full context

**Then:** You're ready to work! Follow session start protocol in CLAUDE.md.

---

## 🔄 This Document

**Purpose:** Agentic entry point for efficient system understanding

**Update When:**
- Major docs reorganized
- New critical document added
- Success criteria change
- Current state changes significantly

**Owner:** Keep synchronized with TASKS.md

---

*Last synchronized with TASKS.md: 2026-01-10 17:45 UTC*
