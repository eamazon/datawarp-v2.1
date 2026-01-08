# DataWarp v2.1 - Changelog & Lessons Learned

**Purpose:** Track major changes, decisions, and lessons learned across versions.

**Format:**
```
## [Version] - YYYY-MM-DD
### Added / Changed / Fixed / Removed
- Description
- **Lesson Learned:** Why this change was made
```

---

## [2.1.0] - 2026-01-07

### Added
- **Documentation enforcement** via pre-commit hook (12-doc limit)
  - **Lesson:** v2 had 50+ docs, impossible to maintain
  - **Solution:** Category-based limits prevent sprawl

- **TASKS.md** for cross-session work tracking
  - **Lesson:** Work gets lost between sessions without persistent tracking
  - **Solution:** Single source of truth for current epic/tasks

- **SQL_STANDARDS.md** with ANSI SQL + Microsoft best practices
  - **Lesson:** Inconsistent SQL formatting across files
  - **Solution:** Enforce standards via documentation + future linting

- **apply_enrichment.py** workflow step
  - **Lesson:** LLM enrichment was being wasted - codes never applied
  - **Problem:** Nov → `tbl_summary_nov25_table_1`, Dec → `tbl_summary_dec25_table_1` (12 tables/year!)
  - **Solution:** Merge enriched codes back into YAML before loading

- **Fingerprinting module** for cross-period source matching
  - **Lesson:** Can't rely on LLM to generate identical codes across periods
  - **Solution:** Structural fingerprinting (MD5 hash of columns) + Jaccard similarity

### Changed
- **Optimized extractor.py** from 881 → 871 lines (-10 lines)
  - Added row caching for performance
  - Early exit logic in sheet classification
  - 100-row limit in data end detection
  - **Performance:** ~50ms per sheet (was ~80ms)

- **Documentation limit** from 5 → 12 docs (category-based)
  - **Lesson:** 5 was too restrictive for real production
  - **Solution:** Categories (Essential, Operations, Development, Reference)

### Fixed
- **Date-embedded codes breaking continuity**
  - Problem: `msds_sep2025` → `msds_oct2025` (separate tables)
  - Fix: apply_enrichment.py + canonicalization
  - Impact: Single table across all periods

### Removed
- **All experimental manifests** (50+ files from v2)
- **Versioned documentation** (v1, v2, v3 docs)
- **Session handover files** (HANDOVER_*.md)
- **Development specs** (DATAWARP_V2_SPEC_FINAL.md)
- **Old Qwen versions** (v1, v2 docs - kept v3 only)

---

## Lessons Learned (General)

### Documentation

**Problem:** AI agents generate tons of docs, hard to maintain
**Solution:**
1. Hard limit (12 docs max, enforced by pre-commit hook)
2. Categories prevent "just one more doc" syndrome
3. Update in place, never version (v1, v2, v3)
4. Prefer code comments over separate docs

### Work Tracking

**Problem:** Lose context between sessions, unclear what's done
**Solution:**
1. TASKS.md for cross-session persistence
2. TodoWrite for in-session real-time tracking
3. Git commits for historical record
4. CHANGELOG.md for major decisions (this file)

### SQL Standards

**Problem:** Inconsistent formatting, hard to read/maintain
**Solution:**
1. Document standards (SQL_STANDARDS.md)
2. Enforce via code review (manual for now)
3. Future: Add SQL linting to pre-commit hook

### Virtual Environment

**Problem:** Package conflicts, "works on my machine"
**Solution:**
1. Mandatory .venv enforcement (pre-commit hook)
2. All commands documented with venv activation
3. CLAUDE.md warns AI agents to always use .venv

---

## Decision Log

### 2026-01-07: Use LLM Enrichment, Don't Replace It

**Decision:** Keep LLM enrichment, add canonicalization step AFTER
**Alternative Considered:** Pure deterministic code generation (no LLM)
**Rationale:**
- LLM semantic naming is too valuable (`adhd_summary_waiting_assessment_age` vs `table_1`)
- LLM consolidation works well (30 sheets → 20 sources)
- Problem wasn't the LLM, it was not using its output
- Solution: apply_enrichment.py bridges the gap

**Files Affected:** scripts/apply_enrichment.py (new)

### 2026-01-07: 12-Doc Limit (Not 5)

**Decision:** Cap at 12 docs across 4 categories
**Alternative Considered:** Hard 5-doc limit
**Rationale:**
- Real production needs: troubleshooting guides, SQL standards, monitoring docs
- 5 too restrictive, 100 too many
- Categories prevent "overflow" to scratch.md
- Still enforces minimalism via pre-commit hook

**Files Affected:** .git/hooks/pre-commit

### 2026-01-07: Fingerprinting Over Deterministic Code Generation

**Decision:** Use column fingerprints (MD5) + Jaccard similarity
**Alternative Considered:** Deterministic code generation from filename patterns
**Rationale:**
- Filenames change unpredictably (Nov25, November_2025, nov-25)
- Column structure is more stable than filenames
- Handles reordered columns (sorted before hashing)
- 80% threshold allows minor drift while maintaining matches

**Files Affected:** src/datawarp/registry/fingerprint.py (new)

---

## Template for New Entries

```markdown
## [Version] - YYYY-MM-DD

### Added
- Feature X
  - **Lesson:** Why this was needed
  - **Impact:** What problem it solves

### Changed
- Modified Y
  - **Before:** Old behavior
  - **After:** New behavior
  - **Reason:** Why the change

### Fixed
- Bug Z
  - **Problem:** What was broken
  - **Root Cause:** Why it broke
  - **Fix:** How we fixed it

### Removed
- Deprecated A
  - **Reason:** Why removed
  - **Migration:** How to adapt

---

## Decision: [Decision Name]

**Decision:** What we decided
**Alternative Considered:** Other options
**Rationale:** Why this choice
**Files Affected:** Which files changed
**Date:** YYYY-MM-DD
```
---

**Update This File:**
- On major version changes (2.1 → 2.2)
- When adding significant features (Phase 1, Phase 2)
- When making architectural decisions
- When fixing critical bugs
- When learning important lessons

**Don't Update For:**
- Minor bug fixes
- Typo corrections
- Documentation updates (unless policy changes)
- Routine maintenance

**Commit Message When Updating:**
```
chore: update CHANGELOG for v2.1.0 Phase 1 completion

Added lessons learned for canonicalization approach
Documented decision to use fingerprinting over deterministic generation
```
