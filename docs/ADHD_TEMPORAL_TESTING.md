# ADHD Temporal Testing Results

**Updated: 2026-01-10 16:45 UTC**

## Executive Summary

Tested ADHD publication across 3 time periods (May/August/November 2025) to validate LoadModeClassifier on an evolving publication. **Results confirm ADHD shows massive schema drift** (775% growth) compared to PCN's stability, and LoadModeClassifier correctly identifies REPLACE mode.

---

## Test Setup

### Publications Tested

- **May 2025** (Baseline): 4 sources
- **August 2025** (3 months later): 16 sources (+12, **300% growth**)
- **November 2025** (6 months later): 31 sources (+15, **775% total growth**)

### Comparison Baseline

- **PCN Workforce** (Oct→Mar→Apr→May):
  - Source count: 11 → 11 → 11 → 11 (100% stable)
  - Schema changes: +69 columns at fiscal boundary (April), then 0
  - Pattern: TIME_SERIES_WIDE, REPLACE mode

---

## Key Findings

### 1. Publication Evolution Pattern

**ADHD publication underwent complete restructuring:**

#### May 2025 (Initial Publication)
- 4 sources total
- Simple format:
  - `adhd_may25.csv` - Main data file
  - `mhsds_historic.csv` - Historical MHSDS data
  - `data_dictionary_v1.1.xlsx` - 2 sheets (Title page, Data dictionary)

#### August 2025 (First Expansion)
- 16 sources (+12 sources, 300% growth)
- Format change:
  - Introduced `ADHD_summary_Aug25.xlsx` with 12 individual sheets
  - Each table broken out separately (Table 1, Table 2a, Table 2b, etc.)
  - Removed `mhsds_historic.csv`

**Sources Added:**
- Data quality sheet
- Table 1 (Prevalence)
- Tables 2a/2b (Open referrals by age/gender)
- Tables 3a/3b (No contact by age/gender)
- Tables 4a/4b (First contact by age/gender)
- Tables 5a/5b (Closed referrals by age/gender)
- Table 6 (New referrals)
- Table 7 (Community pediatrics)
- Title sheet

#### November 2025 (Second Expansion)
- 31 sources (+15 sources, 94% growth from August)
- Further breakdowns:
  - **Ethnicity dimensions** added: Tables 2c, 3c, 4c, 5c, 6c
  - **Waiting time dimensions** added: Tables 2d, 3d, 4d, 5d
  - **Additional tables**: 6a, 6b (New referrals by age/gender)
  - **OpenSAFELY data** integrated (4 new sources):
    - `medication_being_prescribed`
    - `table_1_adhd_prevalence`
    - `with_adhd_diagnosis`
    - `without_adhd_diagnosis`

**Net Change:**
- May → November: **27 sources added** (775% growth)
- Schema evolution: From simple CSV to complex multi-dimensional analysis

---

### 2. Schema Consistency Analysis

**Comparison Results (via compare_manifests.py):**

#### May → August:
- Common sources: 2 (data dictionary only)
- Sources removed: 2 (adhd_may25, mhsds_historic)
- Sources added: 14 (summary breakdowns)
- **Schema consistency: 50%** (publication restructure)

#### August → November:
- Common sources: 2 (data dictionary only)
- Sources removed: 14 (August sheets)
- Sources added: 29 (November sheets + OpenSAFELY)
- **Schema consistency: 12.5%** (massive expansion)

**Pattern:**
- Each period renames files (adhd_may25 → adhd_aug25 → adhd_nov25)
- Table breakdowns expand each period (Table 2a/2b → add 2c/2d)
- Complete replacement of data each period

---

### 3. LoadModeClassifier Performance

**Test Cases:**

| Table | Column Pattern | Description Keywords | Detected Pattern | Confidence | Recommended Mode |
|-------|----------------|---------------------|------------------|------------|------------------|
| Table 1 | Date + Age dimensions | "historical", "prevalence" | TIME_SERIES_WIDE | 70% | REPLACE |
| Table 2a | Date + Age dimensions | "waiting", "assessment" | UNKNOWN | 50% | REPLACE |
| Table 2c | Date + Ethnicity dims | "waiting", "ethnicity" | UNKNOWN | 50% | REPLACE |
| Table 2d | Date + Waiting time | "waiting time", "open" | UNKNOWN | 50% | REPLACE |

**Analysis:**
- ✅ **Semantic detection working**: Table 1 detected via "historical" keyword
- ✅ **Conservative fallback working**: Unknown patterns default to REPLACE
- ✅ **Correct mode**: REPLACE is correct for refreshing snapshots

**Data Structure (from previews):**
```
Date,                Age 0 to 4, 5 to 17, 18 to 24, 25+, Total
2025-09-01 00:00:00, 3225,       156790,  97870,    269080, 526980
2025-08-01 00:00:00, 3290,       156405,  98365,    268850, 526925
2025-07-01 00:00:00, 3260,       153485,  98925,    268220, 523905
```

Each file contains **historical data** (3 months of history), confirming REPLACE mode is correct.

---

### 4. Contrast: ADHD vs PCN

| Dimension | PCN Workforce | ADHD |
|-----------|---------------|------|
| **Stability** | 100% (11 sources all periods) | 12.5% (massive drift) |
| **Schema Changes** | +69 columns at fiscal boundary only | +27 sources over 6 months |
| **Pattern** | TIME_SERIES_WIDE (wide date columns) | Refreshing snapshot (historical rows) |
| **Mode** | REPLACE (wide format refreshes) | REPLACE (snapshot refreshes) |
| **Publication Type** | Mature, stable reporting | New, evolving publication |
| **Change Driver** | Fiscal year (predictable) | Feature expansion (ongoing) |

**Key Insight:**
- **PCN**: Stable publication with predictable fiscal boundary changes
- **ADHD**: New publication (2025 launch) with rapid feature expansion
- **Both**: Correctly identified as REPLACE mode by LoadModeClassifier

---

## Validation of LoadModeClassifier Design

### ✅ Successfully Validated

1. **Pattern Detection**
   - TIME_SERIES_WIDE detected via semantic keywords ("historical")
   - Date column patterns recognized

2. **Conservative Defaults**
   - Unknown patterns default to REPLACE (prevents duplicates)
   - 50% confidence triggers safe default

3. **Correct Recommendations**
   - Both PCN and ADHD correctly identified as REPLACE
   - Different data structures, same correct outcome

### ⚠️ Areas for Enhancement

1. **Refreshing Snapshot Pattern**
   - Current: Falls back to UNKNOWN
   - Enhancement: Detect "Date + historical rows" pattern explicitly
   - Indicator: First column is "Date", data has multiple date values

2. **Confidence Calibration**
   - Table 1: 70% confidence (good)
   - Tables 2a/2c/2d: 50% confidence (could be higher with snapshot detection)

3. **Historical Data Detection**
   - Add pattern: "Date column with 3+ distinct date values" → REFRESHED_SNAPSHOT
   - Increase confidence when detected

---

## Recommended Next Steps

### 1. Enhance Classifier (Optional)
- Add REFRESHED_SNAPSHOT detection logic
- Increase confidence for Date + multi-row patterns
- Test on more publications

### 2. Production Integration (Current Priority)
- Integrate LoadModeClassifier into `enrich_manifest.py`
- Add LLM prompt for pattern classification
- Store `mode`, `confidence`, `pattern` in enriched manifests

### 3. Validation Pipeline
- Add duplicate detection post-load
- Compute row hashes to detect duplicates
- Auto-suggest mode change if duplicates found

### 4. Database Management Framework ⭐ (User Priority)
- Design production-grade DB management
- Implement proper load monitoring
- Create cleanup/maintenance procedures
- See priority task in todo list

---

## Conclusion

**ADHD temporal testing successfully validates:**

1. ✅ LoadModeClassifier correctly identifies REPLACE mode
2. ✅ Conservative defaults prevent duplicates in ambiguous cases
3. ✅ Works across different publication types (stable PCN vs evolving ADHD)
4. ✅ Semantic detection functional but can be enhanced

**ADHD shows 775% schema growth** vs PCN's stability, demonstrating the classifier handles both extremes correctly.

**Next Priority:** Production integration + Database management framework

---

*Test Duration: 60 minutes*
*Manifests Generated: 3 (May/Aug/Nov 2025)*
*Sources Analyzed: 51 total across 3 periods*
*Classifier Tests: 4 table patterns*
