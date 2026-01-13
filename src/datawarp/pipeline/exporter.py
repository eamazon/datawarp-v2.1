"""DataWarp Parquet Export Library.

Extracts export logic from scripts/export_to_parquet.py for use as library.
Integrates with EventStore for observability.
"""
import os
import pandas as pd
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass
from typing import Optional, List, Dict

from datawarp.storage.connection import get_connection
from datawarp.storage import repository
from datawarp.supervisor.events import EventStore, create_event, EventType, EventLevel


@dataclass
class ExportResult:
    """Result of parquet export operation."""
    success: bool
    canonical_code: str
    row_count: int
    column_count: int
    parquet_size_mb: float
    parquet_path: str
    metadata_path: str
    error: Optional[str] = None


def export_source_to_parquet(
    canonical_code: str,
    output_dir: str,
    event_store: Optional[EventStore] = None,
    publication: str = None,
    period: str = None
) -> ExportResult:
    """Export a single source to Parquet + .md metadata.

    Args:
        canonical_code: Canonical source identifier
        output_dir: Output directory path
        event_store: Optional EventStore for observability
        publication: Publication code for event logging
        period: Period identifier for event logging

    Returns:
        ExportResult with export statistics
    """
    try:
        if event_store:
            event_store.emit(create_event(
                EventType.WARNING,
                event_store.run_id,
                publication=publication,
                period=period,
                level=EventLevel.INFO,
                message=f"Starting Parquet export for {canonical_code}",
                context={'source': canonical_code, 'output_dir': output_dir}
            ))

        with get_connection() as conn:
            # 1. Get source info
            source = repository.get_source(canonical_code, conn)
            if not source:
                raise ValueError(f"Source '{canonical_code}' not found")

            table_name = f"{source.schema_name}.{source.table_name}"

            # 2. Check if table exists
            cur = conn.cursor()
            cur.execute("""
                SELECT COUNT(*) FROM information_schema.tables
                WHERE table_schema = %s AND table_name = %s
            """, (source.schema_name, source.table_name))

            if cur.fetchone()[0] == 0:
                raise ValueError(f"Table {table_name} does not exist")

            # 3. Get first column for deterministic ordering
            cur.execute("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema || '.' || table_name = %s
                ORDER BY ordinal_position
                LIMIT 1
            """, (table_name,))
            first_column = cur.fetchone()
            sort_column = first_column[0] if first_column else None

            # 4. Read entire staging table
            if event_store:
                event_store.emit(create_event(
                    EventType.WARNING,
                    event_store.run_id,
                    publication=publication,
                    period=period,
                    level=EventLevel.INFO,
                    message=f"Reading data from {table_name}",
                    context={'table': table_name, 'sort_column': sort_column}
                ))

            if sort_column:
                df = pd.read_sql(f"SELECT * FROM {table_name} ORDER BY {sort_column}", conn)
            else:
                df = pd.read_sql(f"SELECT * FROM {table_name}", conn)

            row_count = len(df)

            if event_store:
                event_store.emit(create_event(
                    EventType.WARNING,
                    event_store.run_id,
                    publication=publication,
                    period=period,
                    level=EventLevel.INFO,
                    message=f"Read {row_count:,} rows from staging table",
                    context={'rows': row_count, 'columns': len(df.columns)}
                ))

            # 5. Get column metadata
            cur.execute("""
                SELECT column_name, data_type, ordinal_position
                FROM information_schema.columns
                WHERE table_schema || '.' || table_name = %s
                ORDER BY ordinal_position
            """, (table_name,))
            actual_columns = {row[0]: {'data_type': row[1], 'position': row[2]} for row in cur.fetchall()}

            # 6. Create output directory
            os.makedirs(output_dir, exist_ok=True)

            # 7. Write Parquet file
            parquet_path = Path(output_dir) / f"{canonical_code}.parquet"

            if event_store:
                event_store.emit(create_event(
                    EventType.WARNING,
                    event_store.run_id,
                    publication=publication,
                    period=period,
                    level=EventLevel.INFO,
                    message=f"Writing Parquet file: {parquet_path}",
                    context={'path': str(parquet_path)}
                ))

            df.to_parquet(parquet_path, index=False, engine='pyarrow', compression='snappy')
            file_size_mb = parquet_path.stat().st_size / 1024 / 1024

            # 8. Generate simple .md metadata file
            md_path = Path(output_dir) / f"{canonical_code}.md"
            md_content = f"""# {source.name}

**Dataset:** `{canonical_code}`
**Rows:** {row_count:,}
**Columns:** {len(actual_columns)}
**File Size:** {file_size_mb:.2f} MB

---

## Columns

"""
            for col_name in sorted(actual_columns.keys(), key=lambda x: actual_columns[x]['position']):
                col_info = actual_columns[col_name]
                md_content += f"- `{col_name}` ({col_info['data_type']})\n"

            md_content += f"\n---\n\n*Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*\n"
            md_content += "*Source: DataWarp v2.2*\n"

            with open(md_path, 'w') as f:
                f.write(md_content)

            if event_store:
                event_store.emit(create_event(
                    EventType.WARNING,
                    event_store.run_id,
                    publication=publication,
                    period=period,
                    level=EventLevel.INFO,
                    message=f"Parquet export completed: {file_size_mb:.2f} MB",
                    context={
                        'parquet_path': str(parquet_path),
                        'metadata_path': str(md_path),
                        'rows': row_count,
                        'columns': len(actual_columns),
                        'size_mb': file_size_mb
                    }
                ))

            return ExportResult(
                success=True,
                canonical_code=canonical_code,
                row_count=row_count,
                column_count=len(actual_columns),
                parquet_size_mb=file_size_mb,
                parquet_path=str(parquet_path),
                metadata_path=str(md_path)
            )

    except Exception as e:
        if event_store:
            event_store.emit(create_event(
                EventType.ERROR,
                event_store.run_id,
                publication=publication,
                period=period,
                level=EventLevel.ERROR,
                message=f"Parquet export failed: {str(e)}",
                context={'source': canonical_code, 'error': str(e)}
            ))

        return ExportResult(
            success=False,
            canonical_code=canonical_code,
            row_count=0,
            column_count=0,
            parquet_size_mb=0.0,
            parquet_path="",
            metadata_path="",
            error=str(e)
        )


def export_publication_to_parquet(
    publication: str,
    output_dir: str,
    event_store: Optional[EventStore] = None,
    period: str = None
) -> List[ExportResult]:
    """Export all sources for a publication to Parquet.

    Args:
        publication: Publication name (e.g., "adhd", "gp_practice")
        output_dir: Output directory path
        event_store: Optional EventStore for observability
        period: Optional period identifier for event logging

    Returns:
        List of ExportResult for each source
    """
    results = []

    try:
        if event_store:
            event_store.emit(create_event(
                EventType.STAGE_STARTED,
                event_store.run_id,
                publication=publication,
                period=period,
                level=EventLevel.INFO,
                message=f"Starting Parquet export for publication: {publication}",
                context={'publication': publication, 'output_dir': output_dir}
            ))

        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT code FROM datawarp.tbl_data_sources WHERE code LIKE %s",
                (f"{publication}%",)
            )
            sources_to_export = [row[0] for row in cur.fetchall()]

        if event_store:
            event_store.emit(create_event(
                EventType.WARNING,
                event_store.run_id,
                publication=publication,
                period=period,
                level=EventLevel.INFO,
                message=f"Found {len(sources_to_export)} sources to export",
                context={'source_count': len(sources_to_export)}
            ))

        for source_code in sources_to_export:
            result = export_source_to_parquet(source_code, output_dir, event_store, publication, period)
            results.append(result)

        successful = [r for r in results if r.success]
        failed = [r for r in results if not r.success]

        if event_store:
            event_store.emit(create_event(
                EventType.STAGE_COMPLETED,
                event_store.run_id,
                publication=publication,
                period=period,
                level=EventLevel.INFO,
                message=f"Parquet export completed: {len(successful)} successful, {len(failed)} failed",
                context={
                    'successful': len(successful),
                    'failed': len(failed),
                    'total_rows': sum(r.row_count for r in successful),
                    'total_size_mb': sum(r.parquet_size_mb for r in successful)
                }
            ))

        return results

    except Exception as e:
        if event_store:
            event_store.emit(create_event(
                EventType.STAGE_FAILED,
                event_store.run_id,
                publication=publication,
                period=period,
                level=EventLevel.ERROR,
                message=f"Parquet export failed: {str(e)}",
                context={'error': str(e)}
            ))

        return [ExportResult(
            success=False,
            canonical_code="",
            row_count=0,
            column_count=0,
            parquet_size_mb=0.0,
            parquet_path="",
            metadata_path="",
            error=str(e)
        )]
