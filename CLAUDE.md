# CLAUDE.md

This file provides guidance to Claude Code when working with code in this repository.

---

## ⚠️ CRITICAL: Documentation Policy

**DataWarp v2.1 maintains STRICT documentation minimalism.**

### Maximum 5 Documentation Files (ENFORCED BY PRE-COMMIT HOOK)

1. **README.md** - User-facing quick start
2. **CLAUDE.md** - This file (AI agent instructions)
3. **docs/ARCHITECTURE.md** - System overview (1 page max)
4. **docs/PRODUCTION_SETUP.md** - Deployment guide
5. **docs/plans/current_phase.md** - Active implementation plan ONLY
6. **docs/scratch.md** - Temporary notes (wiped weekly, doesn't count toward limit)

### Rules for AI Agents

**NEVER create new documentation files without explicit user approval.**

#### When User Says "Document This"

1. ✅ **Check if existing doc covers it** → Update that doc
2. ✅ **Check if it can be code comment** → Write inline
3. ✅ **Check if it's temporary** → Use docs/scratch.md
4. ❌ **Still needed?** → Ask which doc to update or what to delete

#### Forbidden Patterns

- ❌ Creating versioned docs (v1, v2, v3, final)
- ❌ Session notes (HANDOVER_*.md)
- ❌ "Just in case" documentation
- ❌ Duplicating information across files
- ❌ Implementation details (put in code comments)
- ❌ Migration plans (one-time, delete after completion)
- ❌ Architecture decision records (put in git commit messages)

#### Documentation Priority

1. **Self-documenting code** (best) - Clear function names, type hints
2. **Inline comments** (good) - Explain why, not what
3. **Module docstrings** (acceptable) - High-level purpose
4. **Separate markdown** (last resort) - Only if user-facing

#### Before Writing >50 Lines of Documentation

**STOP and ask:**
- Who is this for? (Users? Developers? AI agents?)
- Can it be code comments instead?
- Does an existing doc cover this?
- Will anyone read this in 2 weeks?

If unsure, **ask the user before writing.**

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

Before starting work:
- `README.md` - User-facing documentation
- `docs/ARCHITECTURE.md` - System overview
- `docs/PRODUCTION_SETUP.md` - Deployment guide
- `docs/plans/current_phase.md` - Active implementation plan

**DO NOT CREATE NEW DOCUMENTATION FILES** without explicit user approval.

---

## Session Initialization

When starting a new session:
1. **Read `docs/TASKS.md`** - Single source of truth for current work
   - Current epic and tasks
   - What's completed, in-progress, pending
   - Recent blockers and work sessions
2. Run `git status` and `git log -n 5 --oneline`
3. Check pre-commit hook: `.git/hooks/pre-commit` exists and is executable
4. Report status to user with:
   - Current epic from TASKS.md
   - Next task to work on
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
