# Task Management System

**Created: 2026-01-10 18:00 UTC**
**Purpose:** Master system for managing evolving tasks and priorities

---

## 📋 Quick Reference

### Where to Track What

| Type | Track In | Update When | Purpose |
|------|----------|-------------|---------|
| **Current Session Work** | TodoWrite tool | During session | Real-time progress |
| **Current Epic** | TASKS.md | End of session | What's active NOW |
| **Next Round Backlog** | IMPLEMENTATION_TASKS.md | When planning | What's coming up |
| **Session Handoff** | handovers/*.md | Session end | Context for next session |

---

## 🎯 Task Lifecycle

### 1. Capture (Where do tasks come from?)

**User Requests** → TASKS.md (Current Epic section)
**System Improvements** → IMPLEMENTATION_TASKS.md (Prioritized backlog)
**Bugs Found** → TASKS.md (Blockers section)
**Ideas/Notes** → Don't capture yet (ask user first)

### 2. Prioritize (What order?)

**P0 - Critical (Drop Everything)**
- PRIMARY OBJECTIVE blocked
- Production system down
- Data corruption

**P1 - High (Current Epic)**
- Active work in current round
- Tracked in TASKS.md → Current Epic

**P2 - Medium (Next Round)**
- Planned improvements
- Tracked in IMPLEMENTATION_TASKS.md

**P3 - Low (Backlog)**
- Nice-to-haves
- Ideas for future

**P4 - Archive (Historical)**
- Completed work
- Old session notes

### 3. Execute (How to work?)

**During Session:**
```
1. Read TASKS.md → Understand current epic
2. Use TodoWrite to break down steps
3. Update TodoWrite as you complete steps
4. Mark tasks complete in real-time
```

**At Session End:**
```
1. Update TASKS.md with progress
2. Move completed work to session history
3. Update blockers if any
4. Create handover if needed
```

### 4. Review (When to reassess?)

**Daily:** Check TodoWrite progress
**End of Session:** Update TASKS.md
**End of Epic:** Create session summary in TASKS.md
**Monthly:** Review IMPLEMENTATION_TASKS.md priorities

---

## 🔄 Current Task System

### Active Now (TASKS.md)

**Section:** Current Epic
**Format:**
```markdown
## 🎯 Current Status (YYYY-MM-DD)

**Epic:** [Epic Name]
**Status:** [In Progress / Blocked / Complete]

**Next Steps:**
1. [ ] Task 1
2. [ ] Task 2
3. [ ] Task 3

**Blockers:**
- [Issue description and status]
```

**Update:** End of every session

### Next Round (IMPLEMENTATION_TASKS.md)

**Section:** Organized by Priority
**Format:**
```markdown
## 🎯 Priority 1: [Name]

**Goal:** [What we're achieving]
**Estimated Effort:** [Time estimate]

### Phase 1: [Phase Name]

- [ ] Task 1.1: [Description]
  - Success criteria
  - Dependencies

- [ ] Task 1.2: [Description]
```

**Update:** When planning next round of improvements

---

## 📊 Task Dashboard (At-a-Glance)

### Current State

**Primary Objective:** ✅ COMPLETE (Agent querying validated)
**Current Epic:** Session 6 - MCP fix + ADHD testing + Frameworks
**Active Tasks:** 0 (session complete)
**Blockers:** 0
**Next Round:** DB Management + Testing Frameworks (80+ tasks)

### This Session (Session 6)

**Completed:**
- [x] Fix MCP metadata parsing (17/18 tests passing)
- [x] ADHD temporal testing (May/Aug/Nov)
- [x] Create DB Management Framework
- [x] Create Testing Goals & Evidence Framework
- [x] Reorganize documentation (22 files → 4 folders)
- [x] Create START_HERE.md (agentic entry point)

**Time Spent:** ~3 hours
**Tokens Used:** 100K / 200K (50%)

### Next Session Priorities

**Option A:** Implement DB Management (Priority 1, Phase 1)
**Option B:** Implement Testing Goals (Priority 2, Phase 1)
**Option C:** Find March/April/May URLs for fiscal testing
**Option D:** User decides

---

## 🎯 Priority Matrix

### Urgency vs Impact

```
High Impact │  P1: Do Now      │  P2: Schedule   │
           │  (Current Epic)  │  (Next Round)   │
           │                  │                 │
───────────┼──────────────────┼─────────────────┤
Low Impact │  P3: Backlog     │  P4: Archive    │
           │  (Ideas)         │  (Historical)   │
           │                  │                 │
           └──────────────────┴─────────────────┘
             High Urgency      Low Urgency
```

**P1 (Do Now):**
- Current epic from TASKS.md
- Critical bugs
- PRIMARY OBJECTIVE blockers

**P2 (Schedule):**
- IMPLEMENTATION_TASKS.md priorities
- Planned improvements
- Framework implementations

**P3 (Backlog):**
- Feature requests
- Optimizations
- Nice-to-haves

**P4 (Archive):**
- Completed sessions
- Old scratch notes
- Historical context

---

## 📝 Task Writing Guidelines

### Good Task (Actionable)

```
❌ BAD: "Fix extractor"
✅ GOOD: "Fix extractor cell type detection for decimal numbers"

❌ BAD: "Improve testing"
✅ GOOD: "Create tbl_test_evidence table and evidence collection scripts"

❌ BAD: "Documentation"
✅ GOOD: "Update CLAUDE.md with new doc structure references"
```

### Task Anatomy

**Every task should have:**
1. **Action verb** (Create, Fix, Update, Test, Deploy)
2. **Specific target** (What exactly)
3. **Success criteria** (How do we know it's done?)
4. **Dependencies** (What needs to happen first?)

**Example:**
```markdown
- [ ] Task: Create tbl_test_evidence table
  - **What:** SQL table for storing test evidence
  - **Success:** Table exists, 4 indexes created
  - **Dependencies:** None
  - **Effort:** 30 min
```

---

## 🔄 Session Workflow

### Session Start (10 min)

```bash
1. Read docs/TASKS.md
   - What's the current epic?
   - What are the next steps?
   - Any blockers?

2. Read relevant context docs
   - Architecture docs if needed
   - Testing docs if validating
   - Implementation docs if building

3. Use TodoWrite to plan session
   - Break down current epic into steps
   - Estimate effort per step
   - Start first task
```

### During Session

```bash
1. Work on task
2. Update TodoWrite as you progress
3. Mark completed immediately (don't batch)
4. If blocked:
   - Update TASKS.md blockers
   - Ask user for guidance
   - Don't pivot without approval
```

### Session End (15 min)

```bash
1. Update TASKS.md
   - Session summary
   - Progress on epic
   - Update blockers
   - Next steps

2. Create handover if complex
   - docs/handovers/handover_YYYYMMDD_HHMM.md

3. Commit work
   - Meaningful commit message
   - Reference session number
   - Include Co-Authored-By

4. Clear TodoWrite
   - Tasks persist only within session
   - Fresh start next session
```

---

## 🚨 Red Flags (Task Management)

### Stop If:

- [ ] No clear success criteria for task
- [ ] Task is too vague ("improve X", "fix Y")
- [ ] Dependencies unclear
- [ ] No idea how long it will take
- [ ] Task not in any tracking system

### Ask User:

- **Before adding new epic:** "Is this the priority?"
- **Before deprioritizing:** "Should I pause current work?"
- **Before creating big task list:** "What's the real priority?"

---

## 📈 Progress Tracking

### Metrics to Track

**Velocity:**
- Tasks completed per session
- Average task duration
- Blockers encountered

**Quality:**
- Test pass rates
- Validation failures
- Rework required

**Focus:**
- Time on PRIMARY OBJECTIVE
- Time on support tasks
- Mission drift incidents

### Current Metrics (Session 6)

**Tasks Completed:** 7 major tasks
**Test Pass Rate:** 94% (MCP), 89% (loads)
**Blockers:** 0
**Focus:** 100% on frameworks (user priority)
**Mission Drift:** 0 (stayed on task)

---

## 🎯 Next Actions

### Immediate (Before Next Session)

- [x] Reorganize documentation
- [x] Create START_HERE.md
- [x] Update CLAUDE.md
- [ ] Find March/April/May URLs
- [ ] Commit reorganization

### Next Session

**User Choice:**
1. Implement DB Management (Priority 1)
2. Implement Testing Goals (Priority 2)
3. Complete fiscal testing (March/April/May)
4. Something else

---

## 📚 References

- **Current Work:** docs/TASKS.md
- **Backlog:** docs/IMPLEMENTATION_TASKS.md
- **Handovers:** docs/handovers/
- **Archive:** docs/archive/

---

*This system helps manage evolving tasks efficiently while maintaining focus on PRIMARY OBJECTIVE.*
