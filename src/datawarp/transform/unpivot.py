#!/usr/bin/env python3
"""
Universal Unpivot Engine.

Transforms wide date format to long format for stable schema.

PROBLEM:
    PCN Workforce has columns like [March 2020, June 2020, ..., November 2025]
    Each month adds a NEW column, causing schema drift.

SOLUTION:
    Unpivot (melt) date columns into a single 'period' column.
    Schema becomes stable: [Org, Staff_Type, period, value]
    
Based on ADIE (Autonomous Data Ingestion Engine) PRD spec.
"""

import pandas as pd
import re
from datetime import datetime
from typing import Optional, List, Tuple


# Month name to number mapping
MONTH_MAP = {
    'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4,
    'may': 5, 'jun': 6, 'jul': 7, 'aug': 8,
    'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12,
    'january': 1, 'february': 2, 'march': 3, 'april': 4,
    'june': 6, 'july': 7, 'august': 8,
    'september': 9, 'october': 10, 'november': 11, 'december': 12
}


def parse_date_column(col_name: str) -> Optional[str]:
    """
    Parse date column header to ISO date string.
    
    Examples:
        "Nov-25"        → "2025-11-01"
        "November 2025" → "2025-11-01"
        "2025-11"       → "2025-11-01"
        "March_2020"    → "2020-03-01"
        "Q1 2025"       → "2025-01-01" (start of quarter)
    
    Args:
        col_name: Column header that looks like a date
        
    Returns:
        ISO date string (YYYY-MM-DD) or None if not parseable
    """
    if not col_name:
        return None
        
    col_lower = col_name.lower().strip()
    
    # Try "Nov-25", "Nov_25", "November 2025", "March_2020" patterns
    for month_str, month_num in MONTH_MAP.items():
        if col_lower.startswith(month_str):
            # Extract year
            match = re.search(r'(\d{2,4})', col_lower)
            if match:
                year = int(match.group(1))
                if year < 100:
                    year += 2000  # Convert 25 -> 2025
                return f"{year}-{month_num:02d}-01"
    
    # Try "2025-11" or "2025_11" pattern
    match = re.match(r'(\d{4})[-_](\d{1,2})', col_lower)
    if match:
        year, month = int(match.group(1)), int(match.group(2))
        if 1 <= month <= 12:
            return f"{year}-{month:02d}-01"
    
    # Try quarter pattern "Q1 2025", "Q2_2024"
    match = re.match(r'q([1-4])[-_\s]?(\d{2,4})', col_lower)
    if match:
        quarter, year = int(match.group(1)), int(match.group(2))
        if year < 100:
            year += 2000
        month = (quarter - 1) * 3 + 1  # Q1->1, Q2->4, Q3->7, Q4->10
        return f"{year}-{month:02d}-01"
    
    return None


def unpivot_wide_dates(
    df: pd.DataFrame,
    static_columns: List[str],
    date_columns: List[str],
    value_name: str = 'value',
    period_name: str = 'period'
) -> pd.DataFrame:
    """
    Transform wide date format to long format.
    
    WIDE FORMAT (input):
    | Org  | Staff_Type | Oct_2025 | Nov_2025 |
    | NHS  | Nurse      | 100      | 110      |
    | NHS  | Doctor     | 50       | 55       |
    
    LONG FORMAT (output):
    | Org  | Staff_Type | period     | value |
    | NHS  | Nurse      | 2025-10-01 | 100   |
    | NHS  | Nurse      | 2025-11-01 | 110   |
    | NHS  | Doctor     | 2025-10-01 | 50    |
    | NHS  | Doctor     | 2025-11-01 | 55    |
    
    Benefits:
    - Schema is STABLE regardless of how many months exist
    - Adding December 2025 just adds more ROWS, not new COLUMNS
    - Cross-period queries are trivial (filter on period column)
    
    Args:
        df: Input DataFrame in wide format
        static_columns: Columns to keep as-is (dimension columns)
        date_columns: Columns to unpivot (date columns that vary)
        value_name: Name for the value column (default: 'value')
        period_name: Name for the period column (default: 'period')
        
    Returns:
        DataFrame in long format with consistent schema
        
    Raises:
        ValueError: If specified columns are not found in DataFrame
    """
    # Validate columns exist
    missing_static = [c for c in static_columns if c not in df.columns]
    missing_date = [c for c in date_columns if c not in df.columns]
    
    if missing_static:
        raise ValueError(f"Static columns not found in DataFrame: {missing_static}")
    if missing_date:
        raise ValueError(f"Date columns not found in DataFrame: {missing_date}")
    
    # Perform pandas melt (unpivot)
    df_long = pd.melt(
        df,
        id_vars=static_columns,
        value_vars=date_columns,
        var_name='_raw_period',
        value_name=value_name
    )
    
    # Parse period column headers to ISO dates
    df_long[period_name] = df_long['_raw_period'].apply(parse_date_column)
    
    # Keep raw period for debugging, but could be dropped
    # df_long = df_long.drop(columns=['_raw_period'])
    
    # Reorder columns: static first, then period, then value
    final_cols = static_columns + [period_name, '_raw_period', value_name]
    df_long = df_long[final_cols]
    
    return df_long


def detect_and_unpivot(
    df: pd.DataFrame,
    min_date_columns: int = 3
) -> Tuple[pd.DataFrame, dict]:
    """
    Auto-detect wide date pattern and unpivot if found.
    
    This is the main entry point for automatic transformation.
    
    Args:
        df: Input DataFrame
        min_date_columns: Minimum date columns to trigger unpivot (default: 3)
        
    Returns:
        (transformed_df, metadata)
        
        metadata contains:
        - transformed: bool - whether unpivot was applied
        - date_columns: list - columns that were unpivoted
        - static_columns: list - columns that were preserved
        - original_shape: tuple - (rows, cols) before transform
        - final_shape: tuple - (rows, cols) after transform
    """
    from datawarp.utils.schema import is_date_column
    
    headers = df.columns.tolist()
    
    # Identify date vs static columns
    date_cols = [h for h in headers if is_date_column(h)]
    static_cols = [h for h in headers if h and not is_date_column(h)]
    
    metadata = {
        'transformed': False,
        'date_columns': date_cols,
        'static_columns': static_cols,
        'original_shape': df.shape,
        'final_shape': df.shape
    }
    
    # Check if transformation is needed
    if len(date_cols) < min_date_columns:
        return df, metadata
    
    # Apply unpivot
    df_transformed = unpivot_wide_dates(
        df,
        static_columns=static_cols,
        date_columns=date_cols,
        value_name='value',
        period_name='period'
    )
    
    metadata['transformed'] = True
    metadata['final_shape'] = df_transformed.shape
    
    return df_transformed, metadata
