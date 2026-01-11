# GP Practice Patient Registration: Age & Region

**Dataset:** `gp_prac_reg_age_region`
**Domain:** Unknown
**Rows:** 1,411,472
**Columns:** 12

---

## Purpose

No description available.

---

## Coverage

- **Date Range:** GP_PRAC_PAT_LIST to GP_PRAC_PAT_LIST
- **Rows in Export:** 1,411,472
- **Load History:** 0 loads, 0 total rows
- **Geographic Scope:** NHS Wales (All Health Boards)

---

## Columns

### Dimensions (Grouping Columns)

#### `publication`

**Original Name:** PUBLICATION  
**Type:** character varying  
**Description:** The name of the publication this data belongs to.  
**Search Terms:** publication  
**Metadata Quality:** ~ llm (confidence: 0.70)  

#### `extract_date`

**Original Name:** EXTRACT_DATE  
**Type:** character varying  
**Description:** The date the data extract was created.  
**Search Terms:** extract date, date  
**Metadata Quality:** ~ llm (confidence: 0.70)  

#### `org_type`

**Original Name:** ORG_TYPE  
**Type:** character varying  
**Description:** The type of organisation the data pertains to (e.g., Comm Region).  
**Search Terms:** organisation type, org type  
**Metadata Quality:** ~ llm (confidence: 0.70)  

#### `org_code`

**Original Name:** ORG_CODE  
**Type:** character varying  
**Description:** The code for the organisation (e.g., Community Region code).  
**Search Terms:** organisation code, org code  
**Metadata Quality:** ~ llm (confidence: 0.70)  

#### `ons_code`

**Original Name:** ONS_CODE  
**Type:** character varying  
**Description:** The ONS code for the organisation.  
**Search Terms:** ons code  
**Metadata Quality:** ~ llm (confidence: 0.70)  

#### `sex`

**Original Name:** SEX  
**Type:** character varying  
**Description:** The sex of the patient group (ALL, FEMALE, MALE).  
**Search Terms:** sex, gender  
**Metadata Quality:** ~ llm (confidence: 0.70)  

#### `age`

**Original Name:** AGE  
**Type:** character varying  
**Description:** The age group of the patient group (ALL or specific age).  
**Search Terms:** age, age group  
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

*Generated: 2026-01-11 17:00:57*
*Source: DataWarp v2.1*
