# Manifest Lifecycle

**Created:** 2026-01-11 UTC
**Purpose:** Manifest states from Draft to Archived

---

## Manifest State Machine

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         Manifest Lifecycle States                           │
└─────────────────────────────────────────────────────────────────────────────┘

                              ┌──────────────┐
                              │  NHS URL     │
                              │  (External)  │
                              └──────┬───────┘
                                     │ url_to_manifest.py
                                     ▼
                    ┌───────────────────────────────────-─┐
                    │              DRAFT                  │
                    │   {source}_draft.yaml               │
                    │                                     │
                    │   • Raw extracted structure         │
                    │   • Auto-generated column names     │
                    │   • No semantic metadata            │
                    │   • Type inference complete         │
                    └────────────────┬───────────────────┘
                                     │
                      ┌──────────────┴──────────────┐
                      │                             │
              (First period)               (Subsequent period)
                      │                             │
                      ▼                             ▼
    ┌─────────────────────────────┐   ┌─────────────────────────────┐
    │         ENRICHED            │   │        CANONICAL            │
    │ {source}_{period}_enriched  │   │ {source}_{period}_canonical │
    │ .yaml                       │   │ .yaml                       │
    │                             │   │                             │
    │ • LLM-generated names       │   │ • Reference-matched names   │
    │ • Semantic column codes     │   │ • Consistent with ref       │
    │ • Description & metadata    │   │ • No LLM call needed        │
    │ • Becomes reference for     │   │ • Cross-period compatible   │
    │   future periods            │   │                             │
    └───────────────┬─────────────┘   └───────────────┬─────────────┘
                    │                                 │
                    └─────────────┬───────────────────┘
                                  │ datawarp load-batch
                                  ▼
                    ┌────────────────────────────────────┐
                    │             LOADED                 │
                    │                                    │
                    │   • Data in PostgreSQL             │
                    │   • Load history recorded          │
                    │   • Can be re-loaded (append)      │
                    └────────────────┬───────────────────┘
                                     │ (manual move after verification)
                                     ▼
                    ┌────────────────────────────────────┐
                    │            ARCHIVED                │
                    │   manifests/archive/{pub}/         │
                    │                                    │
                    │   • Historical reference           │
                    │   • No longer active               │
                    │   • Used for audit/debugging       │
                    └────────────────────────────────────┘
```

---

## First Period vs Subsequent Period

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         First Period (New Publication)                      │
└─────────────────────────────────────────────────────────────────────────────┘

NHS ADHD August 2025 (First time loading ADHD data)

Step 1: Generate Draft                    Step 2: Enrich (LLM)
┌─────────────────────────┐              ┌─────────────────────────┐
│ python scripts/         │              │ python scripts/         │
│   url_to_manifest.py    │     ───▶     │   enrich_manifest.py    │
│   <url>                 │              │   adhd_aug25.yaml       │
│   adhd_aug25.yaml       │              │   adhd_aug25_enriched   │
└─────────────────────────┘              │   .yaml                 │
                                         │                         │
                                         │   ← NO --reference flag │
                                         └─────────────────────────┘
                                                    │
                                                    ▼
                                         ┌─────────────────────────┐
                                         │ Gemini API Call         │
                                         │                         │
                                         │ Input: Raw columns      │
                                         │   Column1, Column2...   │
                                         │                         │
                                         │ Output: Semantic names  │
                                         │   patient_count,        │
                                         │   reporting_period...   │
                                         └─────────────────────────┘

Result: adhd_aug25_enriched.yaml
        ↓
        This becomes the REFERENCE for all future ADHD periods


┌─────────────────────────────────────────────────────────────────────────────┐
│                     Subsequent Period (With Reference)                      │
└─────────────────────────────────────────────────────────────────────────────┘

NHS ADHD November 2025 (Second period, use August as reference)

Step 1: Generate Draft                    Step 2: Enrich (Reference)
┌─────────────────────────┐              ┌─────────────────────────────────────┐
│ python scripts/         │              │ python scripts/enrich_manifest.py   │
│   url_to_manifest.py    │     ───▶     │   adhd_nov25.yaml                   │
│   <url>                 │              │   adhd_nov25_canonical.yaml         │
│   adhd_nov25.yaml       │              │   --reference adhd_aug25_enriched   │
└─────────────────────────┘              │                                     │
                                         │   ← Uses --reference flag           │
                                         └─────────────────────────────────────┘
                                                    │
                                                    ▼
                                         ┌─────────────────────────┐
                                         │ Reference Matching      │
                                         │                         │
                                         │ Nov columns matched to  │
                                         │ Aug enriched columns    │
                                         │                         │
                                         │ NO LLM call needed      │
                                         │ (82.5% cost savings)    │
                                         └─────────────────────────┘

Result: adhd_nov25_canonical.yaml
        ↓
        Uses same codes as aug25 → Data consolidates in same table
```

---

## Naming Conventions

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          Manifest Naming Pattern                            │
└─────────────────────────────────────────────────────────────────────────────┘

Publication: ADHD
Period: August 2025

┌────────────────────────────────────────────────────────────────────────────┐
│                                                                            │
│  Draft:     adhd_aug25.yaml                                                │
│             └──┬──┘└─┬─┘                                                   │
│                │     └── Period code (mon + 2-digit year)                  │
│                └── Publication code                                        │
│                                                                            │
│  Enriched:  adhd_aug25_enriched.yaml    ← First period (LLM)               │
│                        └───────┘                                           │
│                        State suffix                                        │
│                                                                            │
│  Canonical: adhd_nov25_canonical.yaml   ← Subsequent (reference-based)     │
│                        └────────┘                                          │
│                        State suffix                                        │
│                                                                            │
└────────────────────────────────────────────────────────────────────────────┘

Period Codes:
┌───────────┬─────────┬───────────┬─────────┐
│ Period    │ Code    │ Period    │ Code    │
├───────────┼─────────┼───────────┼─────────┤
│ Jan 2025  │ jan25   │ Jul 2025  │ jul25   │
│ Feb 2025  │ feb25   │ Aug 2025  │ aug25   │
│ Mar 2025  │ mar25   │ Sep 2025  │ sep25   │
│ Apr 2025  │ apr25   │ Oct 2025  │ oct25   │
│ May 2025  │ may25   │ Nov 2025  │ nov25   │
│ Jun 2025  │ jun25   │ Dec 2025  │ dec25   │
└───────────┴─────────┴───────────┴─────────┘
```

---

## Directory Organization (Proposed)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     Proposed Manifest Directory Structure                   │
└─────────────────────────────────────────────────────────────────────────────┘

manifests/
├── active/                           ← Ready to load (current batch)
│   ├── adhd/
│   │   └── adhd_jan26_canonical.yaml
│   └── pcn/
│       └── pcn_dec25_canonical.yaml
│
├── pending/                          ← Being enriched (WIP)
│   └── gp_practice/
│       └── gp_feb26.yaml             ← Draft, not enriched yet
│
├── reference/                        ← First-period templates
│   ├── adhd_aug25_enriched.yaml      ← Reference for all ADHD
│   ├── pcn_mar25_enriched.yaml       ← Reference for all PCN
│   └── gp_apr25_enriched.yaml        ← Reference for all GP
│
├── archive/                          ← Already loaded
│   ├── adhd/
│   │   ├── adhd_aug25_enriched.yaml
│   │   ├── adhd_nov25_canonical.yaml
│   │   └── adhd_dec25_canonical.yaml
│   └── pcn/
│       ├── pcn_mar25_enriched.yaml
│       └── pcn_apr25_canonical.yaml
│
└── e2e_test/                         ← Testing manifests
    └── ...


Current State (Flat):
┌─────────────────────────────────────────────────────────────────────────────┐
│ manifests/                                                                  │
│ ├── adhd_aug25.yaml                  ← Mixed states                         │
│ ├── adhd_aug25_enriched.yaml         ← Which is current?                    │
│ ├── adhd_nov25.yaml                  ← Draft or loaded?                     │
│ ├── adhd_nov25_canonical.yaml        ← Active or archive?                   │
│ ├── pcn_workforce_may25.yaml         ← No clear organization                │
│ ├── ...                              ← 100+ files in same folder            │
│ └── e2e_test/                                                               │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Manifest Content Structure

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         Manifest YAML Structure                             │
└─────────────────────────────────────────────────────────────────────────────┘

Draft Manifest:
┌────────────────────────────────────────────────────────────────────────────-─┐
│ file_url: https://files.digital.nhs.uk/.../adhd-aug25.xlsx                   │
│ downloaded_at: 2026-01-10T10:30:00Z                                          │
│                                                                              │
│ sheets:                                                                      │
│   - name: "Summary"                                                          │
│     classification: TABULAR                                                  │
│     header_row: 2                                                            │
│     data_start_row: 3                                                        │
│     data_end_row: 8151                                                       │
│     columns:                                                                 │
│       - name: "Column A"                 ← Auto-detected names               │
│         original_header: "Age Band"                                          │
│         inferred_type: VARCHAR                                               │
│       - name: "Column B"                                                     │
│         original_header: "Count"                                             │
│         inferred_type: INTEGER                                               │
└────────────────────────────────────────────────────────────────────────────-─┘

Enriched Manifest:
┌─────────────────────────────────────────────────────────────────────────────┐
│ file_url: https://files.digital.nhs.uk/.../adhd-aug25.xlsx                  │
│ downloaded_at: 2026-01-10T10:30:00Z                                         │
│ enriched_at: 2026-01-10T10:35:00Z         ← Enrichment timestamp            │
│ enrichment_method: gemini-2.5-flash-lite  ← LLM used                        │
│                                                                             │
│ sources:                                                                    │
   - code: adhd_prevalence_estimate        ← Semantic source code             │
│     description: "ADHD prevalence estimates by age group and region"        │
│     sheet: "Summary"                                                        │
│     columns:                                                                │
│       - code: age_band                    ← LLM-generated column codes      │
│         original: "Age Band"                                                │
│         type: VARCHAR                                                       │
│         description: "Age group classification"                             │
│       - code: patient_count                                                 │
│         original: "Count"                                                   │
│         type: INTEGER                                                       │
│         description: "Number of patients with ADHD diagnosis"               │
└─────────────────────────────────────────────────────────────────────────────┘

Canonical Manifest (Reference-based):
┌─────────────────────────────────────────────────────────────────────────────┐
│ file_url: https://files.digital.nhs.uk/.../adhd-nov25.xlsx                   │
│ downloaded_at: 2026-01-10T12:00:00Z                                          │
│ canonicalized_at: 2026-01-10T12:01:00Z    ← No LLM call                     │
│ reference_manifest: adhd_aug25_enriched.yaml                                 │
│                                                                              │
│ sources:                                                                     │
│   - code: adhd_prevalence_estimate        ← Same code as reference          │
│     description: "ADHD prevalence estimates by age group and region"        │
│     columns:                              ← Matched from reference          │
│       - code: age_band                                                       │
│       - code: patient_count                                                  │
│       - code: regional_breakdown          ← New column (auto-added)          │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Workflow Commands

```bash
# ══════════════════════════════════════════════════════════════════════════════
# First Period Workflow (ADHD August 2025)
# ══════════════════════════════════════════════════════════════════════════════

# Step 1: Generate draft manifest
python scripts/url_to_manifest.py \
  "https://files.digital.nhs.uk/adhd-data-aug25.xlsx" \
  manifests/pending/adhd/adhd_aug25.yaml

# Step 2: Enrich with LLM (NO --reference)
python scripts/enrich_manifest.py \
  manifests/pending/adhd/adhd_aug25.yaml \
  manifests/active/adhd/adhd_aug25_enriched.yaml

# Step 3: Load to database
datawarp load-batch manifests/active/adhd/adhd_aug25_enriched.yaml

# Step 4: Archive after successful load
mv manifests/active/adhd/adhd_aug25_enriched.yaml manifests/archive/adhd/
cp manifests/archive/adhd/adhd_aug25_enriched.yaml manifests/reference/

# ══════════════════════════════════════════════════════════════════════════════
# Subsequent Period Workflow (ADHD November 2025)
# ══════════════════════════════════════════════════════════════════════════════

# Step 1: Generate draft manifest
python scripts/url_to_manifest.py \
  "https://files.digital.nhs.uk/adhd-data-nov25.xlsx" \
  manifests/pending/adhd/adhd_nov25.yaml

# Step 2: Enrich with reference (USE --reference)
python scripts/enrich_manifest.py \
  manifests/pending/adhd/adhd_nov25.yaml \
  manifests/active/adhd/adhd_nov25_canonical.yaml \
  --reference manifests/reference/adhd_aug25_enriched.yaml

# Step 3: Load to database
datawarp load-batch manifests/active/adhd/adhd_nov25_canonical.yaml

# Step 4: Archive after successful load
mv manifests/active/adhd/adhd_nov25_canonical.yaml manifests/archive/adhd/
```

---

## Validation Gates

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        Validation Between States                             │
└─────────────────────────────────────────────────────────────────────────────┘

DRAFT → ENRICHED
┌───────────────────────────────────────────────────────────────────────────┐
│ Gate: Validate manifest structure                                          │
│                                                                            │
│ python scripts/validate_manifest.py manifests/pending/adhd/adhd_aug25.yaml │
│                                                                            │
│ Checks:                                                                    │
│   ✓ YAML is valid                                                          │
│   ✓ file_url exists                                                        │
│   ✓ At least one sheet with columns                                        │
│   ✓ Column types are valid                                                 │
└───────────────────────────────────────────────────────────────────────────┘

ENRICHED → LOADED
┌───────────────────────────────────────────────────────────────────────────┐
│ Gate: Validate enriched manifest                                           │
│                                                                            │
│ python scripts/validate_manifest.py adhd_aug25_enriched.yaml --strict      │
│                                                                            │
│ Checks:                                                                    │
│   ✓ All columns have semantic codes                                        │
│   ✓ Source codes are unique                                                │
│   ✓ Descriptions present                                                   │
│   ✓ No duplicate column codes                                              │
└───────────────────────────────────────────────────────────────────────────┘

LOADED → ARCHIVED
┌───────────────────────────────────────────────────────────────────────────┐
│ Gate: Validate loaded data                                                 │
│                                                                            │
│ python scripts/validate_loaded_data.py adhd_prevalence_estimate            │
│                                                                            │
│ Checks:                                                                    │
│   ✓ Table exists in staging schema                                         │
│   ✓ Row count > 0                                                          │
│   ✓ Load history record exists                                             │
│   ✓ No load errors                                                         │
└───────────────────────────────────────────────────────────────────────────┘
```

---

*See CLAUDE.md "Canonical Workflow Decision Tree" for complete workflow guidance.*
