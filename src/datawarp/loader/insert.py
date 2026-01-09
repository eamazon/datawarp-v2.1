"""Data insertion for DataWarp v2 - simplified from v1 preserve.py."""

import pandas as pd
from datetime import date, datetime
from typing import Any, Optional


# NHS suppression markers (match FileExtractor.SUPPRESSED_VALUES)
# Include both statistical suppression (*, c, z, x) and data quality markers
SUPPRESSED_VALUES = {':', '..', '.', '-', '*', 'c', 'z', 'x', '[c]', '[z]', '[x]', 'n/a', 'na', 'low dq', 'unknown'}
BATCH_SIZE = 1000


def is_null(value: Any) -> bool:
    """Check if value should be treated as SQL NULL."""
    if value is None:
        return True
    
    if not isinstance(value, str):
        return False
    
    stripped = value.strip()
    if not stripped:
        return True
    
    return stripped.upper() in ["N/A", "NA", "NULL", "NONE", "-"]


def cast_text(value: Any) -> Optional[str]:
    """Cast value to TEXT."""
    if is_null(value):
        return None
    return str(value)


def cast_integer(value: Any) -> Optional[int]:
    """Cast value to INTEGER."""
    if is_null(value):
        return None
    
    if str(value).strip().lower() in SUPPRESSED_VALUES:
        return None
    
    clean = str(value).replace(",", "").strip()
    
    try:
        # Handle Excel's float representation of integers (e.g., "155380.0")
        # Convert to float first, then to int
        return int(float(clean))
    except ValueError:
        raise ValueError(f"Cannot cast '{value}' to INTEGER")


def cast_float(value: Any) -> Optional[float]:
    """Cast value to FLOAT."""
    if is_null(value):
        return None
    
    # CRITICAL FIX: Check for suppression markers BEFORE trying to convert
    # NHS uses *, c, z, x, :, .. etc. to indicate suppressed/unavailable data
    str_val = str(value).strip().lower()
    if str_val in SUPPRESSED_VALUES:
        return None
    
    clean = str(value).replace(",", "").replace("%", "").strip()
    
    try:
        return float(clean)
    except ValueError:
        raise ValueError(f"Cannot cast '{value}' to FLOAT")


def cast_date(value: Any) -> Optional[date]:
    """Cast value to DATE."""
    if is_null(value):
        return None
    
    if isinstance(value, date):
        return value
    
    if isinstance(value, datetime):
        return value.date()
    
    value_str = str(value).strip()
    
    formats = [
        "%Y-%m-%d",      # ISO: 2024-01-15
        "%d/%m/%Y",      # UK: 15/01/2024
        "%m/%d/%Y",      # US: 01/15/2024
        "%Y%m%d",        # Compact: 20240115
        "%b%Y",          # NOV2022 (month abbreviation + year)
        "%B%Y",          # November2022 (full month name + year)
    ]
    
    for fmt in formats:
        try:
            parsed = datetime.strptime(value_str, fmt).date()
            # For month-year formats with no day, default to 1st of month
            if fmt in ["%b%Y", "%B%Y"]:
                return parsed.replace(day=1)
            return parsed
        except ValueError:
            continue
    
    raise ValueError(f"Cannot cast '{value}' to DATE")


def cast_boolean(value: Any) -> Optional[bool]:
    """Cast value to BOOLEAN."""
    if is_null(value):
        return None
    
    if isinstance(value, bool):
        return value
    
    v = str(value).strip().lower()
    
    if v in ["yes", "y", "true", "t", "1"]:
        return True
    elif v in ["no", "n", "false", "f", "0"]:
        return False
    else:
        raise ValueError(f"Cannot cast '{value}' to BOOLEAN")


def cast_value(value: Any, target_type: str) -> Any:
    """Cast value to target SQL type.
    
    Args:
        value: Raw value from file
        target_type: Target type from FileExtractor (e.g. 'VARCHAR(255)', 'INTEGER')
        
    Returns:
        Casted value or None
    """
    # Normalize type
    target_type = target_type.upper()
    if target_type.startswith('VARCHAR') or target_type == 'TEXT':
        return cast_text(value)
    if target_type in ('INTEGER', 'BIGINT'):
        return cast_integer(value)
    if target_type.startswith('NUMERIC') or target_type in ('FLOAT', 'DOUBLE PRECISION', 'REAL'):
        return cast_float(value)
    if target_type == 'DATE':
        return cast_date(value)
    if target_type == 'BOOLEAN':
        return cast_boolean(value)
    
    # Default to text
    return cast_text(value)


def insert_dataframe(
    df: pd.DataFrame,
    table_name: str,
    schema_name: str,
    load_id: int,  # ← Added: Load ID for lineage tracking
    period: Optional[str] = None,  # ← NEW: Time period from manifest
    manifest_file_id: Optional[int] = None,  # ← NEW: Manifest file tracking ID
    conn=None
) -> int:
    """Insert DataFrame rows into table.
    
    Args:
        df: DataFrame to insert
        table_name: Table name (no schema prefix)
        schema_name: Schema name
        load_id: Load ID from tbl_load_history for row-level lineage
        conn: Database connection (if None, will get from env)
        
    Returns:
        Number of rows inserted
    """
    if conn is None:
        from datawarp.storage.repository import get_connection
        conn = get_connection()
    
    if df.empty:
        return 0
    
    # Stamp rows with provenance
    df = df.copy()  # Don't mutate the original
    df['_load_id'] = load_id
    df['_period'] = period
    df['_manifest_file_id'] = manifest_file_id
    # _loaded_at will use DEFAULT NOW() in the database
    
    # CRITICAL FIX: Replace NHS suppression markers with None BEFORE COPY
    # Suppression markers like *, c, z, x, :, .. cannot be cast to numeric types
    # This must happen BEFORE the COPY command attempts type conversion
    # Use case-insensitive matching to catch variants like "Low DQ", "low dq", "LOW DQ"
    for col in df.columns:
        if col not in ['_load_id', '_period', '_manifest_file_id']:  # Skip metadata columns
            # Apply case-insensitive replacement for text columns
            if df[col].dtype == 'object':  # Text columns
                df[col] = df[col].apply(
                    lambda x: None if pd.notna(x) and str(x).strip().lower() in SUPPRESSED_VALUES else x
                )
            else:
                # For numeric columns, just replace exact matches
                df[col] = df[col].replace(list(SUPPRESSED_VALUES), None)
    
    # Fix: Convert float columns to int if they contain only whole numbers
    # This handles Excel's tendency to store integers as floats (e.g., 155380.0)
    import sys
    for col in df.columns:
        if pd.api.types.is_float_dtype(df[col]):
            # Check if all non-null values are whole numbers
            non_null = df[col].dropna()
            if len(non_null) > 0 and (non_null % 1 == 0).all():
                # Convert to Int64 (nullable integer type)
                print(f"DEBUG INSERT: Converting {col} from float64 to Int64 (whole numbers detected)", file=sys.stderr)
                df[col] = df[col].astype('Int64')
            else:
                print(f"DEBUG INSERT: Keeping {col} as float64 (not all whole numbers)", file=sys.stderr)
    
    # Fix: Convert date strings like "NOV2022" to proper dates
    # This handles month-year format dates before PostgreSQL COPY
    for col in df.columns:
        if pd.api.types.is_object_dtype(df[col]):
            # Sample first non-null value
            sample = df[col].dropna().head(1)
            if len(sample) > 0:
                sample_val = str(sample.iloc[0]).strip()
                # Check if it looks like a month-year date (e.g., NOV2022)
                import re
                if re.match(r'^[A-Z]{3}\d{4}$', sample_val):
                    # Convert NOV2022 -> 2022-11-01
                    df[col] = df[col].apply(lambda x: cast_date(x).strftime("%Y-%m-%d") if pd.notna(x) else None)
    
    
    cursor = conn.cursor()
    
    # Build INSERT statement
    columns = list(df.columns)
    # Quote column names to handle special characters
    col_names = ", ".join([f'"{col}"' for col in columns])
    placeholders = ", ".join(["%s"] * len(columns))
    
    qualified_table = f"{schema_name}.{table_name}"
    
    # Use PostgreSQL COPY for 10-100x faster bulk insert
    import io
    
    # Prepare data as CSV in memory
    buffer = io.StringIO()
    df.to_csv(buffer, index=False, header=False, na_rep='\\N')
    buffer.seek(0)
    
    # COPY from buffer
    cursor = conn.cursor()
    columns = list(df.columns)
    col_names = ", ".join([f'"{col}"' for col in columns])
    
    copy_sql = f"COPY {qualified_table} ({col_names}) FROM STDIN WITH (FORMAT CSV, NULL '\\N')"
    cursor.copy_expert(copy_sql, buffer)
    
    conn.commit()
    cursor.close()
    
    return len(df)
