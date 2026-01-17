# DataWarp Implementation Tasks

**Updated: 2026-01-17 22:00 UTC**
**Philosophy:** Only track what blocks you NOW or what you'll do THIS WEEK

**Backup:** Full 80+ task list archived in `docs/archive/IMPLEMENTATION_TASKS_BACKUP_20260110.md`

**Session 24 Update:** Completed add_publication.py CLI + discovery mode infrastructure, added 11 NHS publications

---

## ✅ Recently Fixed

**get_metadata JSON serialization error** - FIXED Session 15
- Added `make_json_safe()` helper using `hasattr(val, 'isoformat')` pattern
- MCP server now correctly serializes date/datetime objects

**EventType.WARNING misused for info-level logging** - FIXED Session 17
- Changed 674 events from WARNING to semantic types (STAGE_STARTED, STAGE_COMPLETED, LLM_CALL)
- Events now have proper `stage` parameter for filtering

**--force flag not working** - FIXED Session 17
- Force flag now propagates through batch.py → load_file()
- Added visible warnings for table mismatch errors

---

## 🚨 Fix When You Hit It (Not Before)

**These are real problems, but DON'T fix them until they actually break your workflow.**

### Database Hygiene

**Orphaned tables** (tables with no registry entry)
- **When to fix:** Storage is getting full OR you can't find data
- **How to fix:** Run query from DB_MANAGEMENT_FRAMEWORK.md → Detect orphans → Ask user which to keep/archive
- **Don't:** Build automated cleanup system preemptively

**Stale sources** (not loaded in 30+ days)
- **When to fix:** User asks "why is X data old?" OR dashboard shows staleness matters
- **How to fix:** Run freshness query → Archive old sources OR update them
- **Don't:** Build alerting system until staleness causes actual issues

**Failed loads** (sources that won't load anymore)
- **When to fix:** User reports missing data OR you need that specific source
- **How to fix:** Check tbl_load_events → Investigate error → Fix that source
- **Don't:** Try to fix all failed sources at once

**Junk data** (test loads, duplicate periods)
- **When to fix:** Storage >80% OR data quality questions arise
- **How to fix:** Manual cleanup script → DROP TABLE specific junk → Update registry
- **Don't:** Build comprehensive data quality framework yet

### Testing Issues

**Regression bugs** (something that worked before breaks)
- **When to fix:** Immediately when discovered
- **How to fix:** Write minimal test case → Fix bug → Add test to suite
- **Don't:** Build golden dataset infrastructure preemptively

**Missing metadata** (sources with no LLM descriptions)
- **When to fix:** Agent can't answer questions about that source
- **How to fix:** Run enrich_manifest.py on that specific source
- **Don't:** Try to achieve 100% metadata coverage across all 173 sources

---

## 💡 Ideas (Not Blocking Anything)

**If you have time and want to improve things, here are ideas. Most of these are from the 80+ task backup.**

### MCP Performance & Usability (Session 12 + 13 Discoveries)

**Real-World Performance Issue:**
- User query: "Show me SWL GP appointments by year and month"
- Time taken: **7-10 minutes**
- Root cause: Client-side aggregation, multiple tool calls, no pre-computed views

**Session 13 Feedback from Claude Desktop** (10 suggestions triaged):

**Quick Wins** (High impact, <1 hour each):
1. ✅ **Add get_schema() tool** - Returns columns, types, sample values, suggested queries
   - Impact: 60% → 95% first-time query success rate
   - Implementation: ~30 minutes, new MCP tool
2. ✅ **Dataset discovery tags** - Add region/topic/granularity tags to catalog
   - Impact: 5 searches → 1 search for dataset discovery
   - Implementation: ~20 minutes, update export_to_parquet.py
3. ✅ **Improve get_metadata response** - Add date_range, row_count, dimensions, sample_query
   - Impact: Better query planning, fewer errors
   - Implementation: ~15 minutes, enhance existing tool

**High Impact** (Aligned with Session 12 findings):
4. **Pre-aggregated summary tables OR statistical tools** - Server-side computation
   - Two approaches:
     - A: Create pre-computed datasets (swl_gp_monthly_summary, adhd_monthly_aggregates)
     - B: Add statistical MCP tools (get_time_series, get_summary_stats) ← Recommended
   - Impact: 7-10 min queries → 10-20 seconds
   - Implementation: 2 hours (statistical tools approach)
5. **Multi-dataset queries (JOINs)** - Enable comparative analysis
   - Example: "Compare SWL to national average" in single query
   - Impact: Multi-dataset analysis without manual Python combination
   - Implementation: 3 hours (DuckDB multi-table support)

**Data Quality**:
6. **Partial data flags** - Mark incomplete periods (Nov 2025 was 52% complete)
   - Impact: Prevent incorrect conclusions about data drops
   - Implementation: 1 hour (add to catalog during export)
7. **Cross-tabulation datasets** - Compute age × wait band tables
   - Problem: NHS doesn't publish, but source data may support computation
   - Impact: Answer "which age groups have longest waits" directly
   - Implementation: 2 hours (analyze source, add to export if possible)

**Optimization**:
8. **Query result caching** - Session-level cache for repeated queries
   - Impact: 50% speedup for iterative analysis
   - Implementation: 1.5 hours
9. **Pagination** - Return row counts first, then data
   - Impact: Faster query verification
   - Implementation: 1 hour
10. **Time-series optimized datasets** - Pre-pivoted data
    - Impact: Trend queries in 1 query instead of aggregating 150+ rows
    - Implementation: 2 hours (data re-modeling)

**What Works Well** (Don't change):
- ✅ SQL passthrough
- ✅ Natural language query option
- ✅ Fast query execution (when queries run)
- ✅ Large result sets (1000s of rows)

### MCP Performance Optimization (Session 12 Discovery - ORIGINAL)
**Problem:** Claude Desktop takes 8-15 sec for statistical queries - processes client-side with pandas
**Solution:** Add pre-built statistical tools to MCP server for server-side execution
**Speed Improvement:** 10-20x faster (1 sec vs 10 sec)

**Phase 1: Core Stats (30 min)**
- `get_statistics(dataset, columns, metrics)` - Fast descriptive stats (mean, median, stddev, cv, quartiles)
- `compare_groups(dataset, group_columns, analysis)` - CV, variance decomposition, group comparison
- `detect_outliers(dataset, column, method, threshold)` - Z-score or IQR-based outlier detection

**Phase 2: Time Series (45 min)**
- `analyze_time_series(dataset, date_col, value_col)` - Trend, seasonality, forecasts
- `calculate_correlations(dataset, columns)` - Correlation matrices, Pearson coefficients

**Phase 3: ADHD-Specific (45 min)**
- `get_seasonal_patterns(dataset, by_age_group)` - Pre-computed seasonal indices
- `analyze_wait_times(dataset, target_weeks)` - NHS target compliance metrics
- `analyze_medication_trends(start_year, end_year)` - Long-term prescribing CAGR

**Implementation:**
- File: `mcp_server/tools/statistics.py` (new module)
- Integration: `mcp_server/stdio_server.py` (add new tool definitions)
- Testing: `mcp_server/test_statistics_tools.py` (validation suite)

**User Value:** Enables instant statistical analysis through conversational interface

---

### Production Query Handler (NL→SQL/Code)
- Replace hardcoded query patterns with LLM-powered code generation
- Approach 1: LLM → Pandas code (safer, sandboxed execution)
- Approach 3: LLM tool chains (most flexible for complex questions)
- Current prototype: mcp_server/server.py handle_query() uses pattern matching
- Implementation guide: mcp_server/demo_nl_to_sql.py (Session 8)
- Benefits: Handles infinite query types with one endpoint, no fixed interfaces
- Reference: Session 8 discussion on NL→SQL translation
- **When to build:** If query endpoint becomes actively used or patterns insufficient

### Monitoring & Observability
- 4 dashboards (Load Health, Data Freshness, Storage Growth, Schema Evolution)
- Automated weekly reports
- Alerting system (Slack/Email)
- Prometheus/Grafana integration

### Validation & Quality
- Automated validation gates in load pipeline
- Golden dataset regression tests
- Data quality checks (row count sanity, type validation)
- Evidence collection for 8 testing goals

### Lifecycle Management
- Source registration workflow with metadata requirements
- Deprecation workflow (grace period → archive)
- Archival automation (export Parquet → move to archive schema)
- Schema change review process
- **`datawarp refresh` command** - Re-extract, re-enrich, re-load workflow (from Session 10)
- **Cloud storage (Cloudflare R2)** - Archive old manifests/parquet to cloud (from Session 10)
- **Manifest reorganization** - active/pending/archive structure (from Session 10)
- **Postgres backend for MCP** - Query staging tables directly (from Session 10)
- **search_columns MCP tool** - Semantic column search across datasets (from Session 10)

### Agentic DataWarp - Two-Track Roadmap (Sessions 23-24-27)

**Vision:** Transform DataWarp into an AI-assisted platform for ICB commissioning intelligence. Agents handle routine work, humans provide judgment.

**Context:** ICB commissioning intelligence focuses on statutory return metrics (performance indicators submitted by providers), not financial/contract data.

**Full Roadmap:** See `docs/agentic/agentic_vision_roadmap.md`

---

## Epic 1: Track A - Ingestion Automation (Steps 1-5)

**Goal:** Reduce human effort from 100% → 10% for adding and maintaining NHS publications

**Total Time:** 8.5 hours | **Status:** Step 1 complete, Steps 2-5 planned

### ✅ Step 1: add_publication.py CLI + Discovery Mode (COMPLETE - Session 24)
- **Status:** ✅ Built and tested
- **What:** Automated NHS URL classification and YAML config generation
- **Files:**
  - `scripts/add_publication.py` (235 lines)
  - `src/datawarp/discovery/` (252 lines - html_parser, url_matcher, discover)
- **Capabilities:**
  - Detects NHS Digital (templatable) vs NHS England (hash codes)
  - Generates proper YAML config blocks
  - **Discovery mode:** Runtime URL resolution for NHS England publications
  - Handles WordPress hash codes, flexible period matching
- **Impact:** Human effort 100% → 20%, unblocked 21+ NHS England publications
- **Usage:** `python scripts/add_publication.py <url> [--dry-run]`
- **Session 24 Results:**
  - Added 11 new publications (24 total, +85% from 13)
  - NHS Digital: 18 publications (template mode)
  - NHS England: 4 publications (discover mode) + 2 (explicit mode)
  - All 4 discover mode publications tested and working

### Step 2: Log MCP Tools (2 hours) ← NEXT FOR TRACK A
```
Tools:
  - list_runs()              # Recent backfill runs
  - get_summary(run_id)      # Success/fail/skipped counts
  - find_errors(run_id)      # All ERROR entries
  - find_failures(run_id)    # Failed periods with reasons
  - trace_period(run_id, period)  # Full pipeline trace for one period
  - is_running(run_id)       # Check if backfill still active
```
- **Live backfill safe:** Logs are append-only, read during run is fine
- **Detection:** Check file mtime to know if run in progress
- **Use case:** "What happened in the last backfill?" → Claude queries, explains, suggests fixes
- **Files:** `mcp_server/stdio_server.py` (+100 lines)

### Step 3: Golden Tests (1.5 hours)
- **What:** Validate every load, catch problems before commit
- **Tests:** Row count sanity, no future dates, null rate checks, required columns
- **Workflow:** Load → Run tests → All pass? Commit : Rollback + Alert
- **Files:** `src/datawarp/validation/golden_tests.py` (new), `scripts/backfill.py` (integration)

### Step 4: Schema Fingerprinting (2 hours)
- **What:** Detect column drift/renames across periods
- **Logic:** Fuzzy matching on aliases, confidence scores for rename detection
- **Files:** `src/datawarp/validation/schema_fingerprint.py` (new), `config/schema_fingerprints/` (per-pub YAML)

### Step 5: Config MCP Tools (2 hours)
```
Tools:
  - list_publications()      # Show current config
  - classify_url(url)        # Detect pattern (schedule/manual, template/explicit)
  - generate_config(url)     # Generate YAML block from URL
  - add_publication(config)  # Append new publication to YAML
  - update_urls(pub, urls)   # Add URLs to existing publication
  - validate_config()        # Validate YAML syntax and patterns
```
- **Use case:** "Add CAMHS waiting times" → Claude classifies, generates config, appends
- **Files:** `mcp_server/stdio_server.py` (+150 lines)
- **Depends on:** Step 1 (add_publication.py logic)

---

## Epic 2: Track B - Intelligent Querying (Steps 6-7)

**Goal:** Enable semantic discovery and querying without schema knowledge - transform agent experience from "find tables, write SQL" to "ask question, get answer"

**Total Time:** 5 hours | **Status:** Designed in Session 27, ready for implementation

**Context:** ICB commissioning uses 4 organizational lenses (Provider, ICB, Sub-ICB, GP Practice) to analyze statutory return metrics. The semantic layer must support lens-aware queries and benchmarking.

**Design Docs:**
- `docs/architecture/metadata_driven_reporting.md` - Complete implementation design
- `docs/architecture/icb_scorecard_structure.md` - Real ICB scorecard analysis (485 metrics)
- `docs/architecture/SEMANTIC_LAYER_FINAL_DESIGN.md` - Full specification

### Step 6: Populate Metadata Layer (1 hour)

**The Insight:** We already have semantic metadata in `tbl_column_metadata`:
- `is_measure = true` → KPIs (statutory return metrics)
- `is_dimension = true` → Filters (geography, time, age, provider)
- `query_keywords` → Searchable terms for discovery

**Just need to consolidate into dataset-level metadata JSONB for agent consumption.**

**Implementation:**
```python
# Script: scripts/populate_dataset_metadata.py

def populate_metadata(source_code: str):
    """Extract metadata from tbl_column_metadata and populate JSONB."""

    # Get measures (KPIs)
    measures = query("""
        SELECT column_name, description, data_type, query_keywords
        FROM datawarp.tbl_column_metadata
        WHERE canonical_source_code = %s AND is_measure = true
    """, source_code)

    # Get dimensions
    dimensions = query("""
        SELECT column_name, description, query_keywords
        FROM datawarp.tbl_column_metadata
        WHERE canonical_source_code = %s AND is_dimension = true
    """, source_code)

    # Build metadata JSON with ICB lens support
    metadata = {
        "organizational_lenses": {
            "provider": infer_provider_support(source_code),
            "icb": infer_icb_support(source_code),
            "sub_icb": infer_subicb_support(source_code),
            "gp_practice": infer_practice_support(source_code)
        },
        "kpis": [
            {
                "column": m['column_name'],
                "label": m['description'],
                "unit": infer_unit(m['description']),
                "aggregation": infer_aggregation(m['data_type']),
                "query_keywords": m['query_keywords'],
                "has_target": infer_has_target(m),
                "metric_type": infer_metric_type(m)  # "performance" or "intelligence"
            }
            for m in measures
        ],
        "dimensions": [...],
        "granularity": infer_granularity(dimensions),
        "typical_queries": generate_typical_queries(measures, dimensions)
    }

    # Update tbl_canonical_sources.metadata
    update("""
        UPDATE datawarp.tbl_canonical_sources
        SET metadata = %s::jsonb
        WHERE canonical_code = %s
    """, json.dumps(metadata), source_code)
```

**Usage:**
```bash
# Populate all datasets
python scripts/populate_dataset_metadata.py --all

# Populate specific domain
python scripts/populate_dataset_metadata.py --domain mental_health
```

**Files:** `scripts/populate_dataset_metadata.py` (new, ~200 lines)

**Time:** 1 hour script + 10 minutes execution for 181 datasets

---

### Step 7: Enhanced Query Tools (4 hours)

**Purpose:** Enable lens-aware semantic discovery and intelligent querying

**New MCP Tools (5 tools):**

#### 1. `discover_by_keyword(keywords)` - Semantic dataset discovery
```python
# Find datasets by query_keywords (e.g., ['adhd', 'waiting', 'time'])
# Uses GIN index on tbl_column_metadata.query_keywords
# Returns datasets ranked by KPI count
```

#### 2. `get_kpis(dataset)` - List available KPIs
```python
# Returns KPI metadata from tbl_canonical_sources.metadata JSONB
# Includes: column name, label, unit, aggregation method, target info
# Fallback to tbl_column_metadata if JSONB not populated
```

#### 3. `query_metric(dataset, metric, lens, lens_value, filters)` - Lens-aware metric query
```python
# Query specific metric with organizational lens
# Example: query_metric(
#     dataset='adhd_waiting_times',
#     metric='median_wait_weeks',
#     lens='provider',
#     lens_value='Norfolk & Suffolk FT',
#     filters={'period': '2024-Q3'}
# )
# Dynamically generates SQL based on metadata
```

#### 4. `aggregate_by(dataset, metric, dimension, filters)` - Dimensional aggregation
```python
# Aggregate metric by dimension (age, geography, etc.)
# Uses aggregation method from metadata (SUM, AVG, WEIGHTED_AVG)
# Example: aggregate_by(
#     dataset='adhd_prevalence',
#     metric='prevalence_rate',
#     dimension='age_band',
#     filters={'geography_level': 'icb'}
# )
```

#### 5. `compare_periods(dataset, metric, periods, filters)` - Time series comparison
```python
# Compare metric across time periods
# Example: compare_periods(
#     dataset='adhd_referrals',
#     metric='referral_count',
#     periods=['2024-Q2', '2024-Q3'],
#     filters={'geography_level': 'national'}
# )
```

**Implementation:**
- **Files:** `mcp_server/stdio_server.py` (+250 lines), `mcp_server/backends/postgres.py` (+100 lines)
- **Key Logic:**
  - Read metadata JSONB to understand schema
  - Find measure/dimension columns using `is_measure`/`is_dimension` flags
  - Generate SQL dynamically based on metadata
  - Support 4 organizational lenses (Provider, ICB, Sub-ICB, GP Practice)

**Time:** 4 hours

---

### Track B Success Metrics

| Metric | Current | After Step 7 |
|--------|---------|--------------|
| MCP calls to answer "What's X metric?" | 3-5 calls | 1 call |
| Schema knowledge required | High (must know tables/columns) | None (semantic search) |
| Time to discover datasets | 5-10 min (manual) | 10 sec (keyword search) |
| Query complexity | Must write SQL | Natural language |
| Agent query success rate | ~40% (schema confusion) | ~90% (metadata-driven) |

---

### Track A + Track B Together

**Track A** loads data with enriched metadata → **Track B** enables intelligent queries

```
Track A: Backfill → staging.tbl_* + tbl_column_metadata populated
                           ↓
Track B: Agents discover and query KPIs intelligently without schema knowledge
```

**Both tracks are independent and can be developed in parallel.**

**Recommendation:** Start Track B first (Steps 6-7) for faster time to value - demonstrates AI-native querying in 5 hours using existing data.

### Automation & Monitoring (from Session 11)
- **Auto URL Discovery** - Crawl NHS landing pages to find new releases automatically
  - Scrape publication landing pages for new period links
  - Auto-add to publications.yaml or database
  - Trigger backfill.py when new URLs detected
  - Note: NHS pages are inconsistent, may need per-publication scrapers
- **Email/Slack notifications** - Alert on failures, daily digest
- **Web dashboard** - Simple status page for non-technical users

### Production Features
- LoadModeClassifier integration into enrich_manifest.py
- Duplicate detection post-load
- Access control (role-based permissions)
- Row-level security

### Temporal Awareness Framework
- Implement domain calendar (fiscal boundaries, quarter-ends, special events)
- Schema versioning with business event context (FY2024_Q1_FISCAL_EXPANSION vs generic v2)
- Anticipatory data modeling (optional fiscal extensions, temporal variations)
- Configuration-driven temporal rules (publication_schedule.yaml)
- Predictive schema validation (expected variations vs actual errors)
- Temporal boundary testing (March→April→May sequences)
- Reference: Session 7 discussion on building NHS fiscal patterns into applications

**See backup for full details:** `docs/archive/IMPLEMENTATION_TASKS_BACKUP_20260110.md`

---

## 📌 Could Do This Week (User Decides)

**These are concrete, achievable tasks if user wants to work on them. Pick 0-1.**

### Option A: Autonomous Supervisor Phase 1 - Event System (2 hours) ← NEW - USER'S VISION
- **What:** Implement structured event logging system (foundation for autonomous supervisor)
- **Design Doc:** `docs/design/autonomous_supervisor_architecture.md`
- **Pattern Doc:** `docs/design/autonomous_supervisor_patterns.md`
- **Why:** User wants "mini Claude Code" - LLM that runs backfill, detects errors, investigates, fixes manifests, resumes
- **Phase 1 Tasks:**
  1. Create `src/datawarp/supervisor/events.py` - Event dataclass + EventStore
  2. Create `logs/events/` directory structure (YYYY-MM-DD/run_*.jsonl)
  3. Integrate event emission into backfill.py (run_started, source_started, error, success, etc.)
  4. Test: Run backfill, verify JSONL events captured with full context
- **Benefit:** Foundation for all subsequent phases (error classification, investigation, manifest fixes)
- **Files:** `src/datawarp/supervisor/events.py` (new), `scripts/backfill.py` (+30 lines)
- **Commands:** Create module → Integrate → Test with `python scripts/backfill.py --config config/publications_test.yaml`

### Option B: MCP Quick Wins - Bug Fix + Usability (30 min)
- **What:** Fix critical bug + add 2 quick wins from Session 13 feedback
- **Tasks:**
  1. Fix get_metadata JSON serialization error (5 min)
  2. Add get_schema() MCP tool (20 min)
  3. Add dataset discovery tags to catalog (5 min)
- **Why:** Critical bug blocking users, quick wins have high impact
- **Benefit:** get_metadata works, 95% first-time query success, faster dataset discovery
- **Files:** `mcp_server/stdio_server.py` (+50 lines), `scripts/export_to_parquet.py` (+10 lines)
- **Commands:** Edit files → Restart MCP server → Test in Claude Desktop

### Option C: Continue Backfill (User-Driven)
- **What:** Add more URLs to `config/publications.yaml` and process them
- **Why:** Expand NHS data coverage beyond current 35 processed periods
- **Benefit:** More data for conversational analytics
- **Commands:**
  1. Edit `config/publications.yaml` (add URLs)
  2. `python scripts/backfill.py --dry-run` (preview)
  3. `python scripts/backfill.py` (execute)
- **LLM Cost:** $0.09/month with Gemini (50 events/day monitoring)

### Option D: MCP Statistical Tools - Performance Fix (2 hours)
- **What:** Add 3 pre-built statistical tools to MCP server
- **Tools:** `get_statistics`, `compare_groups`, `detect_outliers`
- **Why:** Claude Desktop takes 8-15 sec for statistical queries (processes client-side)
- **Benefit:** 10-20x speedup - CV analysis in 1 sec instead of 10 sec
- **Files:** `mcp_server/stdio_server.py` (+150 lines), `mcp_server/tools/statistics.py` (new)
- **Commands:** Add tools → Test → Restart Claude Desktop → Instant stats
- **Details:** See "💡 Ideas → MCP Performance Optimization" below

---

### ✅ Completed This Week

**Session 14: Autonomous Supervisor Design** - ✅ Complete
- E2E testing with failure scenarios (404, type mismatch, partial success)
- Discovered 5 error patterns for supervisor to handle
- Designed full architecture with 7-phase implementation plan
- Created comprehensive design docs
- Key discovery: Need per-source state tracking (not per-URL)

**Session 13: MCP Validation + ADHD Waiting Time Analysis** - ✅ Complete
- Diagnosed MCP connection drops (long conversations lose tools)
- Validated MCP server health (no errors, responds correctly)
- Analyzed ADHD waiting time distribution by age group
- Discovered NHS data limitation (no age × wait band cross-tabulation)
- Generated comprehensive waiting time report using YoY growth proxy
- Key finding: 62.8% waiting 1+ year, 25+ age group likely longest waits

**Session 12: Enhanced MCP + Complex ADHD Analytics** - ✅ Complete
- Integrated DuckDB backend into MCP server (full SQL support)
- Window functions (LAG), aggregations, complex queries now working
- Created 6-category test suite (all passing)
- Validated with real ADHD queries (CV analysis, MoM growth)
- User successfully ran statistical queries through Claude Desktop
- Identified performance optimization opportunity (statistical tools)

**Session 11: Simplified Backfill & Monitor System** - ✅ Complete
- Created `config/publications.yaml` with 12 seed URLs
- Created `scripts/backfill.py` (~200 lines processing script)
- Created `scripts/init_state.py` for manifest-based state initialization
- Initialized state with 26 processed periods
- Tested: 12/12 URLs show as already processed
- Created 6 ASCII pipeline diagrams in `docs/pipelines/`

**Session 10: MCP Multi-Dataset Design** - ✅ Complete
- Created dataset registry (181 datasets, 8 domains)
- Implemented DuckDB backend, router, registry loader
- All components tested and working
- Design doc: `docs/MCP_PIPELINE_DESIGN.md`

**Session 10: File Lifecycle Assessment** - ✅ Complete
- Deep dive into file organization (486 files)
- Identified 5 critical gaps (versioning, cleanup, cascade delete, downloads, cloud)
- Created cleanup script: `scripts/cleanup_orphans.py`
- Assessment doc: `docs/FILE_LIFECYCLE_ASSESSMENT.md`

**Session 9: E2E Test + Claude Desktop MCP** - ✅ Complete
- 9-period enrichment with 82.5% cost savings
- Rewrote stdio_server.py with official MCP SDK
- Successfully connected to Claude Desktop

**Previous Sessions (7-8):** Fiscal Testing, Database Cleanup, Load Validation, DB Snapshot

---

## 🎯 How to Use This File

**During testing loop:**
- Bug found → Fix immediately (don't add to list)
- Enhancement idea → Add to "💡 Ideas" section
- Critical blocker → Add to "🚨 Fix When You Hit It"

**End of session:**
- Review "Could Do This Week" options
- Pick ONE task for next session
- Don't try to do everything

**Monthly:**
- Review "Fix When You Hit It" section
- Actually hit any of these issues? → Fix them now
- Not hitting them? → Leave them alone

---

**Total active tasks:** 4 options (A: Supervisor Phase 1, B: MCP Quick Wins, C: Backfill, D: MCP Stats)
**Completed this week:** 8 tasks (Supervisor Design, MCP Validation, Backfill System, MCP Design, File Assessment, E2E Test, MCP SDK, Fiscal)
**Total deferred items:** ~15 "fix when hit" scenarios + lifecycle ideas
**Total ideas:** ~90 (archived, reference only - includes automation ideas)

**Previous 80+ task breakdown:** See `docs/archive/IMPLEMENTATION_TASKS_BACKUP_20260110.md`

**Next planning cycle:** Pick 0-1 from Options A-D, or defer all

---

*Philosophy: Don't fix problems you don't have. Don't build systems you don't need. Do work that unblocks you TODAY.*
