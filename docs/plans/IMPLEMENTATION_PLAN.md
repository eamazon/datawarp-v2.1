# Implementation Plan: Deterministic Schema + Transform Pipeline

**Created:** 2026-01-10
**Status:** Ready for Implementation
**Prerequisite:** AGENTIC_SOLUTION.md analysis complete

---

## Executive Summary

### Problem Statement

```
ADHD August:  "Age 0 to 4" → LLM → "age_0_to_4_referral_count"  ✅ Table created
ADHD November: "Age 0 to 4" → LLM → "age_0_to_4_count"          ❌ Column mismatch!
```

LLM non-determinism breaks cross-period data consolidation.

### Solution Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    DETERMINISTIC LAYER                          │
├─────────────────────────────────────────────────────────────────┤
│  Excel Header    →   to_schema_name()   →   PostgreSQL Column   │
│  "Age 0 to 4"    →   deterministic      →   "age_0_to_4"        │
│                      (no LLM)                                    │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                    METADATA LAYER (Optional)                     │
├─────────────────────────────────────────────────────────────────┤
│  LLM provides:  description, data_type_hint, is_measure         │
│  Stored in:     tbl_column_metadata (non-blocking)              │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                    TRANSFORM LAYER (Edge Cases)                  │
├─────────────────────────────────────────────────────────────────┤
│  Pattern Detection:  3+ date columns → trigger unpivot          │
│  Transformation:     Pandas melt() → long format                │
│  Result:             Stable schema regardless of date range      │
└─────────────────────────────────────────────────────────────────┘
```

### Publication Pattern Support

| Pattern | Example | Schema Stable? | Solution | Phase |
|---------|---------|----------------|----------|-------|
| Stable | GP Practice | ✅ Yes | Direct load | P0 |
| Column Shift | ADHD | ✅ Yes | Fingerprint ignores empty | P0 |
| Long Format | A&E Waiting, MSA | ✅ Yes | Direct load | P0 |
| Date-as-Columns | PCN Workforce | ❌ No | Auto-unpivot | P3 |
| Rolling Columns | Dementia 65+ | ❌ No | Auto-unpivot | P3 |

---

## Phase 0: Deterministic Naming (CRITICAL PATH)

**Goal:** ADHD Aug→Nov loads without schema drift error.  
**Effort:** 2-3 hours  
**Risk:** None - this is pure improvement

### Task 0.1: Create schema_utils.py

**File:** `scripts/schema_utils.py` (NEW)

```python
#!/usr/bin/env python3
"""
Deterministic schema naming utilities.

This module removes LLM from the critical path for schema generation.
Same input → same output, always.
"""
import re
import hashlib
from typing import Optional


def to_schema_name(header: str) -> Optional[str]:
    """
    Convert Excel header to PostgreSQL column name.
    
    100% DETERMINISTIC - no LLM, no variation.
    
    Examples:
        "Age 0 to 4"     → "age_0_to_4"
        "NHS Number"     → "nhs_number"
        "2024-01-15"     → "col_2024_01_15"  (prefix for leading digit)
        ""               → None (empty headers ignored)
    
    Args:
        header: Raw Excel column header
        
    Returns:
        Valid PostgreSQL column name, or None if header is empty
    """
    if not header or not header.strip():
        return None
    
    # Lowercase and clean
    name = header.lower().strip()
    
    # Replace any non-alphanumeric with underscore
    name = re.sub(r'[^a-z0-9]+', '_', name)
    
    # Strip leading/trailing underscores
    name = name.strip('_')
    
    # Collapse multiple underscores
    name = re.sub(r'_+', '_', name)
    
    # PostgreSQL columns can't start with a digit
    if name and name[0].isdigit():
        name = 'col_' + name
    
    # Truncation with hash suffix for collision safety
    if len(name) > 60:
        hash_suffix = hashlib.md5(name.encode()).hexdigest()[:6]
        name = f"{name[:53]}_{hash_suffix}"
    
    return name if name else None


def to_schema_names(headers: list[str]) -> list[Optional[str]]:
    """
    Convert list of headers to unique schema names.
    
    Handles collisions by adding numeric suffix.
    
    Examples:
        ["Age (0-4)", "Age 0-4"]  → ["age_0_4", "age_0_4_1"]
        ["", "Name", "Code"]     → [None, "name", "code"]
    """
    seen: dict[str, int] = {}
    result: list[Optional[str]] = []
    
    for h in headers:
        name = to_schema_name(h)
        if name is None:
            result.append(None)
            continue
        
        # Check for collision
        if name in seen:
            count = seen[name]
            seen[name] = count + 1
            result.append(f"{name}_{count}")
        else:
            seen[name] = 1
            result.append(name)
    
    return result


def generate_fingerprint(headers: list[str]) -> str:
    """
    Generate deterministic fingerprint from headers.
    
    Used for cross-period source matching.
    Order-independent (sorted), ignores empty headers.
    """
    normalized = [to_schema_name(h) for h in headers if h]
    normalized = [n for n in normalized if n]
    sorted_names = sorted(normalized)
    return hashlib.sha256("|".join(sorted_names).encode()).hexdigest()[:16]
```

### Task 0.2: Modify apply_enrichment.py

**File:** `scripts/apply_enrichment.py`  
**Change:** Use `to_schema_name()` for column names, store LLM output as metadata only

```python
# ADD at top of file
from schema_utils import to_schema_name

# MODIFY merge_column_data function
def merge_column_data(yaml_col: dict, llm_col: dict) -> dict:
    """Merge YAML column with LLM enrichment data."""
    result = yaml_col.copy()
    
    # DETERMINISTIC: Schema name from original header (NOT LLM)
    original_name = yaml_col.get('original_name', '')
    result['column_name'] = to_schema_name(original_name)
    
    # LLM: Optional metadata (non-blocking)
    if llm_col:
        result['description'] = llm_col.get('description', '')
        result['data_type_hint'] = llm_col.get('data_type', 'varchar')
        result['is_measure'] = llm_col.get('is_measure', False)
        result['is_dimension'] = llm_col.get('is_dimension', False)
        result['query_keywords'] = llm_col.get('query_keywords', [])
        # Store LLM's suggestion for audit, but don't use for schema
        result['llm_suggested_name'] = llm_col.get('semantic_name', '')
    
    return result
```

### Task 0.3: Test with ADHD Aug→Nov

**Validation Commands:**

```bash
cd /Users/speddi/projectx/datawarp-v2.1

# 1. Regenerate November manifest with deterministic naming
python scripts/apply_enrichment.py \
  manifests/test_adhd_nov25_enriched.yaml \
  manifests/test_adhd_nov25_enriched_llm_response.json \
  manifests/test_adhd_nov25_canonical_v2.yaml

# 2. Compare column names between August and November
echo "=== August columns ==="
grep "column_name:" manifests/test_adhd_aug25_canonical.yaml | head -20

echo "=== November columns (new) ==="
grep "column_name:" manifests/test_adhd_nov25_canonical_v2.yaml | head -20

# 3. Load November data (should work now!)
datawarp load-batch manifests/test_adhd_nov25_canonical_v2.yaml

# 4. Verify consolidation
psql -h localhost -U databot_dev_user -d datawarp2 -c "
  SELECT _period, COUNT(*) 
  FROM staging.tbl_adhd_summary_new_referrals_age 
  GROUP BY _period 
  ORDER BY _period;
"
# Expected: 2024-08, 2024-11 both present
```

### Success Criteria (Phase 0)

- [ ] `to_schema_name("Age 0 to 4")` → `"age_0_to_4"` (always)
- [ ] August and November manifests have identical column names
- [ ] November loads into existing August tables
- [ ] SQL query returns rows from both periods
- [ ] No schema drift errors

---

## Phase 1: Collision Detection

**Goal:** Prevent duplicate column errors when multiple headers normalize to same name.  
**Effort:** 1 hour  
**Risk:** Low

### Task 1.1: Add collision detection to extractor

**File:** `src/datawarp/extractor/excel.py`

```python
from scripts.schema_utils import to_schema_names

def extract_columns(df: pd.DataFrame) -> list[dict]:
    """Extract column definitions with collision handling."""
    raw_headers = df.columns.tolist()
    schema_names = to_schema_names(raw_headers)
    
    columns = []
    for i, (raw, schema) in enumerate(zip(raw_headers, schema_names)):
        if schema is None:
            continue  # Skip empty columns
        
        columns.append({
            'original_name': raw,
            'column_name': schema,
            'position': i,
            'collision': schema != to_schema_name(raw)  # Flag if suffix added
        })
    
    return columns
```

### Task 1.2: Log collision warnings

```python
# Add to extraction logging
for col in columns:
    if col.get('collision'):
        logger.warning(
            f"Column collision detected: '{col['original_name']}' → '{col['column_name']}'"
        )
```

### Success Criteria (Phase 1)

- [ ] Headers `["Age (0-4)", "Age 0-4"]` → `["age_0_4", "age_0_4_1"]`
- [ ] Collision warning logged
- [ ] No duplicate column errors during table creation

---

## Phase 2: Wide Date Detection

**Goal:** Detect date-as-columns pattern and log warning.  
**Effort:** 2 hours  
**Risk:** Low (detection only, no transform yet)

### Task 2.1: Create date column detector

**File:** `scripts/schema_utils.py` (append)

```python
import re
from typing import Tuple

# Date patterns to detect
DATE_PATTERNS = [
    r'^(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[-_\s]?\d{2,4}$',
    r'^(january|february|march|april|may|june|july|august|september|october|november|december)\s*\d{4}$',
    r'^\d{4}[-_](0?[1-9]|1[0-2])$',  # 2025-01
    r'^(q[1-4])[-_\s]?\d{2,4}$',  # Q1 2025
    r'^\d{2,4}[-/]\d{2,4}$',  # 24/25, 2024/2025
]


def is_date_column(header: str) -> bool:
    """Check if header looks like a date/period column."""
    if not header:
        return False
    norm = header.lower().strip()
    return any(re.match(p, norm, re.IGNORECASE) for p in DATE_PATTERNS)


def detect_wide_date_pattern(headers: list[str]) -> Tuple[bool, list[str], list[str]]:
    """
    Detect if headers contain wide date format.
    
    Returns:
        (is_wide, date_columns, static_columns)
        
    Threshold: 3+ date columns triggers wide format detection
    """
    date_cols = [h for h in headers if is_date_column(h)]
    static_cols = [h for h in headers if h and not is_date_column(h)]
    
    is_wide = len(date_cols) >= 3
    
    return is_wide, date_cols, static_cols
```

### Task 2.2: Add detection to extraction pipeline

**File:** `scripts/url_to_manifest.py` (modify)

```python
from schema_utils import detect_wide_date_pattern

def process_sheet(df: pd.DataFrame, sheet_name: str) -> dict:
    headers = df.columns.tolist()
    
    # Detect wide date pattern
    is_wide, date_cols, static_cols = detect_wide_date_pattern(headers)
    
    if is_wide:
        logger.warning(
            f"⚠️ Wide date pattern detected in '{sheet_name}': "
            f"{len(date_cols)} date columns ({date_cols[:3]}...)"
        )
    
    return {
        'sheet_name': sheet_name,
        'is_wide_format': is_wide,
        'date_columns': date_cols,
        'static_columns': static_cols,
        # ... rest of sheet metadata
    }
```

### Success Criteria (Phase 2)

- [ ] PCN Workforce detected as wide format (has Sep_2025, Oct_2025, Nov_2025)
- [ ] GP Practice NOT detected as wide format (no date columns)
- [ ] Warning logged when wide format detected
- [ ] `is_wide_format: true` in manifest YAML

---

## Phase 3: Auto-Unpivot Transform

**Goal:** Transform wide date format to long format automatically.  
**Effort:** 4-6 hours  
**Risk:** Medium (data transformation)

### Task 3.1: Implement unpivot transformer

**File:** `src/datawarp/transform/unpivot.py` (NEW)

```python
#!/usr/bin/env python3
"""
Universal Unpivot Engine.

Transforms wide date format to long format for stable schema.

Based on ADIE (Autonomous Data Ingestion Engine) PRD spec.
"""
import pandas as pd
import re
from datetime import datetime
from typing import Optional


def parse_date_column(col_name: str) -> Optional[str]:
    """
    Parse date column header to ISO date string.
    
    Examples:
        "Nov-25"      → "2025-11-01"
        "November 2025" → "2025-11-01"
        "2025-11"     → "2025-11-01"
    """
    col_lower = col_name.lower().strip()
    
    # Month-Year patterns
    month_map = {
        'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4,
        'may': 5, 'jun': 6, 'jul': 7, 'aug': 8,
        'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12,
        'january': 1, 'february': 2, 'march': 3, 'april': 4,
        'june': 6, 'july': 7, 'august': 8,
        'september': 9, 'october': 10, 'november': 11, 'december': 12
    }
    
    # Try "Nov-25" or "November 2025" pattern
    for month_str, month_num in month_map.items():
        if col_lower.startswith(month_str):
            # Extract year
            match = re.search(r'(\d{2,4})', col_lower)
            if match:
                year = int(match.group(1))
                if year < 100:
                    year += 2000
                return f"{year}-{month_num:02d}-01"
    
    # Try "2025-11" pattern
    match = re.match(r'(\d{4})[-_](\d{1,2})', col_lower)
    if match:
        year, month = int(match.group(1)), int(match.group(2))
        return f"{year}-{month:02d}-01"
    
    return None


def unpivot_wide_dates(
    df: pd.DataFrame,
    static_columns: list[str],
    date_columns: list[str],
    value_name: str = 'value',
    period_name: str = 'period'
) -> pd.DataFrame:
    """
    Transform wide date format to long format.
    
    WIDE:
    | Org  | Staff_Type | Oct_2025 | Nov_2025 |
    | NHS  | Nurse      | 100      | 110      |
    
    LONG:
    | Org  | Staff_Type | period     | value |
    | NHS  | Nurse      | 2025-10-01 | 100   |
    | NHS  | Nurse      | 2025-11-01 | 110   |
    
    Args:
        df: Input DataFrame in wide format
        static_columns: Columns to keep as-is (id_vars)
        date_columns: Columns to unpivot (value_vars)
        value_name: Name for value column
        period_name: Name for period column
        
    Returns:
        DataFrame in long format
    """
    # Validate columns exist
    missing_static = [c for c in static_columns if c not in df.columns]
    missing_date = [c for c in date_columns if c not in df.columns]
    
    if missing_static:
        raise ValueError(f"Static columns not found: {missing_static}")
    if missing_date:
        raise ValueError(f"Date columns not found: {missing_date}")
    
    # Perform melt
    df_long = pd.melt(
        df,
        id_vars=static_columns,
        value_vars=date_columns,
        var_name='_raw_period',
        value_name=value_name
    )
    
    # Parse period to ISO date
    df_long[period_name] = df_long['_raw_period'].apply(parse_date_column)
    
    # Drop raw period column
    df_long = df_long.drop(columns=['_raw_period'])
    
    # Reorder columns: static, period, value
    col_order = static_columns + [period_name, value_name]
    df_long = df_long[col_order]
    
    return df_long
```

### Task 3.2: Add unpivot_append to loader

**File:** `src/datawarp/loader/batch.py` (modify)

```python
from datawarp.transform.unpivot import unpivot_wide_dates

def load_source(source: dict, conn) -> LoadResult:
    """Load a single source with optional transformation."""
    
    # Check if unpivot needed
    if source.get('is_wide_format'):
        logger.info(f"Applying unpivot transformation for {source['code']}")
        
        df = read_source_file(source)
        
        df_long = unpivot_wide_dates(
            df,
            static_columns=source['static_columns'],
            date_columns=source['date_columns'],
            value_name='metric_value',
            period_name='period'
        )
        
        # Update columns in source metadata
        source['columns'] = generate_columns_from_df(df_long)
        source['transformation_applied'] = 'unpivot_wide_dates'
        
        return load_dataframe(df_long, source, conn)
    
    # Standard load path
    return load_source_standard(source, conn)
```

### Task 3.3: Update manifest schema

**File:** `manifests/schema.yaml` (if exists) or document in YAML

```yaml
# Source with wide date format
sources:
  - code: pcn_workforce_fte
    sheet_name: "FTE by Role"
    is_wide_format: true              # ← Trigger unpivot
    static_columns:                    # ← Keep as-is
      - Organisation
      - Staff_Type
    date_columns:                      # ← Unpivot these
      - Sep_2025
      - Oct_2025
      - Nov_2025
    transformation: unpivot_wide_dates # ← Explicit transform
    columns:                           # ← Result columns (after transform)
      - original_name: Organisation
        column_name: organisation
      - original_name: Staff_Type
        column_name: staff_type
      - original_name: period          # ← Added by transform
        column_name: period
      - original_name: metric_value    # ← Added by transform
        column_name: metric_value
```

### Success Criteria (Phase 3)

- [ ] PCN Workforce Oct + Nov load into same table
- [ ] Table has `period` column with dates (2025-10-01, 2025-11-01)
- [ ] Row count: wide_rows × date_cols = long_rows
- [ ] Fingerprint matches across periods (static columns only)

---

## Phase 4: Metadata Persistence

**Goal:** Store LLM descriptions in database for Parquet export.  
**Effort:** 2-3 hours  
**Risk:** Low

### Task 4.1: Create tbl_column_metadata table

**File:** `sql/05_create_column_metadata.sql` (NEW)

```sql
-- Column metadata for agent consumption
CREATE TABLE IF NOT EXISTS datawarp.tbl_column_metadata (
    id SERIAL PRIMARY KEY,
    canonical_source_code VARCHAR(100) NOT NULL,
    column_name VARCHAR(100) NOT NULL,
    original_name VARCHAR(255),
    description TEXT,
    data_type VARCHAR(50) DEFAULT 'varchar',
    is_dimension BOOLEAN DEFAULT FALSE,
    is_measure BOOLEAN DEFAULT FALSE,
    query_keywords TEXT[],
    sample_values TEXT[],
    null_rate NUMERIC(5,2),
    distinct_count INTEGER,
    metadata_source VARCHAR(20) DEFAULT 'llm',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    
    UNIQUE (canonical_source_code, column_name)
);

CREATE INDEX idx_column_metadata_source 
ON datawarp.tbl_column_metadata(canonical_source_code);

COMMENT ON TABLE datawarp.tbl_column_metadata IS 
'Column-level metadata from LLM enrichment for agent consumption';
```

### Task 4.2: Persist metadata after load

**File:** `src/datawarp/loader/batch.py` (append)

```python
def persist_column_metadata(source: dict, conn):
    """Store column metadata in registry after successful load."""
    
    code = source.get('canonical_code') or source.get('code')
    columns = source.get('columns', [])
    
    for col in columns:
        if not col.get('column_name'):
            continue
            
        upsert_sql = """
        INSERT INTO datawarp.tbl_column_metadata 
            (canonical_source_code, column_name, original_name, 
             description, data_type, is_dimension, is_measure, 
             query_keywords, metadata_source)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (canonical_source_code, column_name) 
        DO UPDATE SET
            description = EXCLUDED.description,
            data_type = EXCLUDED.data_type,
            is_dimension = EXCLUDED.is_dimension,
            is_measure = EXCLUDED.is_measure,
            query_keywords = EXCLUDED.query_keywords,
            updated_at = NOW()
        """
        
        conn.execute(upsert_sql, (
            code,
            col['column_name'],
            col.get('original_name', ''),
            col.get('description', ''),
            col.get('data_type_hint', 'varchar'),
            col.get('is_dimension', False),
            col.get('is_measure', False),
            col.get('query_keywords', []),
            'llm'
        ))
```

### Success Criteria (Phase 4)

- [ ] tbl_column_metadata populated after load
- [ ] Descriptions from LLM available for query
- [ ] Parquet export can read metadata for .md generation

---

## Implementation Schedule

| Phase | Task | Est. Time | Dependencies | Owner |
|-------|------|-----------|--------------|-------|
| **P0** | Create schema_utils.py | 30 min | None | - |
| **P0** | Modify apply_enrichment.py | 1 hour | schema_utils.py | - |
| **P0** | Test ADHD Aug→Nov | 1 hour | apply_enrichment.py | - |
| **P1** | Add collision detection | 1 hour | P0 complete | - |
| **P2** | Wide date detection | 2 hours | P0 complete | - |
| **P3** | Unpivot transformer | 3 hours | P2 complete | - |
| **P3** | Loader integration | 2 hours | Transformer | - |
| **P4** | tbl_column_metadata | 1 hour | P0 complete | - |
| **P4** | Metadata persistence | 2 hours | Table created | - |

**Total Estimate:** 13-14 hours

**Critical Path:** P0 → P1 → (P2 → P3) || P4

---

## Testing Matrix

| Test Case | Input | Expected Output | Validates |
|-----------|-------|-----------------|-----------|
| ADHD Aug + Nov | Same Excel headers | Same table, 2 periods | P0 |
| Collision | `["Age (0-4)", "Age 0-4"]` | `["age_0_4", "age_0_4_1"]` | P1 |
| GP Practice | No date columns | `is_wide_format: false` | P2 |
| PCN Workforce | 3+ date columns | `is_wide_format: true` | P2 |
| Unpivot | Wide → Long | period column added | P3 |
| Metadata | LLM description | tbl_column_metadata row | P4 |

---

## Rollback Plan

Each phase is independently reversible:

- **P0:** Revert apply_enrichment.py to use LLM column names
- **P1:** Remove collision suffix logic
- **P2:** Set `is_wide_format: false` in manifest
- **P3:** Remove unpivot transformer, load wide format as-is
- **P4:** Drop tbl_column_metadata, continue without persistence

---

## Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| ADHD cross-period load | ✅ No errors | November loads into August tables |
| Schema determinism | 100% | Same header → same column name |
| Wide format detection | >95% | PCN, Dementia detected |
| Transform accuracy | 100% | Row count matches wide × periods |
| Metadata coverage | >80% | Columns have descriptions |

---

## Files to Create/Modify

| File | Action | Lines | Phase |
|------|--------|-------|-------|
| `scripts/schema_utils.py` | CREATE | ~100 | P0 |
| `scripts/apply_enrichment.py` | MODIFY | ~30 | P0 |
| `src/datawarp/extractor/excel.py` | MODIFY | ~20 | P1 |
| `scripts/url_to_manifest.py` | MODIFY | ~15 | P2 |
| `src/datawarp/transform/unpivot.py` | CREATE | ~100 | P3 |
| `src/datawarp/loader/batch.py` | MODIFY | ~50 | P3, P4 |
| `sql/05_create_column_metadata.sql` | CREATE | ~30 | P4 |

**Total New Code:** ~350 lines

---

## Next Steps

1. **Immediate:** Implement Phase 0 (deterministic naming)
2. **Validate:** Test with ADHD Aug→Nov
3. **Iterate:** Add phases 1-4 based on success
4. **Document:** Update ARCHITECTURE.md with new flow

---

**Ready to start Phase 0?**
