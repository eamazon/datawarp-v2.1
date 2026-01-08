"""DataWarp v2 Pipeline. Extract → Compare → Evolve → Load."""

from datetime import datetime
from typing import Optional
from dataclasses import dataclass

from datawarp.core.extractor import FileExtractor
from datawarp.core.csv_extractor import CSVExtractor
from datawarp.core.drift import detect_drift
from datawarp.storage.connection import get_connection
from datawarp.storage import repository
from datawarp.loader.ddl import create_table, add_columns
from datawarp.loader.insert import insert_dataframe
from datawarp.utils.download import download_file


@dataclass
class LoadResult:
    """Result of a load operation."""
    success: bool
    rows_loaded: int
    table_name: str
    columns_added: list
    duration_ms: int
    error: Optional[str] = None


def check_already_loaded(file_url: str, source_id: int, conn) -> dict:
    """Check if this exact file URL was already loaded for this source."""
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, rows_loaded, loaded_at, load_mode
        FROM datawarp.tbl_load_history
        WHERE source_id = %s AND file_url = %s
        ORDER BY loaded_at DESC
        LIMIT 1
        """,
        (source_id, file_url)
    )
    result = cur.fetchone()
    cur.close()
    
    if result:
        return {
            'loaded': True,
            'load_id': result[0],
            'rows': result[1],
            'when': result[2],
            'mode': result[3]
        }
    return {'loaded': False}


def load_file(
    url: str,
    source_id: str,
    sheet_name: Optional[str] = None,
    mode: str = 'append',
    force: bool = False,
    period: Optional[str] = None,
    manifest_file_id: Optional[int] = None,
    progress_callback=None,
    column_mappings: Optional[dict] = None
) -> LoadResult:
    """Load a file. Handle drift. That's it."""
    start = datetime.utcnow()
    columns_added = []
    
    try:
        # 1. Download
        filepath = download_file(url)
        
        # Notify: processing stage
        if progress_callback:
            progress_callback("processing")
        
        # 2. Get source config
        with get_connection() as conn:
            source = repository.get_source(source_id, conn)
            if not source:
                raise ValueError(f"Source '{source_id}' not registered")
            
            # 2.5 Check for duplicate load (URL-based deduplication)
            existing = check_already_loaded(url, source.id, conn)
            
            if existing['loaded'] and mode == 'append' and not force:
                # File already loaded - abort to prevent duplicates
                when_str = existing['when'].strftime('%Y-%m-%d %H:%M:%S') if existing['when'] else 'unknown'
                raise ValueError(
                    f"⚠️  File already loaded on {when_str} ({existing['rows']} rows)\n"
                    f"   Use --replace to reload, or --force to append anyway"
                )
        
        # 3. Extract structure - route by file extension
        from pathlib import Path
        file_ext = Path(filepath).suffix.lower()
        
        if file_ext == '.csv':
            extractor = CSVExtractor(str(filepath), sheet_name)
        elif file_ext in ['.xlsx', '.xls']:
            extractor = FileExtractor(str(filepath), sheet_name)
        else:
            raise ValueError(f"Unsupported file type: {file_ext}")
        
        structure = extractor.infer_structure()

        if not structure.is_valid:
            error_msg = structure.error_message or f"Sheet is {structure.sheet_type.name}, not TABULAR data"

            # If no sheet specified and first sheet is metadata, suggest trying a different sheet
            if not sheet_name and structure.sheet_type.name == 'METADATA':
                sheets = FileExtractor.get_sheet_names(str(filepath))
                raise ValueError(
                    f"{error_msg}. "
                    f"File has {len(sheets)} sheets. Try specifying --sheet with one of: {', '.join(sheets[:5])}"
                )
            raise ValueError(error_msg)

        # Apply column mappings if provided (enriched manifest)
        if column_mappings:
            for col in structure.columns.values():
                original_header = ' '.join(col.original_headers).strip()
                if original_header in column_mappings:
                    col.semantic_name = column_mappings[original_header]

        file_columns = [c.final_name for c in structure.columns.values()]
        
        with get_connection() as conn:
            # 4. Ensure table exists
            db_columns = repository.get_db_columns(source.table_name, source.schema_name, conn)
            
            if not db_columns:
                # New table
                create_table(source.table_name, source.schema_name, structure.columns, conn)
            else:
                # Handle replace mode - period-aware deletion ONLY (no table truncation)
                if mode == 'replace':
                    if not period:
                        raise ValueError(
                            "Replace mode requires a 'period' to avoid accidental data loss. "
                            "Use 'append' mode for non-period-based loads."
                        )
                    
                    cur = conn.cursor()
                    # Delete ONLY this period's data
                    cur.execute(
                        f"DELETE FROM {source.schema_name}.{source.table_name} WHERE _period = %s",
                        (period,)
                    )
                    deleted_rows = cur.rowcount
                    if deleted_rows > 0:
                        print(f"      Replacing {deleted_rows} existing rows for period {period}")
                    cur.close()
                
                # Existing table - check for drift
                drift = detect_drift(file_columns, db_columns)
                
                if drift.new_columns:
                    # Add new columns to database
                    new_column_info = [
                        c for c in structure.columns.values() 
                        if c.pg_name in drift.new_columns
                    ]
                    add_columns(source.table_name, source.schema_name, new_column_info, conn)
                    columns_added = drift.new_columns
            
            # 5. Prepare data
            df = extractor.to_dataframe()
            
            # Apply column renaming for enriched manifests
            if column_mappings:
                rename_map = {}
                for col in structure.columns.values():
                    # Map: actual DataFrame column (pg_name) → semantic name
                    # The DataFrame uses pg_name (sanitized/lowercased), not original headers
                    if col.pg_name != col.final_name:
                        rename_map[col.pg_name] = col.final_name
                
                if rename_map:
                    df = df.rename(columns=rename_map)
            
            rows = len(df)
            
            # Notify: uploading stage
            if progress_callback:
                progress_callback("uploading")
            
            # 6. Create audit entry (get load_id for lineage tracking)
            load_id = repository.log_load(source.id, url, rows, columns_added, mode, conn)
            
            # 7. Insert data with load_id stamping
            insert_dataframe(df, source.table_name, source.schema_name, load_id, period, manifest_file_id, conn)
        
        duration_ms = int((datetime.utcnow() - start).total_seconds() * 1000)
        
        return LoadResult(
            success=True,
            rows_loaded=rows,
            table_name=f"{source.schema_name}.{source.table_name}",
            columns_added=columns_added,
            duration_ms=duration_ms
        )
    
    except Exception as e:
        duration_ms = int((datetime.utcnow() - start).total_seconds() * 1000)
        return LoadResult(
            success=False,
            rows_loaded=0,
            table_name="",
            columns_added=[],
            duration_ms=duration_ms,
            error=str(e)
        )
