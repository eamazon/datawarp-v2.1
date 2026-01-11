# ADHD Nov25 Raw Data

**Dataset:** `adhd_nov25_raw`
**Domain:** Clinical - Mental Health
**Rows:** 8,149
**Columns:** 12

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
**Search Terms:** reporting period start, date  
**Metadata Quality:** ~ llm (confidence: 0.70)  

#### `reporting_period_end_date`

**Original Name:** REPORTING_PERIOD_END_DATE  
**Type:** character varying  
**Description:** The end date of the reporting period.  
**Search Terms:** reporting period end, date  
**Metadata Quality:** ~ llm (confidence: 0.70)  

#### `breakdown`

**Original Name:** BREAKDOWN  
**Type:** character varying  
**Description:** The category of breakdown for the data (e.g., Age Group, Gender).  
**Search Terms:** breakdown, category  
**Metadata Quality:** ~ llm (confidence: 0.70)  

#### `primary_level`

**Original Name:** PRIMARY_LEVEL  
**Type:** character varying  
**Description:** The primary level of the breakdown (e.g., specific age band or gender).  
**Search Terms:** primary level, category  
**Metadata Quality:** ~ llm (confidence: 0.70)  

#### `primary_level_description`

**Original Name:** PRIMARY_LEVEL_DESCRIPTION  
**Type:** character varying  
**Description:** A description of the primary level.  
**Search Terms:** primary level description, description  
**Metadata Quality:** ~ llm (confidence: 0.70)  

#### `indicator_id`

**Original Name:** INDICATOR_ID  
**Type:** character varying  
**Description:** Identifier for the specific indicator being reported.  
**Search Terms:** indicator id, code  
**Metadata Quality:** ~ llm (confidence: 0.70)  

#### `_period`

**Original Name:** REPORTING_PERIOD_START_DATE  
**Type:** character varying  
**Description:** The start date of the reporting period.  
**Search Terms:** reporting period start, date  
**Metadata Quality:** ~ llm (confidence: 0.70)  


### Measures (Numeric Metrics)

#### `value`

**Original Name:** VALUE  
**Type:** character varying  
**Description:** The numerical value for the indicator.  
**Search Terms:** value, count, number  
**Metadata Quality:** ~ llm (confidence: 0.70)  

#### `value_val`

**Original Name:** VALUE  
**Type:** character varying  
**Description:** The numerical value for the indicator.  
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
**Search Terms:** reporting period start, date  
**Metadata Quality:** ~ llm (confidence: 0.70)  

#### `_manifest_file_id`

**Type:** integer  
**Description:** Reference to the manifest file that sourced this data  
**Metadata Quality:** ✓ system (confidence: 1.00)  


---

*Generated: 2026-01-11 16:58:53*
*Source: DataWarp v2.1*
