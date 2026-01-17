# Agentic DataWarp - Documentation Index

**Created:** 2026-01-17
**Purpose:** Navigation guide for agentic DataWarp vision and implementation

---

## 📖 Start Here

### Vision & Roadmap
**[agentic_vision_roadmap.md](agentic_vision_roadmap.md)** - The complete vision and implementation roadmap

**What it covers:**
- End-state interaction scenarios (how agents will work)
- Two-track implementation approach (Track A + Track B)
- 7 implementation steps with time estimates
- Human-in-the-loop philosophy
- Success metrics and trade-offs

**Key sections:**
- Track A: Ingestion Automation (Steps 1-5, 8.5 hours)
- Track B: Intelligent Querying (Steps 6-7, 5 hours)
- Component architecture diagrams
- When to use which track

---

## 🎯 Implementation Tracks

### Track A: Ingestion Automation

**Goal:** Reduce human effort from 100% → 10% for pipeline operations

**Status:** Step 1 complete (Session 24), Steps 2-5 planned

**Steps:**
1. ✅ `add_publication.py` CLI + Discovery Mode (COMPLETE)
2. Log MCP Tools (2 hours)
3. Golden Tests (1.5 hours)
4. Schema Fingerprinting (2 hours)
5. Config MCP Tools (2 hours)

**Use case:** Data engineers managing DataWarp pipeline

**See:** [agentic_vision_roadmap.md](agentic_vision_roadmap.md#track-a-ingestion-automation-steps-1-5) (Steps 1-5)

---

### Track B: Intelligent Querying

**Goal:** Enable semantic discovery and querying without schema knowledge

**Status:** Designed in Session 27, ready for implementation

**Steps:**
6. Populate Metadata Layer (1 hour) - `scripts/populate_dataset_metadata.py`
7. Enhanced Query Tools (4 hours) - 5 new MCP tools

**Use case:** Analysts, agents, end-users querying data conversationally

**Key Design Principle:** Generic pattern-based lens detection (NOT hard-coded to ICB)
- Works for healthcare (Provider, ICB, Sub-ICB, GP Practice)
- Works for retail (Store, District, Region)
- Works for finance (Branch, Zone, HQ)
- Works for ANY hierarchy

**See:** [agentic_vision_roadmap.md](agentic_vision_roadmap.md#track-b-intelligent-querying-steps-6-7) (Steps 6-7)

---

## 🏗️ Architecture & Design Docs

### Semantic Layer Design (Session 27)

**Primary Design Doc:**
- **[../architecture/metadata_driven_reporting.md](../architecture/metadata_driven_reporting.md)** - Complete implementation design for Track B
  - Metadata-driven approach (no materialized views)
  - 5 enhanced MCP tools with examples
  - Pattern-based lens detection
  - Implementation guide

**Context Documents:**
- **[../architecture/icb_scorecard_structure.md](../architecture/icb_scorecard_structure.md)** - Real ICB commissioning intelligence structure
  - 485 metrics across 40+ domains
  - 4 organizational lenses explained
  - Performance vs intelligence metrics (37% vs 63%)
  - Real-world commissioning patterns

- **[../architecture/SEMANTIC_LAYER_FINAL_DESIGN.md](../architecture/SEMANTIC_LAYER_FINAL_DESIGN.md)** - Complete specification
  - 4-layer semantic architecture
  - 8 MCP tools with full specs
  - Testing strategy
  - Success metrics

**Key Insight:**
```
We already have the foundation in tbl_column_metadata:
├─ is_measure = true     → KPIs (statutory return metrics)
├─ is_dimension = true   → Filters (geography, time, age, provider)
└─ query_keywords        → Searchable terms for discovery

Just need to consolidate into dataset-level metadata for agent consumption.
```

---

## 🚀 Getting Started

### For Track A (Ingestion Automation):
1. Read: [agentic_vision_roadmap.md](agentic_vision_roadmap.md#step-2-log-mcp-tools)
2. Check: `../../docs/IMPLEMENTATION_TASKS.md` → Epic 1
3. Start with: Step 2 (Log MCP Tools)

### For Track B (Intelligent Querying):
1. Read: [../architecture/metadata_driven_reporting.md](../architecture/metadata_driven_reporting.md)
2. Read: [agentic_vision_roadmap.md](agentic_vision_roadmap.md#step-6-populate-metadata-layer)
3. Check: `../../docs/IMPLEMENTATION_TASKS.md` → Epic 2
4. Start with: Step 6 (Populate Metadata Layer)

**Recommended:** Start with Track B - faster time to value (5 hours), demonstrates AI-native querying

---

## 📊 Quick Reference

### Two-Track Comparison

| Aspect | Track A (Ingestion) | Track B (Querying) |
|--------|---------------------|-------------------|
| **Time** | 8.5 hours (Steps 1-5) | 5 hours (Steps 6-7) |
| **Status** | Step 1 done, 6.5 hrs remain | Designed, 5 hrs remain |
| **Users** | Data engineers | Analysts, agents, end-users |
| **Value** | Operational efficiency | User experience transformation |
| **Dependencies** | None (independent steps) | Enrichment running (✅ already is) |

**Both tracks are independent - can be developed in parallel**

---

## 🎓 Context: ICB Commissioning Intelligence

DataWarp's primary use case is **ICB (Integrated Care Board) commissioning intelligence**:

- **Statutory return metrics** - Performance indicators submitted by providers (NOT financial/contract data)
- **4 organizational lenses** - Provider, ICB, Sub-ICB, GP Practice
- **485 metrics** across 40+ domains (Cancer, Diagnostics, Mental Health, etc.)
- **37% performance metrics** (with targets) + **63% intelligence metrics** (trends/correlation)

**Generic Design:** Examples use ICB, but implementation works for ANY domain/hierarchy

---

## 📚 Related Documentation

**Task Management:**
- `../../docs/TASKS.md` - Current session work, what's next
- `../../docs/IMPLEMENTATION_TASKS.md` - Weekly options, deferred tasks, ideas

**Architecture:**
- `../../docs/architecture/system_overview_20260110.md` - Complete system design
- `../../docs/pipelines/` - Pipeline diagrams and workflows

**Session History:**
- `../../docs/sessions/session_20260117.md` - Sessions 23, 24, 27 (agentic work)

---

## 🔄 Update History

- **2026-01-17:** Created (Session 27) - Semantic layer design + task consolidation
- **2026-01-17:** Track B added (Steps 6-7) - Intelligent querying vision

---

**Navigation:** [← Back to docs/](../../docs/) | [→ Vision & Roadmap](agentic_vision_roadmap.md)
