# DataWarp Implementation Tasks

**Updated: 2026-01-10 19:00 UTC**
**Philosophy:** Only track what blocks you NOW or what you'll do THIS WEEK

**Backup:** Full 80+ task list archived in `docs/archive/IMPLEMENTATION_TASKS_BACKUP_20260110.md`

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

**These are concrete, achievable tasks if user wants to work on them.**

### ✅ Completed This Week

**Option A: Execute Fiscal Testing** - ✅ Complete (Session 7)
**Option B: Basic Database Cleanup** - ✅ Complete (Session 7)
**Option C: Add Basic Validation** - ✅ Complete (Session 8)

---

### Option D: Document Current Database State (30 min)

**Goal:** Snapshot of what's in database right now

```bash
# Generate report
python scripts/reports/database_snapshot.py > docs/DATABASE_STATE_20260110.md

# Include:
# - Total sources: 173
# - Total tables: X
# - Total rows: X
# - Storage size: X GB
# - Oldest load: X
# - Newest load: X
# - Sources by domain: X
```

**Benefit:** Baseline for future cleanup decisions

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

**Total active tasks:** 1 option remaining this week (pick 0-1)
**Completed this week:** 3 tasks (Fiscal Testing, Database Cleanup, Load Validation)
**Total deferred items:** ~10 "fix when hit" scenarios
**Total ideas:** ~80 (archived, reference only)

**Previous 80+ task breakdown:** See `docs/archive/IMPLEMENTATION_TASKS_BACKUP_20260110.md`

---

*Philosophy: Don't fix problems you don't have. Don't build systems you don't need. Do work that unblocks you TODAY.*
