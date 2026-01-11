---
description: Agent Team - Invoke sub-agents for DataWarp tasks
---

# DataWarp Agent Team

**Purpose:** Delegate work to specialized agents instead of doing everything yourself.
**Updated:** 2026-01-11 17:00 UTC

---

## Quick Reference (Copy-Paste)

### Start of Session - Health Check
```
Run pipeline_guardian quick check:
1. python scripts/backfill.py --status
2. Check state/state.json for failures
3. Count sources in database
Report in 5 lines or less.
```

### After Data Load - Validate
```
Validate the last 5 loads in DataWarp:
1. Query tbl_load_events for recent loads
2. Flag 0-row loads as CRITICAL
3. Flag <100 row loads as WARNING
4. Verify staging tables exist
5-line report.
```

### Before Commit - Test + Review
```
Pre-commit checks:
1. pytest tests/ -v --tb=line
2. Check file sizes (extractor.py <900, insert.py <200)
3. Count docs: ls docs/*.md | wc -l (should be <=5)
4. git diff --stat
Report: Ready to commit or issues found.
```

### Weekly - Cleanup Audit
```
Weekly cleanup audit:
1. python scripts/cleanup_orphans.py --dry-run
2. Find sources not loaded in 7 days
3. Report orphans and stale items
DO NOT execute cleanup.
```

---

## Agent Descriptions

| Agent | Purpose | Trigger |
|-------|---------|---------|
| pipeline_guardian | Health check, backfill status | Session start |
| data_validator | Verify loads, check quality | After loads |
| test_runner | Run tests, catch regressions | Before commits |
| catalog_curator | Keep catalog.parquet fresh | After exports |
| cleanup_crew | Find orphans, stale data | Weekly |
| mcp_quality | Test MCP endpoints | After MCP changes |
| code_reviewer | Review changes, file limits | Before commits |

---

## How to Invoke Agents

In Claude Code, just describe what you need:

**"Run a health check"** → I'll invoke pipeline_guardian
**"Validate my last load"** → I'll invoke data_validator
**"Run tests before commit"** → I'll invoke test_runner
**"Find orphaned data"** → I'll invoke cleanup_crew
**"Test the MCP server"** → I'll invoke mcp_quality

Or be specific:
**"Run pipeline_guardian full audit"**
**"Run cleanup_crew and show stale sources"**

---

## Session Workflow with Agents

### Morning (2 min)
1. "Run health check" → pipeline_guardian
2. Review TASKS.md

### During Work
3. After load: "Validate that load" → data_validator
4. After export: "Update catalog" → catalog_curator

### Before Commit (3 min)
5. "Run tests" → test_runner
6. "Pre-commit review" → code_reviewer
7. Commit if clean

### Weekly (5 min)
8. "Find orphans" → cleanup_crew
9. "Catalog audit" → catalog_curator

---

## Agent Config File

Full agent prompts in: `config/agents.yaml`

Use for custom agent invocations or to understand what each does.
