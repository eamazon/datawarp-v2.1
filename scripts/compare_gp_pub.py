# Compare resources between July and August GP Practice publications
july_resources = [
    ("gp-reg-pat-prac-all.zip", "74 KB", "Totals (GP practice-all persons)"),
    ("gp-reg-pat-prac-sing-age-regions.zip", "1 MB", "Single year of age (Regions-ICBs-SICBLs-PCNs)"),
    ("gp-reg-pat-prac-sing-age-female.zip", "3 MB", "Single year of age (GP practice-females)"),
    ("gp-reg-pat-prac-sing-age-male.zip", "3 MB", "Single year of age (GP practice-males)"),
    ("gp-reg-pat-prac-quin-age.zip", "2 MB", "5-year age groups"),
    ("gp-reg-pat-prac-lsoa-2021-male-female-July-25.zip", "14 MB", "LSOA 2021"),  # QUARTERLY
    ("gp-reg-pat-prac-lsoa-2011-male-female-July-25.zip", "14 MB", "LSOA 2011"),  # QUARTERLY
    ("gp-reg-pat-prac-map.csv", "1 MB", "Mapping CSV"),
    ("Pre-Release Access List.pdf", "96 KB", "Pre-Release Access List"),
]

august_resources = [
    ("gp-reg-pat-prac-all.zip", "74 KB", "Totals (GP practice-all persons)"),
    ("gp-reg-pat-prac-sing-age-regions.zip", "1 MB", "Single year of age (Regions-ICBs-SICBLs-PCNs)"),
    ("gp-reg-pat-prac-sing-age-female.zip", "3 MB", "Single year of age (GP practice-females)"),
    ("gp-reg-pat-prac-sing-age-male.zip", "3 MB", "Single year of age (GP practice-males)"),
    ("gp-reg-pat-prac-quin-age.zip", "2 MB", "5-year age groups"),
    # NO LSOA FILES - Not a quarterly month
    ("gp-reg-pat-prac-map.zip", "131 KB", "Mapping ZIP (not CSV!)"),  # NOTE: Different format!
    ("Pre-Release Access List.pdf", "95 KB", "Pre-Release Access List"),
]

print("=" * 80)
print("GP PRACTICE PUBLICATION: JULY vs AUGUST 2025")
print("=" * 80)

print("\n📊 JULY 2025 (Quarterly month - includes LSOA):")
for f, size, desc in july_resources:
    print(f"  • {f:<50} {size:>6}  {desc}")

print(f"\n  Total files: {len(july_resources)}")

print("\n📊 AUGUST 2025 (Non-quarterly month):")
for f, size, desc in august_resources:
    print(f"  • {f:<50} {size:>6}  {desc}")
    
print(f"\n  Total files: {len(august_resources)}")

print("\n" + "=" * 80)
print("KEY DIFFERENCES:")
print("=" * 80)
print("""
1. LSOA FILES: Only in quarterly months (Jan, Apr, Jul, Oct)
   - July has 2 LSOA files (14 MB each for 2011 and 2021)
   - August has 0 LSOA files

2. MAPPING FILE FORMAT CHANGED:
   - July: gp-reg-pat-prac-map.csv (1 MB - direct CSV)
   - August: gp-reg-pat-prac-map.zip (131 KB - zipped!)
   
3. FILE COUNTS: 9 files in July vs 7 files in August

4. KEY FACTS CHANGE:
   - July: 63,803,502 patients
   - August: 63,821,662 patients (+18,160)
   
5. SCHEMA STABILITY:
   - Core CSV files have IDENTICAL structure across periods
   - Fields documented in central metadata page (not per-release)
""")
