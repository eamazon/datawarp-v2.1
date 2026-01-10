# DataWarp v2.1 - Documentation Guide

**Last Updated: 2026-01-10 18:45 UTC**

---

## 🎯 Quick Answer: Which Doc Do I Read?

### I Want To...

**Know what to work on NOW**
→ Read `TASKS.md` (5 min)

**Understand the system**
→ Read `architecture/system_overview_20260110.md` (30 min)

**Run the pipeline**
→ Read `CLAUDE.md` Section: "Essential Commands" (5 min)

**Test something**
→ Read `testing/TESTING_STRATEGY.md` (15 min)

**Implement next round features**
→ Read `IMPLEMENTATION_TASKS.md` (browse, 10 min)

**Learn workflows**
→ Read `implementation/WORKFLOW.md` (10 min)

---

## 📚 All Documentation (Simple Map)

### Root (Start Here)

1. **TASKS.md** - What's current? What's next? (READ FIRST)
2. **IMPLEMENTATION_TASKS.md** - Backlog for next round
3. **CLAUDE.md** - Project rules & commands

### Folders (When You Need Details)

**architecture/** - How system works
- `system_overview_20260110.md` ← Main architecture doc
- `cross_period_solution_20260110.md` ← Cross-period patterns

**testing/** - How to test & validate
- `TESTING_STRATEGY.md` ← Main testing doc
- `TESTING_GOALS_AND_EVIDENCE.md` ← Goals & metrics
- Other files: Test results (read when validating)

**implementation/** - How to do things
- `WORKFLOW.md` ← Main workflow doc
- `DB_MANAGEMENT_FRAMEWORK.md` ← DB management plan

**archive/** - Old stuff (ignore unless investigating history)

---

## ⚡ Common Scenarios

### New Session Starting

```
1. Read TASKS.md (current epic)
2. Read CLAUDE.md (session start protocol)
3. Start working
```

### Need to Understand Feature

```
1. Check TASKS.md for context
2. Read relevant architecture/ or testing/ doc
3. Search codebase if needed
```

### Stuck / Blocked

```
1. Check TASKS.md (known blockers?)
2. Ask user
```

---

## 🎯 Document Purpose (One-Liner Each)

| Document | Purpose |
|----------|---------|
| **TASKS.md** | Current status + what to work on |
| **IMPLEMENTATION_TASKS.md** | Backlog (80+ tasks, 4 priorities) |
| **CLAUDE.md** | Rules, commands, workflows |
| **architecture/system_overview** | Complete system design |
| **testing/TESTING_STRATEGY** | Testing approach + results |
| **implementation/WORKFLOW** | How-to guides |

**That's it. 6 core documents.**

Everything else is supporting detail or archive.

---

## 🔍 Search By Topic

**Cross-period consolidation:** architecture/cross_period_solution_20260110.md
**Fiscal year testing:** testing/FISCAL_TESTING_FINDINGS.md
**MCP server:** testing/MCP_PROTOTYPE_RESULTS.md
**LoadModeClassifier:** implementation/LOAD_MODE_STRATEGY.md
**Database management:** implementation/DB_MANAGEMENT_FRAMEWORK.md
**Production setup:** architecture/PRODUCTION_SETUP.md

---

## 📖 For AI Agents

**Every session:**
1. Read TASKS.md
2. Follow current epic
3. Use TodoWrite for progress
4. Update TASKS.md at end

**Never:**
- Create new docs (update existing)
- Skip reading TASKS.md
- Work without clear epic

**See CLAUDE.md for full rules.**

---

*This is the ONLY navigation guide you need.*
