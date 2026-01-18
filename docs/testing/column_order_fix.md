# Column Order Fix for Pattern Compression

**Date:** 2026-01-18 02:30 UTC
**Issue:** Column order mismatch between `columns` list and `sample_rows` dictionaries
**Status:** ✅ FIXED

---

## Problem Description

### Original Issue
In the compressed manifest, the `columns` list and `sample_rows` dictionaries had different orderings:

**columns list:**
```yaml
columns:
  - provider_level_data_region_code
  - provider_code
  - provider_name
  - treatment_function_code
  - treatment_function
  - total_number_of_incomplete_pathways      # Summary columns
  - total_within_18_weeks
  - ...
  - the_number_of_incomplete_pathways_by_week_since_referral_0_1    # Pattern columns LAST
  - the_number_of_incomplete_pathways_by_week_since_referral_1_2
  - the_number_of_incomplete_pathways_by_week_since_referral_104_pl
```

**sample_rows (WRONG ORDER):**
```yaml
sample_rows:
  - provider_level_data_region_code: Y56
    provider_code: R1H
    provider_name: BARTS HEALTH NHS TRUST
    treatment_function_code: C_100
    treatment_function: General Surgery Service
    the_number_of_incomplete_pathways_by_week_since_referral_0_1: 239    # Pattern columns FIRST
    the_number_of_incomplete_pathways_by_week_since_referral_1_2: 103
    the_number_of_incomplete_pathways_by_week_since_referral_104_pl: 0
    total_number_of_incomplete_pathways: 4720                            # Summary columns LAST
    total_within_18_weeks: 2386
    ...
```

### Root Cause
The compression code used a dict comprehension that preserved the **original dictionary key order** from the uncompressed rows, instead of reordering to match the compressed columns list.

**Buggy code:**
```python
compressed_row = {k: v for k, v in row.items() if k in compressed_cols_set}
```

This filtered keys but didn't reorder them.

---

## Solution

### Code Fix
**File:** `src/datawarp/pipeline/column_compressor.py`
**Lines:** 113-122

**Before:**
```python
# CRITICAL: Also compress sample_rows to only include compressed columns
if 'sample_rows' in compressed_preview:
    compressed_cols_set = set(non_pattern_cols + sample_cols)
    compressed_sample_rows = []
    for row in compressed_preview['sample_rows']:
        compressed_row = {k: v for k, v in row.items() if k in compressed_cols_set}
        compressed_sample_rows.append(compressed_row)
    compressed_preview['sample_rows'] = compressed_sample_rows
```

**After:**
```python
# CRITICAL: Also compress sample_rows to only include compressed columns
# AND maintain same order as columns list
if 'sample_rows' in compressed_preview:
    compressed_cols_list = non_pattern_cols + sample_cols  # Ordered list
    compressed_sample_rows = []
    for row in compressed_preview['sample_rows']:
        # Build dict in same order as columns list
        compressed_row = {col: row[col] for col in compressed_cols_list if col in row}
        compressed_sample_rows.append(compressed_row)
    compressed_preview['sample_rows'] = compressed_sample_rows
```

**Key Change:** Iterate through `compressed_cols_list` (ordered) instead of `row.items()` (original order).

---

## Validation

### Test 1: Order Consistency Check
Verified all 4 data sheets have matching order between `columns` list and `sample_rows`:

```
Source 0: xlsx_77252_provider
  Columns in list: 17
  Keys in sample_rows[0]: 17
  ✅ ORDER MATCHES

Source 1: xlsx_77252_provider_with_dta
  Columns in list: 10
  Keys in sample_rows[0]: 10
  ✅ ORDER MATCHES

Source 2: xlsx_77252_is_provider
  Columns in list: 17
  Keys in sample_rows[0]: 17
  ✅ ORDER MATCHES

Source 3: xlsx_77252_is_provider_with_dta
  Columns in list: 10
  Keys in sample_rows[0]: 10
  ✅ ORDER MATCHES
```

### Test 2: Manual Inspection
**File:** `manifests/test/rtt_provider_apr25_compressed.yaml`

**columns list:**
```yaml
columns:
  - provider_level_data_region_code
  - provider_code
  - provider_name
  - treatment_function_code
  - treatment_function
  - total_number_of_incomplete_pathways
  - total_within_18_weeks
  - within_18_weeks
  - average_median_waiting_time_in_weeks
  - col_92nd_percentile_waiting_time_in_weeks
  - total_52_plus_weeks
  - total_78_plus_weeks
  - total_65_plus_weeks
  - col_52_plus_weeks
  - the_number_of_incomplete_pathways_by_week_since_referral_0_1
  - the_number_of_incomplete_pathways_by_week_since_referral_1_2
  - the_number_of_incomplete_pathways_by_week_since_referral_104_pl
```

**sample_rows[0] (NOW CORRECT):**
```yaml
- provider_level_data_region_code: Y56
  provider_code: R1H
  provider_name: BARTS HEALTH NHS TRUST
  treatment_function_code: C_100
  treatment_function: General Surgery Service
  total_number_of_incomplete_pathways: 4720
  total_within_18_weeks: 2386
  within_18_weeks: 0.505508474576271
  average_median_waiting_time_in_weeks: 17.551724137931
  col_92nd_percentile_waiting_time_in_weeks: 46.9294117647059
  total_52_plus_weeks: 201
  total_78_plus_weeks: 1
  total_65_plus_weeks: 9
  col_52_plus_weeks: 0.042584745762711866
  the_number_of_incomplete_pathways_by_week_since_referral_0_1: 239
  the_number_of_incomplete_pathways_by_week_since_referral_1_2: 103
  the_number_of_incomplete_pathways_by_week_since_referral_104_pl: 0
```

✅ **Order matches perfectly!**

### Test 3: YAML Validity
```bash
$ wc -l manifests/test/rtt_provider_apr25_compressed.yaml
332 manifests/test/rtt_provider_apr25_compressed.yaml

$ python3 -c "import yaml; yaml.safe_load(open('manifests/test/rtt_provider_apr25_compressed.yaml'))"
✅ Valid YAML
```

---

## Impact Assessment

### Why This Matters

1. **Consistency:** LLM receives columns and sample data in same order
2. **Readability:** Humans inspecting compressed manifest can follow column order
3. **Correctness:** Sample values align with column headers
4. **Debugging:** Easier to validate compression worked correctly

### What Doesn't Break

- ✅ LLM enrichment still works (YAML keys are unordered in dicts)
- ✅ Data loading unaffected (uses column names, not order)
- ✅ Unit tests still pass
- ✅ Backward compatibility maintained

### Additional Benefits

- Better YAML formatting for human review
- Compressed manifests easier to inspect
- Values align with column headers in documentation

---

## Testing Checklist

- ✅ Order matches for all 4 data sheets
- ✅ YAML valid after compression
- ✅ LLM enrichment succeeds (no YAML errors)
- ✅ Data loading works correctly
- ✅ Unit tests pass

---

## Related Issues

### Issue 1: sample_rows Compression (Fixed)
- **When:** 2026-01-18 01:30 UTC
- **What:** sample_rows not being compressed at all
- **Fix:** Added sample_rows filtering logic

### Issue 2: Column Order (Fixed)
- **When:** 2026-01-18 02:30 UTC
- **What:** sample_rows order didn't match columns list
- **Fix:** Iterate through ordered columns list instead of row dict

### Future Enhancements
- Consider adding validation check for order consistency
- Add test case specifically for column order matching
- Document expected YAML format in compression module

---

## Lessons Learned

### What Worked
- User inspection of output caught the issue
- Automated validation script confirmed fix across all sheets
- Iterative testing with real data revealed edge cases

### What to Watch
- Dict comprehensions preserve insertion order (Python 3.7+) but can mislead
- Always test with actual YAML inspection, not just programmatic checks
- Order matters for human readability even if code doesn't care

### Key Insight
> "Sample data should mirror column structure, not just content. Order communicates relationships."

---

**Fixed:** 2026-01-18 02:30 UTC
**Validated:** All 4 sheets, manual + automated checks
**Status:** ✅ PRODUCTION READY
