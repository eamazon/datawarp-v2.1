# DataWarp v2.1 - Intelligent Load Mode Strategy

**Date:** 2026-01-10
**Status:** Implemented
**Problem:** Automatic determination of append vs replace mode to prevent duplicates

---

## The Challenge

When loading multiple periods of NHS data:
- **Wrong mode = Data corruption**
  - APPEND on refreshed data → Duplicates (e.g., YTD data counted twice)
  - REPLACE on incremental data → Lost history (e.g., transactions deleted)

**Example Scenarios:**

| Data Type | Wrong Mode | Impact |
|-----------|------------|---------|
| Time-series (wide) | APPEND | Each load adds duplicate historical columns |
| YTD Cumulative | APPEND | March YTD + April YTD = double counting |
| Individual transactions | REPLACE | Lose previous period's transactions |
| Point-in-time snapshots | REPLACE | Lose historical snapshots |

---

## Solution: Multi-Layer Classification System

### Architecture

```
Input: Column Names + Description + Table Name
   ↓
Layer 1: Column Pattern Analysis (Deterministic, 95% confidence)
   ↓
Layer 2: Semantic Analysis (Heuristic, 70% confidence)
   ↓
Layer 3: LLM Classification (Optional, 80%+ confidence)
   ↓
Weighted Decision → Load Mode Recommendation
```

### Data Patterns Detected

#### Pattern 1: TIME_SERIES_WIDE (→ REPLACE)
**Indicators:**
- 6+ columns with date patterns: `march_2024`, `april_2024`, `q1_2024`
- Examples: `january_2020`, `fy_2024_2025`, `q3_2024`

**Why REPLACE:**
- Each publication contains full historical time-series
- April 2025 pub includes March 2025 data (refreshed)
- APPENDing would duplicate all historical columns

**Example:** PCN Workforce
- Columns: `march_2020, april_2020, ..., march_2025, april_2025`
- Each publication: Complete 5-year history
- **Mode:** REPLACE

#### Pattern 2: CUMULATIVE_YTD (→ REPLACE)
**Indicators:**
- Columns with: `ytd`, `cumulative`, `running_total`, `total_since`
- Descriptions mentioning: "year-to-date", "accumulated"

**Why REPLACE:**
- March YTD = Jan+Feb+Mar
- April YTD = Jan+Feb+Mar+Apr
- APPENDing April would double-count Jan-Mar

**Example:** NHS Trust Financial YTD
- Columns: `referrals_ytd`, `admissions_ytd`, `budget_spent_ytd`
- April contains March data (cumulative)
- **Mode:** REPLACE

#### Pattern 3: REFRESHED_SNAPSHOT (→ REPLACE)
**Indicators:**
- Descriptions: "latest", "current", "most recent"
- Entire table refreshes each period

**Why REPLACE:**
- Full table snapshot, not incremental
- Each publication supersedes previous

**Example:** Active Patient List
- Each month: Complete list of active patients
- Patients may leave/join between periods
- **Mode:** REPLACE

#### Pattern 4: INCREMENTAL_TRANSACTIONAL (→ APPEND)
**Indicators:**
- Individual-level records
- Columns: `new_`, `during_period`, `in_period`, `this_month`
- Descriptions: "transaction", "event", "individual", "record"

**Why APPEND:**
- Each period adds NEW transactions
- March referrals ≠ April referrals (distinct events)
- REPLACEing would lose previous periods

**Example:** ADHD Individual Referrals
- Each month: New patient referrals
- March: 5,000 referrals (Jan-Mar events)
- April: 1,500 referrals (April events only)
- **Mode:** APPEND

#### Pattern 5: POINT_IN_TIME_SNAPSHOT (→ APPEND)
**Indicators:**
- Columns: `as_of_date`, `snapshot_date`, `end_of_period`, `closing`
- Descriptions: "as of [date]", "snapshot", "position as at"

**Why APPEND:**
- Each period = distinct point-in-time
- March 31 snapshot ≠ April 30 snapshot
- Both are valid, independent data points

**Example:** NHS Trust Capacity Snapshot
- March 31: 1,200 beds available
- April 30: 1,250 beds available
- Both needed for trend analysis
- **Mode:** APPEND

#### Pattern 6: EVENT_LOG (→ APPEND)
**Indicators:**
- Timestamped events
- Columns: `event_timestamp`, `occurred_at`, `logged_at`
- Log-structured data

**Why APPEND:**
- Immutable event log
- Each period adds new events
- Never replace historical events

**Example:** System Audit Log
- Continuous event stream
- **Mode:** APPEND

---

## Classification Algorithm

### Confidence Levels

| Confidence | Meaning | Action |
|------------|---------|--------|
| 95%+ | Very High | Trust classification fully |
| 80-94% | High | Use classification, log for review |
| 60-79% | Medium | Use classification, flag for manual review |
| <60% | Low | Default to REPLACE (safer), require user confirmation |

### Decision Logic

```python
def recommend_mode(pattern, confidence):
    if confidence >= 0.80:
        if pattern in [TIME_SERIES_WIDE, CUMULATIVE_YTD, REFRESHED_SNAPSHOT]:
            return REPLACE
        elif pattern in [INCREMENTAL_TRANSACTIONAL, POINT_IN_TIME_SNAPSHOT, EVENT_LOG]:
            return APPEND

    # Conservative default: REPLACE (prevents duplicates)
    return REPLACE
```

### Why REPLACE is Default

**Duplicates are worse than missing data:**
- Duplicates corrupt analytics (double-counted metrics)
- Missing data is visible (row count drops)
- Users notice missing data immediately
- Users may not notice inflated metrics until analysis

**Recovery:**
- Wrong REPLACE → Reload with APPEND, data recoverable
- Wrong APPEND → Must identify and dedupe, data corrupted

---

## Integration Points

### 1. During Enrichment (enrich_manifest.py)

**Step 1: Analyze Columns**
```python
from datawarp.utils.load_mode_classifier import LoadModeClassifier

classifier = LoadModeClassifier()
result = classifier.classify(
    column_names=source_columns,
    description=source_description,
    table_name=source_table
)

# Store in manifest
source['load_mode'] = result['mode']
source['load_mode_confidence'] = result['confidence']
source['load_mode_reason'] = result['reason']
```

**Step 2: LLM Enhancement (Optional)**
Add to enrichment prompt:
```
Analyze this data source and classify its temporal pattern:

Patterns:
- TIME_SERIES_WIDE: Multiple historical date columns (2020-2025)
- CUMULATIVE_YTD: Year-to-date aggregations
- INCREMENTAL_TRANSACTIONAL: New records each period
- POINT_IN_TIME_SNAPSHOT: Period-specific snapshots
- REFRESHED_SNAPSHOT: Full table refresh
- EVENT_LOG: Timestamped events

Pattern: [classification]
Confidence: [0.0-1.0]
Reason: [explanation]
```

### 2. During Loading (pipeline.py)

**Respect manifest mode:**
```python
# Read mode from manifest
mode = source.get('mode', 'replace')  # Default to replace

if mode == 'replace':
    # Delete existing period data
    conn.execute(f"DELETE FROM {table} WHERE _period = %s", (period,))
    # Insert new data

elif mode == 'append':
    # Check for duplicates first
    existing = conn.execute(
        f"SELECT COUNT(*) FROM {table} WHERE _period = %s",
        (period,)
    ).fetchone()[0]

    if existing > 0:
        print(f"⚠️  Period {period} already exists ({existing} rows)")
        print(f"   Use --force to reload anyway")
        return

    # Insert new data (no delete)
```

### 3. Post-Load Validation

**Duplicate Detection:**
```python
# Check for potential duplicates
duplicates = conn.execute(f"""
    SELECT _period, COUNT(*) as count
    FROM {table}
    GROUP BY _period
    HAVING COUNT(*) > (
        SELECT AVG(row_count) * 1.5
        FROM (
            SELECT _period, COUNT(*) as row_count
            FROM {table}
            GROUP BY _period
        ) sub
    )
""").fetchall()

if duplicates:
    print(f"⚠️  Possible duplicates detected:")
    for period, count in duplicates:
        print(f"   - {period}: {count:,} rows (unusually high)")
    print(f"   Consider using mode='replace' instead")
```

---

## PCN Workforce Analysis

**Test Results:**

```
Input:
  Columns: march_2020, april_2020, may_2020, ..., march_2025, april_2025
  Description: "Primary Care Network Workforce FTE by role, March 2020 to April 2025"
  Table: pcn_wf_fte_gender_role

Classification:
  Pattern: time_series_wide
  Confidence: 95%
  Mode: REPLACE
  Reason: "Found 12 date-based columns indicating time-series data"

Explanation:
  "Data pattern 'time_series_wide' indicates refreshed data - use REPLACE to avoid duplicates"
```

**Validation:**
- ✅ Correct: Each publication contains full 2020-2025 history
- ✅ Mode: REPLACE prevents duplicate historical data
- ✅ Cross-period view: Export single period (latest refresh)

---

## Edge Cases

### Case 1: Mixed Data
**Scenario:** Some sources in publication are time-series, others are transactional

**Solution:** Per-source classification
- Each source gets independent mode determination
- Example: PCN Workforce (REPLACE) + Individual CSV (APPEND)

### Case 2: Publication Structural Change
**Scenario:** Publication changes from snapshot to cumulative mid-year

**Detection:**
- Compare column patterns across periods
- Flag when pattern changes (e.g., no date columns → suddenly has YTD columns)

**Action:**
- Alert user to structural change
- Re-classify with new pattern
- Document change in metadata

### Case 3: Partial Updates
**Scenario:** Publication only includes changed records (delta)

**Detection:**
- Row count significantly lower than previous periods
- Description mentions "changes only", "updates", "deltas"

**Action:**
- Classify as INCREMENTAL_TRANSACTIONAL → APPEND
- Add validation: check row count doesn't drop unexpectedly

### Case 4: Corrected Data
**Scenario:** NHS republishes March data in April with corrections

**Handling:**
- REPLACE mode handles this automatically
- Previous March data deleted, corrected data inserted
- Audit trail in tbl_load_history shows replacement

---

## Future Enhancements

### 1. Learning System
- Track user overrides (manual mode changes)
- Learn from corrections
- Improve classification over time

### 2. Duplicate Detection Post-Load
- Compute row hashes
- Detect identical rows across periods
- Auto-suggest mode change if duplicates found

### 3. Smart Unpivot Detection
- If TIME_SERIES_WIDE detected, suggest unpivot
- Offer to convert wide → long format
- Enable true cross-period time-series analysis

### 4. Metadata-Driven Overrides
- Store user preferences per publication
- "Always APPEND for ADHD individual data"
- "Always REPLACE for PCN Workforce"

---

## Decision Matrix

| Data Characteristic | Pattern | Mode | Confidence |
|---------------------|---------|------|------------|
| 6+ date columns (mar_2024...) | TIME_SERIES_WIDE | REPLACE | 95% |
| YTD/cumulative columns | CUMULATIVE_YTD | REPLACE | 85% |
| Individual records, period-specific | INCREMENTAL_TRANSACTIONAL | APPEND | 75% |
| as_of_date, snapshot indicators | POINT_IN_TIME_SNAPSHOT | APPEND | 80% |
| Event timestamps | EVENT_LOG | APPEND | 90% |
| Full table refresh mentioned | REFRESHED_SNAPSHOT | REPLACE | 75% |
| No clear signals | UNKNOWN | REPLACE | 50% (default) |

---

## Summary

**Key Principle:** **Conservative by default, intelligent when confident**

1. **Analyze columns first** (deterministic, fast, high confidence)
2. **Semantic analysis second** (heuristic, context-aware)
3. **LLM enhancement optional** (highest accuracy, but slower)
4. **Default to REPLACE** (prevents duplicates, safest)
5. **Validate post-load** (catch classification errors)
6. **Learn from corrections** (improve over time)

**Result:** Automatic, intelligent mode selection that prevents data corruption while enabling cross-period analysis.

---

**Status:** Ready for production integration
**Next Steps:** Integrate into enrich_manifest.py, add LLM prompt enhancement
**Owner:** DataWarp v2.1 System
