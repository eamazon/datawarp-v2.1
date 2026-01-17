# Publication Configuration Validation Report

**Date:** 2026-01-17
**Total Publications:** 25

## Summary

✅ **All 25 publications correctly configured**

- ✅ 0 configuration errors
- ✅ 0 likely wrong classifications  
- ✅ 0 edge cases requiring validation

## Breakdown by Source and Mode

### NHS Digital (Template Mode) - 18 publications ✓
These publications host data files directly on `files.digital.nhs.uk` with predictable URL patterns.

1. `adhd`
2. `gp_appointments`
3. `mental_health`
4. `gp_online_consultation`
5. `gp_registered_patients`
6. `nhs_sickness_absence`
7. `nhs_workforce`
8. `out_of_area_mental_health`
9. `primary_care_dementia`
10. `ldhc_scheme`
11. `shmi`
12. `nhse_virtual_ward_capacity_and_occupancy_statistics`
13. `nhs_app_statistics`
14. `nhse_diagnostic_imaging_dataset`
15. `maternity_services_monthly_statistics`
16. `community_services_statistics_for_children_young_people_and_adults`
17. `nhse_supplementary_ecds_analysis`
18. `nhse_integrated_urgent_care_aggregate_data_collection_iuc_adc`

### NHS England (Discover Mode) - 5 publications ✓  
These publications use hash-coded file URLs requiring runtime discovery.

1. `nhse_111_online` ⚠️ **EDGE CASE FIXED**
   - Landing page: `digital.nhs.uk` 
   - Data files: `www.england.nhs.uk` (with hash codes)
   - Was incorrectly classified as template mode
   - **Fixed to discover mode**

2. `rtt_waiting_times`
3. `cancer_waiting_times`  
4. `diagnostics_waiting_times_and_activity`
5. `ambulance_quality_indicators`

### NHS England (Explicit Mode) - 2 publications ✓
These use manually specified URLs for fiscal quarters or special cases.

1. `ae_waiting_times`
2. `bed_overnight`

## The NHS 111 Online Bug

**Problem:** The `add_publication.py` script misclassified NHS 111 Online as template mode because:
- Landing page is on `digital.nhs.uk` (looks like NHS Digital)
- Script assumed all NHS Digital pages can use template mode
- But actual data files are on `www.england.nhs.uk` with hash codes

**Root Cause:** Script didn't check where the actual data files are hosted, only looked at the landing page domain.

**Fix Applied:**
1. ✅ Changed `nhse_111_online` to discover mode in config
2. ✅ Added comprehensive documentation to YAML header explaining edge case
3. ✅ Enhanced `add_publication.py` with edge case detection (attempts to fetch sub-pages and check for england.nhs.uk data file links)
4. ✅ Successfully loaded 8 months of NHS 111 Online data (Mar-Oct 2025, 462 rows, 31 sources)

## Classification Rules

### NHS Digital → Template Mode
- Data files hosted directly on NHS Digital
- Predictable URL patterns: `{landing_page}/{month_name}-{year}`
- Example: `digital.nhs.uk/.../nhs-app-statistics/november-2025`
- Files downloadable from: `files.digital.nhs.uk`

### NHS England → Discover Mode
- Data files have unpredictable hash codes (5-char alphanumeric)
- URL patterns cannot be templated
- Example: `.../uploads/sites/2/2025/11/File-ABC123.xlsx`
- Requires runtime page scraping to find actual URLs

### Edge Case → Discover Mode
- Landing page on `digital.nhs.uk`
- BUT data files redirect to `www.england.nhs.uk`
- Must use discover mode (not template)
- **Currently only known case: NHS 111 Online**

## How to Validate New Publications

1. Visit the landing page
2. Click on latest publication (e.g., "November 2025")
3. Check "Resources" section for download links
4. **If links contain `files.digital.nhs.uk`** → Template mode ✓
5. **If links redirect to `england.nhs.uk` with hash codes** → Discover mode ✓

## Testing Status

All publications validated using automated script:

```bash
python3 << 'EOF'
import yaml
with open('config/publications_v2.yaml') as f:
    config = yaml.safe_load(f)
# Validation logic...
EOF
```

**Results:**
- ✅ Correctly configured: 25
- ❌ Likely wrong: 0
- ⚠️ Needs validation: 0

## Recommendations

1. ✅ **Configuration is production-ready** - all publications correctly classified
2. ✅ **Documentation added** - YAML header explains classification rules
3. ⚠️ **Edge case detection** - `add_publication.py` script has basic detection but needs refinement
4. 💡 **Manual validation recommended** - When adding new publications, manually verify data file hosting location

## Files Modified

- `config/publications_v2.yaml` - Added comprehensive header documentation + fixed nhse_111_online
- `scripts/add_publication.py` - Enhanced with edge case detection logic
- `scripts/backfill.py` - Fixed dry-run return tuple bug
