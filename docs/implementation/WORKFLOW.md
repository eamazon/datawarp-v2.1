# DataWarp v2.1 - Proven Workflows

**Purpose:** Quick reference for validated workflows. Always follow these patterns.

---

## Track A: Agent-Ready Data Export Workflow

**Goal:** Export PostgreSQL staging tables to Parquet with rich metadata that agents can query

**Time per source:** ~5-10 minutes with validation gates
**Success metric:** 6/6 validation tests passing

**DO NOT skip validation gates** - they prevent building on broken foundations

---

### The Proven Pattern (Track A Day 1 - Validated)

For each publication, follow this sequence:

#### Step 1: Generate Manifest

```bash
python scripts/url_to_manifest.py <nhs_url> manifests/source.yaml
```

**✅ Validation Gate:**
- File created successfully
- YAML structure is valid
- Source count matches expectation

**❌ If Failed:** Check URL, network, file format

---

#### Step 2: Enrich with LLM

```bash
python scripts/enrich_manifest.py manifests/source.yaml manifests/source_enriched.yaml
```

**✅ Validation Gate:**
- No YAML parse errors in output
- LLM response captured (check *_llm_response.json exists)
- Search terms present in enriched YAML
- Semantic names assigned to columns

**❌ If Failed:**
- Check for YAML syntax errors in LLM output
- Retry enrichment (LLM can produce malformed YAML)
- If repeated failures, use fallback (original manifest)
- **CRITICAL:** Don't proceed without semantic metadata - agents need it

---

#### Step 3: Load to PostgreSQL

```bash
datawarp load-batch manifests/source_enriched.yaml
```

**✅ Validation Gate:**
- All sources loaded successfully (check status output)
- "→ Stored metadata for N columns" appears for each source
- No database errors
- Row counts reasonable

**❌ If Failed:**
- Check database connection
- Check for schema drift errors
- Verify file downloads successful

---

#### Step 4: Export to Parquet

```bash
python scripts/export_to_parquet.py --publication source_prefix
# OR for single source:
python scripts/export_to_parquet.py source_code
# OR for all:
python scripts/export_to_parquet.py --all
```

**✅ Validation Gate:**
- .parquet file created for each source
- .md companion file created for each source
- File sizes reasonable (not 0 bytes)
- Check one .md file manually - should have column descriptions

**❌ If Failed:**
- Check database has data
- Check output/ directory exists
- Verify metadata was captured in Step 3

---

#### Step 5: Validate Exports (CRITICAL - DO NOT SKIP)

```bash
python scripts/validate_parquet_export.py --all
# OR for specific source:
python scripts/validate_parquet_export.py source_code
```

**✅ Validation Gate - ALL 6 tests must pass:**

1. **Row Count Match** - PostgreSQL ↔ DuckDB ↔ Pandas all have same count
2. **Schema Consistency** - Column names and types match across all engines
3. **Sample Data Integrity** - First 3 rows (sorted) match exactly
4. **DuckDB Queryability** - SQL queries execute without errors
5. **Pandas Readability** - DataFrame loads successfully
6. **Column Name Match** - Metadata .md column names match Parquet columns exactly

**❌ If ANY Test Fails:**
- STOP immediately
- Do NOT process more sources
- Fix the issue before continuing
- Re-run validation until 6/6 pass

**Common Failures:**
- Test 1 fails → Data corruption or export incomplete
- Test 3 fails → Sorting issue (usually DuckDB vs Pandas difference, not data corruption)
- Test 6 fails → Fuzzy matching failed, column names don't match

---

#### Step 6: Meta-Test (Self-Validation)

**Run once per session to verify validator works:**

```bash
python scripts/validate_parquet_export.py --self-test
```

**✅ Expected:**
- Test 1: Row deletion detection → PASS
- Test 2: Value corruption detection → PASS

**This proves the validator itself is working correctly.**

---

### Success Criteria for Publication

**When is a publication "complete"?**

✅ All sources from publication:
- Have .parquet files
- Have .md files with rich metadata
- Pass 6/6 validation tests
- Have semantic column names (LLM enrichment succeeded)
- Have search terms for agent discovery

❌ NOT complete if:
- Validation tests failing
- LLM enrichment fell back to originals (no semantic names)
- Metadata missing search terms
- Orphaned files (files without corresponding database tables)

---

### Scaling Pattern

**Once pattern validated on 1 publication, scale:**

```bash
# Process multiple publications sequentially
for url in publication_urls; do
  # Steps 1-5 for each
  # STOP if validation fails
done
```

**CRITICAL:** Validate each publication before moving to next. Don't batch without validation.

---

## Red Flags (Session Failure Indicators)

🚩 **Skipping enrichment retry after YAML errors**
- Impact: No semantic metadata, agents can't understand columns

🚩 **Loading multiple publications without validating any**
- Impact: Building on broken foundations, cascading failures

🚩 **Celebrating row counts without validation**
- Impact: Wrong success metric, quality unknown

🚩 **Orphaned Parquet files (database reset without cleanup)**
- Impact: Inconsistent state, validation confusion

🚩 **Missing search terms in metadata (enrichment fell back)**
- Impact: Agents can't discover datasets

🚩 **Proceeding when validation shows 3/6 or 5/6 passing**
- Impact: Broken agent queries, silent failures

---

## Success Metrics

**Correct Metrics:**
- ✅ N/N publications pass 6/6 validation tests
- ✅ LLM enrichment success rate > 90%
- ✅ 100% of exports have search terms
- ✅ Zero orphaned files
- ✅ Agent can query data without errors

**Wrong Metrics:**
- ❌ "Loaded 3.4M rows"
- ❌ "Exported 71 files"
- ❌ "Completed in 10 minutes"
- ❌ "60 tables created"

**The only metric that matters: Can agents reliably query this data?**

---

## Validation Test Details

### Test 1: Row Count Match
**What:** Counts rows in PostgreSQL, DuckDB, Pandas
**Why:** Ensures no data loss during export
**Failure means:** Data corruption or incomplete export

### Test 2: Schema Consistency
**What:** Compares column names and types across engines
**Why:** Ensures structure preserved
**Failure means:** Schema mismatch, broken queries

### Test 3: Sample Data Integrity
**What:** Sorts by first column, compares first 3 rows
**Why:** Verifies actual data values match
**Failure means:** Data corruption (or minor sorting difference - check carefully)

### Test 4: DuckDB Queryability
**What:** Executes SELECT query on Parquet file
**Why:** Ensures file format is valid
**Failure means:** Corrupted Parquet file

### Test 5: Pandas Readability
**What:** Loads Parquet into DataFrame
**Why:** Ensures compatibility with Python analytics
**Failure means:** Format incompatibility

### Test 6: Column Name Match
**What:** Extracts columns from .md, compares to Parquet
**Why:** Ensures metadata accuracy for agent queries
**Failure means:** Agent will write broken queries

---

## Common Questions

**Q: Why can't I just load all data first, then validate?**
A: Because if validation fails, you've wasted time on bad data. Validate early and often.

**Q: Some validation tests fail but data looks okay - can I continue?**
A: NO. 6/6 must pass. If Test 3 fails due to sorting differences (not corruption), that's acceptable only if you verify manually. All other failures = STOP.

**Q: LLM enrichment keeps failing with YAML errors - what do I do?**
A: Retry 2-3 times. If persistent, proceed with original manifest but NOTE that metadata will be limited. Don't claim "agent-ready" without LLM metadata.

**Q: Can I run validation at the end after processing 10 publications?**
A: NO. Validate each publication immediately after export. Batch validation hides which publication failed.

---

**Remember: The goal is agent-queryable data, not row counts.**
**Validation gates prevent wasted effort on broken foundations.**
**When in doubt, validate more, not less.**
