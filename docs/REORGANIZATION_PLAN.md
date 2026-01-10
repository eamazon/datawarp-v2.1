# Documentation Reorganization Plan

**Created: 2026-01-10 17:45 UTC**

## Current State: 22 files in docs/ root (CHAOS)

## Proposed Structure

```
docs/
├── TASKS.md                          ← KEEP (Quick Reference: Current status)
├── IMPLEMENTATION_TASKS.md           ← KEEP (Quick Reference: Next round backlog)
│
├── architecture/                     📐 Architecture & Design
│   ├── system_overview_20260110.md
│   ├── cross_period_solution_20260110.md
│   ├── ARCHITECTURE.md
│   ├── CANONICAL_FIX_DESIGN.md
│   ├── PRODUCTION_SETUP.md
│   └── SQL_STANDARDS.md
│
├── testing/                          🧪 Testing Strategy & Results
│   ├── TESTING_STRATEGY.md
│   ├── TESTING_GOALS_AND_EVIDENCE.md
│   ├── TESTING_IMPLEMENTATION_PLAN.md
│   ├── ADHD_TEMPORAL_TESTING.md
│   ├── E2E_FISCAL_TEST_RESULTS.md
│   ├── FISCAL_TESTING_FINDINGS.md
│   ├── VALIDATION_TEST_FINDINGS.md
│   ├── AGENTIC_TEST_RESULTS.md
│   └── MCP_PROTOTYPE_RESULTS.md
│
├── implementation/                   🔧 Implementation Plans & Frameworks
│   ├── DB_MANAGEMENT_FRAMEWORK.md
│   ├── LOAD_MODE_STRATEGY.md
│   └── WORKFLOW.md
│
├── archive/                          📦 Old Session Notes & Scratch
│   ├── SESSION_5_SUMMARY.md
│   ├── PHASE1_SUMMARY.md
│   ├── test_results_phase1.md
│   ├── testing_plan.md
│   └── scratch.md
│
└── plans/                            📝 Vision Documents (gitignored)
    ├── features.md
    └── AGENTIC_SOLUTION.md
```

## Quick Reference (2 files)

**docs/TASKS.md**
- Current epic and status
- Session history
- Active blockers
- What to work on NOW

**docs/IMPLEMENTATION_TASKS.md**
- Backlog for next round
- 80+ tasks organized by priority
- Estimated effort

## Actions Required

1. **Create folders**
   ```bash
   mkdir -p docs/testing docs/implementation docs/archive
   ```

2. **Move architecture docs**
   ```bash
   mv docs/ARCHITECTURE.md docs/architecture/
   mv docs/CANONICAL_FIX_DESIGN.md docs/architecture/
   mv docs/PRODUCTION_SETUP.md docs/architecture/
   mv docs/SQL_STANDARDS.md docs/architecture/
   ```

3. **Move testing docs**
   ```bash
   mv docs/TESTING_*.md docs/testing/
   mv docs/*_TEST*.md docs/testing/
   mv docs/VALIDATION_*.md docs/testing/
   mv docs/AGENTIC_TEST_RESULTS.md docs/testing/
   mv docs/MCP_PROTOTYPE_RESULTS.md docs/testing/
   mv docs/ADHD_TEMPORAL_TESTING.md docs/testing/
   ```

4. **Move implementation docs**
   ```bash
   mv docs/DB_MANAGEMENT_FRAMEWORK.md docs/implementation/
   mv docs/LOAD_MODE_STRATEGY.md docs/implementation/
   mv docs/WORKFLOW.md docs/implementation/
   ```

5. **Archive old docs**
   ```bash
   mv docs/SESSION_5_SUMMARY.md docs/archive/
   mv docs/PHASE1_SUMMARY.md docs/archive/
   mv docs/test_results_phase1.md docs/archive/
   mv docs/testing_plan.md docs/archive/
   mv docs/scratch.md docs/archive/
   ```

6. **Update CLAUDE.md references**
   - Update paths to moved docs
   - Keep "Core Documentation" section accurate

## Result

**Root docs/:** 2 files (TASKS.md, IMPLEMENTATION_TASKS.md)
**Organized:** 22 files across 4 folders
**Discoverable:** Clear purpose for each folder
**Maintainable:** New docs have obvious home
