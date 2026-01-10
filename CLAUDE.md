# CLAUDE.md

This file provides guidance to Claude Code when working with code in this repository.

---

## ⚠️ CRITICAL: Timestamps in Documentation

**MANDATORY RULE: Always add date/time stamps when appending to documentation files.**

### Format

When appending to any documentation file (features.md, scratch.md, TASKS.md, etc.):

```markdown
---

## [Section Title]

**Updated: 2026-01-08 21:30 UTC**

[Content here...]
```

### Examples

**CORRECT:**
```markdown
---

## Test Results - Track A Validation

**Updated: 2026-01-08 20:45 UTC**

- Metadata capture: ✅ Working
- Parquet export: ✅ Working
```

**WRONG:**
```markdown
## Test Results

- Metadata capture: Working
- Parquet export: Working
```

### Why This Matters

- Tracks when information was added
- Shows progression of work over time
- Helps identify stale information
- Critical for session handovers

**NEVER append to a documentation file without a timestamp. NO EXCEPTIONS.**

---

## Project Overview

**DataWarp v2.1** - Deterministic NHS data ingestion engine for semi-production deployment.

**Architecture:** ~20 files, ~1,500 lines of production code, **zero LLM calls in core** (enrichment optional).

**Core Flow:** Download → Extract → Compare → Evolve → Load

**Key Difference from v1:** v2 is fully deterministic (no LLM needed), v1 required LLM for structure detection.

---

## Essential Commands

### Development Setup

```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install package in editable mode
pip install -e .

# Database setup (requires PostgreSQL running)
python scripts/reset_db.py
```

### Running DataWarp

```bash
# Generate manifest from NHS URL
python scripts/url_to_manifest.py <url> output.yaml

# Enrich with LLM (Gemini or Qwen)
python scripts/enrich.py input.yaml output.yaml

# Apply enrichment (CRITICAL - Phase 1)
python scripts/apply_enrichment.py enriched.yaml llm_response.json canonical.yaml

# Load single file
datawarp load <url_or_path> --source SOURCE_CODE --sheet "Sheet Name"

# Load from manifest
datawarp load-batch canonical.yaml

# List registered sources
datawarp list

# Check source status
datawarp status SOURCE_CODE
```

### Testing

```bash
# Run all tests
pytest tests/

# Run specific test file
pytest tests/test_extractor.py -v

# Run with verbose output
pytest -vv tests/
```

### Database Management

```bash
# Reset database (drops all tables, recreates schema)
python scripts/reset_db.py

# Connect to database
psql -h localhost -U databot_dev_user -d databot_dev
```

---

## Canonical Workflow Decision Tree

**CRITICAL:** Follow this workflow for ALL new publications to ensure consistency.

### When Loading First Period of a Publication

**Example:** ADHD August 2025 (first time loading ADHD data)

```bash
# 1. Generate manifest
python scripts/url_to_manifest.py <url> manifests/production/adhd/adhd_aug25.yaml

# 2. Enrich with LLM (NO --reference flag)
python scripts/enrich_manifest.py \
  manifests/production/adhd/adhd_aug25.yaml \
  manifests/production/adhd/adhd_aug25_enriched.yaml

# 3. Load to database
datawarp load-batch manifests/production/adhd/adhd_aug25_enriched.yaml

# 4. Export to Parquet
python scripts/export_to_parquet.py --publication adhd output/
```

**Result:** LLM creates semantic names, establishes schema baseline.

---

### When Loading Subsequent Periods

**Example:** ADHD November 2025 (second period, use August as reference)

```bash
# 1. Generate manifest
python scripts/url_to_manifest.py <url> manifests/production/adhd/adhd_nov25.yaml

# 2. Enrich with reference (USE --reference flag)
python scripts/enrich_manifest.py \
  manifests/production/adhd/adhd_nov25.yaml \
  manifests/production/adhd/adhd_nov25_canonical.yaml \
  --reference manifests/production/adhd/adhd_aug25_enriched.yaml  # ← CRITICAL

# 3. Load to database
datawarp load-batch manifests/production/adhd/adhd_nov25_canonical.yaml

# 4. Export to Parquet
python scripts/export_to_parquet.py --publication adhd output/
```

**Result:** Reference-based enrichment produces consistent codes, cross-period consolidation works.

---

### Naming Conventions

- **First period:** `{publication}_{period}_enriched.yaml`
- **Subsequent periods:** `{publication}_{period}_canonical.yaml`
- **Placement:** `manifests/production/{publication}/`

---

### Validation Steps (Run After Each Stage)

```bash
# After manifest generation
python scripts/validate_manifest.py manifests/production/adhd/adhd_nov25.yaml

# After enrichment
python scripts/validate_manifest.py manifests/production/adhd/adhd_nov25_canonical.yaml --strict

# After loading
python scripts/validate_loaded_data.py adhd_summary_open_referrals_age

# After export
python scripts/validate_parquet_export.py output/adhd_summary_open_referrals_age.parquet
```

---

## Architecture

### Module Organization

```
src/datawarp/
├── core/                    # Extraction & drift detection
│   ├── extractor.py         # NHS Excel structure detection (871 lines - OPTIMIZED)
│   └── drift.py             # Column comparison (30 lines)
├── storage/                 # Database layer
│   ├── connection.py        # DB connection management
│   ├── models.py            # SQLAlchemy models
│   └── repository.py        # CRUD operations
├── loader/                  # Schema evolution & data loading
│   ├── pipeline.py          # Main orchestration (50 lines - THE entry point)
│   ├── ddl.py               # CREATE/ALTER TABLE generation (150 lines)
│   └── insert.py            # Batch INSERT with type casting (200 lines)
├── registry/                # Phase 1 - Canonicalization (NEW in v2.1)
│   └── fingerprint.py       # Cross-period source matching (80 lines)
├── cli/
│   └── commands.py          # Typer CLI (register, load, list, status)
└── utils/
    └── download.py          # File fetching (HTTP + local paths)
```

### Execution Flow

**NEW Workflow (v2.1 with Phase 1):**
```
url_to_manifest → enrich → apply_enrichment → load
                  (LLM)    (canonicalize)    (PostgreSQL)
```

**When you run `datawarp load-batch canonical.yaml`:**

1. **cli/commands.py:load_batch()** - Entry point
2. **loader/pipeline.py:load_file()** - Orchestrates for each source:
   - Download file (utils/download.py)
   - Get source config (storage/repository.py:get_source)
   - Extract structure (core/extractor.py:FileExtractor)
   - Detect drift (core/drift.py:detect_drift)
   - Generate fingerprint (registry/fingerprint.py) ← NEW
   - Match to canonical (registry/fingerprint.py) ← NEW
   - Evolve schema if needed (loader/ddl.py:add_columns)
   - Load data (loader/insert.py:insert_dataframe)
   - Log event (storage/repository.py:log_load_event)
3. Returns LoadResult with success, rows loaded, columns added

### Key Design Principles

**CRITICAL RULES (from v2 development):**

1. **No LLM Code in Core** - v2.1 core pipeline is deterministic. LLMs are OPTIONAL for enrichment only.
2. **File Size Limits:**
   - extractor.py: 900 lines max (currently 871)
   - insert.py: 200 lines max
   - Everything else: 100 lines or less
3. **One Drift Behavior** - No policies, no configuration. New columns → ALTER TABLE ADD, missing columns → INSERT NULL
4. **No Abstraction** - No abstract base classes, factories, plugins, config files, retry decorators, or async/await
5. **PostgreSQL Only** - Single database target (for now)
6. **Virtual Environment Mandatory** - ALL Python commands must run in .venv

### The Extractor (Core Intelligence)

`core/extractor.py:FileExtractor` is the brain of DataWarp. It:
- Detects multi-tier hierarchical headers (e.g., "April > 2024 > Patients")
- Handles merged cells and year/period rows
- Classifies sheets (TABULAR, METADATA, EMPTY)
- Infers column types (VARCHAR, INTEGER, NUMERIC) from keywords + sampling
- Finds data boundaries (detects footer rows like "Note:", "Source:")
- Handles NHS-specific patterns (suppressed values: *, -, ..)

**OPTIMIZED in v2.1:**
- Row caching for faster access
- Early exit logic in sheet classification
- 100-row limit in data end detection

**Critical:** Always runs fresh on every load (~50ms). No caching, no fingerprinting of structure.

### Database Schema

Located in `scripts/schema/`:
- `01_create_schemas.sql` - Creates `datawarp` and `staging` schemas
- `02_create_tables.sql` - Registry tables (tbl_data_sources, tbl_load_events)
- `03_create_indexes.sql` - Performance indexes
- `04_create_registry_tables.sql` - Phase 1 canonicalization tables (NEW)

**Registry Tables:**
- `datawarp.tbl_data_sources` - Registered sources (code → table mapping)
- `datawarp.tbl_load_events` - Audit log of all loads
- `datawarp.tbl_canonical_sources` - Canonical source registry (Phase 1)
- `datawarp.tbl_source_mappings` - LLM code → canonical mapping (Phase 1)
- `datawarp.tbl_drift_events` - Schema change tracking (Phase 1)
- `staging.tbl_*` - Actual data tables (created dynamically)

### Configuration

`.env` file contains:
- `POSTGRES_*` - Database connection (uses shared databot-postgres container)
- `LLM_PROVIDER` - "external" (Gemini) or "local" (Qwen)
- `GEMINI_API_KEY` - If using external LLM
- `QWEN_MODEL_PATH` - If using local LLM
- `DATABASE_TYPE=postgres` - Target database

---

## Development Workflow

### When Making Changes

1. **For substantial tasks** (>100 lines, multi-file, architecture changes):
   - Update `docs/plans/current_phase.md` with checklist
   - Request user consent before coding
   - Use TodoWrite to track progress

2. **After completing tasks:**
   - Run tests: `pytest tests/`
   - Check documentation limit: `git commit` will run pre-commit hook
   - Commit with format: `git commit -m "feat: description"`

3. **File size check:**
   - If approaching limits (see rules above), STOP and ask user

### Code Style Requirements

- Python 3.10+ with type hints on ALL functions
- One-line docstrings for functions
- Use stdlib logging, not print statements
- No async/await
- Simple, direct code (see CLAUDE_RULES below)

### Permitted Libraries Only

- openpyxl - Excel parsing
- pandas - DataFrame operations
- sqlalchemy - SQL query building (raw SQL only, NO ORM)
- psycopg2 - PostgreSQL driver
- typer - CLI framework
- rich - Terminal formatting
- requests - HTTP downloads
- python-dateutil - Date parsing (Phase 3)

**If you need a new library, ask first.**

---

## CLAUDE_RULES (Inline)

### File Size Limits (ENFORCED)

- **extractor.py:** 900 lines max (currently 871 - room for ~30 lines)
- **insert.py:** 200 lines max
- **All other files:** 100 lines max

### Code Complexity Rules

**NO:**
- Abstract base classes (ABC)
- Factory patterns
- Plugin systems
- Configuration files for behavior
- Retry decorators
- Async/await
- Class inheritance deeper than 1 level
- Metaclasses
- Monkey patching

**YES:**
- Simple functions
- Direct imports
- Explicit control flow
- Type hints
- Dataclasses (for data structures only)

**Example - GOOD:**
```python
def load_file(url: str, source_code: str) -> LoadResult:
    """Load file from URL into database."""
    df = download_file(url)
    result = insert_dataframe(df, source_code)
    return result
```

**Example - BAD:**
```python
class AbstractLoader(ABC):
    @abstractmethod
    async def load(self):
        pass

class LoaderFactory:
    @retry(max_attempts=3)
    async def create_loader(self, config: LoaderConfig):
        ...
```

### Drift Handling (Hardcoded Behavior)

**New columns:** ALTER TABLE ADD COLUMN (always)
**Missing columns:** INSERT NULL (always)
**Type changes:** Log warning, continue (always)

**NO configurable drift policies.** This is intentional.

### Error Handling

**DO:**
- Log errors with context
- Return Result types (success/failure)
- Fail fast on unrecoverable errors

**DON'T:**
- Silently catch exceptions
- Retry indefinitely
- Mask errors with generic messages

---

## Testing Strategy

Tests use fixtures in `tests/fixtures/`:
- `test_extractor.py` - Structure detection, multi-tier headers
- `test_drift.py` - Column comparison logic
- `test_phase2_manual.py` - Integration tests

When adding features, add corresponding tests.

---

## Common Tasks

### Adding a New CLI Command

Edit `src/datawarp/cli/commands.py` - uses Typer decorators:
```python
@app.command()
def mycommand(arg: str = typer.Argument(...)):
    """Command description."""
    # Implementation
```

### Modifying Type Inference

Edit `core/extractor.py:_infer_column_types()` - checks:
1. Column name keywords (date, code, name, etc.)
2. Sample first 25 rows of data
3. Returns VARCHAR(255), INTEGER, NUMERIC, DATE, etc.

### Changing DDL Generation

Edit `loader/ddl.py` - maps ColumnInfo.inferred_type → PostgreSQL types

### Adding Database Tables

Add SQL to `scripts/schema/02_create_tables.sql`, then:
```bash
python scripts/reset_db.py
```

---

## Important Context Files

**NEW: Documentation is now organized! Start with:**
- `docs/START_HERE.md` - **Agentic entry point** (read this FIRST for decision tree)
- `docs/TASKS.md` - Current epic, session history, what to work on NOW
- `docs/IMPLEMENTATION_TASKS.md` - Backlog for next round (80+ tasks)

**Before starting work, read:**
- `CLAUDE.md` (this file) - Project instructions, workflows, rules
- `README.md` - User-facing documentation
- `docs/architecture/system_overview_20260110.md` - Complete system design
- `docs/plans/features.md` - PRIMARY OBJECTIVE

**Documentation Structure:**
- `docs/architecture/` - System design, architecture, deployment
- `docs/testing/` - Testing strategy, results, validation
- `docs/implementation/` - Implementation plans, workflows, frameworks
- `docs/archive/` - Old session notes, historical scratch

**DO NOT CREATE NEW DOCUMENTATION FILES** without explicit user approval.
**Max 5 docs in production** (enforced by pre-commit hook)

---

## ⚠️ CRITICAL LESSON: Mission Drift (2026-01-09 00:45 UTC)

**WHAT HAPPENED:**
- Primary objective: **NHS Excel → PostgreSQL → Parquet → MCP → Agent Querying**
- Track A goal: Prove metadata enables agent querying (catalog.parquet → MCP server → test queries)
- What we did: Got stuck perfecting ingestion layer (80% → 100% success rate)
- **Result:** NEVER built catalog.parquet, NEVER built MCP server, NEVER tested actual agent querying

**THE MISTAKE:**
- Focused on making ingestion perfect (fixing date pivoting, schema drift)
- Lost sight of PRIMARY OBJECTIVE: **Enable agents to query data via MCP**
- Perfection paralysis: Trying to fix every ingestion bug before moving to agent layer

**THE LESSON:**
- **Ingestion is a MEANS, not the END**
- **80% working ingestion is ENOUGH to test agent querying**
- **Test the PRIMARY OBJECTIVE first, THEN optimize**
- **Don't fix problems that don't block the main goal**

**HOW TO AVOID:**
Every session, ask: "Does this work move me toward the PRIMARY OBJECTIVE (agent querying)?"
- If YES → proceed
- If NO → STOP, refocus on primary objective

**NEXT CORRECT STEPS:**
1. ✅ Accept 42 working sources (80% success)
2. ⏳ Build catalog.parquet (Track A Day 3) - ENABLES DISCOVERY
3. ⏳ Build basic MCP server (Track A Day 4) - ENABLES QUERYING
4. ⏳ Test actual agent querying (Track A Day 5) - VALIDATES PRIMARY OBJECTIVE
5. THEN evaluate if ingestion bugs matter

**READ THIS AT EVERY SESSION START. DON'T GET STUCK IN SUPPORT LAYERS.**

---

## Session Start Protocol (MANDATORY)

**CRITICAL:** Follow this protocol BEFORE doing any work. Session failures happen when this is skipped.

### 1. Read Current Workflow (5 minutes - DO NOT SKIP)

**ALWAYS read these sections in this order:**

1. **TASKS.md** - Current epic, workflow, success criteria
2. **docs/WORKFLOW.md** (if exists) - Proven patterns for current epic
3. **Current workflow section in features.md:**
   - Search for the current epic name (e.g., "Track A Day 2")
   - Read the "Implementation" and "Test Sequence" sections
   - Note the success criteria and validation gates

**RED FLAG:** If you're about to write >50 lines of code without reading the workflow, STOP.

### 2. Understand Success Criteria BEFORE Starting

**State explicitly:**
- What does "success" mean for this task? (validation passing, not row counts)
- What validation gates exist? (when to stop and validate)
- What's the proven workflow from previous sessions?

**RED FLAG:** If success criteria is unclear, ASK the user before proceeding.

### 3. Follow Validation-Gated Workflow

**For agent-ready data work (Track A pattern):**

```
For each publication:
  1. Generate manifest
  2. Enrich with LLM → [GATE: Verify YAML valid, retry if errors]
  3. Load to PostgreSQL → [GATE: Verify load successful]
  4. Export to Parquet → [GATE: Verify export created]
  5. Run validation → [GATE: ALL tests must pass before continuing]
  6. ONLY THEN move to next publication
```

**RED FLAG:** If you skip a validation gate, you're building on broken foundations.

### 4. Validation-First Mindset

**CRITICAL RULES:**

- ❌ "Loaded 3.4M rows" is NOT success
- ✅ "6/6 tests passing on N sources" IS success
- ❌ "Fast" is NOT better than "correct"
- ❌ "More data" is NOT better than "agent-ready data"
- ❌ Celebrating row counts = you've lost the plot
- ✅ Celebrating test pass rates = you understand the goal

### 5. When in Doubt, STOP and ASK

**If ANY of these are true, STOP and ASK:**
- [ ] I haven't read the workflow for this epic
- [ ] I don't understand why a validation step matters
- [ ] I'm tempted to skip a validation gate "to save time"
- [ ] Success criteria is unclear
- [ ] I'm celebrating row counts instead of test pass rates
- [ ] I'm about to process multiple items without validating any

### 6. Session Initialization Checklist

After reading workflows, complete these steps:

1. Run `git status` and `git log -n 5 --oneline`
2. Check pre-commit hook: `.git/hooks/pre-commit` exists and is executable
3. Report to user:
   - Current epic from TASKS.md
   - Workflow you'll follow (get confirmation)
   - Success criteria you'll measure against
   - Any blockers

---

## Using Claude Code Built-in Tools

**CRITICAL:** Use built-in tools instead of manual tracking.

### TodoWrite (In-Session Tracking)

**Use for:** Tracking multi-step tasks DURING a work session

```python
# When starting complex task
TodoWrite([
  {"content": "Create module X", "status": "in_progress", "activeForm": "Creating module X"},
  {"content": "Test module X", "status": "pending", "activeForm": "Testing module X"}
])

# As you complete steps
TodoWrite([
  {"content": "Create module X", "status": "completed", ...},
  {"content": "Test module X", "status": "in_progress", ...}
])
```

**User sees:** Real-time progress as task list updates
**Don't:** Manually update TASKS.md for every tiny step

### When to Use TodoWrite vs TASKS.md

**TodoWrite:**
- In-session work (you're actively coding NOW)
- 3-10 sub-tasks for current work
- Disappears at end of session

**TASKS.md:**
- Cross-session work (days/weeks)
- Epic-level tracking (Phase 1, Phase 2)
- Persistent (stays in git)

### EnterPlanMode (Complex Tasks)

**Use when:** Task is >100 lines, multi-file, or architectural

```
User: "Implement Phase 1 canonicalization"
You: [Call EnterPlanMode first]
     → Explore codebase
     → Design approach
     → Present plan
     → Get approval
     → THEN implement
```

**Don't:** Jump straight to coding for complex tasks

### Task Tool with Agents

**Explore Agent:** Find files, search code, understand structure
**Plan Agent:** Design implementation strategy

```python
# Instead of manually reading 50 files
Task(subagent_type="Explore", prompt="Find all SQL schema files")

# Instead of guessing architecture
Task(subagent_type="Plan", prompt="Design apply_enrichment.py module")
```

---

## What Makes v2.1 Different

**From v1:**
- v1: Used LLMs for structure detection (~$0.05/call, 7 seconds)
- v2.1: Deterministic extraction (~50ms, $0.00), LLM optional for enrichment

**From v2:**
- v2: Development/experimental version, 50+ docs, 100+ manifests
- v2.1: Production version, 5 docs max, clean architecture

**Key Improvement in v2.1:**
- **Phase 1 Integration:** `apply_enrichment.py` bridges gap between LLM enrichment and loading
- **Before:** LLM codes discarded, date-embedded codes used → 12 tables/year per source
- **After:** LLM codes applied → 1 table per source across all periods

---

## Git Commit Guidelines

**Format:**
```
<type>: <description>

<optional body>
<optional footer>
```

**Types:**
- `feat:` New feature
- `fix:` Bug fix
- `refactor:` Code refactoring
- `test:` Add/update tests
- `docs:` Documentation only (rare - prefer inline)
- `chore:` Maintenance (dependencies, etc.)

**Examples:**
```bash
git commit -m "feat: add apply_enrichment.py for Phase 1"
git commit -m "fix: extractor handles missing merged cells"
git commit -m "refactor: optimize row caching in extractor"
```

---

## Committing Changes with Git

Only create commits when requested by the user. If unclear, ask first.

**Git Safety Protocol:**
- NEVER update git config
- NEVER run destructive git commands (push --force, hard reset)
- NEVER skip hooks (--no-verify)
- NEVER force push to main
- Pre-commit hook will check documentation limit automatically

**When creating commits:**
1. Run `git status` and `git diff` to see changes
2. Add files: `git add <files>`
3. Commit: `git commit -m "message"`
4. Pre-commit hook will run automatically
5. If hook fails (too many docs), remove excess docs before committing

**Commit message format:**
```bash
git commit -m "feat: description

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

---

## Phase 1 Status (Current)

**Completed:**
- ✅ Pre-commit hook for documentation limit enforcement
- ✅ Strict documentation policy in CLAUDE.md

**In Progress:**
- 🔄 apply_enrichment.py implementation
- 🔄 fingerprint.py module
- 🔄 04_create_registry_tables.sql schema

**Pending:**
- ⏳ Testing with ADHD manifest
- ⏳ Cross-period consolidation validation

See `docs/plans/current_phase.md` for detailed checklist.

---

## Quick Reference

**Activate venv:** `source .venv/bin/activate`
**Run tests:** `pytest tests/`
**Check docs:** `.git/hooks/pre-commit` (runs on commit)
**Load data:** `datawarp load-batch manifest.yaml`
**Reset DB:** `python scripts/reset_db.py`

**Documentation limit:** 5 files max (enforced)
**File size limits:** extractor.py 900, insert.py 200, others 100

**Questions?** Ask the user. Don't assume.
**Need new doc?** Ask which existing doc to update or delete.
**Complex task?** Create checklist in current_phase.md first.

---

**END OF CLAUDE.MD - Keep this file under 250 lines**
