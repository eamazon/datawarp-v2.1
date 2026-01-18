# Intelligent Adaptive Sampling: Handling Edge Cases

**Date:** 2026-01-18 11:35 UTC
**Problem:** Adaptive sampling with 15 columns works for PATTERNED files, but what about 80 UNIQUE columns?

---

## The Edge Case

**Scenario:** File with 80 completely unique columns (no patterns)

```
Columns: patient_id, patient_name, address, diagnosis_code_1, diagnosis_code_2,
         medication_1, medication_2, lab_test_1, lab_result_1, ...

Problem:
- Adaptive sampling: 15 of 80 columns (19% coverage)
- LLM has NO sample data for 65 columns (81%)
- Must infer from column names ONLY
```

**Risk:** LLM may produce poor metadata for non-sampled columns.

---

## Solution: Two-Tier Adaptive Strategy

### Tier 1: Detect Column Patterns

```python
def detect_column_pattern(columns: List[str]) -> Dict:
    """Detect if columns follow repetitive patterns."""

    # Check for sequential numeric patterns
    pattern_groups = {}
    for col in columns:
        # Extract prefix (before numbers)
        match = re.match(r'^([a-z_]+?)_*(\d+)', col, re.IGNORECASE)
        if match:
            prefix = match.group(1)
            pattern_groups[prefix] = pattern_groups.get(prefix, 0) + 1

    # Pattern detected if 10+ columns share prefix with numbers
    for prefix, count in pattern_groups.items():
        if count >= 10:
            return {
                'has_pattern': True,
                'pattern_prefix': prefix,
                'pattern_count': count,
                'unique_count': len(columns) - count
            }

    return {
        'has_pattern': False,
        'pattern_count': 0,
        'unique_count': len(columns)
    }
```

### Tier 2: Adaptive Sampling Based on Pattern Detection

```python
def intelligent_adaptive_sampling(columns: List[str], sample_rows: List[Dict]) -> List[Dict]:
    """
    Intelligently sample based on column patterns.

    Rules:
    1. Files ≤ 50 columns: Full sampling (no change)
    2. Pattern files (≥ 10 sequential columns):
       - Sample pattern: 3 columns (first, middle, last)
       - Sample unique: ALL unique columns
       - Total: ~15-20 columns
    3. Non-pattern files (mostly unique):
       - Use higher threshold (75 columns)
       - Sample more columns (25-30)
       - Coverage: ~35-40%
    """

    if len(columns) <= 50:
        return sample_rows  # Small file - full sampling

    pattern_info = detect_column_pattern(columns)

    if pattern_info['has_pattern']:
        # PATTERN FILE: Sample pattern lightly, keep all unique
        return _sample_pattern_file(columns, sample_rows, pattern_info)
    else:
        # UNIQUE FILE: Need higher coverage
        return _sample_unique_file(columns, sample_rows, threshold=75, sample_cols=30)
```

---

## Detailed Strategy

### Strategy A: Pattern Files (RTT Provider)

**Characteristics:**
- 119 total columns
- 105 pattern columns (week_0_1, week_1_2, ...)
- 14 unique columns

**Sampling:**
```python
# Pattern columns: Sample 3 (first, middle, last)
pattern_samples = [week_0_1, week_52_53, week_104_pl]

# Unique columns: Keep ALL
unique_samples = [provider_code, provider_name, total_*, ...]  # All 14

# Total sampled: 3 + 14 = 17 columns
# Coverage: 14.3% (but 100% of unique columns!)
```

**Why this works:**
- LLM sees ALL unique columns with data
- Pattern inferred from 3 samples
- Total sample_rows: manageable size

---

### Strategy B: Mostly-Unique Files (80 unique columns)

**Characteristics:**
- 80 total columns
- 0 pattern columns (all unique)
- 80 unique columns

**Sampling approach 1: Higher threshold**
```python
# Only apply adaptive sampling if > 75 columns (not 50)
if len(columns) > 75:
    # Sample 30 columns (not 15)
    # Coverage: 37.5% (vs 19%)
```

**Sampling approach 2: Stratified sampling**
```python
# Categorize by column type (from names)
identifiers = [patient_id, provider_code, ...]  # Keep ALL
dates = [referral_date, appointment_date, ...]  # Sample 50%
codes = [diagnosis_code_1, procedure_code_1, ...]  # Sample 50%
measures = [lab_result_1, vital_signs_bp, ...]  # Sample 50%
text = [patient_name, address_line_1, ...]  # Sample 50%

# Ensures representation across types
```

---

## Revised Threshold Decision Tree

```
Count columns in file
  │
  ├─ ≤ 50 columns → Full sample_rows (no adaptive sampling)
  │
  ├─ 51-75 columns AND no pattern detected
  │                  → Full sample_rows (risky to sample unique columns)
  │
  ├─ 51-150 columns AND pattern detected (≥10 sequential cols)
  │                  → Pattern-aware sampling:
  │                     - Sample pattern: 3 columns
  │                     - Sample unique: ALL unique columns
  │                     - Total: typically 15-25 columns
  │
  └─ > 75 columns AND no pattern detected
                     → Aggressive sampling:
                        - Sample 30-40 columns (stratified)
                        - Coverage: 35-50%
                        - Prioritize diverse column types
```

---

## Implementation

### Core Function

```python
def adaptive_sample_rows(
    columns: List[str],
    sample_rows: List[Dict],
    force_threshold: int = None
) -> Tuple[List[Dict], Dict]:
    """
    Intelligently sample sample_rows based on column patterns.

    Returns:
        (filtered_sample_rows, sampling_info)
    """

    col_count = len(columns)

    # Threshold 1: Small files - no sampling
    if col_count <= 50:
        return sample_rows, {'strategy': 'full', 'sampled': col_count}

    # Detect patterns
    pattern_info = detect_column_pattern(columns)

    # Threshold 2: Medium files without patterns - be conservative
    if col_count <= 75 and not pattern_info['has_pattern']:
        return sample_rows, {
            'strategy': 'full',
            'reason': 'mostly_unique_below_threshold',
            'sampled': col_count
        }

    # Pattern-aware sampling
    if pattern_info['has_pattern']:
        # Sample pattern lightly, keep all unique
        pattern_cols = _get_pattern_columns(columns, pattern_info)
        unique_cols = [c for c in columns if c not in pattern_cols]

        # Sample pattern: first, middle, last
        pattern_samples = [
            pattern_cols[0],
            pattern_cols[len(pattern_cols)//2],
            pattern_cols[-1]
        ]

        # Keep ALL unique columns
        sample_cols = unique_cols + pattern_samples

        # Filter sample_rows
        filtered_rows = [
            {col: row[col] for col in sample_cols if col in row}
            for row in sample_rows
        ]

        return filtered_rows, {
            'strategy': 'pattern_aware',
            'pattern_count': len(pattern_cols),
            'unique_count': len(unique_cols),
            'sampled': len(sample_cols),
            'coverage_unique': '100%'
        }

    else:
        # Large file, mostly unique - stratified sampling
        sample_cols = _stratified_sample(columns, target=30)

        filtered_rows = [
            {col: row[col] for col in sample_cols if col in row}
            for row in sample_rows
        ]

        return filtered_rows, {
            'strategy': 'stratified',
            'unique_count': col_count,
            'sampled': len(sample_cols),
            'coverage': f'{100 * len(sample_cols) / col_count:.1f}%'
        }
```

### Stratified Sampling Helper

```python
def _stratified_sample(columns: List[str], target: int = 30) -> List[str]:
    """
    Sample columns across different types for diversity.

    Categories detected from column names:
    - IDs: *_id, *_code
    - Dates: *_date, *_time
    - Names: *_name, *_description
    - Measures: *_count, *_total, *_percentage
    - Codes: diagnosis_*, procedure_*, medication_*
    """

    categories = {
        'ids': [],
        'dates': [],
        'names': [],
        'measures': [],
        'codes': [],
        'other': []
    }

    # Categorize
    for col in columns:
        col_lower = col.lower()
        if '_id' in col_lower or '_code' in col_lower and 'diagnosis' not in col_lower:
            categories['ids'].append(col)
        elif '_date' in col_lower or '_time' in col_lower:
            categories['dates'].append(col)
        elif '_name' in col_lower or '_description' in col_lower:
            categories['names'].append(col)
        elif any(x in col_lower for x in ['_count', '_total', '_percentage', '_score']):
            categories['measures'].append(col)
        elif any(x in col_lower for x in ['diagnosis_', 'procedure_', 'medication_']):
            categories['codes'].append(col)
        else:
            categories['other'].append(col)

    # Sample proportionally
    sampled = []

    # Always keep all IDs (important for context)
    sampled.extend(categories['ids'])
    remaining = target - len(sampled)

    # Distribute remaining across other categories
    for category in ['dates', 'names', 'measures', 'codes', 'other']:
        items = categories[category]
        if items and remaining > 0:
            # Take ~20% from each category
            take = max(1, min(len(items) // 5, remaining // 4))
            # Spread evenly (first, middle, last)
            if len(items) >= 3:
                sampled.extend([items[0], items[len(items)//2], items[-1]])
            else:
                sampled.extend(items[:take])
            remaining = target - len(sampled)

    return sampled[:target]
```

---

## Edge Case Coverage

### Case 1: RTT Provider (105 pattern + 14 unique)
```
Strategy: pattern_aware
Sampled: 3 pattern + 14 unique = 17 columns
Coverage unique: 100%
Result: ✅ Validated (works)
```

### Case 2: 80 Unique Columns (no pattern)
```
Strategy: stratified (if > 75 cols) OR full (if ≤ 75 cols)
Sampled: 30 columns (if > 75) or 80 (if ≤ 75)
Coverage: 37.5% or 100%
Result: ⏳ Needs testing
```

### Case 3: 60 Unique Columns (no pattern)
```
Strategy: full (below 75 threshold for non-pattern)
Sampled: 60 columns (all)
Coverage: 100%
Result: Conservative but safe
```

### Case 4: 200 Columns (150 pattern + 50 unique)
```
Strategy: pattern_aware
Sampled: 3 pattern + 50 unique = 53 columns
Coverage unique: 100%
Result: Should work (same as RTT)
```

---

## Recommended Thresholds (Revised)

| File Type | Column Count | Strategy | Sample Columns |
|-----------|--------------|----------|----------------|
| Small | ≤ 50 | Full | All |
| Medium pattern | 51-150 with pattern | Pattern-aware | 3 pattern + all unique |
| Medium unique | 51-75 no pattern | Full | All (conservative) |
| Large unique | 76-150 no pattern | Stratified | 30-40 (~35%) |
| Very large pattern | > 150 with pattern | Pattern-aware | 3 pattern + all unique |
| Very large unique | > 150 no pattern | Stratified | 40-50 (~30%) |

---

## Testing Plan

### Test 1: Pattern file (Already validated ✅)
```
File: RTT Provider (119 cols, 105 pattern)
Strategy: pattern_aware
Expected: 17 sampled, all 462 cols enriched
Status: ✅ PASSED
```

### Test 2: Unique file (Need to test)
```
File: Mock patient data (80 unique cols)
Strategy: full (≤ 75) or stratified (> 75)
Expected: All columns enriched with good metadata
Status: ⏳ TODO
```

### Test 3: Mixed file
```
File: 30 pattern + 60 unique = 90 total
Strategy: pattern_aware
Expected: 3 pattern + 60 unique = 63 sampled
Status: ⏳ TODO
```

---

## Decision Matrix

```
if columns <= 50:
    return FULL_SAMPLING  # Safe for small files

if has_pattern(columns):
    return PATTERN_AWARE_SAMPLING  # Works for RTT (validated)

if columns <= 75:
    return FULL_SAMPLING  # Conservative for medium unique files

if columns > 75:
    return STRATIFIED_SAMPLING  # Aggressive for large unique files
```

---

## Next Steps

1. ✅ Identify edge case (80 unique columns)
2. ✅ Design intelligent solution
3. ⏳ Implement pattern detection
4. ⏳ Implement stratified sampling
5. ⏳ Test with mock 80-column dataset
6. ⏳ Validate enrichment quality
7. ⏳ Deploy to production

---

**Status:** Design complete, needs empirical validation
**Risk mitigation:** Intelligent thresholds + pattern-aware sampling
**Next:** Test with 80 unique columns
