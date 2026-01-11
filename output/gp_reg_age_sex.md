# GP Practice Patient Registration: Age & Sex

**Dataset:** `gp_reg_age_sex`
**Domain:** Unknown
**Rows:** 594,559
**Columns:** 12

---

## Purpose

No description available.

---

## Coverage

- **Date Range:** 2025-04-01 to 2025-04-01
- **Rows in Export:** 594,559
- **Load History:** 0 loads, 0 total rows
- **Geographic Scope:** NHS Wales (All Health Boards)

---

## Columns

### Dimensions (Grouping Columns)

#### `extract_date`

**Original Name:** EXTRACT_DATE  
**Type:** character varying  
**Description:** The date the data extract was generated.  
**Search Terms:** extract date, date  
**Metadata Quality:** ~ llm (confidence: 0.70)  

#### `sub_icb_location_code`

**Original Name:** SUB_ICB_LOCATION_CODE  
**Type:** character varying  
**Description:** The code for the Sub Integrated Care Board (ICB) location.  
**Search Terms:** sub icb code, location code  
**Metadata Quality:** ~ llm (confidence: 0.70)  

#### `ons_sub_icb_location_code`

**Original Name:** ONS_SUB_ICB_LOCATION_CODE  
**Type:** character varying  
**Description:** The Office for National Statistics (ONS) code for the Sub Integrated Care Board (ICB) location.  
**Search Terms:** ons sub icb code, ons location code  
**Metadata Quality:** ~ llm (confidence: 0.70)  

#### `postcode`

**Original Name:** POSTCODE  
**Type:** character varying  
**Description:** The postcode of the GP practice.  
**Search Terms:** postcode, location  
**Metadata Quality:** ~ llm (confidence: 0.70)  

#### `sex`

**Original Name:** SEX  
**Type:** character varying  
**Description:** The sex of the patient group (MALE, FEMALE, ALL).  
**Search Terms:** sex, gender  
**Metadata Quality:** ~ llm (confidence: 0.70)  

#### `age`

**Original Name:** AGE  
**Type:** character varying  
**Description:** The age group of the patient (e.g., ALL, 0-4, 5-9).  
**Search Terms:** age, age group  
**Metadata Quality:** ~ llm (confidence: 0.70)  


### Other Columns

#### `org_code`

**Type:** character varying  
**Description:** System column  
**Metadata Quality:** ✓ system (confidence: 1.00)  

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

*Generated: 2026-01-11 17:01:19*
*Source: DataWarp v2.1*
