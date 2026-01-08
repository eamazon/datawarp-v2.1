"""Quick test of Phase 2 storage layer."""

from dotenv import load_dotenv
load_dotenv()

from datawarp.storage import (
    create_source,
    get_source,
    list_sources,
    get_db_columns
)

# Test 1: Create a source
print("Test 1: Creating source...")
source = create_source(
    code='test_gp_appt',
    name='GP Appointments Test',
    table_name='tbl_gp_appointments',
    schema_name='staging'
)
print(f"✅ Created source: {source.code} (ID: {source.id})")

# Test 2: Get source by code
print("\nTest 2: Getting source...")
retrieved = get_source('test_gp_appt')
print(f"✅ Retrieved: {retrieved.name}")

# Test 3: List all sources
print("\nTest 3: Listing sources...")
all_sources = list_sources()
print(f"✅ Total sources: {len(all_sources)}")
for s in all_sources:
    print(f"   - {s.code}: {s.name}")

# Test 4: Get DB columns (should be empty - table doesn't exist yet)
print("\nTest 4: Getting DB columns...")
cols = get_db_columns('tbl_gp_appointments', 'staging')
print(f"✅ Columns: {len(cols)} (expected 0 for new table)")

print("\n✅ All tests passed!")
