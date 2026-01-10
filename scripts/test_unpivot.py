#!/usr/bin/env python
"""Test the unpivot transformer."""

import pandas as pd
import sys
sys.path.insert(0, './src')

from datawarp.transform.unpivot import unpivot_wide_dates, parse_date_column, detect_and_unpivot

print('=' * 70)
print('PHASE 3: UNPIVOT TRANSFORMER TEST')
print('=' * 70)

# Test date parsing
print()
print('Testing parse_date_column():')
test_dates = ['March 2020', 'Nov-25', 'September_2021', '2025-11', 'Q1 2025', 'Age 0 to 4']
for d in test_dates:
    result = parse_date_column(d)
    icon = '📅' if result else '❌'
    print(f'  {icon} "{d}" -> {result}')

print()
print('=' * 70)
print('Testing unpivot_wide_dates() - PCN Workforce Simulation')
print('=' * 70)

# Simulate PCN Workforce data (wide format)
df_wide = pd.DataFrame({
    'Staff_Group': ['All GPs', 'All GPs', 'All Nurses', 'All Nurses'],
    'Age_Band': ['Under 30', '30-34', 'Under 30', '30-34'],
    'March_2020': [100, 200, 150, 250],
    'June_2020': [110, 210, 160, 260],
    'September_2020': [120, 220, 170, 270],
    'October_2025': [180, 280, 230, 330],
    'November_2025': [190, 290, 240, 340],
})

print()
print('WIDE FORMAT (input):')
print(df_wide.to_string(index=False))
print(f'Shape: {df_wide.shape} (rows, cols)')

# Apply unpivot
df_long = unpivot_wide_dates(
    df_wide,
    static_columns=['Staff_Group', 'Age_Band'],
    date_columns=['March_2020', 'June_2020', 'September_2020', 'October_2025', 'November_2025'],
    value_name='headcount',
    period_name='period'
)

print()
print('LONG FORMAT (output):')
print(df_long.head(10).to_string(index=False))
print(f'Shape: {df_long.shape} (rows, cols)')

print()
print('BENEFITS:')
print('   - Wide: 4 rows x 7 cols = limited by column count')
print('   - Long: 20 rows x 5 cols = STABLE schema')
print('   - Adding December 2025 just adds more ROWS, not new COLUMNS')
print('   - Schema is FIXED regardless of date range')

print()
print('=' * 70)
print('Testing detect_and_unpivot() - Auto Detection')
print('=' * 70)

df_transformed, meta = detect_and_unpivot(df_wide, min_date_columns=3)
print(f'Auto-detection result:')
print(f'  Transformed: {meta["transformed"]}')
print(f'  Date columns found: {len(meta["date_columns"])}')
print(f'  Static columns: {meta["static_columns"]}')
print(f'  Shape change: {meta["original_shape"]} -> {meta["final_shape"]}')
