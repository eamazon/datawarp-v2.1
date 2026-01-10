# ADHD Prevalence Estimate

**Dataset:** `adhd_prevalence_estimate`
**Domain:** Clinical - Mental Health
**Rows:** 8,149
**Columns:** 11

---

## Purpose

No description available.

---

## Coverage

- **Date Range:** 01/01/2025 to 2025-08-01
- **Rows in Export:** 8,149
- **Load History:** 0 loads, 0 total rows
- **Geographic Scope:** NHS Wales (All Health Boards)

---

## Columns

### Dimensions (Grouping Columns)

#### `reporting_period_start_date`

**Original Name:** REPORTING_PERIOD_START_DATE  
**Type:** character varying  
**Description:** The start date of the reporting period.  
**Search Terms:** reporting period, start date  
**Metadata Quality:** ~ llm (confidence: 0.70)  

#### `reporting_period_end_date`

**Original Name:** REPORTING_PERIOD_END_DATE  
**Type:** character varying  
**Description:** The end date of the reporting period.  
**Search Terms:** reporting period, end date  
**Metadata Quality:** ~ llm (confidence: 0.70)  

#### `breakdown`

**Original Name:** BREAKDOWN  
**Type:** character varying  
**Description:** The type of breakdown for the data (e.g., Age Group, Sex).  
**Search Terms:** breakdown, category, type  
**Metadata Quality:** ~ llm (confidence: 0.70)  

#### `primary_level`

**Original Name:** PRIMARY_LEVEL  
**Type:** character varying  
**Description:** The primary level of the breakdown (e.g., age group category, sex category).  
**Search Terms:** primary level, level, category  
**Metadata Quality:** ~ llm (confidence: 0.70)  

#### `primary_level_description`

**Original Name:** PRIMARY_LEVEL_DESCRIPTION  
**Type:** character varying  
**Description:** A descriptive text for the primary level.  
**Search Terms:** description, level description  
**Metadata Quality:** ~ llm (confidence: 0.70)  

#### `indicator_id`

**Original Name:** INDICATOR_ID  
**Type:** character varying  
**Description:** Unique identifier for the indicator being measured.  
**Search Terms:** indicator, ID, code  
**Metadata Quality:** ~ llm (confidence: 0.70)  

#### `_period`

**Original Name:** REPORTING_PERIOD_START_DATE  
**Type:** character varying  
**Description:** The start date of the reporting period.  
**Search Terms:** reporting period, start date  
**Metadata Quality:** ~ llm (confidence: 0.70)  


### Measures (Numeric Metrics)

#### `value_val`

**Original Name:** VALUE  
**Type:** character varying  
**Description:** The measured value for the indicator.  
**Search Terms:** value, count, number  
**Metadata Quality:** ~ llm (confidence: 0.70)  


### System Columns (DataWarp Audit Trail)

These columns are automatically added by DataWarp for data lineage and audit purposes.

#### `_load_id`

**Type:** integer  
**Description:** Unique identifier for the batch load that created this row  
**Metadata Quality:** ✓ system (confidence: 1.00)  

#### `_loaded_at`

**Type:** timestamp without time zone  
**Description:** Timestamp when this row was loaded into DataWarp  
**Metadata Quality:** ✓ system (confidence: 1.00)  

#### `_period`

**Original Name:** REPORTING_PERIOD_START_DATE  
**Type:** character varying  
**Description:** The start date of the reporting period.  
**Search Terms:** reporting period, start date  
**Metadata Quality:** ~ llm (confidence: 0.70)  

#### `_manifest_file_id`

**Type:** integer  
**Description:** Reference to the manifest file that sourced this data  
**Metadata Quality:** ✓ system (confidence: 1.00)  


---

*Generated: 2026-01-10 10:57:29*
*Source: DataWarp v2.1*
