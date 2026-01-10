# OpenSAFELY: Median Time from Diagnosis to Medication

**Dataset:** `opensafely_median_time_diagnosis_to_medication`
**Domain:** Unknown
**Rows:** 648
**Columns:** 12

---

## Purpose

No description available.

---

## Coverage

- **Date Range:** Median_time_ADHD_diagnosis_to_medication to Median_time_ADHD_diagnosis_to_medication
- **Rows in Export:** 648
- **Load History:** 0 loads, 0 total rows
- **Geographic Scope:** NHS Wales (All Health Boards)

---

## Columns

### Dimensions (Grouping Columns)

#### `measure`

**Original Name:** Measure  
**Type:** character varying  
**Description:** The measure being reported (e.g., Median time from ADHD diagnosis to medication).  
**Search Terms:** measure, metric  
**Metadata Quality:** ~ llm (confidence: 0.70)  

#### `year_of_medication`

**Original Name:** Year_of_medication  
**Type:** character varying  
**Description:** The year in which medication was prescribed.  
**Search Terms:** year, medication year  
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


### Measures (Numeric Metrics)

#### `median_time_weeks`

**Original Name:** Median  
**Type:** integer  
**Description:** The median time in weeks from ADHD diagnosis to medication being prescribed.  
**Search Terms:** median time, weeks, diagnosis to medication  
**Metadata Quality:** ~ llm (confidence: 0.70)  

#### `patient_count`

**Original Name:** size  
**Type:** integer  
**Description:** The number of patients included in the median calculation.  
**Search Terms:** size, count, patients  
**Metadata Quality:** ~ llm (confidence: 0.70)  

#### `median`

**Original Name:** Median  
**Type:** integer  
**Description:** The median time in weeks from ADHD diagnosis to medication being prescribed.  
**Search Terms:** median time, weeks, diagnosis to medication  
**Metadata Quality:** ~ llm (confidence: 0.70)  


### Other Columns

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

*Generated: 2026-01-10 20:28:04*
*Source: DataWarp v2.1*
