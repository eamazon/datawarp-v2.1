"""Batch loading from YAML manifests."""
import yaml
import logging
import traceback
import time
from pathlib import Path
from typing import Dict, List, Optional
import re
from datetime import datetime
from dataclasses import dataclass, field
from urllib.parse import urlparse

from datawarp.loader.pipeline import load_file
from datawarp.storage.connection import get_connection
from datawarp.storage.repository import get_source
from datawarp.storage import repository
from datawarp.observability import init as init_logger, print_summary as observability_summary

logger = logging.getLogger(__name__)

# File cache: url → Path (session-scoped, cleared per manifest)
_file_cache = {}


@dataclass
class FileResult:
    """Result of loading a single file."""
    period: str
    status: str  # 'loaded', 'skipped', 'failed'
    source_code: str = ""  # Source identifier
    rows: int = 0
    new_cols: int = 0
    duration: float = 0.0
    details: str = ""
    error: Optional[str] = None


@dataclass
class BatchStats:
    """Statistics from batch load operation."""
    total: int = 0
    loaded: int = 0
    skipped: int = 0
    failed: int = 0
    total_rows: int = 0
    total_columns: int = 0
    total_duration: float = 0.0
    file_results: List[FileResult] = field(default_factory=list)
    errors: List[Dict] = None

    def __post_init__(self):
        if self.errors is None:
            self.errors = []


def parse_manifest(manifest_path: str) -> Dict:
    """Parse YAML manifest file."""
    manifest_file = Path(manifest_path)

    if not manifest_file.exists():
        raise FileNotFoundError(f"Manifest not found: {manifest_path}")

    with open(manifest_file, 'r') as f:
        manifest = yaml.safe_load(f)

    if not manifest:
        raise ValueError("Empty manifest file")

    if 'manifest' not in manifest:
        raise ValueError("Manifest missing 'manifest' section")

    if 'sources' not in manifest:
        raise ValueError("Manifest missing 'sources' section")

    return manifest


def sort_files_chronologically(files: List[Dict]) -> List[Dict]:
    """Sort files by period, oldest first."""
    def get_sort_key(file_info):
        period = file_info.get('period', '')
        # If no period, put at end
        if not period:
            return '9999-99'
        return period

    return sorted(files, key=get_sort_key)


def create_error_details(error: Exception, context: Dict) -> Dict:
    """Create detailed error JSON for storage."""
    error_details = {
        'error_type': type(error).__name__,
        'error_message': str(error),
        'traceback': traceback.format_exc(),
        'timestamp': datetime.utcnow().isoformat(),
        'context': context
    }

    # Add HTTP-specific details if available
    if hasattr(error, 'response'):
        error_details['http_status'] = error.response.status_code
        error_details['response_headers'] = dict(error.response.headers)

    return error_details


def load_from_manifest(manifest_path: str, force_reload: bool = False, auto_heal_mode: str = 'permissive', unpivot_enabled: bool = False, quiet: bool = False) -> BatchStats:
    """
    Load files from YAML manifest.

    Features:
    - Idempotent: skips already-loaded files
    - Resilient: continues on errors
    - Trackable: full audit trail in database
    - Chronological: loads oldest files first

    Args:
        manifest_path: Path to YAML manifest file
        force_reload: If True, reload even if already loaded
        unpivot_enabled: If True, transform wide date patterns to long format
        quiet: If True, suppress all console output (for balanced display mode)

    Returns:
        BatchStats with load results
    """
    # Suppress Python logger warnings and pandas warnings when quiet mode is active
    if quiet:
        import logging as log_module
        import warnings
        pipeline_logger = log_module.getLogger('datawarp.loader.pipeline')
        original_level = pipeline_logger.level
        pipeline_logger.setLevel(log_module.ERROR)  # Only show errors, not warnings
        warnings.filterwarnings('ignore', category=UserWarning, module='pandas')

    # Parse manifest
    manifest = parse_manifest(manifest_path)
    manifest_name = manifest['manifest']['name']
    manifest_file_path = manifest_path  # Track which YAML file was used
    manifest_desc = manifest['manifest'].get('description', '')

    batch_start = time.time()
    stats = BatchStats()
    
    # Initialize observability logger
    obs_logger = None

    # Process each source
    for source_config in manifest['sources']:
        source_code = source_config['code']
        
        # Check if source is enabled (default: true)
        if not source_config.get('enabled', True):
            if not quiet:
                print(f"⏭  Skipping disabled source: {source_code}")
            continue
        
        # Initialize observability for first source (one logger per batch)
        if obs_logger is None:
            obs_logger = init_logger(manifest_name, source_code)

        # Get or create source (auto-registration)
        with get_connection() as conn:
            source = get_source(source_code, conn)

            if not source:
                # Auto-register from manifest with enrichment metadata
                source_name = source_config.get('name', source_code)
                table_name = source_config['table']
                schema_name = source_config.get('schema', 'staging')
                default_sheet = source_config.get('sheet')

                # Extract enrichment metadata if present
                description = source_config.get('description')
                metadata = source_config.get('metadata', {}).copy() if source_config.get('metadata') else {}

                # Add file provenance (URLs, periods, sheets, ZIP extraction)
                files_info = source_config.get('files', [])
                if files_info:
                    metadata['source_files'] = [
                        {
                            'url': f.get('url'),
                            'period': f.get('period'),
                            'mode': f.get('mode', 'replace'),
                            'sheet': f.get('sheet') or source_config.get('sheet'),
                            'extract': f.get('extract')  # File extracted from ZIP
                        }
                        for f in files_info
                    ]

                domain = metadata.get('domain') if metadata else None
                tags = metadata.get('tags') if metadata else None

                source = repository.create_source(
                    code=source_code,
                    name=source_name,
                    table_name=table_name,
                    schema_name=schema_name,
                    default_sheet=default_sheet,
                    conn=conn,
                    description=description,
                    metadata=metadata,
                    domain=domain,
                    tags=tags
                )
            else:
                # Validate invariants
                manifest_table = source_config['table']
                if source.table_name != manifest_table:
                    error_msg = f"Table mismatch for {source_code}: DB has {source.table_name}, manifest has {manifest_table}"
                    if not quiet:
                        print(f"⚠️  {error_msg}")
                    stats.errors.append({'source': source_code, 'error': error_msg})
                    continue

                manifest_sheet = source_config.get('sheet')
                if manifest_sheet and source.default_sheet and source.default_sheet != manifest_sheet:
                    error_msg = f"Sheet mismatch for {source_code}: DB has {source.default_sheet}, manifest has {manifest_sheet}"
                    if not quiet:
                        print(f"⚠️  {error_msg}")
                    stats.errors.append({'source': source_code, 'error': error_msg})
                    continue

        # Setup simple display
        from datawarp.loader.batch_display import (
            create_two_area_display, add_result
        )
        
        # For ZIP files, show ZIP filename instead of "default"
        sheet_display = source_config.get('sheet') or source.default_sheet or "default"
        files = source_config.get('files', [])
        
        # Check if this is a ZIP-based source (has 'extract' field)
        if files and files[0].get('extract'):
            # Extract ZIP basename from URL
            zip_url = files[0]['url']
            zip_basename = Path(urlparse(zip_url).path).name
            sheet_display = zip_basename
        
        target_table = f"{source.schema_name}.{source.table_name}"
        sorted_files = sort_files_chronologically(files)
        stats.total += len(sorted_files)
        
        # Print blank line for visual separation between sources
        if not quiet:
            if stats.total > len(sorted_files):  # Not the first source
                print()

            # Print header and table header
            create_two_area_display(manifest_name, target_table, sheet_display, len(sorted_files))

        # Process files with inline progress in table rows
        for file_info in sorted_files:
            url = file_info['url']
            period = file_info.get('period', 'unknown')
            extract_filename = file_info.get('extract')
            file_start = time.time()
            filename = Path(urlparse(url).path).name or 'file'

            # Get sheet name early for tracking
            sheet_name = file_info.get('sheet') or source_config.get('sheet') or source.default_sheet

            # Create unique identifier
            # For ZIPs: url#filename
            # For Excel with sheets: url#sheetname
            # For regular files: just url
            if extract_filename:
                tracking_url = f"{url}#{extract_filename}"
            elif sheet_name:
                tracking_url = f"{url}#{sheet_name}"
            else:
                tracking_url = url

            # Check if already loaded
            if not force_reload:
                with get_connection() as conn:
                    existing = repository.check_manifest_file_status(manifest_name, tracking_url, conn)

                if existing and existing['status'] == 'loaded':
                    file_result = FileResult(
                        period=period, status='skipped',
                        source_code=source_code,
                        rows=existing.get('rows_loaded', 0),
                        details="Already loaded"
                    )
                    stats.file_results.append(file_result)
                    stats.skipped += 1
                    stats.total_rows += existing.get('rows_loaded', 0)

                    add_result(None, period, "⏭ SKIPPED",
                             str(file_result.rows), "", "", file_result.details)
                    continue

            # Attempt load with inline animated spinner
            try:
                import sys
                from datawarp.loader.spinner import Spinner

                # Only use spinner if stdout is a TTY (not piped/redirected) AND not in quiet mode
                use_spinner = sys.stdout.isatty() and not quiet

                if use_spinner:
                    # Start spinner for download phase
                    spinner = Spinner(f"{period:<12} Downloading...")
                    spinner.start()

                    # Define progress callback to update spinner stages
                    def update_stage(stage):
                        if stage == "complete":
                            spinner.stop()  # Final stop before validation
                            return
                        spinner.stop()
                        if stage == "processing":
                            spinner.message = f"{period:<12} Processing..."
                        elif stage == "uploading":
                            spinner.message = f"{period:<12} Uploading data..."
                        spinner.start()
                else:
                    # No spinner - silent progress
                    def update_stage(stage):
                        pass  # Do nothing when output is redirected
                
                # Load file with progress callback and mode from manifest
                file_mode = file_info.get('mode', 'append')  # Get mode from manifest

                # Extract column mappings from enriched manifest (if present)
                # CRITICAL: Use DETERMINISTIC naming, not LLM semantic_name
                # LLM gives different names each period (e.g., "date" vs "reporting_period")
                # This causes schema drift errors when loading subsequent periods
                column_mappings = None
                wide_date_info = None  # Initialize for optional unpivot
                if 'columns' in source_config:
                    from datawarp.utils.schema import build_column_mappings_with_detection
                    column_mappings, collisions, wide_date_info = build_column_mappings_with_detection(source_config['columns'])
                    
                    # Log collision warnings
                    if not quiet:
                        if collisions:
                            for first, second, schema in collisions:
                                print(f"      ⚠️  Column collision: '{first}' and '{second}' → '{schema}'")

                        # Log wide date pattern warning
                        if wide_date_info.get('is_wide'):
                            print(f"      ⚠️  Wide date pattern: {wide_date_info['date_count']} date columns detected")
                            if unpivot_enabled:
                                print(f"         Unpivot ENABLED: will transform to long format")
                            else:
                                print(f"         Consider --unpivot transformation for schema stability")

                # Handle ZIP extraction (extract_filename already set above)
                file_url = url
                
                if extract_filename:
                    # This is a ZIP file - extract the specified file
                    from datawarp.utils.download import download_file
                    from datawarp.utils.zip_handler import extract_file_from_zip
                    
                    # Download ZIP once and cache for reuse
                    if url not in _file_cache:
                        _file_cache[url] = download_file(url)
                    
                    # Extract the specific file from ZIP
                    file_url = str(extract_file_from_zip(_file_cache[url], extract_filename))
                
                # Force reload: delete existing manifest record if it exists
                if force_reload:
                    with get_connection() as conn:
                        cur = conn.cursor()
                        cur.execute(
                            "DELETE FROM datawarp.tbl_manifest_files WHERE manifest_name = %s AND file_url = %s",
                            (manifest_name, tracking_url)
                        )
                        conn.commit()
                        cur.close()
                
                # Create manifest record FIRST with status='pending'
                with get_connection() as conn:
                    manifest_file_id = repository.record_manifest_file(
                        manifest_name=manifest_name,
                        manifest_file_path=manifest_file_path,
                        source_code=source_code,
                        file_url=tracking_url,
                        period=period,
                        status='pending',
                        rows_loaded=None,
                        columns_added=None,
                        error_details=None,
                        conn=conn
                    )
                
                result = load_file(
                    url=file_url,  # Use extracted file path or original URL
                    source_id=source_code,
                    sheet_name=sheet_name,
                    mode=file_mode,
                    force=force_reload,  # Pass force flag to bypass load history check
                    period=period,  # Pass period for lineage
                    manifest_file_id=manifest_file_id,  # Pass manifest record ID
                    progress_callback=update_stage,
                    column_mappings=column_mappings,  # Enriched manifest column semantics
                    unpivot=unpivot_enabled,  # Optional wide→long transformation
                    wide_date_info=wide_date_info,  # Pre-computed wide date detection
                    quiet=quiet  # Suppress output for progress display
                )

                # Stop spinner before checking result
                if use_spinner:
                    spinner.stop()

                if not result.success:
                    raise ValueError(result.error or "Load failed")

                file_duration = time.time() - file_start
                num_cols_added = len(result.columns_added) if result.columns_added else 0

                # Determine details
                # Extract display filename (from ZIP or regular URL)
                display_filename = extract_filename if extract_filename else filename
                
                # Add attribute info if present (e.g., boundary_version)
                attr_info = ""
                if 'attributes' in file_info and file_info['attributes']:
                    attrs = file_info['attributes']
                    if 'boundary_version' in attrs:
                        attr_info = f" ({attrs['boundary_version']} boundaries)"
                    elif attrs:  # Other attributes
                        attr_str = ', '.join(f"{k}={v}" for k, v in attrs.items())
                        attr_info = f" ({attr_str})"
                
                if stats.loaded == 0:
                    details = f"Table created{attr_info} • {display_filename}"
                elif num_cols_added > 0:
                    col_preview = ', '.join(result.columns_added[:3])
                    if len(result.columns_added) > 3:
                        col_preview += '...'
                    details = f"{col_preview}{attr_info} • {display_filename}"
                else:
                    details = f"Data appended{attr_info} • {display_filename}"

                # Store column metadata if present (for Parquet export)
                # Note: This is optional - if canonical source doesn't exist in tbl_canonical_sources,
                # we skip it gracefully (Phase 1 not fully implemented yet)
                if 'columns' in source_config and source_config['columns']:
                    try:
                        with get_connection() as conn:
                            stored_count = repository.store_column_metadata(
                                canonical_source_code=source_code,
                                columns=source_config['columns'],
                                conn=conn
                            )
                            if stored_count > 0 and not quiet:
                                print(f"  → Stored metadata for {stored_count} columns")
                    except Exception as e:
                        # Skip column metadata if canonical source doesn't exist yet
                        if "tbl_canonical_sources" in str(e):
                            pass  # Silently skip - Phase 1 canonicalization not active
                        else:
                            raise  # Re-raise other errors

                # Update manifest record to 'loaded' (record was created as 'pending' before load)
                with get_connection() as conn:
                    repository.record_manifest_file(
                        manifest_name=manifest_name,
                        manifest_file_path=manifest_file_path,
                        source_code=source_code,
                        file_url=tracking_url,
                        period=period,
                        status='loaded',
                        rows_loaded=result.rows_loaded,
                        columns_added=result.columns_added,
                        error_details=None,
                        conn=conn
                    )

                file_result = FileResult(
                    period=period, status='loaded',
                    source_code=source_code,
                    rows=result.rows_loaded,
                    new_cols=num_cols_added, duration=file_duration, details=details
                )
                stats.file_results.append(file_result)
                stats.loaded += 1
                stats.total_rows += result.rows_loaded

                # Clear progress and print final result
                if not quiet:
                    duration_str = f"({file_duration:.1f}s)"
                    new_cols_str = f"+{num_cols_added}" if num_cols_added > 0 else ""
                    final_msg = f"{period:<12} {'✓ Loaded':<10} {str(result.rows_loaded):<10} {new_cols_str:<10} {duration_str:<10} {details}"
                    print(f"\r{final_msg}{' ' * 20}")  # Extra spaces to clear any residual text

            except Exception as e:
                context = {
                    'manifest': manifest_name, 'source_code': source_code,
                    'period': period, 'url': url,
                    'table': f"{source.schema_name}.{source.table_name}"
                }
                error_details = create_error_details(e, context)
                file_duration = time.time() - file_start
                
                # Auto-heal: Try to fix type mismatches and retry (if enabled)
                error_str = str(e)
                
                if auto_heal_mode in ['permissive', 'aggressive'] and 'invalid input syntax for type integer' in error_str:
                    # Extract column name from error (handles multiline error messages)
                    match = re.search(r'column (\w+):', error_str, re.DOTALL)
                    if match:
                        column_name = match.group(1)
                        
                        # Auto-widen INTEGER → NUMERIC
                        try:
                            with get_connection() as conn:
                                with conn.cursor() as cur:
                                    alter_sql = f"""
                                        ALTER TABLE {source.schema_name}.{source.table_name}
                                        ALTER COLUMN {column_name} TYPE NUMERIC 
                                        USING {column_name}::NUMERIC
                                    """
                                    cur.execute(alter_sql)
                                    conn.commit()
                            
                            # Log the schema change
                            if obs_logger:
                                obs_logger.schema_widened(period, column_name, 'INTEGER', 'NUMERIC')
                            
                            # Retry the load

                            result = load_file(
                                url=file_url,
                                source_id=source_code,
                                sheet_name=sheet_name,
                                mode=file_mode,
                                force=force_reload,  # Pass force flag on retry too
                                period=period,
                                manifest_file_id=manifest_file_id,
                                progress_callback=update_stage,
                                column_mappings=column_mappings,
                                quiet=quiet  # Suppress output for progress display
                            )
                            
                            # Success! Record it
                            file_duration = time.time() - file_start
                            num_cols_added = len(result.columns_added) if result.columns_added else 0
                            display_filename = extract_filename if extract_filename else filename
                            
                            # Add attribute info
                            attr_info = ""
                            if 'attributes' in file_info and file_info['attributes']:
                                attrs = file_info['attributes']
                                if 'boundary_version' in attrs:
                                    attr_info = f" ({attrs['boundary_version']} boundaries)"
                                elif attrs:
                                    attr_str = ', '.join(f"{k}={v}" for k, v in attrs.items())
                                    attr_info = f" ({attr_str})"
                            
                            if stats.loaded == 0:
                                details = f"Table created (auto-widened {column_name}){attr_info} • {display_filename}"
                            elif num_cols_added > 0:
                                col_preview = ', '.join(result.columns_added[:3])
                                if len(result.columns_added) > 3:
                                    col_preview += '...'
                                details = f"{col_preview} (auto-widened {column_name}){attr_info} • {display_filename}"
                            else:
                                details = f"Auto-widened {column_name}{attr_info} • {display_filename}"
                            
                            with get_connection() as conn:
                                repository.record_manifest_file(
                                    manifest_name=manifest_name, manifest_file_path=manifest_file_path,
                                    source_code=source_code,
                                    file_url=tracking_url, period=period, status='loaded',
                                    rows_loaded=result.rows_loaded, 
                                    columns_added=result.columns_added,
                                    error_details=None, conn=conn
                                )
                            
                            file_result = FileResult(
                                period=period, status='loaded',
                                source_code=source_code,
                                rows=result.rows_loaded,
                                new_cols=num_cols_added, duration=file_duration, details=details
                            )
                            stats.file_results.append(file_result)
                            stats.loaded += 1
                            stats.total_rows += result.rows_loaded
                            
                            if not quiet:
                                duration_str = f"({file_duration:.1f}s)"
                                new_cols_str = f"+{num_cols_added}" if num_cols_added > 0 else ""
                                final_msg = f"{period:<12} {'✓ Loaded*':<10} {str(result.rows_loaded):<10} {new_cols_str:<10} {duration_str:<10} {details}"
                                print(f"\r{final_msg}{' ' * 20}")
                            
                            # Skip the rest of error handling - load succeeded!
                            continue
                            
                        except Exception as retry_error:
                            # Auto-heal failed, fall through to regular error handling
                            error_str = f"Auto-widen failed: {str(retry_error)}"
                
                # Regular error handling (if auto-heal didn't work or wasn't applicable)
                with get_connection() as conn:
                    repository.record_manifest_file(
                        manifest_name=manifest_name, manifest_file_path=manifest_file_path,
                        source_code=source_code,
                        file_url=tracking_url, period=period, status='failed',
                        rows_loaded=None, columns_added=None,
                        error_details=error_details, conn=conn
                    )

                # Extract actionable error message
                error_str = str(e)
                
                # Parse common error patterns for better UX
                if 'invalid input syntax for type' in error_str:
                    # Extract column and type info: "invalid input syntax for type integer: "87.0""
                    match = re.search(r'invalid input syntax for type (\w+).*column (\w+)', error_str)
                    if match:
                        sql_type, column = match.groups()
                        # Check if the error is about a decimal in a float-like column
                        # and the value itself contains a decimal point.
                        # If so, this is likely a valid value for a float type,
                        # and the error might be due to an incorrect type inference or a
                        # temporary mismatch that should be handled permissively.
                        # We don't want to report this as a "type mismatch" to the user
                        # if the target type is designed for decimals.
                        value_match = re.search(r'invalid input syntax for type \w+: "([^"]+)"', error_str)
                        if value_match:
                            str_value = value_match.group(1)
                            if '.' in str_value:
                                if sql_type.upper() in ['DOUBLE PRECISION', 'REAL', 'FLOAT']:
                                    # This is an expected decimal value for a float type.
                                    # The error itself is still a DB error, but for UX,
                                    # we might want to treat it differently or suppress
                                    # the "type mismatch" message if it's a known permissive case.
                                    # For now, we'll still report it but acknowledge the type.
                                    error_msg = f"Value '{str_value}' for column '{column}' could not be cast to {sql_type.upper()}. Consider widening column type."
                                else:
                                    error_msg = f"Type mismatch: column '{column}' needs {sql_type.upper()}, got decimal value '{str_value}'"
                            else:
                                error_msg = f"Type mismatch: column '{column}' needs {sql_type.upper()}, got '{str_value}'"
                        else:
                            error_msg = f"Type mismatch: column '{column}' needs {sql_type.upper()}, got unexpected value"
                    else:
                        # Fallback without column name
                        match = re.search(r'invalid input syntax for type (\w+)', error_str)
                        if match:
                            sql_type = match.group(1)
                            error_msg = f"Type mismatch: {sql_type.upper()} column received unexpected value"
                        else:
                            error_msg = error_str[:80]
                elif 'Sheet' in error_str and 'not found' in error_str:
                    # Extract available sheets
                    match = re.search(r"Available: \[([^\]]+)\]", error_str)
                    if match:
                        sheets = match.group(1)
                        error_msg = f"Sheet '{sheet_name or 'specified'}' missing. Available: {sheets[:40]}"
                    else:
                        error_msg = "Sheet not found in file"
                else:
                    # Generic error - show first 80 chars
                    error_msg = error_str[:80] + ("..." if len(error_str) > 80 else "")
                
                # Add filename to error for clarity (show up to 50 chars)
                display_filename = extract_filename if extract_filename else filename
                error_msg = f"{error_msg} (file: {display_filename[:50]})"

                file_result = FileResult(
                    period=period, status='failed',
                    source_code=source_code,
                    duration=file_duration,
                    details=error_msg, error=error_str
                )
                stats.file_results.append(file_result)
                stats.failed += 1
                stats.errors.append({'period': period, 'url': url, 'error': error_str})

                # Clear progress and print error
                if not quiet:
                    duration_str = f"({file_duration:.1f}s)"
                    final_msg = f"{period:<12} {'✗ FAILED':<10} {'':<10} {'':<10} {duration_str:<10} {error_msg}"
                    print(f"\r{final_msg}{' ' * 20}")
        


    # Calculate total duration and get actual DB stats
    stats.total_duration = time.time() - batch_start

    # Get actual final row count and column count from the table
    try:
        with get_connection() as conn:
            from datawarp.storage.repository import get_db_columns
            cols = get_db_columns(source.table_name, source.schema_name, conn)
            stats.total_columns = len(cols)
            
            # Get actual row count from database (not cumulative processed)
            cursor = conn.cursor()
            cursor.execute(f"SELECT COUNT(*) FROM {source.schema_name}.{source.table_name}")
            actual_row_count = cursor.fetchone()[0]
            cursor.close()
            stats.total_rows = actual_row_count  # Override with actual DB count
    except:
        stats.total_columns = 0

    # Print summary
    if not quiet:
        print()
        if obs_logger:
            observability_summary(obs_logger, stats)
        else:
            print_summary(stats, manifest_name)  # Fallback to old summary

    # Clear file cache after manifest completes
    _file_cache.clear()
    
    return stats


def print_summary(stats: BatchStats, manifest_name: str):
    """Print an insight-driven summary (Variation 1)."""
    
    # 1. Header
    status_icon = "✅" if stats.failed == 0 else "⚠️ "
    status_text = "BATCH COMPLETE" if stats.failed == 0 else "LOAD COMPLETED WITH FAILURES"
    print(f"\n{status_icon} {status_text}: {manifest_name}")
    
    # 2. Stats
    print("\n📊 Stats")
    print(f"  • Loaded: {stats.loaded} files ({stats.total_rows:,} rows)")
    if stats.failed > 0:
        print(f"  • Failed: {stats.failed} files ❌")
    
    # 3. Insights (only if we successfully loaded something)
    if stats.loaded > 0:
        print("\n🔎 Key Insights")
        
        # Freshness
        periods = [r.period for r in stats.file_results if r.period]
        if periods:
            latest = sorted(periods)[-1]
            try:
                latest_dt = datetime.strptime(latest, "%Y-%m")
                month_diff = (datetime.now().year - latest_dt.year) * 12 + datetime.now().month - latest_dt.month
                fresh_icon = "✅" if month_diff <= 2 else "⚠️ "
                fresh_msg = "Up-to-date" if month_diff <= 2 else f"{month_diff} months old"
                print(f"  • Freshness: {fresh_icon} {fresh_msg} (Latest: {latest})")
            except:
                print(f"  • Freshness: Latest period is {latest}")
        
        # Drift (Schema Changes)
        if stats.columns_added:
            print(f"  • Drift: Schema evolved ({len(stats.columns_added)} columns added) 🔧")
            for col in stats.columns_added[:3]:
                print(f"    - Added: {col}")
            if len(stats.columns_added) > 3:
                print(f"    - ... and {len(stats.columns_added)-3} more")
        else:
            print("  • Drift: Stable schema (No changes)")

    # 4. Action Required (Failures)
    if stats.failed > 0:
        print("\nAction Required:")
        print(f"  1. Fix {stats.failed} failures:")
        
        failed_files = [f for f in stats.file_results if f.status == 'failed']
        for failure in failed_files[:5]:
            print(f"     - {failure.period or 'Unknown'}: {failure.details}")
        
        if len(failed_files) > 5:
            print(f"     - ... and {len(failed_files)-5} more")
