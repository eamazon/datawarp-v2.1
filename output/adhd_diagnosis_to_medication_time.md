# ADHD Diagnosis to Medication Time

**Dataset:** `adhd_diagnosis_to_medication_time`
**Domain:** Clinical - Mental Health
**Rows:** 162
**Columns:** 10

---

## Purpose

No description available.

---

## Coverage

- **Date Range:** Median_time_ADHD_diagnosis_to_medication to Median_time_ADHD_diagnosis_to_medication
- **Rows in Export:** 162
- **Load History:** 0 loads, 0 total rows
- **Geographic Scope:** NHS Wales (All Health Boards)

---

## Columns

### Dimensions (Grouping Columns)

#### `measure`

**Original Name:** Measure  
**Type:** character varying  
**Description:** The measure being reported (e.g., Median time ADHD diagnosis to medication).  
**Search Terms:** measure, metric, type  
**Metadata Quality:** ~ llm (confidence: 0.70)  

#### `sex`

**Original Name:** Sex  
**Type:** character varying  
**Description:** The sex of the patient.  
**Search Terms:** sex, gender, male, female  
**Metadata Quality:** ~ llm (confidence: 0.70)  

#### `age_band`

**Original Name:** Age_Band  
**Type:** character varying  
**Description:** The age band of the patient.  
**Search Terms:** age band, age group  
**Metadata Quality:** ~ llm (confidence: 0.70)  


### Measures (Numeric Metrics)

#### `median`

**Original Name:** Median  
**Type:** integer  
**Description:** The median time in days from ADHD diagnosis to medication being prescribed.  
**Search Terms:** median, time, days, duration  
**Metadata Quality:** ~ llm (confidence: 0.70)  


### Other Columns

#### `year_of_medication`

**Type:** character varying  
**Description:** System column  
**Metadata Quality:** ✓ system (confidence: 1.00)  

#### `size`

**Type:** integer  
**Description:** System column  
**Metadata Quality:** ✓ system (confidence: 1.00)  


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

**Type:** character varying  
**Description:** Period identifier for this data (format: YYYY-MM)  
**Metadata Quality:** ✓ system (confidence: 1.00)  

#### `_manifest_file_id`

**Type:** integer  
**Description:** Reference to the manifest file that sourced this data  
**Metadata Quality:** ✓ system (confidence: 1.00)  


---

*Generated: 2026-01-10 10:57:28*
*Source: DataWarp v2.1*
