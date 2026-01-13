# Autonomous Supervisor - Architecture Design

**Created:** 2026-01-12 11:30 UTC
**Status:** DRAFT - Awaiting Review
**Author:** Claude (with user vision)

---

## Vision

Build a "mini Claude Code" that autonomously operates the DataWarp backfill pipeline:
- Runs pipeline steps
- Detects and classifies errors
- Investigates root causes (DB, manifests, web pages)
- Generates human-readable troubleshooting reports
- Fixes manifests (NOT code)
- Resumes from exact failure point
- Tracks everything for observability

---

## Current Problems

### 1. Poor Error Capture
```
"error": "See output above"  ← Useless for automation
```

### 2. Coarse State Tracking
```json
{
  "failed": {
    "adhd/nov25": {}  ← No per-source granularity
  }
}
```

### 3. No Structured Logging
```
DEBUG CELL TYPES: column_a → types: {'s'}  ← Unstructured, unparseable
```

### 4. No Traceability
- Can't follow a URL through all stages
- Can't correlate errors with context
- Can't replay or debug past runs

### 5. No Observability
- No metrics (duration, success rate, row counts)
- No dashboards
- No alerting

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         AUTONOMOUS SUPERVISOR                                │
│                                                                              │
│  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐                 │
│  │   ORCHESTRATOR │  │  ERROR HANDLER │  │  INVESTIGATOR  │                 │
│  │                │  │                │  │                │                 │
│  │ - Run stages   │  │ - Classify     │  │ - Gather ctx   │                 │
│  │ - Checkpoint   │  │ - Route        │  │ - Web fetch    │                 │
│  │ - Resume       │  │ - Retry logic  │  │ - DB query     │                 │
│  └───────┬────────┘  └───────┬────────┘  └───────┬────────┘                 │
│          │                   │                   │                          │
│          ▼                   ▼                   ▼                          │
│  ┌──────────────────────────────────────────────────────────────┐           │
│  │                      EVENT BUS                                │           │
│  │  (All components emit and consume structured events)          │           │
│  └──────────────────────────────────────────────────────────────┘           │
│          │                   │                   │                          │
│          ▼                   ▼                   ▼                          │
│  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐                 │
│  │   EVENT STORE  │  │  STATE STORE   │  │  REPORT GEN    │                 │
│  │                │  │                │  │                │                 │
│  │ - All events   │  │ - Granular     │  │ - Troubleshoot │                 │
│  │ - Queryable    │  │ - Checkpoints  │  │ - Summary      │                 │
│  │ - Replayable   │  │ - Per-source   │  │ - Markdown     │                 │
│  └────────────────┘  └────────────────┘  └────────────────┘                 │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           PIPELINE STAGES                                    │
│                                                                              │
│  ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐                  │
│  │ MANIFEST │──▶│ ENRICH   │──▶│  LOAD    │──▶│ EXPORT   │                  │
│  │          │   │          │   │          │   │          │                  │
│  │ url_to_  │   │ enrich_  │   │ datawarp │   │ export_  │                  │
│  │ manifest │   │ manifest │   │ load     │   │ parquet  │                  │
│  └──────────┘   └──────────┘   └──────────┘   └──────────┘                  │
│       │              │              │              │                         │
│       ▼              ▼              ▼              ▼                         │
│  ┌──────────────────────────────────────────────────────────────┐           │
│  │                 STRUCTURED EVENT EMITTER                      │           │
│  │  (Each stage emits events with full context)                  │           │
│  └──────────────────────────────────────────────────────────────┘           │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Part 1: Structured Event System

### Event Schema

Every pipeline event follows this structure:

```json
{
  "event_id": "evt_abc123",
  "run_id": "run_20260112_103000",
  "timestamp": "2026-01-12T10:30:15.123Z",

  "context": {
    "publication": "adhd",
    "period": "nov25",
    "url": "https://digital.nhs.uk/...",
    "source_code": "adhd_summary_open_referrals",
    "stage": "load"
  },

  "event_type": "stage_completed | stage_failed | warning | info",

  "data": {
    "rows_loaded": 450,
    "duration_ms": 1234,
    "columns_added": ["new_col_1"]
  },

  "error": {
    "type": "type_mismatch",
    "message": "INTEGER column received unexpected value '*'",
    "column": "headcount_march_2020",
    "file": "PCNW June 2025.xlsx",
    "sheet": "Table 2b",
    "row": 15,
    "stacktrace": "..."
  }
}
```

### Event Types

| Event Type | When Emitted | Key Data |
|------------|--------------|----------|
| `run_started` | Backfill begins | config_file, total_urls |
| `url_started` | Processing URL begins | url, publication, period |
| `stage_started` | Stage begins | stage_name, inputs |
| `stage_completed` | Stage succeeds | outputs, duration_ms, rows |
| `stage_failed` | Stage fails | error object with full context |
| `source_loaded` | Single source loaded | source_code, rows, table_name |
| `source_skipped` | Source skipped | reason (already loaded, disabled) |
| `source_failed` | Source failed | error with column/row context |
| `warning` | Non-fatal issue | message, context |
| `url_completed` | URL fully processed | summary stats |
| `url_failed` | URL processing failed | error, partial_state |
| `run_completed` | Backfill finished | summary stats |

### Event Store

**File-based (simple, sufficient for now):**
```
logs/
├── events/
│   ├── 2026-01-12/
│   │   ├── run_20260112_103000.jsonl  # One event per line
│   │   └── run_20260112_143000.jsonl
│   └── latest.jsonl  # Symlink to most recent
└── summaries/
    └── 2026-01-12_summary.json  # Daily rollup
```

**JSONL format (one event per line, easy to parse/stream):**
```jsonl
{"event_id":"evt_001","event_type":"run_started","timestamp":"...","data":{...}}
{"event_id":"evt_002","event_type":"url_started","timestamp":"...","context":{...}}
{"event_id":"evt_003","event_type":"stage_completed","timestamp":"...","data":{...}}
```

**Future: Database table** (if needed for querying)
```sql
CREATE TABLE datawarp.tbl_pipeline_events (
    id SERIAL PRIMARY KEY,
    event_id VARCHAR(50) UNIQUE,
    run_id VARCHAR(50),
    timestamp TIMESTAMPTZ,
    publication VARCHAR(100),
    period VARCHAR(20),
    source_code VARCHAR(100),
    stage VARCHAR(50),
    event_type VARCHAR(50),
    data JSONB,
    error JSONB
);

CREATE INDEX idx_events_run ON tbl_pipeline_events(run_id);
CREATE INDEX idx_events_source ON tbl_pipeline_events(source_code);
CREATE INDEX idx_events_type ON tbl_pipeline_events(event_type);
```

---

## Part 2: Granular State Tracking

### Enhanced State Schema

```json
{
  "schema_version": "2.0",
  "last_updated": "2026-01-12T11:00:00Z",

  "runs": {
    "run_20260112_103000": {
      "started_at": "2026-01-12T10:30:00Z",
      "completed_at": "2026-01-12T10:45:00Z",
      "config_file": "config/publications.yaml",
      "status": "completed_with_errors",
      "stats": {
        "urls_total": 10,
        "urls_completed": 7,
        "urls_partial": 2,
        "urls_failed": 1,
        "rows_loaded": 450000,
        "duration_ms": 900000
      }
    }
  },

  "urls": {
    "adhd/nov25": {
      "status": "completed",
      "last_run": "run_20260112_103000",
      "completed_at": "2026-01-12T10:35:00Z",
      "stages": {
        "manifest": {"status": "completed", "file": "adhd_nov25.yaml"},
        "enrich": {"status": "completed", "file": "adhd_nov25_enriched.yaml"},
        "load": {"status": "completed"},
        "export": {"status": "completed"}
      },
      "sources": {
        "adhd_summary": {"status": "loaded", "rows": 450, "table": "tbl_adhd_summary"},
        "adhd_by_age": {"status": "loaded", "rows": 1200, "table": "tbl_adhd_by_age"}
      }
    },

    "online_consultation/nov25": {
      "status": "partial",
      "last_run": "run_20260112_103000",
      "stages": {
        "manifest": {"status": "completed"},
        "enrich": {"status": "completed"},
        "load": {"status": "partial"},
        "export": {"status": "skipped", "reason": "load incomplete"}
      },
      "sources": {
        "gp_submissions_by_practice": {"status": "loaded", "rows": 6170},
        "gp_data_quality": {"status": "failed", "error": "type_mismatch", "column": "quality_score"},
        "practice_oc_submissions": {"status": "pending"}
      }
    },

    "online_consultation/dec25": {
      "status": "pending",
      "pending_until": "2026-01-29",
      "reason": "upcoming_publication",
      "last_checked": "2026-01-12T10:30:00Z"
    }
  }
}
```

### State Transitions

```
                    ┌─────────────┐
                    │   pending   │
                    │ (not started│
                    │  or future) │
                    └──────┬──────┘
                           │ start processing
                           ▼
                    ┌─────────────┐
                    │ in_progress │
                    └──────┬──────┘
                           │
           ┌───────────────┼───────────────┐
           │               │               │
           ▼               ▼               ▼
    ┌─────────────┐ ┌─────────────┐ ┌─────────────┐
    │  completed  │ │   partial   │ │   failed    │
    │ (all sources│ │(some loaded,│ │ (no sources │
    │   loaded)   │ │ some failed)│ │   loaded)   │
    └─────────────┘ └──────┬──────┘ └──────┬──────┘
                           │               │
                           │ fix & retry   │ fix & retry
                           ▼               ▼
                    ┌─────────────┐ ┌─────────────┐
                    │  completed  │ │   partial   │
                    └─────────────┘ └─────────────┘
```

---

## Part 3: Observability Layer

### Metrics to Track

**Pipeline Health:**
- Success rate by stage (manifest, enrich, load, export)
- Success rate by publication
- Partial success rate (some sources loaded)
- Average duration by stage
- Error rate by type

**Data Volume:**
- Rows loaded per run
- Rows loaded per publication
- Tables created/updated
- Storage growth

**LLM Costs (enrichment):**
- Tokens used per enrichment
- Cost per URL
- Reference match rate (deterministic vs LLM)

**Error Distribution:**
- Errors by type (404, type_mismatch, timeout)
- Errors by publication
- Recurring errors (same source failing repeatedly)

### Metrics File

```json
{
  "period": "2026-01-12",

  "pipeline": {
    "runs": 3,
    "urls_processed": 25,
    "urls_succeeded": 20,
    "urls_partial": 3,
    "urls_failed": 2,
    "success_rate": 0.80
  },

  "stages": {
    "manifest": {"attempts": 25, "success": 23, "rate": 0.92},
    "enrich": {"attempts": 23, "success": 23, "rate": 1.00},
    "load": {"attempts": 23, "success": 20, "rate": 0.87},
    "export": {"attempts": 20, "success": 20, "rate": 1.00}
  },

  "errors": {
    "by_type": {
      "404_not_found": 2,
      "type_mismatch": 2,
      "no_files_found": 1
    },
    "by_publication": {
      "adhd": 1,
      "pcn_workforce": 2
    }
  },

  "data": {
    "rows_loaded": 450000,
    "tables_updated": 15,
    "parquet_files_created": 15
  },

  "llm": {
    "enrichment_calls": 5,
    "reference_matches": 18,
    "tokens_used": 25000,
    "estimated_cost_usd": 0.05
  }
}
```

### Dashboard (Future - Simple HTML)

```
┌─────────────────────────────────────────────────────────────────┐
│                    DataWarp Pipeline Dashboard                   │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  TODAY: 2026-01-12                                              │
│                                                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐           │
│  │ ✅ Success   │  │ ⚠️ Partial   │  │ ❌ Failed    │           │
│  │     80%      │  │     12%      │  │      8%      │           │
│  │   20 URLs    │  │    3 URLs    │  │    2 URLs    │           │
│  └──────────────┘  └──────────────┘  └──────────────┘           │
│                                                                  │
│  STAGE SUCCESS RATES:                                           │
│  Manifest  ████████████████████░░░░ 92%                         │
│  Enrich    ████████████████████████ 100%                        │
│  Load      █████████████████░░░░░░░ 87%                         │
│  Export    ████████████████████████ 100%                        │
│                                                                  │
│  RECENT ERRORS:                                                 │
│  • adhd/mar25 - 404 Not Found (1 hour ago)                      │
│  • pcn_workforce/jun25 - Type mismatch (2 hours ago)            │
│                                                                  │
│  DATA LOADED TODAY: 450,000 rows across 15 tables               │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Part 4: LLM Supervisor Integration

### What the LLM Supervisor Receives

When an error occurs, the supervisor receives a **context bundle**:

```json
{
  "error_event": {
    "event_type": "source_failed",
    "error": {
      "type": "type_mismatch",
      "message": "INTEGER column received unexpected value '*'",
      "column": "headcount_march_2020"
    }
  },

  "pipeline_context": {
    "publication": "pcn_workforce",
    "period": "jun25",
    "url": "https://...",
    "source_code": "pcn_wf_headcount_age_staff_group",
    "stage": "load",
    "manifest_file": "manifests/backfill/pcn_workforce/pcn_workforce_jun25_enriched.yaml"
  },

  "state_context": {
    "url_status": "partial",
    "sources_loaded": ["pcn_wf_fte_gender_role", "pcn_wf_fte_age_staff_group"],
    "sources_failed": ["pcn_wf_headcount_age_staff_group"],
    "sources_pending": ["pcn_wf_individual_level"]
  },

  "investigation_data": {
    "manifest_column_definition": {
      "original_name": "March 2020",
      "semantic_name": "headcount_march_2020",
      "data_type": "integer"
    },
    "actual_data_sample": ["450", "320", "*", "180"],
    "db_table_exists": true,
    "db_table_columns": ["..."]
  },

  "available_actions": [
    "fix_manifest_type",
    "disable_source",
    "skip_and_continue",
    "retry",
    "escalate_to_human"
  ]
}
```

### LLM Decision Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                    LLM SUPERVISOR DECISION                       │
└─────────────────────────────────────────────────────────────────┘

1. RECEIVE context bundle (error + pipeline + state + investigation)

2. CLASSIFY error type
   - Is this a known pattern? (404, type_mismatch, no_files, etc.)
   - What stage failed?
   - Is this recoverable?

3. INVESTIGATE if needed
   - Fetch landing page (for 404 errors)
   - Query database (for partial load)
   - Read manifest (for type issues)

4. GENERATE troubleshooting report
   - Human-readable summary
   - What worked, what failed, why
   - Recommended actions

5. DECIDE action
   - fix_manifest_type: Edit YAML to change data_type
   - disable_source: Set enabled: false
   - skip_and_continue: Mark as skipped, continue with other sources
   - retry: Transient error, try again
   - escalate_to_human: Unknown error, need human review

6. EXECUTE action (if approved)
   - Edit manifest file
   - Update state
   - Resume pipeline

7. LOG decision and outcome
   - Store in event log for audit trail
```

### LLM Prompt Template

```
You are the DataWarp Autonomous Supervisor. An error occurred during pipeline execution.

## Error Details
{{error_event}}

## Pipeline Context
{{pipeline_context}}

## Current State
{{state_context}}

## Investigation Data
{{investigation_data}}

## Your Task

1. Analyze the error and determine the root cause
2. Generate a troubleshooting report (markdown format)
3. Recommend an action from the available options
4. If the action involves editing a manifest, provide the exact YAML changes

## Available Actions
{{available_actions}}

## Response Format
```json
{
  "analysis": "Brief analysis of the error",
  "root_cause": "The underlying cause",
  "troubleshooting_report": "# Troubleshooting Report\n\n...",
  "recommended_action": "fix_manifest_type | disable_source | ...",
  "action_details": {
    "file": "path/to/manifest.yaml",
    "changes": [
      {"path": "sources[3].columns[5].data_type", "old": "integer", "new": "varchar"}
    ]
  },
  "confidence": 0.95,
  "requires_human_approval": false
}
```
```

---

## Part 5: Implementation Plan

### Phase 1: Event System (Foundation)

**Goal:** Replace DEBUG print statements with structured events

**Files to create:**
- `src/datawarp/observability/events.py` - Event schema and emitter
- `src/datawarp/observability/store.py` - JSONL file writer

**Files to modify:**
- `src/datawarp/loader/pipeline.py` - Emit load events
- `scripts/url_to_manifest.py` - Emit manifest events
- `scripts/enrich_manifest.py` - Emit enrich events
- `scripts/backfill.py` - Emit run-level events

**Effort:** ~2 hours

### Phase 2: Enhanced State Tracking

**Goal:** Track per-source status, not just per-URL

**Files to create:**
- `src/datawarp/observability/state.py` - Enhanced state manager

**Files to modify:**
- `scripts/backfill.py` - Use new state manager
- `state/state.json` - Migrate to v2 schema

**Effort:** ~1 hour

### Phase 3: Context Gathering

**Goal:** Build investigation tools the supervisor can use

**Files to create:**
- `src/datawarp/supervisor/investigator.py` - Context gatherer
  - `gather_db_context()` - Query load history, table state
  - `gather_manifest_context()` - Read manifest details
  - `gather_web_context()` - Fetch landing pages

**Effort:** ~1 hour

### Phase 4: Error Classifier

**Goal:** Automatically classify errors by pattern

**Files to create:**
- `src/datawarp/supervisor/classifier.py` - Error classifier
  - Pattern matching for known error types
  - Extracts structured data from error messages

**Effort:** ~1 hour

### Phase 5: Report Generator

**Goal:** Generate human-readable troubleshooting reports

**Files to create:**
- `src/datawarp/supervisor/reporter.py` - Report generator
  - Markdown templates for each error type
  - Summary tables

**Effort:** ~1 hour

### Phase 6: LLM Supervisor

**Goal:** Integrate LLM for decision making

**Files to create:**
- `src/datawarp/supervisor/llm_supervisor.py` - LLM integration
  - Builds context bundle
  - Calls LLM with prompt
  - Parses response
  - Executes approved actions

**Effort:** ~2 hours

### Phase 7: Supervisor CLI

**Goal:** Command-line interface for the supervisor

**Commands:**
```bash
# Run supervised backfill
python scripts/supervised_backfill.py --config config/publications.yaml

# Run with auto-fix (no human approval for safe actions)
python scripts/supervised_backfill.py --auto-fix

# Generate report for failed runs
python scripts/supervisor_report.py --run run_20260112_103000

# Retry failed sources only
python scripts/supervisor_retry.py --url adhd/nov25
```

**Effort:** ~1 hour

---

## File Structure

```
src/datawarp/
├── observability/
│   ├── __init__.py
│   ├── events.py          # Event schema, emitter
│   ├── store.py           # Event storage (JSONL)
│   ├── state.py           # Enhanced state manager
│   └── metrics.py         # Metrics calculator
│
├── supervisor/
│   ├── __init__.py
│   ├── classifier.py      # Error pattern classifier
│   ├── investigator.py    # Context gathering
│   ├── reporter.py        # Troubleshooting reports
│   ├── actions.py         # Manifest fix actions
│   └── llm_supervisor.py  # LLM integration
│
scripts/
├── supervised_backfill.py # Main supervised runner
├── supervisor_report.py   # Report generator CLI
└── supervisor_retry.py    # Retry failed sources

logs/
├── events/
│   └── 2026-01-12/
│       └── run_*.jsonl
├── reports/
│   └── 2026-01-12/
│       └── troubleshooting_*.md
└── metrics/
    └── 2026-01-12.json

state/
└── state_v2.json          # Enhanced state
```

---

## Summary

### What This Enables

1. **Structured Logging** - Every event captured with full context
2. **Granular State** - Per-source tracking, not just per-URL
3. **Observability** - Metrics, dashboards, audit trail
4. **Traceability** - Follow any URL through entire pipeline
5. **Autonomous Operation** - LLM supervisor can investigate and fix
6. **Resume** - Pick up exactly where it left off

### What the LLM Supervisor Can Do

- ✅ Detect and classify errors automatically
- ✅ Investigate root causes (web, db, files)
- ✅ Generate troubleshooting reports
- ✅ Fix manifests (types, enabled flags, config)
- ✅ Update state (clear failed, mark pending)
- ✅ Resume from exact failure point
- ❌ Edit Python code (out of scope, too risky)

### Estimated Total Effort

| Phase | Description | Time |
|-------|-------------|------|
| 1 | Event System | 2 hours |
| 2 | Enhanced State | 1 hour |
| 3 | Context Gathering | 1 hour |
| 4 | Error Classifier | 1 hour |
| 5 | Report Generator | 1 hour |
| 6 | LLM Supervisor | 2 hours |
| 7 | Supervisor CLI | 1 hour |
| **Total** | | **9 hours** |

---

## Next Steps

1. Review this design document
2. Approve or suggest changes
3. Start with Phase 1 (Event System) as foundation
4. Build incrementally, testing each phase

---

**Questions for Review:**

1. Is the event schema comprehensive enough?
2. Should state be stored in database instead of JSON file?
3. What LLM should power the supervisor? (Gemini for cost, Claude for quality)
4. Should the supervisor require human approval for all fixes, or auto-fix safe actions?
