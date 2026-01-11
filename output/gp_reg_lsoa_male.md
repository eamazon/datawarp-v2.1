# GP Practice Registration: LSOA (Male)

**Dataset:** `gp_reg_lsoa_male`
**Domain:** Unknown
**Rows:** 1,883,852
**Columns:** 11

---

## Purpose

No description available.

---

## Coverage

- **Date Range:** GP_PRAC_PAT_LIST to GP_PRAC_PAT_LIST
- **Rows in Export:** 1,883,852
- **Load History:** 0 loads, 0 total rows
- **Geographic Scope:** NHS Wales (All Health Boards)

---

## Columns

### Dimensions (Grouping Columns)

#### `publication`

**Original Name:** PUBLICATION  
**Type:** character varying  
**Description:** The name of the publication.  
**Search Terms:** publication, title  
**Metadata Quality:** ~ llm (confidence: 0.70)  

#### `extract_date`

**Original Name:** EXTRACT_DATE  
**Type:** character varying  
**Description:** The date the data extract was generated.  
**Search Terms:** extract date, date  
**Metadata Quality:** ~ llm (confidence: 0.70)  

#### `practice_code`

**Original Name:** PRACTICE_CODE  
**Type:** character varying  
**Description:** The code for the GP practice.  
**Search Terms:** practice code, org code  
**Metadata Quality:** ~ llm (confidence: 0.70)  

#### `practice_name`

**Original Name:** PRACTICE_NAME  
**Type:** character varying  
**Description:** The name of the GP practice.  
**Search Terms:** practice name, name  
**Metadata Quality:** ~ llm (confidence: 0.70)  

#### `lsoa_code`

**Original Name:** LSOA_CODE  
**Type:** character varying  
**Description:** The Lower Layer Super Output Area (LSOA) code.  
**Search Terms:** LSOA code, area code  
**Metadata Quality:** ~ llm (confidence: 0.70)  

#### `sex`

**Original Name:** SEX  
**Type:** character varying  
**Description:** The sex of the patient group (MALE).  
**Search Terms:** sex, gender  
**Metadata Quality:** ~ llm (confidence: 0.70)  


### Other Columns

#### `number_of_patients`

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

*Generated: 2026-01-11 17:01:33*
*Source: DataWarp v2.1*
