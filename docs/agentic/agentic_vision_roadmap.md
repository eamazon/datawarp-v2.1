# Agentic DataWarp Vision & Roadmap

**Created:** 2026-01-17
**Status:** Planning Complete - Ready for Implementation

---

## Executive Summary

Transform DataWarp from a human-operated tool into an AI-assisted platform where agents handle routine work and humans provide judgment at key decision points.

**Philosophy:** Agent as intelligent assistant, not replacement. Human-in-the-loop for judgment calls.

---

## The Vision

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                                                                              │
│                         AGENTIC DATAWARP                                     │
│                    "The AI-Native Data Platform"                             │
│                                                                              │
│           From: "Here's a tool, configure it yourself"                       │
│             To: "Tell me what data you need, I'll handle everything"         │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### End State Interaction

```
User: "I need NHS waiting times data for my healthcare analysis"

Agent: "I found 4 relevant NHS publications. Which would you like?"
       [Shows options]

User: "All of them"

Agent: [Configures, loads, validates, exports]
       "Done! 4.4M rows across 4 publications.
        I'll check for new data daily and notify you.
        Quick insight: A&E 4-hour waits hit 54% - lowest on record."

User: "Which regions have the worst performance?"

Agent: [Queries data, generates analysis]
       "Here are the 5 worst-performing regions..."
```

---

## The Hard Truths

### Where Agents Work Well

- Repetitive, well-defined tasks (download, load, export)
- Pattern matching on stable formats
- Log analysis and error classification
- Query execution (if schema is clean)
- Scheduling and orchestration
- Notification and reporting

### Where Agents Fail

- Semantic understanding (what does this column MEAN?)
- Judgment calls (is this drift or error?)
- Context requiring domain knowledge
- Handling novel situations (format changes)
- Detecting subtle data quality issues
- Understanding user intent from ambiguous queries

### The 10 Hard Problems

1. **Semantic Column Drift** - NHS renames columns constantly
2. **Silent Extraction Failures** - Data loads but is garbage
3. **Suppressed Value Inconsistency** - Different symbols across publications
4. **Organisational Identity Changes** - NHS orgs merge/split/rename
5. **LLM Hallucinations** - Enrichment invents non-existent columns
6. **Format Evolution** - Excel → ZIP → CSV → API changes
7. **Contextual Understanding** - Footnotes contain critical info
8. **Partial/Revised Data** - Provisional data gets revised
9. **Query Understanding** - Ambiguous user requests
10. **Cascading Failures** - One bad decision propagates

### The Solution: Human-in-the-Loop

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     REALISTIC AGENTIC DATAWARP                               │
│                     "Agent Does Work, Human Validates"                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│                          ┌─────────────────┐                                │
│                          │     HUMAN       │                                │
│                          │   (Judgment)    │                                │
│                          └────────┬────────┘                                │
│                                   │                                          │
│           ┌───────────────────────┼───────────────────────┐                 │
│           ▼                       ▼                       ▼                 │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐         │
│  │ Schema Review   │    │ Quality Review  │    │ Query Approval  │         │
│  │ [Approve/Edit]  │    │ [Accept/Flag]   │    │ [Run/Modify]    │         │
│  └────────┬────────┘    └────────┬────────┘    └────────┬────────┘         │
│           └───────────────────────┴───────────────────────┘                 │
│                                   │                                          │
│                                   ▼                                          │
│                          ┌─────────────────┐                                │
│                          │     AGENT       │                                │
│                          │  (Execution)    │                                │
│                          └─────────────────┘                                │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Implementation Roadmap

### Build Order

| Step | Component | Time | Value | Human Effort Reduction |
|------|-----------|------|-------|------------------------|
| 1 | `add_publication.py` CLI | 1 hr | Add URLs without manual YAML | 100% → 80% |
| 2 | Log MCP Tools | 2 hrs | "What failed?" via Claude | 80% → 60% |
| 3 | Golden Tests | 1.5 hrs | Catch bad loads early | 60% → 40% |
| 4 | Schema Fingerprinting | 2 hrs | Detect column drift/renames | 40% → 25% |
| 5 | Config MCP Tools | 2 hrs | Full config management via Claude | 25% → 10% |

### Step 1: add_publication.py CLI

**Purpose:** Classify URLs and generate YAML config automatically

**Input:**
```bash
python scripts/add_publication.py https://digital.nhs.uk/.../new-publication
```

**Output:**
```
Detected: NHS Digital, templatable, monthly
Landing page: https://digital.nhs.uk/.../new-publication
Pattern: {landing_page}/{month_name}-{year}

Generated config:
  new_publication:
    name: "New Publication Name"
    frequency: monthly
    landing_page: https://digital.nhs.uk/.../new-publication
    periods:
      mode: schedule
      start: "2024-01"
      end: current
      publication_lag_weeks: 6
    url:
      mode: template
      pattern: "{landing_page}/{month_name}-{year}"

Append to publications_v2.yaml? [y/n]: y
Added to config.
```

**Implementation:**
1. Parse URL to detect source (NHS Digital vs NHS England)
2. Check for hash codes (indicates explicit mode needed)
3. Extract landing page and period from URL
4. Detect frequency (monthly/quarterly) from URL pattern
5. Generate YAML config block
6. Optionally append to publications_v2.yaml

**Files to create:**
- `scripts/add_publication.py` (~150 lines)

### Step 2: Log MCP Tools

**Purpose:** Query logs conversationally via Claude Desktop

**Tools:**
```python
list_runs(limit=10)           # Recent backfill runs
get_summary(run_id)           # Success/fail/skipped counts
find_errors(run_id)           # All ERROR entries
find_failures(run_id)         # Failed periods with reasons
trace_period(run_id, period)  # Full pipeline trace
is_running(run_id)            # Check if active
```

**Example interaction:**
```
User: "What happened in the last backfill?"

Claude: [calls list_runs(), get_summary(), find_failures()]
        "The last backfill ran at 6am. 5 succeeded, 2 failed.

         Failures:
         - A&E: 404 (URL changed)
         - RTT: Schema drift (new column)

         Suggested fixes:
         - A&E: Update URL pattern
         - RTT: Approve new column

         Want me to fix these?"
```

**Implementation:**
- Add tools to existing MCP server
- Parse log files (append-only, safe to read during backfill)
- Detect active runs via file mtime

**Files to modify:**
- `mcp_server/stdio_server.py` (+100 lines)

### Step 3: Golden Tests

**Purpose:** Validate every load, catch problems before commit

**Tests:**
```python
GOLDEN_TESTS = [
    {
        "name": "row_count_sanity",
        "query": "SELECT COUNT(*) FROM {table} WHERE _period = '{period}'",
        "expect": "BETWEEN 100 AND 50000"
    },
    {
        "name": "no_future_dates",
        "query": "SELECT COUNT(*) FROM {table} WHERE _period_end > CURRENT_DATE",
        "expect": "= 0"
    },
    {
        "name": "null_rate_check",
        "query": "SELECT COUNT(*) FILTER (WHERE org_code IS NULL) * 100.0 / COUNT(*) FROM {table}",
        "expect": "< 5"
    },
    {
        "name": "required_columns",
        "query": "SELECT {required_cols} FROM {table} LIMIT 1",
        "expect": "NO_ERROR"
    }
]
```

**Workflow:**
1. After load, run golden tests
2. If all pass → commit
3. If any fail → rollback, alert human

**Files to create:**
- `src/datawarp/validation/golden_tests.py` (~100 lines)

**Files to modify:**
- `scripts/backfill.py` (integrate validation)

### Step 4: Schema Fingerprinting

**Purpose:** Detect column drift/renames across periods

**Fingerprint structure:**
```yaml
schema_fingerprint:
  adhd:
    columns:
      - name: "org_code"
        type: VARCHAR
        nullable: false
        patterns: ["^[A-Z0-9]{3,5}$"]
      - name: "referrals"
        type: INTEGER
        nullable: true
        aliases: ["Referrals", "Referrals Received", "New Referrals"]
```

**Detection logic:**
```python
def detect_drift(new_schema, golden_schema):
    drift = []
    for col in new_schema:
        if col.name in golden_schema:
            continue  # Exact match

        # Check for rename (fuzzy match)
        for golden_col in golden_schema:
            similarity = fuzzy_match(col.name, golden_col.aliases)
            if similarity > 0.85:
                drift.append({
                    "type": "RENAME",
                    "old": golden_col.name,
                    "new": col.name,
                    "confidence": similarity,
                    "suggestion": f"Map '{col.name}' to '{golden_col.name}'"
                })
                break
        else:
            drift.append({
                "type": "NEW",
                "name": col.name,
                "suggestion": "Add new column"
            })

    return drift
```

**Files to create:**
- `src/datawarp/validation/schema_fingerprint.py` (~150 lines)
- `config/schema_fingerprints/` (per-publication YAML files)

### Step 5: Config MCP Tools

**Purpose:** Full config management via Claude

**Tools:**
```python
list_publications()           # Current config
classify_url(url)             # Pattern detection
generate_config(url)          # YAML generation
add_publication(config)       # Append to YAML
update_urls(pub, urls)        # Update existing
validate_config()             # Validate syntax
```

**Example interaction:**
```
User: "Add the new CAMHS waiting times publication"

Claude: [calls classify_url, generate_config]
        "Found it. NHS Digital, monthly, template pattern.
         Here's the config: [shows YAML]
         Add to publications_v2.yaml?"

User: "Yes"

Claude: [calls add_publication]
        "Added. Run backfill now?"
```

**Files to modify:**
- `mcp_server/stdio_server.py` (+150 lines)

---

## Architecture

### Component Map

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         HOW COMPONENTS CONNECT                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│                        ┌───────────────────┐                                │
│                        │   Claude Desktop  │                                │
│                        │   / Claude Code   │                                │
│                        │   (Orchestrator)  │                                │
│                        └─────────┬─────────┘                                │
│                                  │                                           │
│                    ┌─────────────┼─────────────┐                            │
│                    │             │             │                            │
│                    ▼             ▼             ▼                            │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                         MCP TOOLS LAYER                              │   │
│  ├──────────────────────────────────────────────────────────────────────┤   │
│  │                                                                      │   │
│  │  CONFIG TOOLS          LOG TOOLS           DATA TOOLS (existing)    │   │
│  │  ┌────────────────┐   ┌────────────────┐   ┌────────────────┐       │   │
│  │  │• classify_url  │   │• list_runs     │   │• list_datasets │       │   │
│  │  │• generate_cfg  │   │• get_summary   │   │• get_metadata  │       │   │
│  │  │• add_pub       │   │• find_errors   │   │• query         │       │   │
│  │  │• update_urls   │   │• trace_period  │   │                │       │   │
│  │  └───────┬────────┘   └───────┬────────┘   └───────┬────────┘       │   │
│  │          │                    │                    │                │   │
│  └──────────┼────────────────────┼────────────────────┼────────────────┘   │
│             │                    │                    │                     │
│             ▼                    ▼                    ▼                     │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                       CORE DATAWARP                                  │   │
│  ├──────────────────────────────────────────────────────────────────────┤   │
│  │                                                                      │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐ │   │
│  │  │   Config    │  │   Backfill  │  │  Extractor  │  │   Loader    │ │   │
│  │  │publications │  │ backfill.py │  │ extractor.py│  │ pipeline.py │ │   │
│  │  │_v2.yaml     │  │             │  │             │  │             │ │   │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘ │   │
│  │         │                │                │                │        │   │
│  │         ▼                ▼                ▼                ▼        │   │
│  │  ┌─────────────────────────────────────────────────────────────┐    │   │
│  │  │                    VALIDATION LAYER                         │    │   │
│  │  │  ┌───────────────┐  ┌───────────────┐  ┌───────────────┐   │    │   │
│  │  │  │ Golden Tests  │  │   Schema      │  │  Confidence   │   │    │   │
│  │  │  │ (Step 3)      │  │ Fingerprint   │  │    Scores     │   │    │   │
│  │  │  │               │  │ (Step 4)      │  │               │   │    │   │
│  │  │  └───────────────┘  └───────────────┘  └───────────────┘   │    │   │
│  │  └─────────────────────────────────────────────────────────────┘    │   │
│  │                                │                                    │   │
│  │                                ▼                                    │   │
│  │  ┌─────────────────────────────────────────────────────────────┐    │   │
│  │  │                      DATA LAYER                             │    │   │
│  │  │  PostgreSQL  │  Parquet  │  Logs  │  State  │  Catalog      │    │   │
│  │  └─────────────────────────────────────────────────────────────┘    │   │
│  │                                                                      │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Human-Agent Interaction Pattern

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    HUMAN-AGENT INTERACTION PATTERN                           │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│                          ┌─────────────────┐                                │
│                          │      HUMAN      │                                │
│                          │                 │                                │
│                          │  • Intent       │                                │
│                          │  • Approval     │                                │
│                          │  • Judgment     │                                │
│                          └────────┬────────┘                                │
│                                   │                                          │
│                                   │ "Add new publication"                   │
│                                   │ "Yes, approve that"                     │
│                                   │ "No, that looks wrong"                  │
│                                   │                                          │
│                                   ▼                                          │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                             AGENT                                      │  │
│  │                                                                        │  │
│  │   DOES AUTOMATICALLY:              ASKS HUMAN:                        │  │
│  │   ├─ Discover new periods          ├─ "Add this publication?"         │  │
│  │   ├─ Generate config               ├─ "This column renamed, map it?"  │  │
│  │   ├─ Run backfill                  ├─ "Unusual data, investigate?"    │  │
│  │   ├─ Validate results              ├─ "Low confidence, please review" │  │
│  │   ├─ Detect schema drift           └─ "Unknown error, need help"      │  │
│  │   ├─ Export to parquet                                                │  │
│  │   ├─ Update catalog                                                   │  │
│  │   └─ Generate insights                                                │  │
│  │                                                                        │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Workflow Evolution

### Human Effort Reduction

```
TODAY:
┌─────────────────────────────────────────────────────────────────────────────┐
│ Human ──► YAML ──► CLI ──► Logs ──► grep ──► Fix ──► Repeat                │
│ Human effort: ████████████████████████████████████ 100%                    │
└─────────────────────────────────────────────────────────────────────────────┘

AFTER STEP 1 (add_publication.py):
┌─────────────────────────────────────────────────────────────────────────────┐
│ Human ──► URL ──► Agent generates ──► Human approves ──► CLI ──► ...       │
│ Human effort: ██████████████████████████████░░░░░░ 80%                     │
└─────────────────────────────────────────────────────────────────────────────┘

AFTER STEP 2 (Log MCP):
┌─────────────────────────────────────────────────────────────────────────────┐
│ ... ──► CLI ──► Agent explains results ──► Human decides ──► ...           │
│ Human effort: ████████████████████░░░░░░░░░░░░░░░░ 60%                     │
└─────────────────────────────────────────────────────────────────────────────┘

AFTER STEP 3 (Golden Tests):
┌─────────────────────────────────────────────────────────────────────────────┐
│ ... ──► Auto-validation ──► Only failures need human ──► ...               │
│ Human effort: ████████████░░░░░░░░░░░░░░░░░░░░░░░░ 40%                     │
└─────────────────────────────────────────────────────────────────────────────┘

AFTER STEP 4 (Schema Fingerprinting):
┌─────────────────────────────────────────────────────────────────────────────┐
│ ... ──► Auto-mapping ──► Human confirms suggestions ──► ...                │
│ Human effort: ██████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░ 25%                     │
└─────────────────────────────────────────────────────────────────────────────┘

FULL SYSTEM (All Steps):
┌─────────────────────────────────────────────────────────────────────────────┐
│ Human: "Add CAMHS data" ──► Agent does everything ──► Human: "OK"          │
│ Human effort: ███░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░ 10%                     │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Next Session: Start Building

### Recommended Start: Step 1 (add_publication.py)

**Why:**
- Immediately useful
- No infrastructure needed
- Foundation for Config MCP tools
- Quick win, builds momentum

**Deliverable:**
```bash
python scripts/add_publication.py https://digital.nhs.uk/.../new-publication
# Detects pattern, generates YAML, optionally appends to config
```

**Estimated time:** 1 hour

### Files to Read First

1. `docs/agentic/agentic_vision_roadmap.md` (this file)
2. `docs/TASKS.md` (current session summary)
3. `config/publications_v2.yaml` (understand current config format)
4. `src/datawarp/utils/url_resolver.py` (existing URL pattern logic)

---

## Success Metrics

| Metric | Current | After Step 5 |
|--------|---------|--------------|
| Time to add new publication | 15-30 min | 2 min (mostly approval) |
| Time to diagnose failure | 10-30 min | 1 min (agent explains) |
| Silent data corruption | Possible | Caught by golden tests |
| Column drift handling | Manual | Semi-automatic |
| Human effort per backfill | 100% | 10% |

---

## References

- Session 23 discussion (2026-01-17)
- IMPLEMENTATION_TASKS.md → "Agentic DataWarp" section
- TASKS.md → Session 23 summary

---

*"Agent as intelligent assistant, not replacement. Human-in-the-loop for judgment calls."*
