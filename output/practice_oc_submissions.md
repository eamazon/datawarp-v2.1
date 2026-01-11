# Practice OC Submissions

**Dataset:** `practice_oc_submissions`
**Domain:** Unknown
**Rows:** 8,530,389
**Columns:** 18

---

## Purpose

No description available.

---

## Coverage

- **Date Range:** 2023-10-01 to 2025-11-01
- **Rows in Export:** 8,530,389
- **Load History:** 0 loads, 0 total rows
- **Geographic Scope:** NHS Wales (All Health Boards)

---

## Columns

### Dimensions (Grouping Columns)

#### `month_val`

**Original Name:** MONTH  
**Type:** character varying  
**Description:** The month of the submission data.  
**Search Terms:** month, period, date  
**Metadata Quality:** ~ llm (confidence: 0.70)  

#### `gp_code`

**Original Name:** GP_CODE  
**Type:** character varying  
**Description:** The unique code for the General Practice.  
**Search Terms:** gp code, practice code  
**Metadata Quality:** ~ llm (confidence: 0.70)  

#### `gp_name`

**Original Name:** GP_NAME  
**Type:** character varying  
**Description:** The name of the General Practice.  
**Search Terms:** gp name, practice name  
**Metadata Quality:** ~ llm (confidence: 0.70)  

#### `pcn_code`

**Original Name:** PCN_CODE  
**Type:** character varying  
**Description:** The unique code for the Primary Care Network.  
**Search Terms:** pcn code, primary care network code  
**Metadata Quality:** ~ llm (confidence: 0.70)  

#### `pcn_name`

**Original Name:** PCN_NAME  
**Type:** character varying  
**Description:** The name of the Primary Care Network.  
**Search Terms:** pcn name, primary care network name  
**Metadata Quality:** ~ llm (confidence: 0.70)  

#### `sub_icb_location_code`

**Original Name:** SUB_ICB_LOCATION_CODE  
**Type:** character varying  
**Description:** The code for the Sub-Integrated Care Board Location.  
**Search Terms:** sub icb code, sub integrated care board code  
**Metadata Quality:** ~ llm (confidence: 0.70)  

#### `sub_icb_location_name`

**Original Name:** SUB_ICB_LOCATION_NAME  
**Type:** character varying  
**Description:** The name of the Sub-Integrated Care Board Location.  
**Search Terms:** sub icb name, sub integrated care board name  
**Metadata Quality:** ~ llm (confidence: 0.70)  

#### `icb_code`

**Original Name:** ICB_CODE  
**Type:** character varying  
**Description:** The code for the Integrated Care Board.  
**Search Terms:** icb code, integrated care board code  
**Metadata Quality:** ~ llm (confidence: 0.70)  

#### `icb_name`

**Original Name:** ICB_NAME  
**Type:** character varying  
**Description:** The name of the Integrated Care Board.  
**Search Terms:** icb name, integrated care board name  
**Metadata Quality:** ~ llm (confidence: 0.70)  

#### `region_code`

**Original Name:** REGION_CODE  
**Type:** character varying  
**Description:** The code for the NHS Region.  
**Search Terms:** region code  
**Metadata Quality:** ~ llm (confidence: 0.70)  

#### `region_name`

**Original Name:** REGION_NAME  
**Type:** character varying  
**Description:** The name of the NHS Region.  
**Search Terms:** region name  
**Metadata Quality:** ~ llm (confidence: 0.70)  

#### `supplier`

**Original Name:** SUPPLIER  
**Type:** character varying  
**Description:** The supplier of the Online Consultation system.  
**Search Terms:** supplier, provider, vendor  
**Metadata Quality:** ~ llm (confidence: 0.70)  

#### `metric`

**Original Name:** METRIC  
**Type:** character varying  
**Description:** The type of metric being reported (e.g., OC_CAPABILITY, OC_PARTICIPATION, OC_RATE_PER_1000_REGISTERED_PATIENTS).  
**Search Terms:** metric, measure, type  
**Metadata Quality:** ~ llm (confidence: 0.70)  


### Measures (Numeric Metrics)

#### `value_val`

**Original Name:** VALUE  
**Type:** numeric  
**Description:** The reported value for the given metric.  
**Search Terms:** value, count, rate, number  
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

*Generated: 2026-01-11 16:59:54*
*Source: DataWarp v2.1*
