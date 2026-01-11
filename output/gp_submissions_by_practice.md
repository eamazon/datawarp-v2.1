# General Practice Submissions by Practice

**Dataset:** `gp_submissions_by_practice`
**Domain:** Unknown
**Rows:** 55,719
**Columns:** 25

---

## Purpose

No description available.

---

## Coverage

- **Date Range:** 2025-03-01 to 2025-11-01
- **Rows in Export:** 55,719
- **Load History:** 0 loads, 0 total rows
- **Geographic Scope:** NHS Wales (All Health Boards)

---

## Columns

### Dimensions (Grouping Columns)

#### `gp_code`

**Original Name:** GP Code  
**Type:** character varying  
**Description:** The unique code for the general practice.  
**Search Terms:** GP code, practice code  
**Metadata Quality:** ~ llm (confidence: 0.70)  

#### `gp_name`

**Original Name:** GP Name  
**Type:** character varying  
**Description:** The name of the general practice.  
**Search Terms:** GP name, practice name  
**Metadata Quality:** ~ llm (confidence: 0.70)  

#### `sub_icb_code`

**Original Name:** Sub ICB Code  
**Type:** character varying  
**Description:** The code for the Sub Integrated Care Board (Sub ICB) location.  
**Search Terms:** Sub ICB code, sub integrated care board code  
**Metadata Quality:** ~ llm (confidence: 0.70)  

#### `sub_icb_name`

**Original Name:** Sub ICB Name  
**Type:** character varying  
**Description:** The name of the Sub Integrated Care Board (Sub ICB) location.  
**Search Terms:** Sub ICB name, sub integrated care board name  
**Metadata Quality:** ~ llm (confidence: 0.70)  

#### `icb_code`

**Original Name:** ICB Code  
**Type:** character varying  
**Description:** The code for the Integrated Care Board (ICB).  
**Search Terms:** ICB code, integrated care board code  
**Metadata Quality:** ~ llm (confidence: 0.70)  

#### `icb_name`

**Original Name:** ICB Name  
**Type:** character varying  
**Description:** The name of the Integrated Care Board (ICB).  
**Search Terms:** ICB name, integrated care board name  
**Metadata Quality:** ~ llm (confidence: 0.70)  

#### `region_code`

**Original Name:** Region Code  
**Type:** character varying  
**Description:** The code for the geographical region.  
**Search Terms:** region code  
**Metadata Quality:** ~ llm (confidence: 0.70)  

#### `region_name`

**Original Name:** Region Name  
**Type:** character varying  
**Description:** The name of the geographical region.  
**Search Terms:** region name  
**Metadata Quality:** ~ llm (confidence: 0.70)  


### Measures (Numeric Metrics)

#### `participation`

**Original Name:** Participation  
**Type:** integer  
**Description:** Indicates participation in online consultation systems (likely a binary flag).  
**Search Terms:** participation, flag, indicator  
**Metadata Quality:** ~ llm (confidence: 0.70)  


### Other Columns

#### `month_1`

**Type:** date  
**Description:** System column  
**Metadata Quality:** ✓ system (confidence: 1.00)  

#### `pcn_code_2_3`

**Type:** character varying  
**Description:** System column  
**Metadata Quality:** ✓ system (confidence: 1.00)  

#### `pcn_name_3`

**Type:** character varying  
**Description:** System column  
**Metadata Quality:** ✓ system (confidence: 1.00)  

#### `supplier_4_5_6`

**Type:** character varying  
**Description:** System column  
**Metadata Quality:** ✓ system (confidence: 1.00)  

#### `submissions_7`

**Type:** integer  
**Description:** System column  
**Metadata Quality:** ✓ system (confidence: 1.00)  

#### `clinical_submissions_7`

**Type:** integer  
**Description:** System column  
**Metadata Quality:** ✓ system (confidence: 1.00)  

#### `administrative_submissions_7`

**Type:** integer  
**Description:** System column  
**Metadata Quality:** ✓ system (confidence: 1.00)  

#### `other_unknown_type_submissions_7`

**Type:** integer  
**Description:** System column  
**Metadata Quality:** ✓ system (confidence: 1.00)  

#### `registered_patient_count_8`

**Type:** integer  
**Description:** System column  
**Metadata Quality:** ✓ system (confidence: 1.00)  

#### `rate_per_1_000_registered_patients_9_10`

**Type:** numeric  
**Description:** System column  
**Metadata Quality:** ✓ system (confidence: 1.00)  

#### `supplier_4_5_6_11`

**Type:** character varying  
**Description:** System column  
**Metadata Quality:** ✓ system (confidence: 1.00)  

#### `participation_11`

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

*Generated: 2026-01-11 16:59:56*
*Source: DataWarp v2.1*
