# DataWarp Testing Goals & Evidence Framework

**Updated: 2026-01-10 17:15 UTC**

## Executive Summary

Agentic testing strategy with measurable goals, automated evidence collection, and continuous validation. Ensures DataWarp meets production quality standards with verifiable proof.

---

## 🎯 Testing Goals (S.M.A.R.T.)

### Goal 1: Extract Correctness (Generic System)

**Target:** 95%+ extraction accuracy across NHS publications

**Measurable:**
- Extract 95%+ of data rows correctly (no data loss)
- Detect 100% of tabular sheets (no false negatives)
- Infer column types with 90%+ accuracy

**Evidence:**
- Golden dataset validation reports
- Extraction accuracy metrics per publication
- Monthly regression test results

**Status:** ⚠️ Not yet measured (framework needed)

---

### Goal 2: Schema Stability (Generic System)

**Target:** Zero unintended schema changes

**Measurable:**
- 100% of schema changes are intentional (documented)
- 0 breaking changes to existing tables
- <5% column additions per month (controlled drift)

**Evidence:**
- Schema change audit log
- Drift detection reports
- Breaking change alerts (should be 0)

**Status:** ⚠️ Drift detected but not formally tracked

---

### Goal 3: Load Success Rate (Integration)

**Target:** 95%+ load success rate

**Measurable:**
- 95%+ of batch loads complete successfully
- <5% failure rate on first attempt
- 100% of failures have documented root cause

**Evidence:**
- `tbl_load_events` success rate query
- Weekly load health report
- Failure analysis log

**Status:** ✅ Currently ~85% (based on Session 4 results)

---

### Goal 4: Data Quality (Integration)

**Target:** Zero data quality issues in production

**Measurable:**
- 0 all-NULL columns in loaded tables
- 0 duplicate primary keys
- 0 data type mismatches
- <1% suppressed values (*, -, ..) misinterpreted

**Evidence:**
- Post-load validation reports
- Data quality dashboard
- Quarterly audit reports

**Status:** ⚠️ Not systematically validated

---

### Goal 5: Metadata Coverage (Agent-Ready Data)

**Target:** 90%+ metadata coverage for agent querying

**Measurable:**
- 90%+ columns have descriptions
- 90%+ columns have search terms
- 100% sources have domain classification
- 100% sources have purpose documented

**Evidence:**
- Metadata coverage reports (via export_to_parquet.py)
- Agent confidence surveys
- Metadata quality dashboard

**Status:** ✅ 95% achieved for exported datasets (Session 1)

---

### Goal 6: Cross-Period Consistency (Niche Solution)

**Target:** 80%+ code consistency across periods

**Measurable:**
- 80%+ of enriched codes match across periods (with --reference)
- <20% code drift per period
- 100% of intentional changes documented

**Evidence:**
- Enrichment consistency reports
- Code drift analysis
- Reference-based enrichment logs

**Status:** ✅ 100% achieved with --reference (Session 4)

---

### Goal 7: Performance (NFR)

**Target:** Scale to 100+ publications

**Measurable:**
- Extract 1M rows in <60 seconds
- Load 1M rows in <120 seconds
- End-to-end pipeline <5 minutes for typical publication
- CSV extraction 25x faster than Excel conversion

**Evidence:**
- Performance benchmarks per publication
- Load duration tracking (`tbl_load_events.completed_at - started_at`)
- Monthly performance reports

**Status:** ✅ CSV 25x faster (Session 2), benchmarks needed for scale

---

### Goal 8: MCP Server Performance (PRIMARY OBJECTIVE)

**Target:** Sub-second agent queries

**Measurable:**
- List datasets: <100ms
- Get metadata: <200ms
- Simple query: <500ms
- Complex query: <2 seconds
- 95%+ agentic test pass rate

**Evidence:**
- MCP server response time metrics
- Agentic test suite results
- Agent performance dashboard

**Status:** ✅ 89% tests passing (Session 5), performance within targets

---

## 📊 Evidence Collection Framework

### Automated Evidence (Every Load)

**Collected automatically in `tbl_load_events`:**
```sql
SELECT
  source_code,
  load_id,
  rows_loaded,
  columns_added,
  load_status,
  started_at,
  completed_at,
  (completed_at - started_at) as duration,
  error_message
FROM datawarp.tbl_load_events
WHERE started_at > NOW() - INTERVAL '7 days';
```

**Metrics Derived:**
- Load success rate = COUNT(status='completed') / COUNT(*)
- Average duration = AVG(completed_at - started_at)
- Failure rate = COUNT(status='failed') / COUNT(*)
- Rows per second = SUM(rows_loaded) / SUM(duration_seconds)

---

### Weekly Evidence Report

**Generated every Monday:**

```bash
#!/bin/bash
# generate_weekly_evidence.sh

python scripts/reports/generate_evidence_report.py \
  --week $(date +%Y-W%U) \
  --output reports/evidence_$(date +%Y%m%d).md
```

**Report Contents:**

#### 1. Load Health (Goal 3)
```
Week: 2026-W02
Total Loads: 47
Successful: 42 (89.4%) ⚠️ Below target (95%)
Failed: 5 (10.6%)
Average Duration: 42s

Top Failures:
- adhd_summary_table_1 (3 failures) - URL timeout
- pcn_wf_fte_gender (2 failures) - Schema mismatch
```

#### 2. Schema Stability (Goal 2)
```
Schema Changes: 12
- Intentional: 10 (83.3%) ✓
- Unintended: 2 (16.7%) ⚠️
  - tbl_adhd_summary: Added 'unknown_col_1' (investigate)
  - tbl_pcn_wf_fte: Type change VARCHAR(50) → VARCHAR(100) (approved)

Breaking Changes: 0 ✓
```

#### 3. Data Quality (Goal 4)
```
All-NULL Columns: 0 ✓
Duplicate Keys: 0 ✓
Type Mismatches: 0 ✓
Suppression Errors: 2 (0.01%) ✓

Issues:
- tbl_waiting_list: 2 rows with '*' interpreted as NULL (acceptable)
```

#### 4. Metadata Coverage (Goal 5)
```
Columns with Descriptions: 1,234 / 1,350 (91.4%) ✓
Columns with Search Terms: 1,189 / 1,350 (88.1%) ⚠️ Below target
Sources with Domain: 65 / 65 (100%) ✓
Sources with Purpose: 62 / 65 (95.4%) ⚠️
```

#### 5. Performance (Goal 7)
```
Average Load Duration: 42s ✓
Fastest Load: 3s (tbl_mapping)
Slowest Load: 187s (tbl_practice_level_crosstab) ⚠️

Rows/Second: 24,500 (across all loads)
```

#### 6. MCP Server (Goal 8)
```
Agentic Test Results: 17/18 (94.4%) ⚠️ Just below target
Response Times:
- List datasets: 45ms ✓
- Get metadata: 123ms ✓
- Simple query: 287ms ✓
- Complex query: 1.2s ✓

Failing Test: test_large_dataset_handling (catalog staleness)
```

---

### Monthly Evidence Report

**Generated first of each month:**

```bash
python scripts/reports/generate_monthly_evidence.py \
  --month $(date +%Y-%m) \
  --output reports/monthly_$(date +%Y%m).md
```

**Report Contents:**

#### 1. Goal Progress Scorecard
```
Goal                          | Target | Actual | Status
------------------------------|--------|--------|--------
Extract Correctness           | 95%    | N/A    | ⚠️ Not measured
Schema Stability              | 0      | 2      | ⚠️ 2 unintended changes
Load Success Rate             | 95%    | 89%    | ⚠️ Below target
Data Quality                  | 0      | 0      | ✓ Zero issues
Metadata Coverage             | 90%    | 91%    | ✓ Above target
Cross-Period Consistency      | 80%    | 100%   | ✓ Exceeds target
Performance                   | <5min  | 3.2min | ✓ Meets target
MCP Server                    | 95%    | 94%    | ⚠️ Just below
```

#### 2. Trend Analysis
```
Load Success Rate Trend (Last 3 Months):
Nov: 82%
Dec: 87%
Jan: 89% ↗️ Improving (+7% since Nov)

Recommended Action: Continue monitoring, investigate top 3 failure sources
```

#### 3. Golden Dataset Regression
```
Golden Datasets Tested: 4
- GP Practice Registrations: ✓ PASS (1.8M rows, 6 sources)
- PCN Workforce: ✓ PASS (42K rows, 7 sources)
- ADHD Summary: ✓ PASS (10K rows, 11 sources)
- Primary Care Dementia: ⚠️ FAIL (CSV column mismatch, fixed)

Regression Tests: 18/20 (90%)
```

#### 4. Publication Coverage
```
Total Publications Tested: 8
NHS Publication Types:
- Statistical bulletins: 3
- Workforce reports: 2
- Clinical data: 2
- Administrative: 1

File Format Coverage:
- XLSX: 45 sources
- CSV: 32 sources
- ZIP: 8 sources

Coverage Gap: Mixed-format publications (XLSX + CSV + ZIP in single publication)
```

---

### Quarterly Evidence Audit

**Generated every quarter (Jan/Apr/Jul/Oct):**

```bash
python scripts/reports/generate_quarterly_audit.py \
  --quarter Q1 \
  --year 2026 \
  --output reports/audit_2026_Q1.md
```

**Report Contents:**

#### 1. Comprehensive Goal Assessment
- Full scorecard across all 8 goals
- Trend analysis (quarter-over-quarter)
- Root cause analysis for missed targets
- Recommendations for next quarter

#### 2. Production Readiness
- Code coverage (target: 80%+)
- Documentation coverage (target: 100%)
- Known issues count (target: <10 critical)
- Technical debt score

#### 3. Agent Confidence Survey
- Sample 10 research questions
- Measure agent success rate with MCP server
- Identify gaps in data coverage
- Recommendations for metadata improvements

#### 4. Compliance Check
- Data retention policy adherence
- Access control audit
- Schema change review
- Incident response validation

---

## 🔬 Testing Evidence Database Schema

### New Table: `tbl_test_evidence`

```sql
CREATE TABLE datawarp.tbl_test_evidence (
  evidence_id SERIAL PRIMARY KEY,
  evidence_date DATE DEFAULT CURRENT_DATE,
  goal_id INTEGER,  -- 1-8 for the 8 goals
  metric_name VARCHAR(100),
  target_value NUMERIC,
  actual_value NUMERIC,
  status VARCHAR(20),  -- pass, warn, fail
  evidence_type VARCHAR(50),  -- automated, manual, audit
  notes TEXT,
  created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_evidence_date ON datawarp.tbl_test_evidence(evidence_date);
CREATE INDEX idx_evidence_goal ON datawarp.tbl_test_evidence(goal_id);
```

**Example Entries:**
```sql
INSERT INTO datawarp.tbl_test_evidence (goal_id, metric_name, target_value, actual_value, status, evidence_type, notes) VALUES
(3, 'load_success_rate', 95.0, 89.4, 'warn', 'automated', 'Week 2026-W02: 42/47 loads successful'),
(5, 'metadata_coverage', 90.0, 91.4, 'pass', 'automated', 'Week 2026-W02: 1234/1350 columns have descriptions'),
(8, 'mcp_test_pass_rate', 95.0, 94.4, 'warn', 'automated', 'Session 5: 17/18 agentic tests passing');
```

---

## 📈 Dashboards & Visualization

### Dashboard 1: Goal Progress (Real-Time)

**Grafana/Streamlit dashboard showing:**
- 8 gauges for each goal (green if passing, yellow if warning, red if failing)
- Trend lines for each goal (last 30 days)
- Alert badges for goals below target

**Queries:**
```sql
-- Goal 3: Load Success Rate (Last 7 Days)
SELECT
  COUNT(*) FILTER (WHERE load_status = 'completed') * 100.0 / COUNT(*) as success_rate
FROM datawarp.tbl_load_events
WHERE started_at > NOW() - INTERVAL '7 days';

-- Goal 5: Metadata Coverage
SELECT
  COUNT(*) FILTER (WHERE description IS NOT NULL) * 100.0 / COUNT(*) as coverage
FROM datawarp.tbl_column_metadata;
```

### Dashboard 2: Evidence Trends

**Time-series charts showing:**
- Load success rate (weekly rolling average)
- Metadata coverage growth
- Performance trends (avg load duration)
- MCP test pass rate

### Dashboard 3: Golden Dataset Status

**Table showing:**
- Golden dataset name
- Last test date
- Test status (pass/fail)
- Row count comparison
- Schema drift detected

---

## 🚨 Alert Rules

### Critical Alerts (Immediate Action)

1. **Load Success Rate <80%** (Goal 3)
   - Alert: Slack + Email to on-call DBA
   - Action: Investigate top 3 failure sources immediately

2. **Breaking Schema Change Detected** (Goal 2)
   - Alert: Block deployment, notify team
   - Action: Rollback or emergency review

3. **Zero Metadata Coverage on New Source** (Goal 5)
   - Alert: Block export to Parquet
   - Action: Run enrichment before allowing export

### Warning Alerts (Review Within 24h)

1. **Load Success Rate 80-95%** (Goal 3)
   - Alert: Daily summary email
   - Action: Review and prioritize fixes

2. **Metadata Coverage <90%** (Goal 5)
   - Alert: Weekly summary
   - Action: Schedule re-enrichment

3. **Performance Degradation >20%** (Goal 7)
   - Alert: Weekly summary
   - Action: Profile and optimize

---

## 🎯 Implementation Plan

### Phase 1: Foundation (Week 1)
- [ ] Create `tbl_test_evidence` table
- [ ] Implement basic evidence collection scripts
- [ ] Set up weekly report generation
- [ ] Document current baseline for all 8 goals

### Phase 2: Automation (Week 2)
- [ ] Automate weekly evidence reports
- [ ] Set up alert rules
- [ ] Create dashboard (Streamlit or Grafana)
- [ ] Integrate with load pipeline

### Phase 3: Golden Datasets (Week 3)
- [ ] Define 4 golden datasets (GP Practice, PCN, ADHD, Dementia)
- [ ] Create regression test suite
- [ ] Implement monthly regression runs
- [ ] Document expected outcomes

### Phase 4: Continuous Improvement (Ongoing)
- [ ] Monthly goal review meetings
- [ ] Quarterly audit reports
- [ ] Adjust targets based on production reality
- [ ] Expand golden dataset coverage

---

## Success Criteria for This Framework

✓ **Weekly evidence reports generated automatically**
✓ **All 8 goals have measurable baselines**
✓ **Alert system operational (0 false positives)**
✓ **Dashboard shows real-time goal progress**
✓ **Quarterly audits completed on schedule**
✓ **100% of goals meet or exceed targets (or have documented remediation plans)**

---

**This framework ensures DataWarp testing is not just "running tests" but proving system quality with evidence.**
