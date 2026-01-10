# DataWarp Implementation Tasks

**Created: 2026-01-10 17:30 UTC**
**Status:** Backlog (for next round of system improvements)

---

## 🎯 Priority 1: Database Management Framework

**Goal:** Implement production-grade database management
**Reference:** `docs/DB_MANAGEMENT_FRAMEWORK.md`
**Estimated Effort:** 4 weeks

### Phase 1: Foundation (Week 1)

- [ ] **Task 1.1:** Add new registry fields to `tbl_data_sources`
  ```sql
  ALTER TABLE datawarp.tbl_data_sources ADD COLUMN
    owner VARCHAR(255),
    purpose TEXT,
    retention_days INTEGER DEFAULT 365,
    load_mode VARCHAR(20) DEFAULT 'replace',
    validation_required BOOLEAN DEFAULT true,
    last_validated_at TIMESTAMP,
    deprecation_reason TEXT,
    archived_at TIMESTAMP;
  ```

- [ ] **Task 1.2:** Create `tbl_validation_results` table
  - Schema defined in DB_MANAGEMENT_FRAMEWORK.md
  - Track validation outcomes per load

- [ ] **Task 1.3:** Create `tbl_source_metrics` table
  - Schema defined in DB_MANAGEMENT_FRAMEWORK.md
  - Track performance and quality metrics

- [ ] **Task 1.4:** Implement load validation framework
  - Add validation gates to `loader/pipeline.py`
  - Implement row count sanity checks
  - Implement schema drift detection
  - Implement data quality checks
  - Store results in `tbl_validation_results`

- [ ] **Task 1.5:** Update CLI with validation flags
  ```bash
  datawarp load-batch manifest.yaml --validate
  ```

**Success Criteria:**
- ✓ All registry fields present
- ✓ Validation tables created
- ✓ Basic validation running on every load
- ✓ Validation results stored

---

### Phase 2: Monitoring (Week 2)

- [ ] **Task 2.1:** Build Dashboard 1 - Load Health
  - SQL queries for success rate, avg duration, failed loads
  - Streamlit or SQL view implementation
  - Alert thresholds defined

- [ ] **Task 2.2:** Build Dashboard 2 - Data Freshness
  - Days since last load query
  - Stale sources detection (>30 days)
  - Load frequency analysis

- [ ] **Task 2.3:** Build Dashboard 3 - Storage & Growth
  - Table size queries (top 20)
  - Storage by domain
  - Row count trends

- [ ] **Task 2.4:** Build Dashboard 4 - Schema Evolution
  - Columns added tracking
  - Tables created tracking
  - High-drift source detection

- [ ] **Task 2.5:** Implement alerting system
  - 🔴 Critical alerts (Slack/Email)
  - 🟠 Warning alerts (Daily digest)
  - 🟡 Info alerts (Weekly summary)

- [ ] **Task 2.6:** Create weekly maintenance script
  ```bash
  scripts/maintenance/weekly_maintenance.sh
  ```

- [ ] **Task 2.7:** Document incident response procedures
  - Runbook for failed loads
  - Runbook for orphaned tables
  - Runbook for duplicate data
  - Runbook for runaway storage

**Success Criteria:**
- ✓ 4 dashboards operational
- ✓ Alerts configured and tested
- ✓ Weekly maintenance automated
- ✓ Incident runbooks documented

---

### Phase 3: Lifecycle Management (Week 3)

- [ ] **Task 3.1:** Implement source registration workflow
  ```bash
  datawarp register SOURCE_CODE --publication "..." --domain "..." --owner "..." --purpose "..."
  ```

- [ ] **Task 3.2:** Add source registration validation
  - Check for duplicate source codes
  - Validate required metadata
  - Store in registry

- [ ] **Task 3.3:** Implement deprecation workflow
  ```bash
  datawarp deprecate SOURCE_CODE --reason "..." --archive-date "..."
  ```

- [ ] **Task 3.4:** Implement archival workflow
  ```bash
  datawarp archive SOURCE_CODE
  ```
  - Move table to `archive` schema
  - Rename with timestamp
  - Export to Parquet
  - Update registry status

- [ ] **Task 3.5:** Create orphan detection script
  ```bash
  scripts/maintenance/detect_orphaned_tables.py
  ```

- [ ] **Task 3.6:** Implement schema change review process
  - Auto-approve threshold (<5 columns)
  - Review queue for larger changes
  - DBA notification system

**Success Criteria:**
- ✓ Source registration enforced
- ✓ Deprecation/archival workflows working
- ✓ Orphan detection automated
- ✓ Schema change review in place

---

### Phase 4: Automation (Week 4)

- [ ] **Task 4.1:** Automate weekly maintenance
  - VACUUM ANALYZE
  - Statistics update
  - Orphan detection
  - Failed load checks
  - Health report generation

- [ ] **Task 4.2:** Automate health reports
  - Weekly email to DBAs
  - Monthly summary reports
  - Quarterly audit reports

- [ ] **Task 4.3:** Automate archival process
  - Identify sources past grace period
  - Export to Parquet
  - Move to archive schema
  - Update registry

- [ ] **Task 4.4:** Integration with monitoring tools
  - Prometheus metrics export
  - Grafana dashboard (if applicable)
  - Log aggregation (ELK/Splunk)

- [ ] **Task 4.5:** Access control implementation
  - Role-based permissions (analyst, engineer, dba)
  - Row-level security on registry
  - Audit logging

**Success Criteria:**
- ✓ Weekly maintenance fully automated
- ✓ Reports generated automatically
- ✓ Archival runs on schedule
- ✓ Monitoring integrated
- ✓ Access control enforced

---

## 🎯 Priority 2: Testing Goals & Evidence Framework

**Goal:** Implement agentic testing with measurable goals
**Reference:** `docs/TESTING_GOALS_AND_EVIDENCE.md`
**Estimated Effort:** 4 weeks

### Phase 1: Foundation (Week 1)

- [ ] **Task 1.1:** Create `tbl_test_evidence` table
  ```sql
  CREATE TABLE datawarp.tbl_test_evidence (
    evidence_id SERIAL PRIMARY KEY,
    evidence_date DATE DEFAULT CURRENT_DATE,
    goal_id INTEGER,
    metric_name VARCHAR(100),
    target_value NUMERIC,
    actual_value NUMERIC,
    status VARCHAR(20),
    evidence_type VARCHAR(50),
    notes TEXT,
    created_at TIMESTAMP DEFAULT NOW()
  );
  ```

- [ ] **Task 1.2:** Implement evidence collection scripts
  ```bash
  scripts/evidence/collect_load_success_rate.py  # Goal 3
  scripts/evidence/collect_metadata_coverage.py  # Goal 5
  scripts/evidence/collect_performance_metrics.py  # Goal 7
  scripts/evidence/collect_mcp_test_results.py  # Goal 8
  ```

- [ ] **Task 1.3:** Document current baseline for all 8 goals
  - Goal 1: Extract Correctness (baseline: TBD)
  - Goal 2: Schema Stability (baseline: TBD)
  - Goal 3: Load Success Rate (baseline: 89%)
  - Goal 4: Data Quality (baseline: TBD)
  - Goal 5: Metadata Coverage (baseline: 95%)
  - Goal 6: Cross-Period Consistency (baseline: 100%)
  - Goal 7: Performance (baseline: TBD)
  - Goal 8: MCP Server (baseline: 94%)

- [ ] **Task 1.4:** Set up weekly report generation
  ```bash
  scripts/reports/generate_weekly_evidence.py
  ```

**Success Criteria:**
- ✓ Evidence table created
- ✓ Collection scripts working
- ✓ Baselines documented
- ✓ Weekly reports generating

---

### Phase 2: Automation (Week 2)

- [ ] **Task 2.1:** Automate weekly evidence collection
  - Cron job or scheduled task
  - Collect all 8 goals every Monday
  - Store in `tbl_test_evidence`

- [ ] **Task 2.2:** Automate weekly report generation
  - Generate Markdown report
  - Email to stakeholders
  - Archive in `reports/` directory

- [ ] **Task 2.3:** Set up alert rules
  - Critical: Load success <80%
  - Critical: Breaking schema change
  - Critical: Zero metadata on new source
  - Warning: Load success 80-95%
  - Warning: Metadata coverage <90%
  - Warning: Performance degradation >20%

- [ ] **Task 2.4:** Create evidence dashboard (Streamlit)
  - 8 gauges for goal progress
  - Trend lines (last 30 days)
  - Alert badges

**Success Criteria:**
- ✓ Evidence auto-collected weekly
- ✓ Reports auto-generated
- ✓ Alerts configured
- ✓ Dashboard operational

---

### Phase 3: Golden Datasets (Week 3)

- [ ] **Task 3.1:** Define 4 golden datasets
  1. GP Practice Registrations (Nov 2025)
  2. PCN Workforce (Nov 2025)
  3. ADHD Management Information (Nov 2025)
  4. Primary Care Dementia (Jul 2025)

- [ ] **Task 3.2:** Create golden dataset registry
  ```sql
  CREATE TABLE datawarp.tbl_golden_datasets (
    dataset_id SERIAL PRIMARY KEY,
    name VARCHAR(255),
    manifest_path VARCHAR(500),
    expected_sources INTEGER,
    expected_rows BIGINT,
    validation_rules JSONB,
    last_tested_at TIMESTAMP
  );
  ```

- [ ] **Task 3.3:** Implement regression test suite
  ```bash
  scripts/tests/run_golden_dataset_tests.py
  ```
  - Load from manifest
  - Validate source count
  - Validate row counts
  - Validate schema consistency
  - Compare with baseline

- [ ] **Task 3.4:** Document expected outcomes
  - Create `tests/golden/` directory
  - Store expected schemas
  - Store expected row counts
  - Store validation rules

- [ ] **Task 3.5:** Implement monthly regression runs
  - Scheduled job
  - Run all golden datasets
  - Generate regression report
  - Alert on failures

**Success Criteria:**
- ✓ 4 golden datasets defined
- ✓ Regression tests implemented
- ✓ Expected outcomes documented
- ✓ Monthly runs automated

---

### Phase 4: Continuous Improvement (Week 4)

- [ ] **Task 4.1:** Monthly goal review process
  - Meeting template
  - Review scorecard
  - Action items tracking

- [ ] **Task 4.2:** Quarterly audit report generation
  ```bash
  scripts/reports/generate_quarterly_audit.py
  ```

- [ ] **Task 4.3:** Target adjustment process
  - Review actual vs target
  - Adjust targets based on production reality
  - Document rationale

- [ ] **Task 4.4:** Expand golden dataset coverage
  - Add 2 more publications per quarter
  - Cover different NHS publication types
  - Cover different file formats (XLSX, CSV, ZIP)

- [ ] **Task 4.5:** Agent confidence survey
  - Sample 10 research questions
  - Measure success rate with MCP server
  - Identify metadata gaps
  - Recommend improvements

**Success Criteria:**
- ✓ Monthly reviews scheduled
- ✓ Quarterly audits automated
- ✓ Targets adjusted appropriately
- ✓ Golden dataset coverage expanded
- ✓ Agent confidence validated

---

## 🎯 Priority 3: Correct Fiscal Testing Strategy

**Goal:** Complete the originally requested fiscal boundary testing
**Reference:** User's original request for March/April/May 2025 + November 2025
**Status:** ⚠️ Blocked - March/April 2025 URLs return 404

### Issue

**User Request:** Test ADHD fiscal boundary with:
- March 2025 (pre-fiscal boundary)
- April 2025 (fiscal boundary month)
- May 2025 (post-fiscal boundary)
- November 2025 (6 months later)

**Reality:**
- March 2025: ❌ 404 Not Found
- April 2025: ❌ 404 Not Found
- May 2025: ✅ Available
- November 2025: ✅ Available

**What Was Actually Done:**
- Tested May/August/November 2025 instead
- Valid test but NOT the fiscal boundary test requested
- Documented in `ADHD_TEMPORAL_TESTING.md` (temporal testing, not fiscal)

### Options to Complete Original Request

#### Option A: Find Alternative Publication for Fiscal Testing

- [ ] **Task A.1:** Identify NHS publication with March/April/May 2025 availability
  - Candidate: GP Practice Registrations
  - Candidate: Primary Care Dementia
  - Candidate: Appointments in General Practice

- [ ] **Task A.2:** Generate manifests for fiscal suite
  ```bash
  # Pre-fiscal (March 2025)
  python scripts/url_to_manifest.py <url> manifests/test/fiscal/baseline/XXX_mar25.yaml

  # Fiscal boundary (April 2025)
  python scripts/url_to_manifest.py <url> manifests/test/fiscal/fy_transition/XXX_apr25.yaml

  # Post-fiscal (May 2025)
  python scripts/url_to_manifest.py <url> manifests/test/fiscal/stabilization/XXX_may25.yaml
  ```

- [ ] **Task A.3:** Compare March → April for fiscal boundary
  ```bash
  python scripts/compare_manifests.py \
    manifests/test/fiscal/baseline/XXX_mar25.yaml \
    manifests/test/fiscal/fy_transition/XXX_apr25.yaml \
    --fiscal-boundary
  ```

- [ ] **Task A.4:** Validate column additions at fiscal boundary
  - Expected: Significant column additions in April
  - Compare with PCN results (+69 columns)

- [ ] **Task A.5:** Document fiscal boundary testing results
  - Create `docs/FISCAL_BOUNDARY_TESTING.md`
  - Compare across publications
  - Validate LoadModeClassifier on fiscal patterns

#### Option B: Wait for ADHD March/April 2025 Publication

- [ ] **Task B.1:** Monitor ADHD publication schedule
  - Check if historical data published later
  - Subscribe to NHS publication alerts

- [ ] **Task B.2:** Retry URLs periodically
  - Monthly check for March/April 2025
  - If published, complete original test plan

#### Option C: Use PCN Data as Fiscal Boundary Reference

- [ ] **Task C.1:** Document that PCN already validates fiscal boundary
  - PCN March → April showed +69 columns
  - Already tested in Session 4
  - Use as reference for fiscal pattern

- [ ] **Task C.2:** Focus ADHD testing on temporal evolution
  - Current May/Aug/Nov testing is valid
  - Shows different pattern (rapid expansion)
  - Complements PCN's fiscal stability

### Recommended Approach

**Recommendation:** Option C + Option A (in parallel)

1. **Accept current testing as valid** for temporal evolution
2. **Document PCN as fiscal boundary reference** (already complete)
3. **Find alternative publication** for fiscal boundary validation (GP Practice or Dementia)
4. **Update ADHD_TEMPORAL_TESTING.md** to clarify it's temporal, not fiscal

---

## 🎯 Priority 4: Production Integration (Option C from Session)

**Goal:** Integrate LoadModeClassifier into production pipeline
**Estimated Effort:** 1-2 weeks

### Tasks

- [ ] **Task 1:** Integrate LoadModeClassifier into `enrich_manifest.py`
  - Call classifier after structure detection
  - Add pattern/mode/confidence to enriched YAML
  - Document in manifest

- [ ] **Task 2:** Add LLM prompt for pattern classification
  - Enhance LLM enrichment to include pattern detection
  - Use pattern to recommend load mode
  - Store in enriched manifest

- [ ] **Task 3:** Update manifest schema
  ```yaml
  sources:
  - code: source_code
    load_mode: replace  # ← Add this
    load_mode_confidence: 0.95  # ← Add this
    load_mode_pattern: time_series_wide  # ← Add this
  ```

- [ ] **Task 4:** Implement duplicate detection post-load
  - Compute row hashes after load
  - Detect duplicates across periods
  - Alert if duplicates found

- [ ] **Task 5:** Auto-suggest mode change on duplicates
  - If duplicates detected in APPEND mode
  - Suggest changing to REPLACE
  - Require approval before reloading

- [ ] **Task 6:** Test on additional publications
  - GP Practice Registrations
  - Primary Care Dementia
  - Mixed Sex Accommodation
  - Document patterns found

**Success Criteria:**
- ✓ LoadModeClassifier integrated
- ✓ Mode stored in manifests
- ✓ Duplicate detection working
- ✓ Tested on 3+ publications

---

## 📋 Summary

**Total Tasks:** ~80+ tasks across 4 priorities
**Estimated Effort:** 8-10 weeks
**Dependencies:** Some tasks can run in parallel

**Recommended Sequencing:**
1. **Week 1-4:** DB Management Framework (highest production impact)
2. **Week 5-8:** Testing Goals Framework (enables quality monitoring)
3. **Week 9:** Correct Fiscal Testing (complete original request)
4. **Week 10:** Production Integration (polish and scale)

---

## ✅ Next Steps

1. **Review this task list** - Prioritize what's most important
2. **Adjust estimates** - Based on your team's capacity
3. **Create milestones** - Break into manageable sprints
4. **Assign owners** - Determine who implements what
5. **Schedule kickoff** - When to start next round of improvements

---

*This backlog created from Session 6 deliverables (2026-01-10)*
