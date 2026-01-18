# Git Hooks Guide - Pre-Commit and Pre-Push

**Created: 2026-01-18**
**Purpose: Explain the two-layer git hook protection system**

---

## TL;DR

**Pre-commit hook (0.42s):** Fast health check on every commit
**Pre-push hook (11s):** Real E2E pipeline validation before pushing to main

This gives you speed for frequent commits, and safety for important pushes.

---

## The Two-Layer Defense

### Layer 1: Pre-Commit Hook (Fast - 0.42s)

**When it runs:** Every `git commit`
**What it does:** Health check mode
**Time:** 0.42 seconds

**What it checks:**
- ✅ Database connectivity works
- ✅ ADHD data exists in database
- ✅ Metadata exists in database
- ✅ Core imports work
- ✅ Field mapping logic correct
- ✅ All unit tests pass

**What it DOESN'T do:**
- ❌ Actually download files
- ❌ Actually run enrichment
- ❌ Actually load new data

**Why:** Fast enough to not annoy you during development

---

### Layer 2: Pre-Push Hook (Real E2E - 11s)

**When it runs:** `git push origin main` (only when pushing to main)
**What it does:** REAL pipeline execution with FORCE_E2E=1
**Time:** ~11 seconds

**What it does:**
```
🚀 ADHD Real Pipeline Test (10.79s):
  ✅ Downloads actual NHS file
  ✅ Runs enrichment (reference-based)
  ✅ Loads to database
  ✅ Verifies metadata stored
  ✅ Checks data loaded

📋 Quick Smoke Tests (0.33s):
  ✅ 6 E2E state tests
  ✅ 6 unit logic tests
```

**What it catches:**
- ✅ enricher.py bugs (like v2.2 preview stripping)
- ✅ repository.py bugs (like v2.2 field mapping)
- ✅ Integration between components
- ✅ Database operations
- ✅ File parsing issues

**Why:** Catches integration bugs BEFORE they reach main branch

---

## Workflow Examples

### Normal Development (Fast)

```bash
# Make changes
vim src/datawarp/pipeline/enricher.py

# Commit (0.42s health check)
git add .
git commit -m "refactor: improve enrichment logic"

🏥 Health check mode: Verifying system state (~0.5 seconds)...
✅ All smoke tests passed
[main abc123] refactor: improve enrichment logic

# Push to feature branch (skipped)
git push origin feature/improve-enrichment

📤 Pushing to non-main branch - skipping E2E test
✅ Push successful
```

**Total time:** 0.42s for commit, instant for push

---

### Pushing to Main (Real E2E)

```bash
# Ready to merge to main
git checkout main
git merge feature/improve-enrichment

# Push to main (11s real E2E)
git push origin main

🚨 PUSHING TO MAIN - Running REAL E2E validation...

🚀 ADHD Real Pipeline Test:
  ✅ 1 passed in 10.79s

📋 Quick Smoke Tests:
  ✅ 12 passed in 0.33s

✅ All tests passed - push allowed

Pipeline validated:
  ✅ Real E2E execution (10.79s)
  ✅ State validation (0.33s)
  ✅ Logic validation (0.01s)
```

**Total time:** ~11 seconds - validates entire pipeline

---

### If Tests Fail

**Pre-commit failure:**
```bash
git commit -m "changes"

❌ COMMIT BLOCKED: Smoke tests failed

tests/test_smoke_unit.py::test_field_mapping_all_variants FAILED

Fix the issue, try again
```

**Pre-push failure:**
```bash
git push origin main

🚨 PUSHING TO MAIN - Running REAL E2E validation...

🚀 ADHD Real Pipeline Test:
  ❌ FAILED: No metadata stored!

❌ PUSH BLOCKED: Real E2E pipeline test failed

The actual pipeline is broken! This would break production.
Fix the issues above before pushing to main.
```

**What to do:**
1. Fix the issue locally
2. Commit the fix
3. Try pushing again

---

## Bypass Options (Use Carefully)

### Skip Pre-Commit (Emergency Only)

```bash
git commit --no-verify -m "emergency: fix broken tests"
```

**When to use:**
- Fixing the tests themselves
- Emergency hotfix (with manual verification)
- Documentation-only changes

**Warning:** Skips ALL validation, commit may be broken

---

### Skip Pre-Push (VERY Rare)

```bash
git push --no-verify origin main
```

**When to use:**
- CI/CD is down and you need to push urgently
- You've manually verified everything works
- Emergency production fix

**Warning:** Skips pipeline validation, may break production

---

### Skip Just E2E Smoke Test

```bash
SKIP_E2E_SMOKE=1 git push origin main
```

**When to use:**
- Database is down but you need to push
- You've run tests manually separately

**Note:** Still runs other smoke tests

---

## Configuration

### Enable/Disable Health Check in Pre-Commit

**Current default:** Health check mode (0.42s)

**To enable real E2E in pre-commit (not recommended):**
```bash
bash scripts/toggle_e2e_hook.sh enable
```

**To disable (back to health check):**
```bash
bash scripts/toggle_e2e_hook.sh disable
```

---

### Modify Pre-Push Behavior

**Current default:** Only runs when pushing to main

**To run E2E on ALL pushes:**
Edit `.git/hooks/pre-push`, remove this section:
```bash
if [ -z "$PUSHING_TO_MAIN" ]; then
    echo "📤 Pushing to non-main branch - skipping E2E test"
    exit 0
fi
```

**To increase timeout:**
Edit `tests/test_smoke_adhd_e2e.py`, change:
```python
timeout=60,  # Increase to 120 if needed
```

---

## Troubleshooting

### "Pre-push hook failed: command not found: pytest"

**Cause:** Virtual environment not activated in hook
**Fix:** The hook should auto-activate .venv, but if it doesn't:

```bash
# Edit .git/hooks/pre-push
# Add explicit path to pytest
/Users/speddi/projectx/datawarp-v2.1/.venv/bin/pytest tests/...
```

---

### "ADHD E2E test timeout after 60 seconds"

**Cause:** Network slow, database slow, or actual bug
**Fix:**

1. Check database is running:
   ```bash
   psql -d databot_dev -c "SELECT 1"
   ```

2. Try manually:
   ```bash
   FORCE_E2E=1 pytest tests/test_smoke_adhd_e2e.py -v
   ```

3. If consistently slow, increase timeout in test

---

### "Tests pass locally but fail in hook"

**Cause:** Different environment (PATH, working directory, etc.)
**Debug:**

```bash
# Run hook manually to see full output
bash -x .git/hooks/pre-push origin https://github.com/test/repo.git < /dev/stdin <<EOF
refs/heads/main abc123 refs/heads/main def456
EOF
```

---

## Performance

### Pre-Commit Hook Breakdown

```
E2E State Tests:  0.33s (6 tests)
Unit Logic Tests: 0.01s (6 tests)
Hook overhead:    0.08s
─────────────────────────────
Total:           ~0.42s
```

### Pre-Push Hook Breakdown

```
ADHD Real E2E:    10.79s (actual pipeline)
E2E State Tests:   0.33s (6 tests)
Unit Logic Tests:  0.01s (6 tests)
Hook overhead:     0.05s
─────────────────────────────
Total:            ~11.18s
```

---

## When Each Hook Runs

| Git Command | Pre-Commit | Pre-Push | Total Time |
|-------------|------------|----------|------------|
| `git commit -m "msg"` | ✅ 0.42s | - | 0.42s |
| `git push origin feature-branch` | - | ⏭️ Skipped | ~0s |
| `git push origin main` | - | ✅ 11s | 11s |
| `git commit -m "msg" && git push origin main` | ✅ 0.42s | ✅ 11s | 11.42s |

---

## What Would Have Been Caught

### v2.2 Refactoring Hell Bugs

**Bug 1: enricher.py preview stripping**
- Pre-commit: ❌ Would NOT catch (health check only)
- Pre-push: ✅ Would catch (runs actual enrichment)

**Bug 2: enricher.py LLM prompt missing fields**
- Pre-commit: ❌ Would NOT catch
- Pre-push: ✅ Would catch (verifies all 7 fields exist)

**Bug 3: repository.py field mapping**
- Pre-commit: ✅ Would catch (unit test validates field mapping)
- Pre-push: ✅ Would catch (E2E verifies metadata stored)

**Result:** Pre-push hook would have caught all 3 bugs in 11 seconds instead of discovering them 6 days later.

---

## Best Practices

### DO:
- ✅ Commit frequently (pre-commit is fast)
- ✅ Push to feature branches often (E2E skipped)
- ✅ Let pre-push hook run when pushing to main
- ✅ Fix issues when hook fails (don't bypass)
- ✅ Use `--no-verify` only for emergencies

### DON'T:
- ❌ Bypass hooks regularly (defeats the purpose)
- ❌ Get annoyed by 11-second pre-push (it's catching bugs!)
- ❌ Push directly to main without letting hook run
- ❌ Commit broken code and rely on hook to catch it

---

## Installation

### First-Time Setup

```bash
# Install pre-commit and pre-push hooks
bash scripts/setup_hooks.sh

# Verify pre-commit works
git commit --allow-empty -m "test pre-commit"

# Verify pre-push works (simulate pushing to main)
echo "refs/heads/main abc123 refs/heads/main def456" | \
  bash .git/hooks/pre-push origin test
```

### For Team Members

When someone clones the repo, they need to run:

```bash
bash scripts/setup_hooks.sh
```

This installs both hooks automatically.

---

## Philosophy

### Why Two Layers?

**Pre-commit (fast):**
- Catches obvious mistakes immediately
- Prevents broken code from entering local history
- Fast enough to not disrupt flow

**Pre-push (comprehensive):**
- Catches integration bugs before they reach remote
- Prevents broken code from entering main branch
- Slow but only runs when pushing to main

### Industry Standard

This is the standard pattern:
- Google: Pre-commit (fast), pre-submit (comprehensive)
- Meta: Pre-commit (lint/format), pre-push (tests)
- Netflix: Pre-commit (quick), pre-push (integration)

**Our version:**
- Pre-commit: Health check (0.42s)
- Pre-push: Real E2E (11s)
- CI/CD: Full suite (15 min)

---

## Summary

**You asked:** "how do i run this real e2e before pushing to main (can that be an hook)"

**Answer:** ✅ Yes! Pre-push hook now runs REAL E2E (11s) automatically when you `git push origin main`

**Your workflow:**
1. Commit often: Fast health check (0.42s)
2. Push to feature branches: Skipped
3. Push to main: Real E2E validation (11s)

**Result:** Speed during development, safety before production.

---

**Last Updated: 2026-01-18**
