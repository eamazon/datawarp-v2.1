"""Reset DataWarp v2 database - run SQL schema files."""

import os
import psycopg2
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()


def run_sql_file(filepath, conn):
    """Execute SQL file."""
    print(f"   📄 Running {filepath.name}...")
    with open(filepath, 'r') as f:
        sql = f.read()
        # Remove psql-specific commands (not supported by psycopg2)
        sql = sql.replace('\\echo', '--')
        
        cur = conn.cursor()
        try:
            cur.execute(sql)
            conn.commit()
            print(f"   ✓ {filepath.name} completed")
        except Exception as e:
            print(f"   ❌ Error in {filepath.name}: {e}")
            conn.rollback()
            raise
        finally:
            cur.close()


def reset_database():
    """Drop all DataWarp tables and recreate from SQL files."""
    
    # Find SQL files
    script_dir = Path(__file__).parent
    schema_dir = script_dir / 'schema'
    
    if not schema_dir.exists():
        print(f"❌ Schema directory not found: {schema_dir}")
        print(f"   Create it with: mkdir -p {schema_dir}")
        return
    
    # Connect to database
    conn = psycopg2.connect(
        host=os.getenv('POSTGRES_HOST', 'localhost'),
        port=int(os.getenv('POSTGRES_PORT', '5432')),
        dbname=os.getenv('POSTGRES_DB', 'datawarp'),
        user=os.getenv('POSTGRES_USER', 'datawarp'),
        password=os.getenv('POSTGRES_PASSWORD', '')
    )
    conn.autocommit = True
    
    try:
        print("🗑️  Dropping existing tables...")
        run_sql_file(schema_dir / '99_drop_all.sql', conn)
        
        print("\n🏗️  Creating schemas...")
        run_sql_file(schema_dir / '01_create_schemas.sql', conn)
        
        print("\n📋 Creating tables...")
        run_sql_file(schema_dir / '02_create_tables.sql', conn)
        
        print("\n🔍 Creating indexes...")
        run_sql_file(schema_dir / '03_create_indexes.sql', conn)

        print("\n📊 Creating manifest tracking...")
        run_sql_file(schema_dir / '04_manifest_tracking.sql', conn)

        print("\n🎯 Creating enrichment observability...")
        run_sql_file(schema_dir / '05_enrichment_observability.sql', conn)

        print("\n🌍 Configuring UK date format support...")
        cur = conn.cursor()
        cur.execute("ALTER DATABASE datawarp2 SET DateStyle='DMY,ISO';")
        cur.close()
        print("   ✓ DateStyle set to DMY,ISO (supports DD/MM/YYYY)")

        print("\n✅ Database reset complete!")
        print("\nSchemas:")
        print("  - datawarp (registry tables)")
        print("  - staging (data tables)")
        print("\nRegistry tables:")
        print("  - datawarp.tbl_data_sources")
        print("  - datawarp.tbl_load_events (legacy)")
        print("  - datawarp.tbl_load_history (Phase 4)")
        print("  - datawarp.tbl_pipeline_log (observability)")
        print("  - datawarp.tbl_manifest_files (batch loading)")
        print("  - datawarp.tbl_enrichment_runs (LLM observability)")
        print("  - datawarp.tbl_enrichment_api_calls (LLM metrics)")

        
    except Exception as e:
        print(f"\n❌ Reset failed: {e}")
        return
    finally:
        conn.close()


if __name__ == '__main__':
    print("⚠️  WARNING: This will DELETE ALL DATA in DataWarp v2!")
    response = input("Continue? (yes/no): ")
    
    if response.lower() in ('yes', 'y'):
        reset_database()
    else:
        print("Cancelled.")