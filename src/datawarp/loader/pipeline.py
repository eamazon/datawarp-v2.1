"""DataWarp v2 Pipeline. Extract → Compare → Evolve → Load."""

import logging
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
from datawarp.supervisor.events import EventStore, create_event, EventType, EventLevel

log = logging.getLogger(__name__)


@dataclass
class LoadResult:
    """Result of a load operation."""
    success: bool
    rows_loaded: int
    table_name: str
    columns_added: list
    duration_ms: int
    error: Optional[str] = None


def validate_load(result: LoadResult, expected_min_rows: int = 100) -> LoadResult:
    """Validate load results for common failure patterns.

    Args:
        result: LoadResult from a load operation
        expected_min_rows: Minimum expected rows (default 100)

    Returns:
        LoadResult (same as input if valid)

    Raises:
        ValueError: If load is clearly broken (0 rows loaded)
    """
    # Skip validation for already-failed loads
    if not result.success:
        return result

    # CRITICAL: 0-row loads indicate extraction failure
    if result.rows_loaded == 0:
        raise ValueError(
            f"Validation failed: Loaded 0 rows to {result.table_name}. "
            "Source may be empty, wrong sheet selected, or extraction failed."
        )

    # WARNING: Low row counts may indicate issues
    if result.rows_loaded < expected_min_rows:
        # Force newline before warning to avoid spinner char leakage
        print()  # Clear spinner line
        log.warning(
            f"⚠️  Low row count: {result.rows_loaded} rows loaded to {result.table_name} "
            f"(expected >{expected_min_rows}). Verify source is not truncated."
        )

    return result


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
    column_mappings: Optional[dict] = None,
    unpivot: bool = False,
    wide_date_info: Optional[dict] = None,
    event_store: Optional[EventStore] = None,
    publication: str = None
) -> LoadResult:
    """Load a file. Handle drift. That's it.

    Args:
        unpivot: If True and wide date pattern detected, transform to long format
        wide_date_info: Pre-computed wide date detection results from manifest
        event_store: Optional EventStore for observability
        publication: Publication code for event logging
    """
    start = datetime.utcnow()
    columns_added = []

    if event_store:
        event_store.emit(create_event(
            EventType.STAGE_STARTED,
            event_store.run_id,
            publication=publication,
            period=period,
            stage='load',
            level=EventLevel.INFO,
            message=f"Starting load for source: {source_id}",
            context={'source_id': source_id, 'url': url, 'mode': mode}
        ))
    
    try:
        # 1. Download
        if event_store:
            event_store.emit(create_event(
                EventType.STAGE_STARTED,
                event_store.run_id,
                publication=publication,
                period=period,
                stage='download',
                level=EventLevel.DEBUG,
                message=f"Downloading file: {url}",
                context={'url': url}
            ))

        filepath = download_file(url)

        if event_store:
            event_store.emit(create_event(
                EventType.STAGE_COMPLETED,
                event_store.run_id,
                publication=publication,
                period=period,
                stage='download',
                level=EventLevel.DEBUG,
                message=f"Download completed: {filepath}",
                context={'filepath': str(filepath)}
            ))

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

        # Handle ZIP files - extract specified file first
        zip_file_name = None  # Track ZIP filename for EventStore messages
        if file_ext == '.zip':
            if not sheet_name:  # For ZIP, sheet_name is actually the extract filename
                raise ValueError("ZIP files require 'extract' field in manifest to specify which file to extract")

            from datawarp.utils.zip_handler import extract_file_from_zip

            zip_file_name = Path(filepath).name  # Save ZIP filename

            if event_store:
                event_store.emit(create_event(
                    EventType.STAGE_STARTED,
                    event_store.run_id,
                    publication=publication,
                    period=period,
                    stage='extract',
                    level=EventLevel.DEBUG,
                    message=f"Extracting {sheet_name} from ZIP: {zip_file_name}",
                    context={'zip_file': str(filepath), 'extract': sheet_name}
                ))

            filepath = extract_file_from_zip(Path(filepath), sheet_name)
            file_ext = Path(filepath).suffix.lower()

            if event_store:
                extracted_name = Path(filepath).name
                event_store.emit(create_event(
                    EventType.STAGE_COMPLETED,
                    event_store.run_id,
                    publication=publication,
                    period=period,
                    stage='extract',
                    level=EventLevel.DEBUG,
                    message=f"Processing {file_ext.upper()[1:]}: {extracted_name} from ZIP file {zip_file_name}",
                    context={'extracted_path': str(filepath), 'zip_file': zip_file_name}
                ))

        if file_ext == '.csv':
            extractor = CSVExtractor(str(filepath), sheet_name=None)  # CSV doesn't have sheets
        elif file_ext in ['.xlsx', '.xls']:
            extractor = FileExtractor(str(filepath), sheet_name)
        else:
            raise ValueError(f"Unsupported file type: {file_ext}")
        
        structure = extractor.infer_structure()

        if event_store:
            event_store.emit(create_event(
                EventType.STAGE_COMPLETED,
                event_store.run_id,
                publication=publication,
                period=period,
                stage='structure',
                level=EventLevel.INFO,
                message=f"Structure extracted: {len(structure.columns)} columns",
                context={'columns': len(structure.columns), 'sheet_type': structure.sheet_type.name}
            ))

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

        # 3.5 Prepare data EARLY (before table creation) to handle unpivot
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
        
        # 3.6 Apply unpivot transformation BEFORE table creation
        if unpivot and wide_date_info and wide_date_info.get('is_wide'):
            from datawarp.transform.unpivot import unpivot_wide_dates
            
            date_cols = wide_date_info.get('date_columns', [])
            static_cols = wide_date_info.get('static_columns', [])
            
            # Map column names through column_mappings if present
            if column_mappings:
                date_cols = [column_mappings.get(c, c) for c in date_cols]
                static_cols = [column_mappings.get(c, c) for c in static_cols]
            
            # Filter to columns that exist in the DataFrame
            date_cols = [c for c in date_cols if c in df.columns]
            static_cols = [c for c in static_cols if c in df.columns]
            
            if len(date_cols) >= 3:
                original_shape = df.shape
                df = unpivot_wide_dates(
                    df,
                    static_columns=static_cols,
                    date_columns=date_cols,
                    value_name='value',
                    period_name='period'
                )
                print(f"      📊 Unpivot: {original_shape} → {df.shape} (wide→long)")
        
        # Use DataFrame columns for table creation (may be transformed by unpivot)
        file_columns = list(df.columns)
        
        with get_connection() as conn:
            # 4. Ensure table exists
            db_columns = repository.get_db_columns(source.table_name, source.schema_name, conn)
            
            if not db_columns:
                # New table - create from DataFrame columns (handles unpivot case)
                if event_store:
                    event_store.emit(create_event(
                        EventType.STAGE_STARTED,
                        event_store.run_id,
                        publication=publication,
                        period=period,
                        stage='ddl',
                        level=EventLevel.INFO,
                        message=f"Creating new table: {source.schema_name}.{source.table_name}",
                        context={'table': f"{source.schema_name}.{source.table_name}", 'columns': len(df.columns)}
                    ))

                from datawarp.loader.ddl import create_table_from_df
                create_table_from_df(source.table_name, source.schema_name, df, conn)

                if event_store:
                    event_store.emit(create_event(
                        EventType.STAGE_COMPLETED,
                        event_store.run_id,
                        publication=publication,
                        period=period,
                        stage='ddl',
                        level=EventLevel.INFO,
                        message=f"Table created successfully: {source.schema_name}.{source.table_name}",
                        context={'table': f"{source.schema_name}.{source.table_name}"}
                    ))
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
                    if event_store:
                        event_store.emit(create_event(
                            EventType.WARNING,
                            event_store.run_id,
                            publication=publication,
                            period=period,
                            level=EventLevel.WARNING,
                            message=f"Drift detected: {len(drift.new_columns)} new columns",
                            context={'new_columns': drift.new_columns, 'table': f"{source.schema_name}.{source.table_name}"}
                        ))

                    # Add new columns to database (infer types from DataFrame)
                    from datawarp.loader.ddl import add_columns_from_df
                    add_columns_from_df(source.table_name, source.schema_name, df, drift.new_columns, conn)
                    columns_added = drift.new_columns

                    if event_store:
                        event_store.emit(create_event(
                            EventType.STAGE_COMPLETED,
                            event_store.run_id,
                            publication=publication,
                            period=period,
                            stage='ddl',
                            level=EventLevel.INFO,
                            message=f"Added {len(columns_added)} columns to existing table",
                            context={'columns_added': columns_added}
                        ))
            
            rows = len(df)
            
            # Notify: uploading stage
            if progress_callback:
                progress_callback("uploading")
            
            # 6. Create audit entry (get load_id for lineage tracking)
            load_id = repository.log_load(source.id, url, rows, columns_added, mode, conn)
            
            # 7. Insert data with load_id stamping
            if event_store:
                event_store.emit(create_event(
                    EventType.STAGE_STARTED,
                    event_store.run_id,
                    publication=publication,
                    period=period,
                    stage='insert',
                    level=EventLevel.DEBUG,
                    message=f"Inserting {rows:,} rows into {source.schema_name}.{source.table_name}",
                    context={'rows': rows, 'table': f"{source.schema_name}.{source.table_name}"}
                ))

            insert_dataframe(df, source.table_name, source.schema_name, load_id, period, manifest_file_id, conn)

            if event_store:
                event_store.emit(create_event(
                    EventType.STAGE_COMPLETED,
                    event_store.run_id,
                    publication=publication,
                    period=period,
                    stage='insert',
                    level=EventLevel.DEBUG,
                    message=f"Data inserted successfully: {rows:,} rows",
                    context={'rows': rows, 'columns_added': len(columns_added)}
                ))

        duration_ms = int((datetime.utcnow() - start).total_seconds() * 1000)

        if event_store:
            event_store.emit(create_event(
                EventType.STAGE_COMPLETED,
                event_store.run_id,
                publication=publication,
                period=period,
                stage='load',
                level=EventLevel.INFO,
                message=f"Load completed for {source_id}: {rows:,} rows in {duration_ms}ms",
                context={'source_id': source_id, 'rows': rows, 'duration_ms': duration_ms}
            ))

        return validate_load(LoadResult(
            success=True,
            rows_loaded=rows,
            table_name=f"{source.schema_name}.{source.table_name}",
            columns_added=columns_added,
            duration_ms=duration_ms
        ))
    
    except Exception as e:
        duration_ms = int((datetime.utcnow() - start).total_seconds() * 1000)

        if event_store:
            event_store.emit(create_event(
                EventType.ERROR,
                event_store.run_id,
                publication=publication,
                period=period,
                level=EventLevel.ERROR,
                message=f"Load failed for {source_id}: {str(e)}",
                context={'source_id': source_id, 'error': str(e), 'duration_ms': duration_ms}
            ))

        return LoadResult(
            success=False,
            rows_loaded=0,
            table_name="",
            columns_added=[],
            duration_ms=duration_ms,
            error=str(e)
        )
