# DataWarp v2.1 - Active Work Tracking

**Last Updated:** 2026-01-07
**Current Epic:** Phase 1 - Code Canonicalization & Registry

---

## Current Epic: Phase 1

**Goal:** Enable cross-period data consolidation via source canonicalization

**Status:** 🔄 IN PROGRESS (Week 1 of 2)

**Success Criteria:**
- [ ] apply_enrichment.py merges LLM codes → YAML
- [ ] fingerprint.py matches sources across periods
- [ ] Registry tables track canonical mappings
- [ ] ADHD Nov/Dec consolidate to same tables

---

## Task Breakdown

### ✅ Completed

- [x] **Setup:** Create v2.1 repo with clean structure
- [x] **Setup:** Implement documentation enforcement (12-doc limit)
- [x] **Setup:** Create CLAUDE.md with AI agent rules
- [x] **Setup:** Create ARCHITECTURE.md
- [x] **Setup:** Create PRODUCTION_SETUP.md
- [x] **Setup:** Optimize extractor.py (871 lines, -10 from original)
- [x] **Phase 1.1:** Create apply_enrichment.py (106 lines)
- [x] **Phase 1.2:** Create fingerprint.py (73 lines)
- [x] **Phase 1.3:** Create 04_create_registry_tables.sql (116 lines)

### 🔄 In Progress

- [ ] **Integration:** Update loader/pipeline.py to use fingerprinting
- [ ] **Test:** Apply enrichment to ADHD Nov25 manifest (pending test data)

### ⏳ Pending (Phase 1)

- [ ] **Test:** Load ADHD Nov + Dec, verify same canonical codes
- [ ] **Test:** Fingerprint matching with 80% threshold
- [ ] **Documentation:** Update current_phase.md with Phase 1 completion
- [ ] **Commit:** Phase 1 complete - canonical source registry

### 📋 Backlog (Phase 2 - Future)

- [ ] Create publication registry (tbl_publications)
- [ ] Implement URL discovery module
- [ ] Backfill workflow for 10 publications
- [ ] Email alerting system

---

## Blockers

**Current:** None

**Resolved:**
- ~~Documentation sprawl~~ → Fixed with 12-doc limit (2026-01-07)
- ~~extractor.py size concern~~ → Optimized to 871 lines (2026-01-07)

---

## Work Sessions

### 2026-01-07 - Migration & Setup
- Created v2.1 repo
- Migrated production code from v2
- Implemented documentation enforcement
- Created essential docs (CLAUDE.md, ARCHITECTURE.md, PRODUCTION_SETUP.md)
- Updated pre-commit hook to 12-doc limit

### 2026-01-08 - Phase 1 Implementation & Testing
- ✅ Implemented Phase 1 core modules:
  - scripts/apply_enrichment.py (109 lines) - Fixed URL matching bug
  - src/datawarp/registry/fingerprint.py (71 lines)
  - scripts/schema/04_create_registry_tables.sql (114 lines)
  - src/datawarp/core/csv_extractor.py (45 lines) - Created
  - src/datawarp/observability.py (33 lines) - Created
- ✅ Created comprehensive testing infrastructure:
  - docs/testing_plan.md (5 test scenarios, 600+ lines)
  - docs/test_results_phase1.md (execution log, 750+ lines)
  - docs/PHASE1_SUMMARY.md (complete summary)
- ✅ Tested with real NHS data (ADHD August 2025):
  - Generated manifest (16 sources discovered)
  - Enriched with Gemini (92% success - 12/13 codes cleaned)
  - Verified apply_enrichment works (13/16 matched)
- ❌ **Blocker Found:** XLSX/ZIP handling prevents data loading
- ❌ **Issue Found:** VARCHAR(50) too small for canonical codes
- **Next:** Fix XLSX handling blocker, then complete ADHD test

---

## Quick Commands

```bash
# Mark task complete
# Edit this file, change [ ] to [x]

# Move to next task
# Update "In Progress" section

# Add blocker
# Add to "Blockers" section with date

# Archive completed epic
# Move "Current Epic" to git commit message
# Update with next epic
```

---

**RULE:** This file is the single source of truth for current work.
**UPDATE:** Every work session (daily or per-major-change)
**REFERENCE:** CLAUDE.md points here for "what's current"
