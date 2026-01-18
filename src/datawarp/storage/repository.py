"""Raw SQL queries for DataWarp v2 registry."""

import json
from typing import Optional, List
from datetime import datetime
from .models import Source, LoadEvent


def get_source(code: str, conn) -> Optional[Source]:
    """Get source by code."""
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, code, name, table_name, schema_name, default_sheet, created_at, last_load_at,
               description, metadata, domain, tags
        FROM datawarp.tbl_data_sources
        WHERE code = %s
        """,
        (code,)
    )
    row = cur.fetchone()

    if not row:
        return None

    return Source(
        id=row[0],
        code=row[1],
        name=row[2],
        table_name=row[3],
        schema_name=row[4],
        default_sheet=row[5],
        created_at=row[6],
        last_load_at=row[7],
        description=row[8],
        metadata=row[9],  # PostgreSQL JSONB returns as dict already
        domain=row[10],
        tags=row[11]
    )


def create_source(
    code: str,
    name: str,
    table_name: str,
    schema_name: str,
    default_sheet: Optional[str],
    conn,
    description: Optional[str] = None,
    metadata: Optional[dict] = None,
    domain: Optional[str] = None,
    tags: Optional[List[str]] = None
) -> Source:
    """Create new source with optional enrichment metadata."""
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO datawarp.tbl_data_sources
        (code, name, table_name, schema_name, default_sheet, description, metadata, domain, tags, created_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id, created_at
        """,
        (
            code, name, table_name, schema_name, default_sheet,
            description,
            json.dumps(metadata) if metadata else None,  # psycopg2 handles dict to JSONB
            domain,
            tags,
            datetime.utcnow()
        )
    )
    row = cur.fetchone()

    return Source(
        id=row[0],
        code=code,
        name=name,
        table_name=table_name,
        schema_name=schema_name,
        default_sheet=default_sheet,
        created_at=row[1],
        description=description,
        metadata=metadata,
        domain=domain,
        tags=tags
    )


def list_sources(conn) -> List[Source]:
    """Get all registered sources."""
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, code, name, table_name, schema_name, default_sheet, created_at, last_load_at,
               description, metadata, domain, tags
        FROM datawarp.tbl_data_sources
        ORDER BY created_at DESC
        """
    )

    return [
        Source(
            id=row[0],
            code=row[1],
            name=row[2],
            table_name=row[3],
            schema_name=row[4],
            default_sheet=row[5],
            created_at=row[6],
            last_load_at=row[7],
            description=row[8],
            metadata=row[9],  # PostgreSQL JSONB returns as dict already
            domain=row[10],
            tags=row[11]
        )
        for row in cur.fetchall()
    ]


def get_db_columns(table_name: str, schema_name: str, conn) -> List[str]:
    """Get column names from database table."""
    cur = conn.cursor()
    cur.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = %s
          AND table_name = %s
        ORDER BY ordinal_position
        """,
        (schema_name, table_name)
    )
    
    return [row[0] for row in cur.fetchall()]


def log_load(source_id: int, file_url: str, rows_loaded: int, columns_added: list, mode: str, conn) -> int:
    """Record load in tbl_load_history and return the load_id."""
    cur = conn.cursor()
    
    cur.execute(
        """
        INSERT INTO datawarp.tbl_load_history 
        (source_id, file_url, rows_loaded, columns_added, load_mode, loaded_at)
        VALUES (%s, %s, %s, %s, %s, NOW())
        RETURNING id
        """,
        (source_id, file_url, rows_loaded, columns_added, mode)
    )
    
    load_id = cur.fetchone()[0]
    
    # Update source's last_load_at
    cur.execute(
        """
        UPDATE datawarp.tbl_data_sources
        SET last_load_at = NOW()
        WHERE id = %s
        """,
        (source_id,)
    )
    cur.close()
    
    return load_id
    
# def log_load_event(source_id: int, url: str, rows: int, columns_added: list, conn) -> None:
#     """Record load in audit log."""
#     cur = conn.cursor()
    
#     cur.execute(
#         """
#         INSERT INTO datawarp.tbl_load_events 
#         (source_id, file_url, rows_loaded, columns_added, created_at)
#         VALUES (%s, %s, %s, %s, %s)
#         """,
#         (source_id, url, rows, json.dumps(columns_added), datetime.utcnow())
#     )
    
#     # Update source's last_load_at
#     cur.execute(
#         """
#         UPDATE datawarp.tbl_data_sources
#         SET last_load_at = %s
#         WHERE id = %s
#         """,
#         (datetime.utcnow(), source_id)
#     )


def get_last_load(source_id: int, conn) -> Optional[LoadEvent]:
    """Get most recent load for source."""
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, source_id, file_url, rows_loaded, columns_added, duration_ms, created_at
        FROM datawarp.tbl_load_events
        WHERE source_id = %s
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (source_id,)
    )
    row = cur.fetchone()

    if not row:
        return None

    return LoadEvent(
        id=row[0],
        source_id=row[1],
        file_url=row[2],
        rows_loaded=row[3],
        columns_added=json.loads(row[4]) if row[4] else [],
        duration_ms=row[5],
        created_at=row[6]
    )


# Manifest Tracking Functions

def check_manifest_file_status(manifest_name: str, file_url: str, conn) -> Optional[dict]:
    """Check if file from manifest has been loaded."""
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, status, rows_loaded, loaded_at
        FROM datawarp.tbl_manifest_files
        WHERE manifest_name = %s AND file_url = %s
        """,
        (manifest_name, file_url)
    )
    row = cur.fetchone()

    if not row:
        return None

    return {
        'id': row[0],
        'status': row[1],
        'rows_loaded': row[2],
        'loaded_at': row[3]
    }


def record_manifest_file(
    manifest_name: str,
    manifest_file_path: str,
    source_code: str,
    file_url: str,
    period: str,
    status: str,
    rows_loaded: Optional[int],
    columns_added: Optional[list],
    error_details: Optional[dict],
    conn
) -> int:
    """Record manifest file load attempt (success or failure)."""
    cur = conn.cursor()

    loaded_at = datetime.utcnow() if status == 'loaded' else None

    # Upsert using ON CONFLICT
    cur.execute(
        """
        INSERT INTO datawarp.tbl_manifest_files
        (manifest_name, manifest_file_path, source_code, file_url, period, status,
         error_details, rows_loaded, columns_added, loaded_at, created_at, updated_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
        ON CONFLICT (manifest_name, file_url)
        DO UPDATE SET
            status = EXCLUDED.status,
            error_details = EXCLUDED.error_details,
            rows_loaded = EXCLUDED.rows_loaded,
            columns_added = EXCLUDED.columns_added,
            loaded_at = EXCLUDED.loaded_at,
            updated_at = NOW()
        RETURNING id
        """,
        (
            manifest_name,
            manifest_file_path,
            source_code,
            file_url,
            period,
            status,
            json.dumps(error_details) if error_details else None,
            rows_loaded,
            json.dumps(columns_added) if columns_added else None,
            loaded_at
        )
    )

    return cur.fetchone()[0]


def get_manifest_summary(manifest_name: str, conn) -> dict:
    """Get summary statistics for a manifest."""
    cur = conn.cursor()
    cur.execute(
        """
        SELECT
            status,
            COUNT(*) as count
        FROM datawarp.tbl_manifest_files
        WHERE manifest_name = %s
        GROUP BY status
        """,
        (manifest_name,)
    )

    stats = {'loaded': 0, 'failed': 0, 'skipped': 0, 'pending': 0}
    for row in cur.fetchall():
        stats[row[0]] = row[1]

    return stats


def get_manifest_errors(manifest_name: str, conn) -> List[dict]:
    """Get detailed error information for failed loads."""
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, source_code, file_url, period, error_details, created_at
        FROM datawarp.tbl_manifest_files
        WHERE manifest_name = %s AND status = 'failed'
        ORDER BY period DESC
        """,
        (manifest_name,)
    )

    errors = []
    for row in cur.fetchall():
        error_details = json.loads(row[4]) if row[4] else {}
        errors.append({
            'id': row[0],
            'source_code': row[1],
            'file_url': row[2],
            'period': row[3],
            'error_type': error_details.get('error_type', 'Unknown'),
            'error_message': error_details.get('error_message', 'No details'),
            'timestamp': error_details.get('timestamp'),
            'context': error_details.get('context', {}),
            'traceback': error_details.get('traceback'),
            'created_at': row[5]
        })

    return errors


def get_manifest_files(manifest_name: str, conn) -> List[dict]:
    """Get all files in a manifest with their status."""
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, source_code, file_url, period, status, rows_loaded, loaded_at
        FROM datawarp.tbl_manifest_files
        WHERE manifest_name = %s
        ORDER BY period ASC
        """,
        (manifest_name,)
    )

    files = []
    for row in cur.fetchall():
        files.append({
            'id': row[0],
            'source_code': row[1],
            'file_url': row[2],
            'period': row[3],
            'status': row[4],
            'rows_loaded': row[5],
            'loaded_at': row[6]
        })

    return files


def store_column_metadata(canonical_source_code: str, columns: list, conn) -> int:
    """Store column metadata from manifest enrichment.

    Args:
        canonical_source_code: Canonical source identifier
        columns: List of column metadata dicts from manifest YAML
        conn: Database connection

    Returns:
        Number of columns stored
    """
    if not columns:
        return 0

    cur = conn.cursor()
    stored_count = 0

    for col in columns:
        # Extract fields (with defaults for optional fields)
        # CRITICAL: Look for 'name' (semantic snake_case) from LLM enrichment
        column_name = col.get('name') or col.get('semantic_name') or col.get('code')
        if not column_name:
            continue  # Skip columns without name

        original_name = col.get('original_name', '')
        description = col.get('description', '')
        data_type = col.get('data_type', 'varchar')
        is_dimension = col.get('is_dimension', False)
        is_measure = col.get('is_measure', False)
        query_keywords = col.get('query_keywords', [])

        # Insert or update column metadata
        cur.execute(
            """
            INSERT INTO datawarp.tbl_column_metadata
            (canonical_source_code, column_name, original_name, description,
             data_type, is_dimension, is_measure, query_keywords, metadata_source, confidence)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'llm', 0.70)
            ON CONFLICT (canonical_source_code, column_name)
            DO UPDATE SET
                original_name = EXCLUDED.original_name,
                description = EXCLUDED.description,
                data_type = EXCLUDED.data_type,
                is_dimension = EXCLUDED.is_dimension,
                is_measure = EXCLUDED.is_measure,
                query_keywords = EXCLUDED.query_keywords,
                updated_at = NOW()
            """,
            (canonical_source_code, column_name, original_name, description,
             data_type, is_dimension, is_measure, query_keywords)
        )
        stored_count += 1

    conn.commit()
    return stored_count


def store_column_metadata(
    canonical_source_code: str,
    columns: List[dict],
    conn,
    metadata_source: str = 'enrichment'
) -> int:
    """
    Store column metadata from enriched manifest to tbl_column_metadata.
    
    Args:
        canonical_source_code: Source code (matches tbl_data_sources.code)
        columns: List of column dicts from enriched manifest
        conn: Database connection
        metadata_source: Source of metadata (default: 'enrichment')
    
    Returns:
        Number of columns stored
    
    Schema mapping:
        enriched manifest               → tbl_column_metadata
        ---------------------------------------------------
        column['code']                  → column_name (raw Excel name)
        column['code']                  → original_name (same for now)
        column['description']           → description
        column['metadata']['measure']   → is_measure (bool)
        column['metadata']['dimension'] → is_dimension (bool)
        column['metadata']['tags']      → query_keywords (array)
    """
    cur = conn.cursor()
    
    # First, delete existing metadata for this source
    cur.execute(
        "DELETE FROM datawarp.tbl_column_metadata WHERE canonical_source_code = %s",
        (canonical_source_code,)
    )
    
    stored_count = 0
    
    for col in columns:
        # CRITICAL: Extract column name - LLM enrichment uses 'name' field (semantic snake_case)
        # Legacy format used 'code' field - support both for backwards compatibility
        column_name = col.get('name') or col.get('code') or col.get('semantic_name')
        if not column_name:
            continue  # Skip if no column name

        # Extract enrichment data - support both new and legacy formats
        description = col.get('description')
        original_name = col.get('original_name', column_name)

        # NEW FORMAT (from LLM enrichment prompt): Direct boolean fields
        is_measure = col.get('is_measure', False)
        is_dimension = col.get('is_dimension', False)
        query_keywords = col.get('query_keywords', [])
        data_type = col.get('data_type', 'VARCHAR')

        # LEGACY FORMAT: Extract from metadata JSONB (fallback for old manifests)
        if not is_measure and not is_dimension:
            metadata = col.get('metadata', {})
            measure_type = metadata.get('measure')  # e.g., 'count', 'percentage'
            dimension_type = metadata.get('dimension')  # e.g., 'date', 'provider_type'
            is_measure = measure_type is not None
            is_dimension = dimension_type is not None

            # Extract query keywords from tags (legacy format)
            if not query_keywords:
                tags = metadata.get('tags', [])
                query_keywords = tags if tags else []
        
        # Insert to tbl_column_metadata
        cur.execute("""
            INSERT INTO datawarp.tbl_column_metadata (
                canonical_source_code,
                column_name,
                original_name,
                description,
                data_type,
                is_measure,
                is_dimension,
                query_keywords,
                metadata_source,
                confidence
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (canonical_source_code, column_name)
            DO UPDATE SET
                original_name = EXCLUDED.original_name,
                description = EXCLUDED.description,
                data_type = EXCLUDED.data_type,
                is_measure = EXCLUDED.is_measure,
                is_dimension = EXCLUDED.is_dimension,
                query_keywords = EXCLUDED.query_keywords,
                metadata_source = EXCLUDED.metadata_source,
                updated_at = CURRENT_TIMESTAMP
        """, (
            canonical_source_code,
            column_name,
            original_name,  # Use actual original_name from LLM enrichment
            description,
            data_type,      # Add data_type field
            is_measure,
            is_dimension,
            query_keywords,
            metadata_source,
            0.95  # High confidence for LLM enrichment
        ))
        
        stored_count += 1
    
    conn.commit()
    cur.close()
    
    return stored_count
