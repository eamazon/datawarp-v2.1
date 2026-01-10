# Fiscal Year Boundary Testing Plan

**Created: 2026-01-10 18:00 UTC**
**Status:** Ready to Execute
**Publication:** GP Practice Registrations (Patients Registered at a GP Practice)

---

## ✅ Confirmed URLs (All Available)

**Pre-Fiscal (March 2025):**
https://digital.nhs.uk/data-and-information/publications/statistical/patients-registered-at-a-gp-practice/march-2025

**Fiscal Boundary (April 2025):**
https://digital.nhs.uk/data-and-information/publications/statistical/patients-registered-at-a-gp-practice/april-2025

**Post-Fiscal (May 2025):**
https://digital.nhs.uk/data-and-information/publications/statistical/patients-registered-at-a-gp-practice/may-2025

**6 Months Later (November 2025):**
https://digital.nhs.uk/data-and-information/publications/statistical/patients-registered-at-a-gp-practice/november-2025

---

## 🎯 Test Objectives

### Primary Goal
Validate that fiscal year boundary (March → April) drives schema changes in NHS publications

### Hypotheses

**H1: Schema Expansion at Fiscal Boundary**
- **Expect:** March → April shows column additions
- **Baseline:** PCN showed +69 columns at March → April
- **Measure:** Column count difference, new column names

**H2: Schema Stabilization Post-Boundary**
- **Expect:** April → May shows minimal changes
- **Baseline:** PCN showed 0 columns added May
- **Measure:** Column count stability

**H3: LoadModeClassifier Accuracy**
- **Expect:** Correctly identifies TIME_SERIES_WIDE or REFRESHED_SNAPSHOT
- **Measure:** Pattern detection, confidence score, mode recommendation

---

## 📋 Execution Plan

### Phase 1: Generate Manifests (30 min)

```bash
# Create test directory
mkdir -p manifests/test/fiscal_gp_practice

# March 2025 (pre-fiscal baseline)
python scripts/url_to_manifest.py \
  "https://digital.nhs.uk/data-and-information/publications/statistical/patients-registered-at-a-gp-practice/march-2025" \
  manifests/test/fiscal_gp_practice/gp_practice_mar25.yaml

# April 2025 (fiscal boundary)
python scripts/url_to_manifest.py \
  "https://digital.nhs.uk/data-and-information/publications/statistical/patients-registered-at-a-gp-practice/april-2025" \
  manifests/test/fiscal_gp_practice/gp_practice_apr25.yaml

# May 2025 (post-fiscal)
python scripts/url_to_manifest.py \
  "https://digital.nhs.uk/data-and-information/publications/statistical/patients-registered-at-a-gp-practice/may-2025" \
  manifests/test/fiscal_gp_practice/gp_practice_may25.yaml

# November 2025 (6 months later)
python scripts/url_to_manifest.py \
  "https://digital.nhs.uk/data-and-information/publications/statistical/patients-registered-at-a-gp-practice/november-2025" \
  manifests/test/fiscal_gp_practice/gp_practice_nov25.yaml
```

**Success Criteria:**
- ✓ 4 manifests generated
- ✓ No YAML errors
- ✓ Structure detection successful

---

### Phase 2: Compare March → April (Fiscal Boundary) (15 min)

```bash
# Critical comparison: Pre-fiscal vs Fiscal boundary
python scripts/compare_manifests.py \
  manifests/test/fiscal_gp_practice/gp_practice_mar25.yaml \
  manifests/test/fiscal_gp_practice/gp_practice_apr25.yaml \
  --fiscal-boundary
```

**Expected Output:**
```
📊 Summary:
  Common sources: X
  Only in march: 0 (expect no removals)
  Only in april: Y (expect additions)
  Schema consistency: <100%

➕ Sources added in april:
   - [New fiscal year columns/tables]

🔍 Column Changes:
   - [Detailed column additions]
```

**Key Metrics to Capture:**
- Number of sources added
- Number of columns added per source
- Total column additions (compare with PCN: +69)
- Schema consistency percentage

---

### Phase 3: Compare April → May (Stabilization) (10 min)

```bash
# Validation: Fiscal → Post-fiscal should be stable
python scripts/compare_manifests.py \
  manifests/test/fiscal_gp_practice/gp_practice_apr25.yaml \
  manifests/test/fiscal_gp_practice/gp_practice_may25.yaml
```

**Expected Output:**
```
📊 Summary:
  Common sources: X
  Only in april: 0-2 (minimal)
  Only in may: 0-2 (minimal)
  Schema consistency: >95% (expect stability)

Assessment:
  🟢 STABLE: Minimal changes post-fiscal boundary
```

**Key Metrics:**
- Column additions (expect: 0 or <5)
- Schema consistency (expect: >95%)

---

### Phase 4: LoadModeClassifier Testing (15 min)

```bash
# Test classifier on GP Practice data
python test_classifier_gp_practice.py
```

**Test Script:**
```python
from src.datawarp.utils.load_mode_classifier import LoadModeClassifier

classifier = LoadModeClassifier()

# Sample columns from GP Practice
test_columns = [
    "Date", "Practice Code", "Practice Name",
    "Male 0-4", "Female 0-4", "Male 5-9", "Female 5-9",
    # ... age/gender dimensions
]

result = classifier.classify(
    column_names=test_columns,
    description="Patients registered at GP practices by age and gender",
    table_name="tbl_gp_practice_registrations"
)

print(f"Pattern: {result['pattern'].value}")
print(f"Confidence: {result['confidence']:.0%}")
print(f"Mode: {result['mode'].value}")
```

**Expected Results:**
- Pattern: TIME_SERIES_WIDE or REFRESHED_SNAPSHOT
- Confidence: >70%
- Mode: REPLACE

---

### Phase 5: Document Findings (30 min)

Create comprehensive report: `docs/testing/GP_PRACTICE_FISCAL_TESTING.md`

**Required Sections:**
1. Executive Summary
2. Test Setup (URLs, dates, publication)
3. Results:
   - March → April (fiscal boundary findings)
   - April → May (stabilization findings)
   - LoadModeClassifier performance
4. Comparison with PCN:
   - GP Practice vs PCN column additions
   - Pattern similarities/differences
5. Validation of Hypotheses
6. Recommendations

---

## 📊 Expected Results Template

### March → April (Fiscal Boundary)

| Metric | PCN (Baseline) | GP Practice (Test) | Status |
|--------|----------------|-------------------|--------|
| Sources added | 0 (same 11) | TBD | ⏳ |
| Columns added | +69 | TBD | ⏳ |
| Schema consistency | 11/11 sources stable | TBD | ⏳ |
| Pattern detected | TIME_SERIES_WIDE | TBD | ⏳ |

### April → May (Stabilization)

| Metric | PCN (Baseline) | GP Practice (Test) | Status |
|--------|----------------|-------------------|--------|
| Sources added | 0 | TBD | ⏳ |
| Columns added | 0 | TBD | ⏳ |
| Schema consistency | 100% | TBD | ⏳ |

---

## ✅ Success Criteria

**Test is successful if:**
1. ✓ All 4 manifests generate without errors
2. ✓ March → April shows column additions (>10 columns)
3. ✓ April → May shows stability (<5 column changes)
4. ✓ LoadModeClassifier detects pattern with >70% confidence
5. ✓ Findings documented in comprehensive report

**Hypothesis validated if:**
- H1: ✓ Fiscal boundary drives schema expansion (March → April)
- H2: ✓ Schema stabilizes post-boundary (April → May)
- H3: ✓ LoadModeClassifier correctly identifies pattern

---

## 🚨 Potential Issues

### Issue 1: GP Practice May Have Different Pattern

**Observation:** GP Practice is population registry (not workforce like PCN)
**Impact:** May show different column additions
**Mitigation:** Compare pattern, not absolute numbers

### Issue 2: Publication Structure Differences

**Observation:** GP Practice may use different file format (CSV vs XLSX)
**Impact:** Different source count, comparison methodology
**Mitigation:** Focus on column changes within each source

### Issue 3: Fiscal Year Definition

**Observation:** Different NHS organizations may have different fiscal calendars
**Impact:** Boundary might be in different month
**Mitigation:** Document actual boundary observed

---

## 📅 Execution Timeline

**Estimated Total Time:** 2 hours

| Phase | Duration | Dependencies |
|-------|----------|--------------|
| Phase 1: Generate Manifests | 30 min | URLs accessible |
| Phase 2: March → April Compare | 15 min | Phase 1 complete |
| Phase 3: April → May Compare | 10 min | Phase 1 complete |
| Phase 4: LoadModeClassifier | 15 min | Phase 1 complete |
| Phase 5: Documentation | 30 min | Phases 2-4 complete |
| **Buffer** | 20 min | Contingency |

---

## 🎯 Next Actions

**Immediate:**
- [ ] Execute Phase 1 (Generate 4 manifests)
- [ ] Execute Phase 2 (March → April comparison)
- [ ] Capture column addition data

**Follow-up:**
- [ ] Execute Phase 3-4
- [ ] Create comprehensive report
- [ ] Update IMPLEMENTATION_TASKS.md (mark fiscal testing complete)

---

## 📚 References

- **Baseline:** docs/testing/E2E_FISCAL_TEST_RESULTS.md (PCN +69 columns)
- **Strategy:** docs/testing/FISCAL_TESTING_FINDINGS.md
- **Classifier:** src/datawarp/utils/load_mode_classifier.py

---

*This plan uses the correct URLs (GP Practice Registrations) for fiscal boundary testing as originally requested.*
