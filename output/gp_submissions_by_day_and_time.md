# General Practice Submissions by Day and Time

**Dataset:** `gp_submissions_by_day_and_time`
**Domain:** Unknown
**Rows:** 320,955
**Columns:** 19

---

## Purpose

No description available.

---

## Coverage

- **Date Range:** 2025-03-01 to 2025-04-01
- **Rows in Export:** 320,955
- **Load History:** 0 loads, 0 total rows
- **Geographic Scope:** NHS Wales (All Health Boards)

---

## Columns

### Dimensions (Grouping Columns)

#### `month_val`

**Original Name:** MONTH  
**Type:** character varying  
**Description:** The month for which the submission data is reported.  
**Search Terms:** month, period, date  
**Metadata Quality:** ~ llm (confidence: 0.70)  

#### `gp_code`

**Original Name:** GP_CODE  
**Type:** character varying  
**Description:** The unique code for the general practice.  
**Search Terms:** GP code, practice code  
**Metadata Quality:** ~ llm (confidence: 0.70)  

#### `gp_name`

**Original Name:** GP_NAME  
**Type:** character varying  
**Description:** The name of the general practice.  
**Search Terms:** GP name, practice name  
**Metadata Quality:** ~ llm (confidence: 0.70)  

#### `sub_icb_location_code`

**Original Name:** SUB_ICB_LOCATION_CODE  
**Type:** character varying  
**Description:** The code for the Sub Integrated Care Board (Sub ICB) location.  
**Search Terms:** Sub ICB code, sub integrated care board code  
**Metadata Quality:** ~ llm (confidence: 0.70)  

#### `sub_icb_location_name`

**Original Name:** SUB_ICB_LOCATION_NAME  
**Type:** character varying  
**Description:** The name of the Sub Integrated Care Board (Sub ICB) location.  
**Search Terms:** Sub ICB name, sub integrated care board name  
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
**Description:** The code for the geographical region.  
**Search Terms:** region code  
**Metadata Quality:** ~ llm (confidence: 0.70)  

#### `region_name`

**Original Name:** REGION_NAME  
**Type:** character varying  
**Description:** The name of the geographical region.  
**Search Terms:** region name  
**Metadata Quality:** ~ llm (confidence: 0.70)  

#### `pcn_code`

**Original Name:** PCN_CODE  
**Type:** character varying  
**Description:** The code for the Primary Care Network (PCN) the practice belongs to.  
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
**Description:** The supplier of the online consultation system.  
**Search Terms:** supplier, provider, online system  
**Metadata Quality:** ~ llm (confidence: 0.70)  

#### `weekday`

**Original Name:** WEEKDAY  
**Type:** character varying  
**Description:** The day of the week for the submission.  
**Search Terms:** weekday, day  
**Metadata Quality:** ~ llm (confidence: 0.70)  

#### `submission_time`

**Original Name:** SUBMISSION_TIME  
**Type:** character varying  
**Description:** The time band during which the submission was made.  
**Search Terms:** submission time, time band, period  
**Metadata Quality:** ~ llm (confidence: 0.70)  


### Measures (Numeric Metrics)

#### `value_val`

**Original Name:** VALUE  
**Type:** integer  
**Description:** The count of submissions for the given day, time, and supplier.  
**Search Terms:** value, count, submissions  
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

**Type:** character varying  
**Description:** Period identifier for this data (format: YYYY-MM)  
**Metadata Quality:** ✓ system (confidence: 1.00)  

#### `_manifest_file_id`

**Type:** integer  
**Description:** Reference to the manifest file that sourced this data  
**Metadata Quality:** ✓ system (confidence: 1.00)  


---

*Generated: 2026-01-11 16:52:34*
*Source: DataWarp v2.1*
