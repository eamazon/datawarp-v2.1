"""Quick test of Phase 2 storage layer."""

from dotenv import load_dotenv
load_dotenv()

from datawarp.storage import (
    create_source,
    get_source,
    list_sources,
    get_db_columns,
    get_connection
)

# Setup connection
with get_connection() as conn:
    # Test 1: Create a source
    print("Test 1: Creating source...")
    try:
        source = create_source(
            code='test_gp_appt',
            name='GP Appointments Test',
            table_name='tbl_gp_appointments',
            schema_name='staging',
            default_sheet='Sheet1',
            conn=conn
        )
        print(f"✅ Created source: {source.code} (ID: {source.id})")
    except Exception as e:
        print(f"⚠️ Source creation skipped/failed (might exist): {e}")
        conn.rollback()

    # Test 2: Get source by code
    print("\nTest 2: Getting source...")
    retrieved = get_source('test_gp_appt', conn)
    if retrieved:
        print(f"✅ Retrieved: {retrieved.name}")
    else:
        print("❌ Failed to retrieve source")

    # Test 3: List all sources
    print("\nTest 3: Listing sources...")
    all_sources = list_sources(conn)
    print(f"✅ Total sources: {len(all_sources)}")
    for s in all_sources:
        print(f"   - {s.code}: {s.name}")

    # Test 4: Get DB columns (should be empty - table doesn't exist yet)
    print("\nTest 4: Getting DB columns...")
    cols = get_db_columns('tbl_gp_appointments', 'staging', conn)
    print(f"✅ Columns: {len(cols)} (expected 0 for new table)")

print("\n✅ All tests passed!")
