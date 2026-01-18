# Pre-Commit Hook Options: With vs Without Real E2E

**Created: 2026-01-18**
**Context: After v2.2 refactoring hell, need to decide on pre-commit testing strategy**

---

## The Question

Should pre-commit hook run a REAL E2E test (actual pipeline execution) or just logic tests?

---

## Option 1: WITHOUT Real E2E (Current Default)

**What it runs:**
```
📋 E2E State Tests: (6 tests)
  - Check manifest files exist
  - Check database has data
  - Check metadata stored
  - Validate field mapping logic
  - Validate imports work

🧪 Unit Logic Tests: (6 tests)
  - Field mapping variants
  - Enrichment required fields
  - Manifest structure
  - Source code validation
  - Type inference keywords
  - Drift detection logic
```

**Time:** ~30 seconds

**Pros:**
- ✅ Fast (< 30 seconds)
- ✅ Works offline (no network)
- ✅ No API costs
- ✅ Tests core logic thoroughly
- ✅ Catches most code-level bugs

**Cons:**
- ❌ Doesn't actually RUN the pipeline
- ❌ Integration issues caught in PR, not at commit
- ❌ Can miss subtle pipeline breakage

**Good for:**
- Normal development flow
- Frequent small commits
- When offline
- Quick iterations

---

## Option 2: WITH Real E2E (Recommended After Refactoring Hell)

**What it runs:**
```
🚀 ADHD E2E Pipeline: (1 test)
  - Runs actual backfill for ADHD
  - Downloads file (or uses cache)
  - Runs enrichment (reference-based, no LLM)
  - Loads to database
  - Verifies metadata stored
  - Checks data loaded

📋 E2E State Tests: (6 tests)
  - Same as Option 1

🧪 Unit Logic Tests: (6 tests)
  - Same as Option 1
```

**Time:** ~45 seconds (ADHD E2E adds ~15 seconds)

**Actual measurement:**
```
ADHD E2E: 0.53 seconds (cached manifests + reference enrichment)
E2E Tests: 0.33 seconds
Unit Tests: 0.01 seconds
Total: ~1 second (FAST!)
```

**Pros:**
- ✅ **ACTUALLY RUNS THE PIPELINE** - catches integration issues
- ✅ Validates database connectivity
- ✅ Validates file loading
- ✅ Validates metadata tracking end-to-end
- ✅ Fast (~1 second with cached data)
- ✅ No LLM cost (uses reference enrichment)
- ✅ Would have caught v2.2 refactoring bugs BEFORE commit

**Cons:**
- ⚠️ Requires database running (~45 seconds if DB needs to start)
- ⚠️ Requires ADHD data loaded once (one-time setup)
- ⚠️ Requires network first time (then cached)
- ⚠️ Slightly slower than Option 1

**Good for:**
- After major refactoring (like v2.2)
- When you want maximum confidence
- Before pushing to main branch
- When you've had production issues

---

## Performance Comparison

### Option 1 (No E2E):
```
📋 E2E Tests:     0.33s
🧪 Unit Tests:    0.01s
─────────────────────
Total:           ~0.34s (30 seconds)
```

### Option 2 (With E2E):
```
🚀 ADHD E2E:      0.53s  ← Actually runs pipeline!
📋 E2E Tests:     0.33s
🧪 Unit Tests:    0.01s
─────────────────────
Total:           ~0.87s (45 seconds)
```

**Difference: ~0.5 seconds of REAL pipeline validation!**

---

## What Would Each Have Caught in v2.2 Refactoring?

### Option 1 (No E2E):
```
✅ Would catch:
  - Import errors
  - Field mapping bugs (if in unit tests)
  - Manifest structure issues

❌ Would miss:
  - enricher.py preview stripping bug
  - repository.py field lookup bug
  - Integration between enricher → loader → repository
```

### Option 2 (With E2E):
```
✅ Would catch:
  - ALL of Option 1
  - enricher.py preview stripping bug ✅
  - repository.py field lookup bug ✅
  - Integration issues ✅
  - Database storage issues ✅
  - Pipeline breakage ✅

Result: v2.2 bugs caught in 0.87 seconds instead of 6 days later
```

---

## Recommendation Based on Your Situation

**Given:**
- Last 2 days were "hell" after v2.2 refactoring
- Metadata tracking was broken for 6+ days
- Three separate bugs in integration layer
- Development at standstill due to firefighting

**Recommendation: ENABLE E2E (Option 2)**

**Why:**
1. **Real pain point:** You experienced actual damage from integration bugs
2. **Fast enough:** 0.87 seconds is acceptable for pre-commit
3. **High value:** Catches issues that actually hurt you
4. **No cost:** Uses reference enrichment (no LLM API calls)
5. **Safety net:** After major refactoring, maximum protection is worth it

---

## How to Switch Between Options

### Enable ADHD E2E in Pre-Commit:
```bash
bash scripts/toggle_e2e_hook.sh enable
```

### Disable ADHD E2E (back to fast mode):
```bash
bash scripts/toggle_e2e_hook.sh disable
```

### Skip E2E for one commit (emergency):
```bash
SKIP_E2E_SMOKE=1 git commit -m "message"
```

### Skip all tests (EMERGENCY ONLY):
```bash
git commit --no-verify -m "message"
```

---

## When to Use Each Option

### Use Option 1 (No E2E) when:
- ✅ Making small, isolated changes
- ✅ Frequent commits (multiple per hour)
- ✅ Working on documentation only
- ✅ Database not running
- ✅ Working offline

### Use Option 2 (With E2E) when:
- ✅ After major refactoring (like v2.2)
- ✅ Making changes to core pipeline
- ✅ Changing enricher, loader, or repository
- ✅ Before pushing to main
- ✅ When you want maximum confidence
- ✅ After production issues (like metadata tracking bug)

---

## Setup Instructions

### One-Time Setup for E2E:

1. **Ensure ADHD data loaded:**
   ```bash
   python scripts/backfill.py --pub adhd --config config/publications_with_all_urls.yaml --period 2025-05
   ```

2. **Enable E2E hook:**
   ```bash
   bash scripts/toggle_e2e_hook.sh enable
   ```

3. **Test it works:**
   ```bash
   git commit --allow-empty -m "test hook"
   # Should run ADHD E2E + other tests in ~45 seconds
   ```

---

## CI/CD Integration

**Both options still run full E2E in CI/CD:**

- **Gate 1 (Pre-commit):** Quick smoke OR Full smoke (your choice)
- **Gate 2 (PR):** Core publications E2E (5 minutes, BLOCKING)
- **Gate 3 (Release):** Full test suite (15 minutes)

**So even with Option 1 (no E2E in pre-commit), you still get full E2E validation in CI/CD before merge.**

---

## My Strong Recommendation

**Enable Option 2 (With E2E) for at least the next few weeks:**

**Reasons:**
1. You just fixed 3 critical integration bugs
2. Those bugs were in production for 6 days
3. Development was at standstill
4. The E2E test is FAST (0.87 seconds)
5. It would have caught all 3 bugs instantly

**After things stabilize, you can:**
- Switch back to Option 1 for speed
- Or keep Option 2 as default safety net

**The 0.5 seconds of extra time is worth the peace of mind after what you just went through.**

---

## Bottom Line

| Factor | Option 1 (No E2E) | Option 2 (With E2E) |
|--------|-------------------|---------------------|
| **Speed** | 0.34s | 0.87s |
| **Catches logic bugs** | ✅ Yes | ✅ Yes |
| **Catches integration bugs** | ❌ No | ✅ Yes |
| **Would catch v2.2 bugs** | ❌ No | ✅ Yes |
| **Works offline** | ✅ Yes | ⚠️ After first run |
| **Requires DB** | ❌ No | ✅ Yes |
| **After refactoring hell** | ❌ Risky | ✅ **RECOMMENDED** |

**Your quote: "the last 2 days was a hell after the v2.2 refactoring"**

**My response: Enable Option 2. The 0.5 seconds is worth avoiding another 2 days of hell.**

---

**Last Updated: 2026-01-18**
