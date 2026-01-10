"""DataWarp v2 CLI - Minimal interface to pipeline."""
import os
import sys
from pathlib import Path
import typer
from rich.console import Console
from rich.table import Table
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

from datawarp.loader.pipeline import load_file
from datawarp.loader.batch import load_from_manifest
from datawarp.storage.connection import get_connection
from datawarp.storage import repository

app = typer.Typer(help="DataWarp v2: Load files into PostgreSQL")
console = Console()


@app.command()
def register(
    source: str = typer.Argument(..., help="Unique source identifier (e.g., 'gp_appt')"),
    name: str = typer.Option(..., "--name", "-n", help="Human-readable name"),
    table: str = typer.Option(..., "--table", "-t", help="Target table name"),
    schema: str = typer.Option(None, "--schema", "-s", help="Schema (defaults to DATAWARP_DEFAULT_SCHEMA)"),
    sheet: str = typer.Option(None, "--sheet", help="Default sheet name for Excel files"),
):
    """Register a new data source."""
    try:
        if schema is None:
            schema = os.getenv('DATAWARP_DEFAULT_SCHEMA', 'staging')

        with get_connection() as conn:
            source_obj = repository.create_source(source, name, table, schema, sheet, conn)

        console.print(f"✅ Registered: {source} → {schema}.{table}")
        if sheet:
            console.print(f"   Default sheet: {sheet}")
    except Exception as e:
        console.print(f"❌ Error: {e}", style="bold red")
        raise typer.Exit(1)


@app.command()
def load(
    url: str = typer.Argument(..., help="File URL or local path"),
    source: str = typer.Argument(..., help="Registered source identifier"),
    sheet: str = typer.Option(None, "--sheet", help="Sheet name (Excel only)"),
    replace: bool = typer.Option(False, "--replace", help="Truncate table before loading"),
    force: bool = typer.Option(False, "--force", help="Force reload even if already loaded"),
):
    """Load a file into PostgreSQL."""
    mode = 'replace' if replace else 'append'
    try:
        result = load_file(url=url, source_id=source, sheet_name=sheet, mode=mode, force=force)
        
        if result.success:
            console.print(f"✅ Loaded {result.rows_loaded} rows into {result.table_name}")
            if result.columns_added:
                console.print(f"   Added columns: {', '.join(result.columns_added)}")
        else:
            console.print(f"❌ Error: {result.error}", style="bold red")
            raise typer.Exit(1)
    except Exception as e:
        console.print(f"❌ Error: {e}", style="bold red")
        raise typer.Exit(1)


@app.command()
def list():
    """List registered sources."""
    with get_connection() as conn:
        sources = repository.list_sources(conn)

    if not sources:
        console.print("No sources registered.")
        return

    for s in sources:
        console.print(f"{s.code:20} → {s.schema_name}.{s.table_name}")


@app.command("load-batch")
def load_batch_cmd(
    manifest: str = typer.Argument(..., help="Path to YAML manifest file"),
    force: bool = typer.Option(False, "--force", help="Reload already-loaded files"),
    auto_heal: str = typer.Option(
        None, "--auto-heal",
        help="Auto-fix schema mismatches: strict (disabled), permissive (INTEGER→NUMERIC only), aggressive (widen to TEXT)"
    ),
    unpivot: bool = typer.Option(
        False, "--unpivot",
        help="Transform wide date patterns (dates-as-columns) to long format for schema stability"
    ),
):
    """Load multiple files from a YAML manifest."""
    try:
        # Resolve manifest path
        manifest_path = Path(manifest)
        
        # Resolve auto-heal mode (CLI > env > default)
        if auto_heal is None:
            auto_heal = os.getenv('DATAWARP_AUTO_HEAL', 'permissive')

        # Check in manifests directory if not found
        if not manifest_path.exists():
            manifests_dir = Path(os.getenv('DATAWARP_MANIFESTS_DIR', './manifests'))
            alt_path = manifests_dir / manifest
            if alt_path.exists():
                manifest_path = alt_path
            else:
                console.print(f"❌ Manifest not found: {manifest}", style="bold red")
                console.print(f"   Checked: {manifest_path.absolute()}")
                console.print(f"   Checked: {alt_path.absolute()}")
                raise typer.Exit(1)

        # Load batch
        stats = load_from_manifest(str(manifest_path), force_reload=force, auto_heal_mode=auto_heal, unpivot_enabled=unpivot)

        # Exit with error code if failures
        if stats.failed > 0:
            raise typer.Exit(1)

    except FileNotFoundError as e:
        console.print(f"❌ {e}", style="bold red")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"❌ Error: {e}", style="bold red")
        raise typer.Exit(1)


@app.command("manifest-status")
def manifest_status_cmd(
    manifest_name: str = typer.Argument(..., help="Manifest name"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show all files"),
):
    """Show status of a manifest load."""
    try:
        with get_connection() as conn:
            # Get summary
            stats = repository.get_manifest_summary(manifest_name, conn)

            # Display summary
            console.print(f"\n=== Manifest Status: {manifest_name} ===\n")
            console.print(f"✅ Loaded:  {stats['loaded']} files")
            console.print(f"⏭️  Skipped: {stats['skipped']} files")
            console.print(f"❌ Failed:  {stats['failed']} files")
            console.print(f"⏳ Pending: {stats['pending']} files")

            total = sum(stats.values())
            console.print(f"\n📊 Total:   {total} files\n")

            # Show detailed list if verbose
            if verbose:
                files = repository.get_manifest_files(manifest_name, conn)

                if files:
                    table = Table(title="File Details")
                    table.add_column("Period", style="cyan")
                    table.add_column("Source", style="magenta")
                    table.add_column("Status", style="yellow")
                    table.add_column("Rows", justify="right")
                    table.add_column("Loaded At")

                    for f in files:
                        status_icon = {
                            'loaded': '✅',
                            'failed': '❌',
                            'skipped': '⏭️',
                            'pending': '⏳'
                        }.get(f['status'], '?')

                        table.add_row(
                            f['period'] or 'N/A',
                            f['source_code'],
                            f"{status_icon} {f['status']}",
                            str(f['rows_loaded']) if f['rows_loaded'] else '-',
                            str(f['loaded_at']) if f['loaded_at'] else '-'
                        )

                    console.print(table)

            if stats['failed'] > 0:
                console.print(f"\n⚠️  View error details: datawarp manifest-errors {manifest_name}\n")

    except Exception as e:
        console.print(f"❌ Error: {e}", style="bold red")
        raise typer.Exit(1)


@app.command("manifest-errors")
def manifest_errors_cmd(
    manifest_name: str = typer.Argument(..., help="Manifest name"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show full traceback"),
):
    """Show detailed error information for failed loads."""
    try:
        with get_connection() as conn:
            errors = repository.get_manifest_errors(manifest_name, conn)

        if not errors:
            console.print(f"✅ No errors found for manifest: {manifest_name}")
            return

        console.print(f"\n=== Failed Loads: {manifest_name} ===\n")

        for i, err in enumerate(errors, 1):
            console.print(f"{i}. Period: {err['period']}", style="bold yellow")
            console.print(f"   Source: {err['source_code']}")
            console.print(f"   URL: {err['file_url']}")
            console.print(f"   Error: {err['error_type']}: {err['error_message']}", style="red")
            console.print(f"   Time: {err['created_at']}")

            # Show context
            if err['context']:
                console.print(f"   Context: {err['context']}")

            # Show traceback if verbose
            if verbose and err['traceback']:
                console.print("\n   [dim]Traceback:[/dim]")
                console.print(f"   [dim]{err['traceback']}[/dim]")

            console.print(f"\n   💾 Database ID: {err['id']}")
            console.print(f"   🔍 Query details: SELECT error_details FROM datawarp.tbl_manifest_files WHERE id={err['id']};\n")

        console.print(f"Total failures: {len(errors)}\n")

    except Exception as e:
        console.print(f"❌ Error: {e}", style="bold red")
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
