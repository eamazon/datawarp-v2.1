# Canonical Schema Fix: Complete Phase 1 Implementation

**Created: 2026-01-09 06:15 UTC**
**Problem:** LLM generates different semantic names each period → schema drift
**Solution:** Complete Phase 1 fingerprint-based canonicalization

---

## The Problem (Concrete Example)

### Current Broken Flow

```
ADHD August 2025:
  Excel header: "Age 0 to 4"
  ↓
  LLM enrichment → semantic_name: "age_0_to_4_referral_count"
  ↓
  apply_enrichment.py copies VERBATIM
  ↓
  Load creates: tbl_adhd_xxx with column "age_0_to_4_referral_count"
  ✅ SUCCESS

ADHD November 2025:
  Excel header: "Age 0 to 4" (SAME!)
  ↓
  LLM enrichment → semantic_name: "age_0_to_4_count" (DIFFERENT!)
  ↓
  apply_enrichment.py copies VERBATIM (doesn't check registry)
  ↓
  Load tries INSERT with column "age_0_to_4_count"
  ❌ ERROR: column "age_0_to_4_referral_count" of relation does not exist
```

### Why This Happens

1. LLMs are non-deterministic (same input → different outputs)
2. `apply_enrichment.py` trusts LLM output blindly
3. Canonical registry (`tbl_canonical_sources`) exists but isn't queried
4. Column-level mapping missing

---

## The Solution: Match by Structure, Not Names

### Core Principle

**Original Excel headers are STABLE** → Use them as the fingerprint

```
Excel headers: ["Date", "Age 0 to 4", "Age 5 to 17", "Total"]
              ↓
    Generate fingerprint (MD5 of sorted lowercased names)
              ↓
         Match to existing source in registry
              ↓
         Use CANONICAL semantic names (from first period)
```

### Fixed Flow

```
ADHD August 2025:
  Excel headers: ["Date", "Age 0 to 4", ...]
  ↓
  LLM enrichment → semantic_name: "age_0_to_4_referral_count"
  ↓
  apply_enrichment.py:
    - Generate fingerprint from Excel headers
    - No match in registry (first time)
    - Use LLM names as-is (establish canonical)
  ↓
  Load creates: tbl_adhd_xxx
  ↓
  Store in tbl_canonical_sources:
    - canonical_code: "adhd_xxx"
    - fingerprint: {column_names: ["date", "age 0 to 4", ...], signature_hash: "abc123"}
    - canonical_columns: [{original: "Age 0 to 4", semantic: "age_0_to_4_referral_count"}]

ADHD November 2025:
  Excel headers: ["Date", "Age 0 to 4", ...] (SAME!)
  ↓
  LLM enrichment → semantic_name: "age_0_to_4_count" (DIFFERENT!)
  ↓
  apply_enrichment.py:
    - Generate fingerprint from Excel headers
    - MATCH FOUND in registry (fingerprint = "abc123")
    - Query canonical columns
    - MAP: LLM names → Canonical names
      "age_0_to_4_count" → "age_0_to_4_referral_count"
  ↓
  Load with CANONICAL names
  ✅ SUCCESS - INSERT into existing table
```

---

## Implementation Design

### Step 1: Enhance apply_enrichment.py

**File:** `scripts/apply_enrichment.py`

**Add imports:**
```python
from datawarp.storage.connection import get_connection
from datawarp.registry.fingerprint import generate_fingerprint, find_best_match
import json
```

**New function: Query canonical registry**
```python
def find_canonical_source(fingerprint_obj, conn):
    """
    Check if source exists in canonical registry by fingerprint.

    Returns: {
        'canonical_code': 'adhd_xxx',
        'canonical_columns': [...],
        'fingerprint': {...}
    } or None
    """
    with conn.cursor() as cur:
        # Get all canonical sources
        cur.execute("""
            SELECT canonical_code, fingerprint
            FROM datawarp.tbl_canonical_sources
        """)

        registry = {}
        for row in cur.fetchall():
            code = row[0]
            fp_json = row[1]  # JSONB

            # Reconstruct Fingerprint object
            from datawarp.registry.fingerprint import Fingerprint
            fp = Fingerprint(
                column_names=set(fp_json['column_names']),
                column_count=fp_json['column_count'],
                signature_hash=fp_json['signature_hash']
            )
            registry[code] = fp

        # Find best match
        canonical_code, confidence = find_best_match(
            fingerprint_obj,
            registry,
            threshold=0.95  # High threshold - exact match
        )

        if canonical_code:
            # Get canonical column mappings
            cur.execute("""
                SELECT original_name, column_name
                FROM datawarp.tbl_column_metadata
                WHERE canonical_source_code = %s
            """, (canonical_code,))

            canonical_columns = {
                row[0].lower(): row[1]  # original -> semantic
                for row in cur.fetchall()
            }

            return {
                'canonical_code': canonical_code,
                'canonical_columns': canonical_columns,
                'confidence': confidence
            }

    return None
```

**New function: Map columns**
```python
def map_columns_to_canonical(llm_columns, canonical_columns_map):
    """
    Map LLM-generated semantic names to canonical names.

    Args:
        llm_columns: [{'original_name': 'Age 0 to 4', 'semantic_name': 'age_0_to_4_count', ...}]
        canonical_columns_map: {'age 0 to 4': 'age_0_to_4_referral_count', ...}

    Returns:
        Mapped columns with canonical semantic names
    """
    mapped = []

    for col in llm_columns:
        original = col['original_name'].lower()

        if original in canonical_columns_map:
            # Use canonical semantic name
            col['semantic_name'] = canonical_columns_map[original]
            mapped.append(col)
        else:
            # New column (schema evolution) - keep LLM name
            mapped.append(col)

    return mapped
```

**Modified main function:**
```python
def apply_enrichment(yaml_path: str, json_path: str, output_path: str):
    """Apply enriched codes with canonical mapping."""

    # Load files
    yaml_data = yaml.safe_load(open(yaml_path))
    json_data = json.load(open(json_path))

    # Connect to database for canonical lookup
    conn = get_connection()

    enriched_map = {s['code']: s for s in json_data.get('manifest', [])}

    updates = []

    for source in yaml_data.get('sources', []):
        old_code = source.get('code', 'N/A')
        enriched = enriched_map.get(old_code)

        if not enriched:
            continue

        llm_code = enriched['code']
        llm_columns = enriched.get('columns', [])

        # Generate fingerprint from original Excel headers
        if llm_columns:
            from datawarp.registry.fingerprint import generate_fingerprint
            fingerprint = generate_fingerprint(llm_columns)

            # Check canonical registry
            canonical_match = find_canonical_source(fingerprint, conn)

            if canonical_match:
                # EXISTING SOURCE - map to canonical
                canonical_code = canonical_match['canonical_code']
                canonical_columns = canonical_match['canonical_columns']

                # Map LLM names → canonical names
                mapped_columns = map_columns_to_canonical(
                    llm_columns,
                    canonical_columns
                )

                source['code'] = canonical_code  # Use existing code
                source['columns'] = mapped_columns  # Canonical names

                console.print(f"  ✓ Mapped to existing: {canonical_code} (confidence: {canonical_match['confidence']:.2f})")

                # Log mapping for audit
                store_source_mapping(llm_code, canonical_code, fingerprint, conn)
            else:
                # NEW SOURCE - establish as canonical
                source['code'] = llm_code
                source['columns'] = llm_columns

                console.print(f"  → New canonical source: {llm_code}")
        else:
            # No columns (metadata sheet?) - use as-is
            source['code'] = llm_code
            source['columns'] = llm_columns

        # Update metadata
        source['table'] = f"tbl_{source['code']}"
        source['name'] = enriched.get('name', source.get('name', ''))
        source['description'] = enriched.get('description', '')
        source['metadata'] = enriched.get('metadata', {})
        source['_original_code'] = old_code

        updates.append({...})

    conn.close()

    # Save updated YAML
    with open(output_path, 'w') as f:
        yaml.dump(yaml_data, f, sort_keys=False, default_flow_style=False)

    console.print(f"\n✅ Enriched manifest saved: {output_path}")
```

**Helper function: Store mapping**
```python
def store_source_mapping(llm_code, canonical_code, fingerprint, conn):
    """Store LLM → canonical mapping for audit."""
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO datawarp.tbl_source_mappings
            (llm_generated_code, canonical_code, match_confidence, match_method, source_fingerprint)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (llm_generated_code, period) DO UPDATE
            SET canonical_code = EXCLUDED.canonical_code,
                match_confidence = EXCLUDED.match_confidence,
                mapped_at = NOW()
        """, (
            llm_code,
            canonical_code,
            0.95,  # High confidence (fingerprint match)
            'fingerprint',
            json.dumps({
                'column_names': list(fingerprint.column_names),
                'signature_hash': fingerprint.signature_hash
            })
        ))
    conn.commit()
```

### Step 2: Update loader to populate canonical registry

**File:** `src/datawarp/loader/batch.py`

**After successful load, register in canonical registry:**

```python
# In load_source() function, after successful load:

if result.success and source.get('columns'):
    # Register in canonical registry (first time only)
    from datawarp.registry.fingerprint import generate_fingerprint

    fingerprint = generate_fingerprint(source['columns'])

    with conn.cursor() as cur:
        # Check if already registered
        cur.execute("""
            SELECT 1 FROM datawarp.tbl_canonical_sources
            WHERE canonical_code = %s
        """, (source_code,))

        if not cur.fetchone():
            # Register new canonical source
            cur.execute("""
                INSERT INTO datawarp.tbl_canonical_sources
                (canonical_code, canonical_name, canonical_table, fingerprint, first_seen_period)
                VALUES (%s, %s, %s, %s, %s)
            """, (
                source_code,
                source.get('name', source_code),
                table_name,
                json.dumps({
                    'column_names': list(fingerprint.column_names),
                    'column_count': fingerprint.column_count,
                    'signature_hash': fingerprint.signature_hash
                }),
                period
            ))
            conn.commit()

            logger.info(f"Registered canonical source: {source_code}")
```

---

## Testing Plan

### Test 1: Fresh Start (Clean Registry)

```bash
# Reset database (clear canonical registry)
python scripts/reset_db.py

# Load August ADHD (establishes canonical)
python scripts/url_to_manifest.py <aug_url> manifests/adhd_aug25.yaml
python scripts/enrich_manifest.py manifests/adhd_aug25.yaml manifests/adhd_aug25_enriched.yaml
python scripts/apply_enrichment.py \
  manifests/adhd_aug25_enriched.yaml \
  manifests/adhd_aug25_enriched_llm_response.json \
  manifests/adhd_aug25_canonical.yaml

datawarp load-batch manifests/adhd_aug25_canonical.yaml

# Verify canonical registry populated
psql -c "SELECT canonical_code, fingerprint->>'signature_hash' FROM datawarp.tbl_canonical_sources;"
# Expected: 11-12 sources registered
```

### Test 2: Cross-Period Consolidation

```bash
# Load November ADHD (maps to August canonical)
python scripts/url_to_manifest.py <nov_url> manifests/adhd_nov25.yaml
python scripts/enrich_manifest.py manifests/adhd_nov25.yaml manifests/adhd_nov25_enriched.yaml
python scripts/apply_enrichment.py \
  manifests/adhd_nov25_enriched.yaml \
  manifests/adhd_nov25_enriched_llm_response.json \
  manifests/adhd_nov25_canonical.yaml

# THIS SHOULD NOW MAP TO AUGUST'S CANONICAL NAMES!

datawarp load-batch manifests/adhd_nov25_canonical.yaml

# Verify:
# 1. No new tables created (uses existing)
psql -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='staging' AND table_name LIKE 'tbl_adhd%';"
# Expected: Same count as after Test 1

# 2. Rows appended to existing tables
psql -c "SELECT canonical_code, COUNT(*) FROM staging.tbl_adhd_summary_new_referrals_age GROUP BY canonical_code;"
# Expected: 2 periods (Aug + Nov)

# 3. Source mappings logged
psql -c "SELECT llm_generated_code, canonical_code, match_method FROM datawarp.tbl_source_mappings;"
# Expected: Mappings showing Nov LLM codes → Aug canonical codes
```

### Test 3: Column Name Verification

```bash
# Check that November used August's column names
psql -c "SELECT column_name FROM information_schema.columns WHERE table_name='tbl_adhd_summary_new_referrals_age' ORDER BY ordinal_position;"

# Expected: Columns match August (e.g., "age_0_to_4_referral_count", not "age_0_to_4_count")
```

---

## Success Criteria

✅ August loads successfully (establishes canonical)
✅ November enrichment generates DIFFERENT semantic names (normal LLM behavior)
✅ apply_enrichment.py maps November → August canonical names
✅ November loads successfully into SAME tables as August
✅ No schema drift errors
✅ tbl_source_mappings shows LLM → canonical mappings
✅ Row counts increase (appended data)

---

## Rollback Plan

If this doesn't work:

**Option B: Abandon semantic renaming**
- Keep `original_name` as column names
- Use metadata for descriptions only
- 100% deterministic (Excel headers never change)

**Implementation:**
```python
# In apply_enrichment.py, don't rename columns
for col in llm_columns:
    col['semantic_name'] = sanitize(col['original_name'])  # Use original
```

This guarantees stability but loses semantic naming benefits.

---

## Time Estimate

- **Step 1:** Enhance apply_enrichment.py → 2 hours
- **Step 2:** Update loader registry logic → 1 hour
- **Testing:** → 1 hour
- **Total:** 4 hours

---

## Next Steps

1. **Review this design** - confirm approach is sound
2. **Implement Step 1** - enhance apply_enrichment.py
3. **Test with ADHD Aug → Nov** - verify cross-period consolidation
4. **If successful** - proceed to remaining publications
5. **If fails** - fall back to Option B (original names)

---

**The key insight:** Stop fighting LLM variance. Accept it and map to canonical deterministically.
