# Quick Start: NHS Data Pipeline with Gemini Monitoring

**For beginners - explained in simple terms**

---

## What Does This System Do?

Think of it like this:

```
NHS Website  →  Download Files  →  Read Tables  →  Save to Database  →  Monitor Quality
     ↓              ↓                  ↓                ↓                    ↓
   URLs        Excel/CSV         Find columns    PostgreSQL          Gemini checks
```

**The Goal:** Automatically grab NHS data, put it in a database, and have Gemini watch for problems.

---

## Option 1: Test with ONE URL (Recommended for beginners)

This is the **easiest way** to see how everything works.

### Step 1: Run the test script

```bash
python scripts/test_single_url.py
```

**What happens:**
- Downloads ONE NHS file (ADHD December 2025)
- Extracts all the tables and columns
- Uses Gemini to create smart names
- Loads data into PostgreSQL
- Uses Gemini to check: "Does this look right?"

**Time:** ~3 minutes
**Cost:** ~$0.01 (one penny for Gemini API calls)

The script will **pause at each step** and explain what's happening. Just press ENTER to continue.

---

## Option 2: Test with publications.yaml (More automated)

Once you understand Option 1, try this.

### Step 1: Look at the test config

```bash
cat config/publications_test.yaml
```

You'll see:
```yaml
publications:
  adhd:
    name: "ADHD Management Information"
    urls:
      - period: dec25
        url: https://digital.nhs.uk/.../december-2025
```

This is your **shopping list** of NHS URLs to process.

### Step 2: Process all URLs in the list

```bash
python scripts/backfill.py --config config/publications_test.yaml
```

**What happens:**
- Reads `publications_test.yaml`
- For each URL:
  - Downloads file
  - Extracts structure
  - Enriches with Gemini
  - Loads to PostgreSQL
  - Saves state (so it doesn't re-process)

**First time:** Takes ~5 minutes for 1 URL
**Second time:** Skips already-processed URLs (instant)

---

## How Gemini Monitoring Works

### What Gemini Watches For

After each file loads, Gemini checks:

1. **Critical Problems (alerts you immediately):**
   - ❌ 0 rows loaded (extraction failed)
   - ❌ Rows way below expected (e.g., 100 rows instead of 100,000)

2. **Warnings (might need checking):**
   - ⚠️ Connection timeouts (network issues)
   - ⚠️ Suspicious row counts (much lower than usual)

3. **Normal (no action needed):**
   - ✅ Row count looks reasonable
   - ✅ No errors

### Gemini's Output

```json
{
  "status": "normal",
  "action": "none",
  "reason": "Loaded 45,234 rows, within expected range of 40k-50k"
}
```

**In plain English:** "Everything looks fine, don't worry!"

---

## Understanding the Flow

### What Each Script Does

1. **`url_to_manifest.py`** - The Explorer
   - Visits NHS website
   - Finds all Excel/CSV files
   - Downloads them
   - Detects tables and columns
   - Saves to `.yaml` file

2. **`enrich_manifest.py`** - The Name-Giver
   - Reads `.yaml` file
   - Uses Gemini to create smart names
   - Instead of "Sheet1" → "adhd_summary_referrals_by_age"
   - Saves enriched `.yaml` file

3. **`datawarp load-batch`** - The Loader
   - Reads enriched `.yaml` file
   - Creates PostgreSQL tables
   - Loads all rows
   - Tracks what was loaded

4. **`monitor.py`** (we'll build this next) - The Watcher
   - Reads load history from database
   - Uses Gemini to check: "Normal or broken?"
   - Sends alerts if something is wrong

### Where Files Go

```
manifests/
  test/
    adhd_dec25.yaml              ← Raw structure (from url_to_manifest)
    adhd_dec25_enriched.yaml     ← Smart names (from enrich_manifest)

staging.*                        ← PostgreSQL tables (your data lives here)

datawarp.tbl_load_history        ← Tracking table (what was loaded when)
```

---

## Adding More URLs

### Easy Way: Edit publications_test.yaml

Open `config/publications_test.yaml` and add more URLs:

```yaml
publications:
  adhd:
    urls:
      - period: dec25
        url: https://digital.nhs.uk/.../december-2025
      - period: nov25  # ← ADD THIS
        url: https://digital.nhs.uk/.../november-2025  # ← AND THIS
```

Then run:
```bash
python scripts/backfill.py --config config/publications_test.yaml
```

It will **only process the new URL** (skips December since it's already done).

---

## Costs (Gemini API)

**Per file:**
- Enrichment (naming): ~$0.003 (less than a penny)
- Monitoring check: ~$0.00006 (tiny)

**Monthly (50 files/month):**
- Enrichment: ~$0.15
- Monitoring: ~$0.09
- **Total: ~$0.24/month** (less than a coffee)

---

## Common Questions

### "What if it breaks?"

The script saves state after each file. If it crashes:
1. Fix the problem
2. Run the script again
3. It will **skip already-processed files** and continue where it left off

### "How do I see what's in the database?"

```bash
psql -h localhost -U databot -d datawarp2
```

Then:
```sql
-- See all tables
\dt staging.*;

-- See data in a table
SELECT * FROM staging.adhd_summary_referrals_age LIMIT 10;
```

### "How do I know if monitoring is working?"

Run the test script:
```bash
python scripts/test_monitor_gemini.py
```

It will show you:
- ✅ What Gemini detects
- 💰 How much it costs
- 📊 Accuracy rate

### "Can I use a different LLM?"

Yes! You tested:
- **Gemini:** Best accuracy (60%), cheapest ($0.09/month) ← **Recommended**
- **Claude Haiku:** Lower accuracy (40%), more expensive ($0.61/month)
- **Qwen (local):** FREE but slower, good for simple checks

---

## Next Steps

1. **Run Option 1** (`test_single_url.py`) to understand the flow
2. **Add 2-3 more URLs** to `publications_test.yaml`
3. **Run backfill** to process them
4. **Set up monitoring** (we'll build `monitor.py` next)
5. **Automate with cron** (runs daily, checks for new files)

---

## Need Help?

- **Read the code:** It's well-commented and simple
- **Check docs:** `docs/README.md` has more details
- **Ask questions:** I'm here to help!

**Remember:** Start small (1 URL), understand it, then scale up.
