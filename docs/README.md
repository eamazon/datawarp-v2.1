# DataWarp v2.1 - Documentation Guide

**Last Updated: 2026-01-11 11:25 UTC**

---

## 🚦 System Status

| Component | Status | Details |
|-----------|--------|---------|
| **PRIMARY OBJECTIVE** | ✅ Complete | Claude Desktop querying 75.8M rows |
| **Database** | ✅ Healthy | 182 sources, 181 tables, 15 GB |
| **MCP Server** | ✅ Operational | 3 tools, stdio protocol |
| **Parquet Exports** | ✅ Current | 179 files, 204 MB |
| **Orphans** | ✅ Clean | Last cleaned 2026-01-11 |

---

## 🎯 Quick Answer: Which Doc Do I Read?

### I Want To...

| Goal | Document | Time |
|------|----------|------|
| **Know what to work on NOW** | `TASKS.md` | 5 min |
| **See weekly options** | `IMPLEMENTATION_TASKS.md` | 5 min |
| **Understand the system** | `architecture/system_overview_20260110.md` | 30 min |
| **Run the pipeline** | `CLAUDE.md` → "Essential Commands" | 5 min |
| **Test something** | `testing/TESTING_STRATEGY.md` | 15 min |
| **Design MCP extensions** | `MCP_PIPELINE_DESIGN.md` | 20 min |
| **Manage files/cleanup** | `FILE_LIFECYCLE_ASSESSMENT.md` | 15 min |
| **Check E2E pipeline status** | `E2E_PIPELINE_STATUS.md` | 10 min |

---

## 📚 Documentation Map

### 🔴 Essential (Read Every Session)

| Document | Purpose | Audience |
|----------|---------|----------|
| **TASKS.md** | Current session work + what's next | Everyone |
| **IMPLEMENTATION_TASKS.md** | Weekly options (pick 0-1) + Ideas archive | Planning |
| **CLAUDE.md** | Project rules, commands, task philosophy | AI Agents |

### 🟡 Architecture (Read When Designing)

| Document | Purpose | When to Read |
|----------|---------|--------------|
| **architecture/system_overview_20260110.md** | Complete system design | Understanding the pipeline |
| **architecture/cross_period_solution_20260110.md** | Cross-period patterns | Multi-period loading |
| **MCP_PIPELINE_DESIGN.md** | Multi-dataset MCP design | Extending MCP server |
| **E2E_PIPELINE_STATUS.md** | End-to-end pipeline stages | Debugging pipeline issues |

### 🟢 Operations (Read When Doing)

| Document | Purpose | When to Read |
|----------|---------|--------------|
| **FILE_LIFECYCLE_ASSESSMENT.md** | File organization & cleanup | Managing files/orphans |
| **pipelines/** | ASCII pipeline visuals (5 diagrams) | Quick reference diagrams |
| **implementation/WORKFLOW.md** | How-to guides | Running workflows |
| **implementation/DB_MANAGEMENT_FRAMEWORK.md** | Database management | DB maintenance |
| **testing/TESTING_STRATEGY.md** | Testing approach | Running tests |

### ⚪ Reference (Read When Needed)

| Document | Purpose | When to Read |
|----------|---------|--------------|
| **testing/TESTING_GOALS_AND_EVIDENCE.md** | Goals & metrics | Validating tests |
| **testing/FISCAL_TESTING_FINDINGS.md** | Fiscal boundary results | Understanding NHS patterns |
| **implementation/LOAD_MODE_STRATEGY.md** | LoadModeClassifier | Data loading decisions |
| **archive/** | Historical docs | Investigating history |

---

## 🗺️ Document Relationships

```
                    ┌─────────────────┐
                    │   CLAUDE.md     │ ← Project Rules
                    │  (Start Here)   │
                    └────────┬────────┘
                             │
              ┌──────────────┼──────────────┐
              ▼              ▼              ▼
        ┌─────────┐    ┌──────────┐    ┌───────────────┐
        │ TASKS   │    │ IMPLEMEN │    │ architecture/ │
        │  .md    │    │ TATION   │    │ system_over   │
        │         │    │ _TASKS   │    │ view          │
        │ Current │    │          │    │               │
        │ Session │    │ Weekly   │    │ System        │
        │         │    │ Options  │    │ Design        │
        └────┬────┘    └────┬─────┘    └───────────────┘
             │              │
             │   ┌──────────┴──────────┐
             │   ▼                     ▼
             │  ┌──────────────┐  ┌───────────────┐
             │  │ MCP_PIPELINE │  │ FILE_LIFECYCLE│
             │  │ _DESIGN.md   │  │ _ASSESSMENT   │
             │  │              │  │ .md           │
             │  │ MCP Server   │  │ File Mgmt     │
             │  │ Extensions   │  │ & Cleanup     │
             │  └──────────────┘  └───────────────┘
             │
             ▼
        ┌──────────────────┐
        │ E2E_PIPELINE     │
        │ _STATUS.md       │
        │                  │
        │ Pipeline Health  │
        └──────────────────┘
```

---

## 📊 New in Session 10 (2026-01-11)

### Added Documents

| Document | Purpose | Key Sections |
|----------|---------|--------------|
| **MCP_PIPELINE_DESIGN.md** | Multi-dataset MCP server architecture | Registry schema, backend design, tool surface |
| **FILE_LIFECYCLE_ASSESSMENT.md** | File organization gaps & solutions | 5 gaps, proposed structure, cleanup workflows |

### Added Scripts

| Script | Purpose | Command |
|--------|---------|---------|
| `scripts/cleanup_orphans.py` | Find and remove orphaned data | `python scripts/cleanup_orphans.py --execute` |
| `scripts/generate_mcp_registry.py` | Bootstrap MCP registry from catalog | `python scripts/generate_mcp_registry.py` |

### Added MCP Components

| Component | Purpose | Location |
|-----------|---------|----------|
| Dataset Registry | 181 datasets, 8 domains | `mcp_server/config/datasets.yaml` |
| Domain Metadata | Column descriptions, keywords | `mcp_server/metadata/*.yaml` |
| DuckDB Backend | SQL queries on parquet | `mcp_server/backends/duckdb_parquet.py` |
| Query Router | Backend dispatch | `mcp_server/core/router.py` |

---

## 🏷️ Document Tags (For Signposting)

Each document can be tagged for quick filtering:

| Tag | Meaning | Documents |
|-----|---------|-----------|
| `#current` | Read every session | TASKS.md, CLAUDE.md |
| `#planning` | Weekly/monthly planning | IMPLEMENTATION_TASKS.md |
| `#architecture` | System design | system_overview, MCP_PIPELINE_DESIGN |
| `#operations` | Day-to-day operations | WORKFLOW, FILE_LIFECYCLE, cleanup scripts |
| `#testing` | Test execution | TESTING_STRATEGY, TESTING_GOALS |
| `#reference` | Look up when needed | FISCAL_TESTING, LOAD_MODE_STRATEGY |
| `#archive` | Historical only | archive/* |

---

## ⚡ Common Scenarios

### New Session Starting
```
1. Read TASKS.md (current status)
2. Read CLAUDE.md → Session Start Protocol
3. Check IMPLEMENTATION_TASKS.md for options
4. Start working
```

### Extending MCP Server
```
1. Read MCP_PIPELINE_DESIGN.md (architecture)
2. Check mcp_server/config/datasets.yaml (registry)
3. Modify mcp_server/stdio_server.py
```

### Cleaning Up Data
```
1. Run: python scripts/cleanup_orphans.py (dry run)
2. Read FILE_LIFECYCLE_ASSESSMENT.md if needed
3. Run: python scripts/cleanup_orphans.py --execute
```

### Debugging Pipeline Issues
```
1. Read E2E_PIPELINE_STATUS.md (which stage?)
2. Check relevant stage documentation
3. Use datawarp manifest-status <name> for details
```

---

## 🔮 README Evolution: Signposting Ideas

### Current State
- Static documentation map
- Manual updates required
- No status indicators

### Future Enhancements

**1. Dynamic Status Badges**
```markdown
![Database](https://img.shields.io/badge/DB-182%20sources-green)
![MCP](https://img.shields.io/badge/MCP-operational-green)
![Orphans](https://img.shields.io/badge/Orphans-0-green)
```

**2. Document Freshness Indicators**
```markdown
| Document | Last Updated | Freshness |
|----------|--------------|-----------|
| TASKS.md | 2026-01-11 | 🟢 Current |
| system_overview | 2026-01-10 | 🟡 Recent |
| FISCAL_TESTING | 2026-01-07 | 🟠 Aging |
```

**3. Dependency Graph**
- Auto-generate from document cross-references
- Show which docs depend on which

**4. Search Index**
- Topic → Document mapping
- Keyword search across all docs

**5. Reading Path Suggestions**
```markdown
## New to DataWarp?
1. CLAUDE.md (10 min) - Understand the rules
2. system_overview (30 min) - See the architecture
3. TASKS.md (5 min) - Current state
4. Try: datawarp list

## Want to Extend MCP?
1. MCP_PIPELINE_DESIGN.md (20 min)
2. mcp_server/stdio_server.py (code)
3. Test: python -c "from mcp_server.core.router import QueryRouter; ..."
```

**6. Version History**
```markdown
## Document Changelog
- 2026-01-11: Added MCP_PIPELINE_DESIGN, FILE_LIFECYCLE_ASSESSMENT
- 2026-01-10: Added E2E_PIPELINE_STATUS, DATABASE_STATE
- 2026-01-09: Reorganized architecture/, testing/
```

---

## 📖 For AI Agents

**Every session:**
1. Read TASKS.md
2. Read CLAUDE.md → Session Start Protocol
3. Follow current epic / pick from options
4. Use TodoWrite for progress
5. Update TASKS.md at end

**Document Rules:**
- ❌ Never create new docs without asking
- ✅ Update existing docs (add timestamped sections)
- ✅ Check docs/README.md for navigation
- ✅ Follow task management philosophy (brutal filter)

**Key Files:**
- `docs/TASKS.md` - Current session
- `docs/IMPLEMENTATION_TASKS.md` - Weekly options
- `CLAUDE.md` - Project rules

---

## 📁 Complete File Inventory

```
docs/
├── README.md                          # This file (navigation)
├── TASKS.md                           # Current session work
├── IMPLEMENTATION_TASKS.md            # Weekly options + Ideas
├── MCP_PIPELINE_DESIGN.md             # MCP server design (NEW)
├── FILE_LIFECYCLE_ASSESSMENT.md       # File management (NEW)
├── E2E_PIPELINE_STATUS.md             # Pipeline stages
├── DATABASE_STATE_20260110.md         # Database snapshot
├── pipelines/                         # ASCII pipeline visuals (NEW)
│   ├── README.md                      # Index + Quick reference
│   ├── 01_e2e_data_pipeline.md        # NHS Excel → Agent Querying
│   ├── 02_mcp_architecture.md         # Multi-dataset MCP design
│   ├── 03_file_lifecycle.md           # File states, cleanup, archival
│   ├── 04_database_schema.md          # Tables, relationships, audit
│   └── 05_manifest_lifecycle.md       # Draft → Enriched → Loaded
├── architecture/
│   ├── system_overview_20260110.md    # Main architecture
│   └── cross_period_solution_20260110.md
├── testing/
│   ├── TESTING_STRATEGY.md            # Main testing doc
│   ├── TESTING_GOALS_AND_EVIDENCE.md
│   └── FISCAL_TESTING_FINDINGS.md
├── implementation/
│   ├── WORKFLOW.md                    # How-to guides
│   ├── DB_MANAGEMENT_FRAMEWORK.md
│   └── LOAD_MODE_STRATEGY.md
├── handovers/                         # Session handover notes
├── plans/                             # Planning docs (gitignored)
└── archive/                           # Historical docs
```

---

*This is the navigation guide. Start here, follow the map.*
