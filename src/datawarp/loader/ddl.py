"""DDL generation for DataWarp v2 - PostgreSQL only."""

from typing import Dict
from datawarp.core.extractor import ColumnInfo


# Type mapping: FileExtractor types → PostgreSQL types
TYPE_MAP = {
    "VARCHAR(50)": "VARCHAR(50)",
    "VARCHAR(255)": "VARCHAR(255)",
    "VARCHAR(20)": "VARCHAR(20)",
    "TEXT": "TEXT",
    "INTEGER": "INTEGER",
    "BIGINT": "BIGINT",
    "NUMERIC(10,4)": "NUMERIC(10,4)",
    "NUMERIC(18,2)": "NUMERIC(18,2)",
    "NUMERIC(18,6)": "NUMERIC(18,6)",
    "DOUBLE PRECISION": "DOUBLE PRECISION",
    "REAL": "REAL",
    "DATE": "DATE",
    "BOOLEAN": "BOOLEAN",
}


def get_pg_type(inferred_type: str) -> str:
    """Map FileExtractor type to PostgreSQL type."""
    return TYPE_MAP.get(inferred_type, "TEXT")


def create_table(
    table_name: str,
    schema_name: str,
    columns: Dict[int, ColumnInfo],
    conn=None
) -> None:
    """Create table with columns.
    
    Args:
        table_name: Table name (no schema prefix)
        schema_name: Schema name
        columns: Dict of ColumnInfo from FileExtractor
        conn: Database connection (if None, will get from env)
        
    Raises:
        Exception: If table creation fails
    """
    if conn is None:
        from datawarp.storage.repository import get_connection
        conn = get_connection()
    
    cursor = conn.cursor()
    
    # Build column definitions
    col_defs = []
    for col_idx in sorted(columns.keys()):
        col_info = columns[col_idx]
        pg_type = get_pg_type(col_info.inferred_type)
        # Quote column name to handle special characters
        col_defs.append(f'    "{col_info.final_name}" {pg_type}')
    
    # Auto-add provenance columns for lineage tracking
    col_defs.append('    "_load_id" INTEGER')
    col_defs.append('    "_loaded_at" TIMESTAMP DEFAULT NOW()')
    col_defs.append('    "_period" VARCHAR(20)')
    col_defs.append('    "_period_start" DATE')
    col_defs.append('    "_period_end" DATE')
    col_defs.append('    "_manifest_file_id" INTEGER')
    
    # Create table SQL
    ddl = f"CREATE TABLE {schema_name}.{table_name} (\n"
    ddl += ",\n".join(col_defs)
    ddl += "\n);"
    
    cursor.execute(ddl)
    conn.commit()
    cursor.close()


def add_columns(
    table_name: str,
    schema_name: str,
    columns: list,
    conn=None
) -> None:
    """Add columns to existing table.
    
    Args:
        table_name: Table name (no schema prefix)
        schema_name: Schema name
        columns: List of ColumnInfo objects to add
        conn: Database connection (if None, will get from env)
    """
    if conn is None:
        from datawarp.storage.repository import get_connection
        conn = get_connection()
    
    if not columns:
        return
    
    cursor = conn.cursor()
    
    # Add each column (separate ALTER statements for compatibility)
    for col_info in columns:
        pg_type = get_pg_type(col_info.inferred_type)
        # Quote column name to handle special characters
        ddl = f'ALTER TABLE {schema_name}.{table_name} ADD COLUMN "{col_info.final_name}" {pg_type};'
        cursor.execute(ddl)
    
    conn.commit()
    cursor.close()


def table_exists(
    table_name: str,
    schema_name: str,
    conn=None
) -> bool:
    """Check if table exists.
    
    Args:
        table_name: Table name (no schema prefix)
        schema_name: Schema name
        conn: Database connection (if None, will get from env)
        
    Returns:
        True if table exists
    """
    if conn is None:
        from datawarp.storage.repository import get_connection
        conn = get_connection()
    
    cursor = conn.cursor()
    
    cursor.execute(
        """
        SELECT EXISTS (
            SELECT 1
            FROM information_schema.tables
            WHERE table_schema = %s
              AND table_name = %s
        )
        """,
        (schema_name, table_name)
    )
    
    exists = cursor.fetchone()[0]
    cursor.close()
    
    return bool(exists)


def infer_pg_type_from_series(series) -> str:
    """Infer PostgreSQL type from a pandas Series.
    
    Args:
        series: pandas Series
        
    Returns:
        PostgreSQL type string
    """
    import pandas as pd
    import numpy as np
    
    dtype = series.dtype
    
    # Handle numpy/pandas types
    if pd.api.types.is_integer_dtype(dtype):
        return "INTEGER"
    elif pd.api.types.is_float_dtype(dtype):
        return "NUMERIC(18,6)"
    elif pd.api.types.is_datetime64_any_dtype(dtype):
        return "DATE"
    elif pd.api.types.is_bool_dtype(dtype):
        return "BOOLEAN"
    else:
        # Default to TEXT for object/string types
        # Check max length for VARCHAR sizing
        max_len = series.astype(str).str.len().max()
        if max_len <= 50:
            return "VARCHAR(50)"
        elif max_len <= 255:
            return "VARCHAR(255)"
        else:
            return "TEXT"


def create_table_from_df(
    table_name: str,
    schema_name: str,
    df,
    conn=None
) -> None:
    """Create table from DataFrame columns (used when unpivot transforms data).
    
    Args:
        table_name: Table name (no schema prefix)
        schema_name: Schema name
        df: pandas DataFrame to create table from
        conn: Database connection (if None, will get from env)
    """
    if conn is None:
        from datawarp.storage.repository import get_connection
        conn = get_connection()
    
    cursor = conn.cursor()
    
    # Build column definitions from DataFrame
    col_defs = []
    for col_name in df.columns:
        pg_type = infer_pg_type_from_series(df[col_name])
        col_defs.append(f'    "{col_name}" {pg_type}')
    
    # Auto-add provenance columns for lineage tracking
    col_defs.append('    "_load_id" INTEGER')
    col_defs.append('    "_loaded_at" TIMESTAMP DEFAULT NOW()')
    col_defs.append('    "_period" VARCHAR(20)')
    col_defs.append('    "_period_start" DATE')
    col_defs.append('    "_period_end" DATE')
    col_defs.append('    "_manifest_file_id" INTEGER')
    
    # Create table SQL
    ddl = f"CREATE TABLE {schema_name}.{table_name} (\n"
    ddl += ",\n".join(col_defs)
    ddl += "\n);"
    
    cursor.execute(ddl)
    conn.commit()
    cursor.close()


def add_columns_from_df(
    table_name: str,
    schema_name: str,
    df,
    new_columns: list,
    conn=None
) -> None:
    """Add columns to existing table, inferring types from DataFrame.
    
    Args:
        table_name: Table name (no schema prefix)
        schema_name: Schema name
        df: pandas DataFrame to infer types from
        new_columns: List of column names to add
        conn: Database connection (if None, will get from env)
    """
    if conn is None:
        from datawarp.storage.repository import get_connection
        conn = get_connection()
    
    if not new_columns:
        return
    
    cursor = conn.cursor()
    
    # Add each column (separate ALTER statements for compatibility)
    for col_name in new_columns:
        if col_name in df.columns:
            pg_type = infer_pg_type_from_series(df[col_name])
        else:
            pg_type = "TEXT"  # Default for unknown columns
        
        ddl = f'ALTER TABLE {schema_name}.{table_name} ADD COLUMN "{col_name}" {pg_type};'
        cursor.execute(ddl)
    
    conn.commit()
    cursor.close()
