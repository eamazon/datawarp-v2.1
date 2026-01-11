# Mental Health Services Data Set: Historic ADHD Data

**Dataset:** `mhsds_historic_adhd_data`
**Domain:** Clinical - Mental Health
**Rows:** 5,609
**Columns:** 9

---

## Purpose

No description available.

---

## Coverage

- **Date Range:** 01/01/2020 to 01/12/2023
- **Rows in Export:** 5,609
- **Load History:** 0 loads, 0 total rows
- **Geographic Scope:** NHS Wales (All Health Boards)

---

## Columns

### Dimensions (Grouping Columns)

#### `reporting_period_start_date`

**Original Name:** REPORTING_PERIOD_START_DATE  
**Type:** character varying  
**Description:** The start date of the reporting period.  
**Search Terms:** reporting period, start date, date  
**Metadata Quality:** ~ llm (confidence: 0.70)  

#### `reporting_period_end_date`

**Original Name:** REPORTING_PERIOD_END_DATE  
**Type:** character varying  
**Description:** The end date of the reporting period.  
**Search Terms:** reporting period, end date, date  
**Metadata Quality:** ~ llm (confidence: 0.70)  

#### `indicator_id`

**Original Name:** INDICATOR_ID  
**Type:** character varying  
**Description:** The unique identifier for the indicator being reported.  
**Search Terms:** indicator, ID, code  
**Metadata Quality:** ~ llm (confidence: 0.70)  

#### `age_group`

**Original Name:** AGE_GROUP  
**Type:** character varying  
**Description:** The age group to which the data pertains.  
**Search Terms:** age, group, demographics  
**Metadata Quality:** ~ llm (confidence: 0.70)  

#### `_period`

**Original Name:** REPORTING_PERIOD_START_DATE  
**Type:** character varying  
**Description:** The start date of the reporting period.  
**Search Terms:** reporting period, start date, date  
**Metadata Quality:** ~ llm (confidence: 0.70)  


### Measures (Numeric Metrics)

#### `value_val`

**Original Name:** VALUE  
**Type:** character varying  
**Description:** The measured value for the indicator and age group.  
**Search Terms:** value, count, number, metric  
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
**Search Terms:** reporting period, start date, date  
**Metadata Quality:** ~ llm (confidence: 0.70)  

#### `_manifest_file_id`

**Type:** integer  
**Description:** Reference to the manifest file that sourced this data  
**Metadata Quality:** ✓ system (confidence: 1.00)  


---

*Generated: 2026-01-11 16:59:57*
*Source: DataWarp v2.1*
