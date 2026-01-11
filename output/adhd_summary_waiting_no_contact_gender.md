# ADHD Summary: Waiting with No Contact by Gender

**Dataset:** `adhd_summary_waiting_no_contact_gender`
**Domain:** Clinical - Mental Health
**Rows:** 13
**Columns:** 13

---

## Purpose

No description available.

---

## Coverage

- **Date Range:** 2024-09-24 to 2025-09-01
- **Rows in Export:** 13
- **Load History:** 0 loads, 0 total rows
- **Geographic Scope:** NHS Wales (All Health Boards)

---

## Columns

### Dimensions (Grouping Columns)

#### `date_val`

**Original Name:** Date  
**Type:** character varying  
**Description:** The date for which the data is reported.  
**Search Terms:** period, date, reporting  
**Metadata Quality:** ~ llm (confidence: 0.70)  

#### `_period`

**Original Name:** Date  
**Type:** character varying  
**Description:** The date for which the data is reported.  
**Search Terms:** period, date, reporting  
**Metadata Quality:** ~ llm (confidence: 0.70)  


### Measures (Numeric Metrics)

#### `male_count`

**Original Name:** Gender1 Male  
**Type:** integer  
**Description:** Number of males waiting for an ADHD assessment with no contact.  
**Search Terms:** male, waiting, no contact, assessment, count  
**Metadata Quality:** ~ llm (confidence: 0.70)  

#### `total`

**Original Name:** Total  
**Type:** integer  
**Description:** Total number of individuals waiting for an ADHD assessment with no contact.  
**Search Terms:** total, waiting, no contact, assessment, count  
**Metadata Quality:** ~ llm (confidence: 0.70)  


### Other Columns

#### `gender1_female`

**Type:** integer  
**Description:** System column  
**Metadata Quality:** ✓ system (confidence: 1.00)  

#### `gender1_indeterminate`

**Type:** integer  
**Description:** System column  
**Metadata Quality:** ✓ system (confidence: 1.00)  

#### `gender1_non_binary`

**Type:** integer  
**Description:** System column  
**Metadata Quality:** ✓ system (confidence: 1.00)  

#### `gender1_other_not_listed`

**Type:** integer  
**Description:** System column  
**Metadata Quality:** ✓ system (confidence: 1.00)  

#### `gender1_unknown`

**Type:** integer  
**Description:** System column  
**Metadata Quality:** ✓ system (confidence: 1.00)  

#### `gender1_male`

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

**Original Name:** Date  
**Type:** character varying  
**Description:** The date for which the data is reported.  
**Search Terms:** period, date, reporting  
**Metadata Quality:** ~ llm (confidence: 0.70)  

#### `_manifest_file_id`

**Type:** integer  
**Description:** Reference to the manifest file that sourced this data  
**Metadata Quality:** ✓ system (confidence: 1.00)  


---

*Generated: 2026-01-11 16:58:54*
*Source: DataWarp v2.1*
