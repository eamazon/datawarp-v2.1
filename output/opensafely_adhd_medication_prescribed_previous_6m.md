# OpenSAFELY: ADHD Medication Prescribed in Previous 6 Months

**Dataset:** `opensafely_adhd_medication_prescribed_previous_6m`
**Domain:** Clinical - Mental Health
**Rows:** 3,240
**Columns:** 12

---

## Purpose

No description available.

---

## Coverage

- **Date Range:** ADHD_patients_with_ADHD_medication_prescribed_in_previous_6_months to ADHD_patients_with_ADHD_medication_prescribed_in_previous_6_months
- **Rows in Export:** 3,240
- **Load History:** 0 loads, 0 total rows
- **Geographic Scope:** NHS Wales (All Health Boards)

---

## Columns

### Dimensions (Grouping Columns)

#### `measure`

**Original Name:** Measure  
**Type:** character varying  
**Description:** The measure being reported (e.g., ADHD patients with ADHD medication prescribed in previous 6 months).  
**Search Terms:** measure, metric  
**Metadata Quality:** ~ llm (confidence: 0.70)  

#### `reporting_period_start_date`

**Original Name:** Reporting_Period_Start_Date  
**Type:** character varying  
**Description:** The start date of the reporting period.  
**Search Terms:** reporting period start, date  
**Metadata Quality:** ~ llm (confidence: 0.70)  

#### `reporting_period_end_date`

**Original Name:** Reporting_Period_End_Date  
**Type:** character varying  
**Description:** The end date of the reporting period.  
**Search Terms:** reporting period end, date  
**Metadata Quality:** ~ llm (confidence: 0.70)  

#### `sex`

**Original Name:** Sex  
**Type:** character varying  
**Description:** The sex of the patient.  
**Search Terms:** sex, gender  
**Metadata Quality:** ~ llm (confidence: 0.70)  

#### `age_band`

**Original Name:** Age_Band  
**Type:** character varying  
**Description:** The age band of the patient.  
**Search Terms:** age band, age group  
**Metadata Quality:** ~ llm (confidence: 0.70)  

#### `_period`

**Original Name:** Reporting_Period_Start_Date  
**Type:** character varying  
**Description:** The start date of the reporting period.  
**Search Terms:** reporting period start, date  
**Metadata Quality:** ~ llm (confidence: 0.70)  


### Measures (Numeric Metrics)

#### `numerator`

**Original Name:** Numerator  
**Type:** integer  
**Description:** The numerator for the percentage calculation.  
**Search Terms:** numerator, count  
**Metadata Quality:** ~ llm (confidence: 0.70)  

#### `denominator`

**Original Name:** Denominator  
**Type:** integer  
**Description:** The denominator for the percentage calculation.  
**Search Terms:** denominator, total  
**Metadata Quality:** ~ llm (confidence: 0.70)  

#### `percentage`

**Original Name:** Percentage  
**Type:** numeric  
**Description:** The percentage of patients with an ADHD diagnosis prescribed ADHD medication in the previous 6 months.  
**Search Terms:** percentage, rate  
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

**Original Name:** Reporting_Period_Start_Date  
**Type:** character varying  
**Description:** The start date of the reporting period.  
**Search Terms:** reporting period start, date  
**Metadata Quality:** ~ llm (confidence: 0.70)  

#### `_manifest_file_id`

**Type:** integer  
**Description:** Reference to the manifest file that sourced this data  
**Metadata Quality:** ✓ system (confidence: 1.00)  


---

*Generated: 2026-01-11 16:58:54*
*Source: DataWarp v2.1*
