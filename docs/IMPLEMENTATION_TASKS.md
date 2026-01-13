# DataWarp Implementation Tasks

**Updated: 2026-01-13 11:30 UTC**
**Philosophy:** Only track what blocks you NOW or what you'll do THIS WEEK

**Backup:** Full 80+ task list archived in `docs/archive/IMPLEMENTATION_TASKS_BACKUP_20260110.md`

**Session 17 Update:** Created analyze_logs.py for operational observability, fixed --force flag propagation

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
