"""Deterministic schema naming utilities.

This module provides functions to convert Excel headers to PostgreSQL column names
in a DETERMINISTIC way - avoiding LLM non-determinism that causes schema drift.

The key insight: LLM-generated semantic_name varies between periods (e.g., "date" vs 
"reporting_period" for the same "Date" header). This causes INSERT failures when
November data tries to insert into a table schema created in August.

Solution: Column names are derived from Excel headers using pure string transformation.
LLM-provided semantic_name is stored as metadata only, not used for PostgreSQL columns.
"""

import re
from typing import List, Dict, Optional


# PostgreSQL reserved words that need suffixing to avoid conflicts
RESERVED_WORDS = {
    'month', 'year', 'group', 'order', 'table', 'index', 'key',
    'value', 'date', 'time', 'user', 'name', 'type', 'level',
    'desc', 'asc', 'limit', 'offset', 'case', 'when', 'then',
    'else', 'end', 'and', 'or', 'not', 'null', 'true', 'false',
    'select', 'from', 'where', 'join', 'on', 'as', 'in', 'is',
    'between', 'like', 'having', 'by', 'all', 'any', 'some'
}


def to_schema_name(header: str) -> str:
    """
    Convert Excel header to PostgreSQL column name deterministically.
    
    This is the SINGLE SOURCE OF TRUTH for column naming.
    Same input ALWAYS produces same output.
    
    Transformations:
    1. Lowercase
    2. Remove currency symbols (£$€%)
    3. Replace non-alphanumeric with underscore
    4. Collapse multiple underscores
    5. Strip leading/trailing underscores
    6. Handle empty strings
    7. Suffix reserved words with _val
    8. Prefix digit-starting names with col_
    9. Truncate to 63 chars (PostgreSQL limit)
    
    Examples:
        "Age 0 to 4"           -> "age_0_to_4"
        "Date"                 -> "date_val" (reserved word)
        "Waiting time Up to 12 weeks" -> "waiting_time_up_to_12_weeks"
        "£ Cost Per Unit"      -> "cost_per_unit"
        "2024 Total"           -> "col_2024_total"
    """
    if not header:
        return 'col_unnamed'
    
    # Step 1: Lowercase
    clean = header.lower()
    
    # Step 2: Remove currency/percentage symbols
    clean = re.sub(r'[£$€%]', '', clean)
    
    # Step 3: Replace any non-alphanumeric with underscore
    clean = re.sub(r'[^a-z0-9]+', '_', clean)
    
    # Step 4: Collapse multiple underscores
    clean = re.sub(r'_+', '_', clean)
    
    # Step 5: Strip leading/trailing underscores
    clean = clean.strip('_')
    
    # Step 6: Handle empty result
    if not clean:
        return 'col_unnamed'
    
    # Step 7: Suffix reserved words
    if clean in RESERVED_WORDS:
        clean = f"{clean}_val"
    
    # Step 8: Prefix if starts with digit
    if clean[0].isdigit():
        clean = f"col_{clean}"
    
    # Step 9: Truncate to PostgreSQL limit (63 chars)
    return clean[:63]


def build_column_mappings(columns: List[Dict]) -> Dict[str, str]:
    """
    Build deterministic column mappings from manifest columns.
    
    This replaces the LLM-based mapping in batch.py:
        OLD: {original_name: semantic_name}  # LLM-generated, varies!
        NEW: {original_name: to_schema_name(original_name)}  # Deterministic!
    
    Args:
        columns: List of column dicts with 'original_name' key
        
    Returns:
        Dict mapping original_name -> deterministic schema name
    """
    mappings = {}
    seen_names: Dict[str, int] = {}  # Track for collision detection
    
    for col in columns:
        original = col.get('original_name', '')
        if not original:
            continue
        
        schema_name = to_schema_name(original)
        
        # Handle collisions (e.g., "Age 0-4" and "Age 0 to 4" both -> "age_0_4")
        if schema_name in seen_names:
            seen_names[schema_name] += 1
            schema_name = f"{schema_name}_{seen_names[schema_name]}"
        else:
            seen_names[schema_name] = 1
        
        mappings[original] = schema_name
    
    return mappings


def validate_column_name(name: str) -> bool:
    """
    Check if a string is a valid PostgreSQL identifier.
    
    Returns True if valid, False otherwise.
    """
    if not name:
        return False
    
    # Must not exceed 63 chars
    if len(name) > 63:
        return False
    
    # Must start with letter or underscore (after our transformations, always letter)
    if not (name[0].isalpha() or name[0] == '_'):
        return False
    
    # Must contain only alphanumeric and underscore
    if not re.match(r'^[a-z_][a-z0-9_]*$', name):
        return False
    
    return True


# ============================================================================
# PHASE 2: Wide Date Detection
# ============================================================================

# Date patterns for detecting date-as-columns (wide format)
# Patterns match the START of normalized header - can have trailing annotations
DATE_PATTERNS = [
    r'^(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[-_\s]?\d{2,4}',
    r'^(january|february|march|april|may|june|july|august|september|october|november|december)[-_\s]?\d{4}',
    r'^(janaury|febuary|feburary)[-_\s]?\d{4}',  # Common misspellings in NHS data
    r'^\d{4}[-_](0?[1-9]|1[0-2])',  # 2025-01
    r'^(q[1-4])[-_\s]?\d{2,4}',  # Q1 2025
    r'^\d{2,4}[-/]\d{2,4}',  # 24/25, 2024/2025
]


def is_date_column(header: str) -> bool:
    """
    Check if header looks like a date/period column.
    
    Used to detect wide date format (dates as columns).
    
    Examples:
        "March 2020"     -> True
        "Jan-25"         -> True  
        "Q1 2025"        -> True
        "Age 0 to 4"     -> False
        "Region Code"    -> False
    """
    if not header:
        return False
    norm = header.lower().strip()
    return any(re.match(p, norm, re.IGNORECASE) for p in DATE_PATTERNS)


def detect_wide_date_pattern(headers: List[str]) -> dict:
    """
    Detect if headers contain wide date format (dates as columns).
    
    NHS publications like PCN Workforce have columns like:
    [Region, Staff Type, March 2020, June 2020, Sep 2020, ...]
    
    This pattern causes schema drift when new months are added.
    
    Detection threshold: 3+ date columns triggers wide format detection.
    
    Args:
        headers: List of column headers
        
    Returns:
        dict with keys:
            - is_wide: bool - True if wide date pattern detected
            - date_columns: list - Column headers that are dates
            - static_columns: list - Column headers that are static (dimensions)
            - recommendation: str - Suggested action
    """
    date_cols = [h for h in headers if is_date_column(h)]
    static_cols = [h for h in headers if h and not is_date_column(h)]
    
    is_wide = len(date_cols) >= 3
    
    recommendation = ""
    if is_wide:
        recommendation = (
            f"WIDE DATE PATTERN DETECTED: {len(date_cols)} date columns found. "
            f"Consider using unpivot transformation to convert to long format. "
            f"Static dimensions: {static_cols[:3]}..."
        )
    
    return {
        'is_wide': is_wide,
        'date_columns': date_cols,
        'static_columns': static_cols,
        'date_count': len(date_cols),
        'static_count': len(static_cols),
        'recommendation': recommendation
    }


def build_column_mappings_with_detection(columns: List[Dict]) -> tuple:
    """
    Build deterministic column mappings with collision and wide date detection.
    
    Returns:
        (mappings, collisions, wide_date_info)
        
        - mappings: Dict[str, str] - original_name -> schema_name
        - collisions: List[tuple] - [(original1, original2, schema_name), ...]
        - wide_date_info: dict - from detect_wide_date_pattern()
    """
    mappings = {}
    collisions = []
    seen_names: Dict[str, tuple] = {}  # schema_name -> (first_original, count)
    
    headers = [col.get('original_name', '') for col in columns if col.get('original_name')]
    
    for col in columns:
        original = col.get('original_name', '')
        if not original:
            continue
        
        schema_name = to_schema_name(original)
        
        # Handle collisions
        if schema_name in seen_names:
            first_original, count = seen_names[schema_name]
            seen_names[schema_name] = (first_original, count + 1)
            collisions.append((first_original, original, schema_name))
            schema_name = f"{schema_name}_{count + 1}"
        else:
            seen_names[schema_name] = (original, 1)
        
        mappings[original] = schema_name
    
    # Detect wide date pattern
    wide_date_info = detect_wide_date_pattern(headers)
    
    return mappings, collisions, wide_date_info
