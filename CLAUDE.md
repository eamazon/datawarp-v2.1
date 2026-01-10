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

## ⚠️ CRITICAL: Task Management - The Brutal Filter

**MANDATORY PHILOSOPHY: Only work on what blocks you NOW or what you'll do THIS WEEK**

### Problem This Solves

**Before:** Rigorous testing loops generate 10-20 discoveries → 80+ task backlog → Solo developer overwhelmed → Analysis paralysis

**After:** Apply "brutal filter" to every discovery → Only track what blocks you TODAY → Pick 0-1 task per week

### The Two Question Filter

**Apply to EVERY discovery during testing loops:**

1. **"Does this break the PRIMARY OBJECTIVE right now?"**
   - YES → Fix immediately (don't add to list)
   - NO → Go to question 2

2. **"Will I hit this issue in my actual workflow this week?"**
   - YES → Add to IMPLEMENTATION_TASKS.md → "Could Do This Week"
   - NO → Forget it exists (or add one line to "Ideas" section)

### Managing TASKS.md (Current Session Work)

**Purpose:** What should I work on RIGHT NOW (this session)?

**Structure:**
```markdown
## 🎯 WORK ON THIS NOW
- Current session status
- What just finished
- What's next (pick ONE option)

## 📊 System Status
- High-level metrics

## 📋 Task Management Philosophy
- Link to IMPLEMENTATION_TASKS.md

## 📝 Session History (Last 5)
- Brief summaries

## 🔄 Task Management Workflow
- How to use this file
```

**Rules:**
- ✅ Update at start and end of each session
- ✅ Keep "WORK ON THIS NOW" section at top
- ✅ Move completed work to "Session History"
- ✅ Always timestamp updates
- ❌ Never let it exceed 250 lines
- ❌ Never add detailed task breakdowns (that's IMPLEMENTATION_TASKS.md)

### Managing IMPLEMENTATION_TASKS.md (Weekly Options + Archive)

**Purpose:** What COULD I work on this week? What should I defer/ignore?

**Structure:**
```markdown
## 🚨 Fix When You Hit It (Not Before)
- ~10 known problems
- Don't fix until they break your workflow
- Each item: "When to fix" + "How to fix" + "Don't [build system]"

## 💡 Ideas (Not Blocking Anything)
- ~80 archived ideas
- Reference only
- Don't try to do them all

## 📌 Could Do This Week (User Decides)
- 4 concrete, achievable options
- Pick ZERO or ONE per session
- Each has clear goal + commands + benefit

## 🎯 How to Use This File
- Workflow for adding discoveries
- Monthly review guidance
```

**Rules:**
- ✅ Keep "Could Do This Week" to 4 options maximum
- ✅ When adding discovery: One line in "Ideas" section
- ✅ Monthly review: Move "Fix When Hit It" items that actually broke workflow
- ❌ Never expand "Could Do This Week" beyond 4 options
- ❌ Never remove "Ideas" section (it's the pressure valve)
- ❌ Never promote ideas to "Could Do This Week" without user request

**Backup:** Full task history in `docs/archive/IMPLEMENTATION_TASKS_BACKUP_YYYYMMDD.md`

### During Rigorous Testing Loops

**CRITICAL WORKFLOW:**

```
Test URL 1 → Bug found → Does it block PRIMARY OBJECTIVE?
                         ├─ YES → Fix immediately, keep testing
                         └─ NO → Keep testing (don't add to list)

Test URL 2 → Enhancement idea → Add ONE LINE to "Ideas", keep testing

Test URL 3 → Keep testing...
...
Test URL 8 → Done testing → NOW triage discoveries

End of loop:
1. Review "Ideas" section additions
2. Pick ZERO or ONE for "Could Do This Week"
3. Forget the rest
```

**DON'T:**
- ❌ Ask user "should I fix X?" for every discovery (creates permission fatigue)
- ❌ Stop testing to fix non-blocking issues
- ❌ Create 20 tasks from 20 discoveries
- ❌ Try to fix everything found during testing

**DO:**
- ✅ Fix blockers immediately and keep testing
- ✅ Add one-line notes for enhancements
- ✅ Complete the testing loop before triaging
- ✅ Present user with 0-4 options at end

### Philosophy Reminders

**Read these every session:**

> "Don't fix problems you don't have."
> "Don't build systems you don't need."
> "Do work that unblocks you TODAY."

**Key Insight:** For a solo developer, 4 weekly options is sustainable. 80+ tasks is paralyzing.

**Primary Objective Status:** ✅ COMPLETE (MCP server works, agents can query NHS data)

Therefore: Most "improvements" are nice-to-haves, not blockers.

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

**ALWAYS read these at session start:**
1. `CLAUDE.md` (this file) - **Read "Brutal Filter" section EVERY session**
2. `docs/TASKS.md` - What to work on RIGHT NOW (current session)
3. `docs/IMPLEMENTATION_TASKS.md` - Weekly options (4 max) + Ideas archive
4. `docs/README.md` - Navigation guide (which doc for which purpose)

**Task Management Files (CRITICAL):**
- `docs/TASKS.md` - Current session work, updated each session
- `docs/IMPLEMENTATION_TASKS.md` - 3 sections:
  - 🚨 Fix When You Hit It (~10 deferred problems)
  - 💡 Ideas (~80 archived ideas - reference only)
  - 📌 Could Do This Week (4 options max - pick 0-1)
- `docs/archive/IMPLEMENTATION_TASKS_BACKUP_*.md` - Full task history

**Architecture & Planning:**
- `README.md` - User-facing documentation
- `docs/architecture/system_overview_20260110.md` - Complete system design
- `docs/testing/TESTING_STRATEGY.md` - Testing approach

**Documentation Structure:**
- `docs/architecture/` - System design, architecture, deployment
- `docs/testing/` - Testing strategy, results, validation
- `docs/implementation/` - Implementation plans, workflows, frameworks
- `docs/archive/` - Old session notes, task backups, historical scratch

**DO NOT CREATE NEW DOCUMENTATION FILES** without explicit user approval.
**Max 5 docs in production** (enforced by pre-commit hook)

### CRITICAL RULE: Update, Don't Create

**Before creating ANY new .md file, you MUST:**

1. **Check existing docs first:**
   - Testing topic? → Add to `docs/testing/TESTING_STRATEGY.md`
   - Implementation plan? → Add to `docs/IMPLEMENTATION_TASKS.md`
   - Workflow/process? → Add to `docs/implementation/WORKFLOW.md`
   - Task tracking? → Add to `docs/TASKS.md`
   - Architecture? → Add to `docs/architecture/system_overview_20260110.md`

2. **Ask yourself:** "Can this be a NEW SECTION in existing doc?"
   - If YES → UPDATE existing doc (add timestamped section)
   - If NO → ASK USER before creating

3. **Valid reasons for new doc:**
   - Fundamentally different purpose (not just new topic)
   - Existing doc would exceed 2000 lines
   - User explicitly requested separate doc

4. **Invalid reasons (STOP):**
   - "It's easier to create new"
   - "This feels like separate topic"
   - "I don't know where it fits" ← ASK USER

**Example of GOOD behavior:**
```markdown
## Existing Section

---

## NEW: Fiscal Testing Plan
**Added: 2026-01-10 18:30 UTC**

[New content as section in existing doc]
```

**Remember:** User wants easily locatable, manageable docs. Consolidate, don't sprawl.

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

### 0. Remember the Brutal Filter (2 minutes - DO NOT SKIP)

**ALWAYS review task management philosophy at session start:**

1. **Read:** "⚠️ CRITICAL: Task Management - The Brutal Filter" section above
2. **Remember:** Only fix what blocks you NOW or what you'll do THIS WEEK
3. **Check:** IMPLEMENTATION_TASKS.md → "Could Do This Week" (should have 4 options max)
4. **Verify:** TASKS.md → "WORK ON THIS NOW" (should have 1 clear current task)

**RED FLAG:** If IMPLEMENTATION_TASKS.md has >4 weekly options, you're doing it wrong.
**RED FLAG:** If you're about to create a new task list or backlog, STOP.

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
**Complex task?** Use EnterPlanMode first.

---

## 🔍 Quick Validation Checklist (Every Session)

**At session start, verify:**
- [ ] Read "Brutal Filter" section in CLAUDE.md
- [ ] TASKS.md updated (timestamp, current session status)
- [ ] IMPLEMENTATION_TASKS.md has ≤4 options in "Could Do This Week"
- [ ] I know PRIMARY OBJECTIVE status (✅ COMPLETE - MCP server works)
- [ ] I understand current session goal from TASKS.md

**During testing loops:**
- [ ] Fix blockers immediately, keep testing (don't ask permission for each)
- [ ] Add one-liners to "Ideas" for enhancements
- [ ] Complete full loop before triaging
- [ ] Present 0-4 options at end, not 20 tasks

**At session end:**
- [ ] Update TASKS.md (move current work to history)
- [ ] IMPLEMENTATION_TASKS.md still has ≤4 weekly options
- [ ] Commit changes with timestamp
- [ ] Created zero new docs (or got explicit approval)

**If ANY of these fail, I'm doing it wrong.**

---

**END OF CLAUDE.MD - Task management rules added 2026-01-10**
