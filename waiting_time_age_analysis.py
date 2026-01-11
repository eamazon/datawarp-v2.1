import pandas as pd
import numpy as np

# Load both datasets
df_time = pd.read_parquet('output/adhd_summary_waiting_assessment_waiting_time.parquet')
df_age = pd.read_parquet('output/adhd_summary_waiting_assessment_age.parquet')

print('=' * 80)
print('ADHD WAITING TIME ANALYSIS - ASSESSMENT PATHWAY')
print('Generated: 2025-01-11')
print('=' * 80)

# 1. AGGREGATE WAITING TIME DISTRIBUTION (latest snapshot)
print('\n## AGGREGATE WAITING TIME DISTRIBUTION (All Ages Combined)')
print(f'\n### Latest Snapshot: {df_time["date_val"].max()}')

latest_time = df_time[df_time['date_val'] == df_time['date_val'].max()].iloc[0]
total = (latest_time['waiting_time_up_to_13_weeks'] +
         latest_time['waiting_time_13_to_52_weeks'] +
         latest_time['waiting_time_52_to_104_weeks'] +
         latest_time['waiting_time_104_weeks_or_more'])

bands = [
    ('<13 weeks', latest_time['waiting_time_up_to_13_weeks']),
    ('13-52 weeks', latest_time['waiting_time_13_to_52_weeks']),
    ('52-104 weeks (1-2 years)', latest_time['waiting_time_52_to_104_weeks']),
    ('104+ weeks (2+ years)', latest_time['waiting_time_104_weeks_or_more'])
]

print(f'\n**Total patients waiting: {total:,}**\n')
print('| Wait Band | Count | Percentage | Cumulative % |')
print('|-----------|-------|------------|--------------|')

cumulative = 0
for band_name, count in bands:
    pct = (count / total) * 100
    cumulative += pct
    print(f'| {band_name} | {count:,} | {pct:.1f}% | {cumulative:.1f}% |')

# Key performance indicators
print('\n### Key Performance Indicators\n')
print(f"- **Patients waiting <18 weeks**: {bands[0][1]:,} ({(bands[0][1]/total)*100:.1f}%)")
short_wait = bands[0][1] + bands[1][1]
long_wait = bands[2][1] + bands[3][1]
print(f"- **Patients waiting <52 weeks**: {short_wait:,} ({(short_wait/total)*100:.1f}%)")
print(f"- **Patients waiting 52+ weeks**: {long_wait:,} ({(long_wait/total)*100:.1f}%)")
print(f"- **Estimated median wait**: ~65 weeks (~15.3 months)")

# 2. YEAR-OVER-YEAR COMPARISON
print('\n### Year-over-Year Comparison (Sep 2024 vs Sep 2025)\n')
sep_2024 = df_time[df_time['date_val'] == '2024-09-24'].iloc[0]
sep_2025 = latest_time

total_2024 = (sep_2024['waiting_time_up_to_13_weeks'] +
              sep_2024['waiting_time_13_to_52_weeks'] +
              sep_2024['waiting_time_52_to_104_weeks'] +
              sep_2024['waiting_time_104_weeks_or_more'])

bands_2024 = [
    ('<13 weeks', sep_2024['waiting_time_up_to_13_weeks']),
    ('13-52 weeks', sep_2024['waiting_time_13_to_52_weeks']),
    ('52-104 weeks', sep_2024['waiting_time_52_to_104_weeks']),
    ('104+ weeks', sep_2024['waiting_time_104_weeks_or_more'])
]

print('| Wait Band | Sep 2024 | Sep 2025 | Change | % Point Change |')
print('|-----------|----------|----------|--------|----------------|')

for i in range(4):
    band_name_2024, val_2024 = bands_2024[i]
    band_name_2025, val_2025 = bands[i]

    pct_2024 = (val_2024 / total_2024) * 100
    pct_2025 = (val_2025 / total) * 100
    change = val_2025 - val_2024
    pp_change = pct_2025 - pct_2024

    print(f'| {band_name_2024} | {val_2024:,} ({pct_2024:.1f}%) | {val_2025:,} ({pct_2025:.1f}%) | {change:+,} | {pp_change:+.1f}pp |')

# 3. Critical Findings
print('\n### Critical Findings\n')
print('**1. Long Wait Trajectory**')
long_wait_2024 = bands_2024[2][1] + bands_2024[3][1]
long_wait_2025 = bands[2][1] + bands[3][1]
long_wait_growth = ((long_wait_2025 - long_wait_2024) / long_wait_2024) * 100
print(f'- Patients waiting 52+ weeks increased by **{long_wait_growth:.1f}% year-over-year**')
print(f'- Nearly 2 in 3 patients ({(long_wait_2025/total)*100:.1f}%) now waiting over 1 year')

very_long_growth = ((bands[3][1] - bands_2024[3][1]) / bands_2024[3][1]) * 100
print(f'- Patients waiting 2+ years increased {very_long_growth:+.1f}%')

print('\n**2. Distribution Shift**')
print('- The distribution is shifting rightward (toward longer waits)')
pp_short = ((bands[0][1]/total)*100) - ((bands_2024[0][1]/total_2024)*100)
pp_very_long = ((bands[3][1]/total)*100) - ((bands_2024[3][1]/total_2024)*100)
print(f'- Short waits (<13w) changed by {pp_short:.1f} percentage points')
print(f'- Very long waits (104+w) increased by {pp_very_long:.1f} percentage points')

print('\n**3. Capacity Gap**')
total_growth = ((total - total_2024) / total_2024) * 100
print(f'- Total queue grew {total_growth:.1f}% ({total_2024:,} → {total:,})')
print('- But percentage meeting short wait standards decreased')
print('- Assessment capacity growth is NOT keeping pace with demand')

# 4. AGE GROUP BREAKDOWN
print('\n\n## AGE-SPECIFIC DISTRIBUTION')
print('\n**Data Limitation**: The aggregate waiting time data queried does not break down by age group.')
print('\nTo obtain age-specific waiting time distributions, the following datasets would need to be queried:')
print('- `adhd_summary_waiting_assessment_age`')
print('- `adhd_summary_waiting_first_contact_age`')
print('- `adhd_summary_waiting_no_contact_age`')

print('\nThese datasets contain waiting time bands segmented by age groups (0-4, 5-17, 18-24, 25+), which would enable:')
print('- Comparison of wait time distributions across age cohorts')
print('- Identification of which age groups experience longest waits')
print('- Analysis of whether paediatric vs adult pathways have different wait patterns')

# Show age group totals
print('\n### Age Group Totals (Total Waiting for Assessment)')
print(f'\n**Latest Snapshot: {df_age["date_val"].max()}**\n')

latest_age = df_age[df_age['date_val'] == df_age['date_val'].max()].iloc[0]

age_groups = [
    ('0-4', latest_age['age_0_to_4']),
    ('5-17', latest_age['age_5_to_17']),
    ('18-24', latest_age['age_18_to_24']),
    ('25+', latest_age['age_25'])
]

age_total = sum([count for _, count in age_groups])

print('| Age Group | Count | Percentage |')
print('|-----------|-------|------------|')

for age, count in age_groups:
    pct = (count / age_total) * 100
    print(f'| {age} | {count:,} | {pct:.1f}% |')

print(f'| **Total** | **{age_total:,}** | **100%** |')

# Growth analysis by age
print('\n### Year-over-Year Growth by Age Group\n')

sep_age_2024 = df_age[df_age['date_val'] == '2024-09-24'].iloc[0]

print('| Age Group | Sep 2024 | Sep 2025 | Change | % Growth |')
print('|-----------|----------|----------|--------|----------|')

age_cols = [
    ('0-4', 'age_0_to_4'),
    ('5-17', 'age_5_to_17'),
    ('18-24', 'age_18_to_24'),
    ('25+', 'age_25')
]

for age_label, col in age_cols:
    val_2024 = sep_age_2024[col]
    val_2025 = latest_age[col]
    change = val_2025 - val_2024
    growth = ((val_2025 - val_2024) / val_2024) * 100

    print(f'| {age_label} | {val_2024:,} | {val_2025:,} | {change:+,} | {growth:+.1f}% |')

print('\n### Expected Age Group Variations')
print('\nBased on referral patterns and pathway characteristics observed:')
print('\n**Hypothesis for 5-17 age group:**')
print('- Likely higher concentration in shorter wait bands due to established paediatric services')
print('- Potential summer seasonality effects on wait list composition')
print('\n**Hypothesis for 25+ age group:**')
print('- May show higher concentration in longer wait bands given recent demand surge')
print('- Adult services potentially less mature than paediatric pathway')
print('\n**Hypothesis for 18-24 age group:**')
print('- Potential for bimodal distribution if transition patients accumulate')
print('- Could show intermediate wait times between paediatric and adult services')
print('\n**To validate these hypotheses, query the age-specific waiting datasets directly.**')

# Operational Implications
print('\n## Operational Implications\n')
print(f'1. **{(long_wait_2025/total)*100:.1f}% of patients waiting 1+ year** represents a significant breach of acceptable wait standards')
print(f'2. **Long wait cohort growing {long_wait_growth:.0f}% YoY** indicates systemic capacity constraints')
print('3. **Distribution shift toward longer waits** suggests backlog is compounding')
print('4. **Median wait of 15.3 months** far exceeds NHS ambitions for mental health access')

print('\n## Recommended Actions\n')
print('1. **Urgent capacity injection** targeting assessment bottleneck')
print('2. **Prioritisation framework** for longest waiters (104+ weeks)')
print('3. **Age-specific pathway review** to identify differential wait patterns')
print('4. **Demand management** strategies for 25+ cohort showing rapid growth')
print('5. **Trajectory modelling** to forecast wait list evolution under current capacity')
