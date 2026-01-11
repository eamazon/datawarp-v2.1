# Online Consultation Submissions: Day and Time

**Dataset:** `oc_submissions_day_time`
**Domain:** Unknown
**Rows:** 521,178
**Columns:** 19

---

## Purpose

No description available.

---

## Coverage

- **Date Range:** 2025-06-01 to 2025-08-01
- **Rows in Export:** 521,178
- **Load History:** 0 loads, 0 total rows
- **Geographic Scope:** NHS Wales (All Health Boards)

---

## Columns

### Dimensions (Grouping Columns)

#### `gp_code`

**Original Name:** GP_CODE  
**Type:** character varying  
**Description:** The unique code for the General Practice.  
**Search Terms:** GP code, practice code  
**Metadata Quality:** ~ llm (confidence: 0.70)  

#### `gp_name`

**Original Name:** GP_NAME  
**Type:** character varying  
**Description:** The name of the General Practice.  
**Search Terms:** GP name, practice name  
**Metadata Quality:** ~ llm (confidence: 0.70)  

#### `sub_icb_location_code`

**Original Name:** SUB_ICB_LOCATION_CODE  
**Type:** character varying  
**Description:** The code for the Sub Integrated Care Board (ICB) location.  
**Search Terms:** Sub ICB code, ICB location code  
**Metadata Quality:** ~ llm (confidence: 0.70)  

#### `sub_icb_location_name`

**Original Name:** SUB_ICB_LOCATION_NAME  
**Type:** character varying  
**Description:** The name of the Sub Integrated Care Board (ICB) location.  
**Search Terms:** Sub ICB name, ICB location name  
**Metadata Quality:** ~ llm (confidence: 0.70)  

#### `icb_code`

**Original Name:** ICB_CODE  
**Type:** character varying  
**Description:** The code for the Integrated Care Board (ICB).  
**Search Terms:** ICB code, integrated care board code  
**Metadata Quality:** ~ llm (confidence: 0.70)  

#### `icb_name`

**Original Name:** ICB_NAME  
**Type:** character varying  
**Description:** The name of the Integrated Care Board (ICB).  
**Search Terms:** ICB name, integrated care board name  
**Metadata Quality:** ~ llm (confidence: 0.70)  

#### `region_code`

**Original Name:** REGION_CODE  
**Type:** character varying  
**Description:** The code for the NHS region.  
**Search Terms:** region code, NHS region code  
**Metadata Quality:** ~ llm (confidence: 0.70)  

#### `region_name`

**Original Name:** REGION_NAME  
**Type:** character varying  
**Description:** The name of the NHS region.  
**Search Terms:** region name, NHS region name  
**Metadata Quality:** ~ llm (confidence: 0.70)  

#### `pcn_code`

**Original Name:** PCN_CODE  
**Type:** character varying  
**Description:** The code for the Primary Care Network (PCN).  
**Search Terms:** PCN code, primary care network code  
**Metadata Quality:** ~ llm (confidence: 0.70)  

#### `pcn_name`

**Original Name:** PCN_NAME  
**Type:** character varying  
**Description:** The name of the Primary Care Network (PCN).  
**Search Terms:** PCN name, primary care network name  
**Metadata Quality:** ~ llm (confidence: 0.70)  

#### `supplier`

**Original Name:** SUPPLIER  
**Type:** character varying  
**Description:** The name of the supplier of the online consultation system.  
**Search Terms:** supplier, system provider  
**Metadata Quality:** ~ llm (confidence: 0.70)  

#### `weekday`

**Original Name:** WEEKDAY  
**Type:** character varying  
**Description:** The day of the week for the submission.  
**Search Terms:** weekday, day of week  
**Metadata Quality:** ~ llm (confidence: 0.70)  

#### `submission_time`

**Original Name:** SUBMISSION_TIME  
**Type:** character varying  
**Description:** The time band during which the submission was made.  
**Search Terms:** submission time, time band  
**Metadata Quality:** ~ llm (confidence: 0.70)  


### Other Columns

#### `month_val`

**Type:** character varying  
**Description:** System column  
**Metadata Quality:** ✓ system (confidence: 1.00)  

#### `value_val`

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

*Generated: 2026-01-11 16:58:53*
*Source: DataWarp v2.1*
