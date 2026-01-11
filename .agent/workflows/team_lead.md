---
description: Team Lead - One command to coordinate all agents
trigger: "run team", "team standup", "what needs attention"
---

# Team Lead Agent

**Purpose:** You say ONE thing. Team Lead coordinates everything else.

---

## How to Use

Just say any of these:
- "run team"
- "team standup"
- "what needs attention"
- "start my session"

Team Lead will:
1. Run all agents in parallel
2. Synthesize findings
3. Prioritize issues (CRITICAL → WARNING → INFO)
4. Recommend exactly what to do next

---

## What Team Lead Coordinates

```
                    ┌─────────────────┐
                    │   TEAM LEAD     │  ← You talk to this
                    │   (Coordinator) │
                    └────────┬────────┘
                             │
         ┌───────────────────┼───────────────────┐
         │                   │                   │
         ▼                   ▼                   ▼
   ┌───────────┐      ┌───────────┐      ┌───────────┐
   │ Pipeline  │      │  Test     │      │  Cleanup  │
   │ Guardian  │      │  Runner   │      │  Crew     │
   └───────────┘      └───────────┘      └───────────┘
         │                   │                   │
         ▼                   ▼                   ▼
   ┌───────────┐      ┌───────────┐      ┌───────────┐
   │ Data      │      │  Code     │      │  Catalog  │
   │ Validator │      │  Reviewer │      │  Curator  │
   └───────────┘      └───────────┘      └───────────┘
                             │
                             ▼
                      ┌───────────┐
                      │    MCP    │
                      │  Quality  │
                      └───────────┘
```

---

## Team Lead Output Format

```
## TEAM STANDUP

### CRITICAL (Fix Now)
- [issue description] → [exact command to fix]

### WARNING (Fix Soon)
- [issue description] → [recommendation]

### INFO (All Good)
- Pipeline: ✅ healthy
- Tests: ✅ passing
- Orphans: ✅ none

### RECOMMENDED NEXT ACTION
> [Single most important thing to do]
```

---

## Automatic Triggers

Team Lead runs automatically when you:
- Start a new session
- Say "what's broken"
- Say "morning standup"
- Ask "what should I work on"

---

## Team Lead Decision Tree

```
Start
  │
  ├─ Database down? ──────────────────► CRITICAL: Fix DB first
  │
  ├─ Tests failing? ──────────────────► CRITICAL: Fix tests
  │
  ├─ Recent failed loads? ────────────► WARNING: Investigate loads
  │
  ├─ Orphans found? ──────────────────► WARNING: Run cleanup
  │
  ├─ Catalog stale? ──────────────────► INFO: Rebuild catalog
  │
  └─ All healthy? ────────────────────► "Pick from IMPLEMENTATION_TASKS.md"
```

---

## Example Session

**You:** "run team"

**Team Lead:**
```
## TEAM STANDUP

### CRITICAL (Fix Now)
- Database missing → `python scripts/reset_db.py`

### WARNING (Fix Soon)
- 10 orphan manifest records → `python scripts/cleanup_orphans.py --execute`
- Test collection error in test_phase2_manual.py

### INFO
- Backfill: 12/12 URLs processed ✅
- State tracking: Working ✅

### RECOMMENDED NEXT ACTION
> Run `python scripts/reset_db.py` to restore database, then re-run team standup
```

**You:** "do it"

**Team Lead:** [Fixes critical issue, re-runs checks, reports new status]
