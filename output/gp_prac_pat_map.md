# GP Practice Patient Mapping

**Dataset:** `gp_prac_pat_map`
**Domain:** Unknown
**Rows:** 31,108
**Columns:** 21

---

## Purpose

No description available.

---

## Coverage

- **Date Range:** GP_PRAC_PAT_LIST to GP_PRAC_PAT_LIST
- **Rows in Export:** 31,108
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

#### `practice_code`

**Original Name:** PRACTICE_CODE  
**Type:** character varying  
**Description:** The unique code identifying the GP practice.  
**Search Terms:** practice code, gp code  
**Metadata Quality:** ~ llm (confidence: 0.70)  

#### `practice_name`

**Original Name:** PRACTICE_NAME  
**Type:** character varying  
**Description:** The name of the GP practice.  
**Search Terms:** practice name, gp name  
**Metadata Quality:** ~ llm (confidence: 0.70)  

#### `practice_postcode`

**Original Name:** PRACTICE_POSTCODE  
**Type:** character varying  
**Description:** The postcode of the GP practice.  
**Search Terms:** practice postcode, postcode  
**Metadata Quality:** ~ llm (confidence: 0.70)  

#### `pcn_code`

**Original Name:** PCN_CODE  
**Type:** character varying  
**Description:** The unique code identifying the Primary Care Network (PCN).  
**Search Terms:** pcn code, primary care network code  
**Metadata Quality:** ~ llm (confidence: 0.70)  

#### `pcn_name`

**Original Name:** PCN_NAME  
**Type:** character varying  
**Description:** The name of the Primary Care Network (PCN).  
**Search Terms:** pcn name, primary care network name  
**Metadata Quality:** ~ llm (confidence: 0.70)  

#### `ons_sub_icb_location_code`

**Original Name:** ONS_SUB_ICB_LOCATION_CODE  
**Type:** character varying  
**Description:** The ONS code for the Sub-Integrated Care Board (Sub-ICB) location.  
**Search Terms:** ons sub icb code, sub icb code  
**Metadata Quality:** ~ llm (confidence: 0.70)  

#### `sub_icb_location_code`

**Original Name:** SUB_ICB_LOCATION_CODE  
**Type:** character varying  
**Description:** The code for the Sub-Integrated Care Board (Sub-ICB) location.  
**Search Terms:** sub icb code, location code  
**Metadata Quality:** ~ llm (confidence: 0.70)  

#### `sub_icb_location_name`

**Original Name:** SUB_ICB_LOCATION_NAME  
**Type:** character varying  
**Description:** The name of the Sub-Integrated Care Board (Sub-ICB) location.  
**Search Terms:** sub icb name, location name  
**Metadata Quality:** ~ llm (confidence: 0.70)  

#### `ons_icb_code`

**Original Name:** ONS_ICB_CODE  
**Type:** character varying  
**Description:** The ONS code for the Integrated Care Board (ICB).  
**Search Terms:** ons icb code, icb code  
**Metadata Quality:** ~ llm (confidence: 0.70)  

#### `icb_code`

**Original Name:** ICB_CODE  
**Type:** character varying  
**Description:** The code for the Integrated Care Board (ICB).  
**Search Terms:** icb code  
**Metadata Quality:** ~ llm (confidence: 0.70)  

#### `icb_name`

**Original Name:** ICB_NAME  
**Type:** character varying  
**Description:** The name of the Integrated Care Board (ICB).  
**Search Terms:** icb name  
**Metadata Quality:** ~ llm (confidence: 0.70)  

#### `ons_comm_region_code`

**Original Name:** ONS_COMM_REGION_CODE  
**Type:** character varying  
**Description:** The ONS code for the Community Region.  
**Search Terms:** ons region code, region code  
**Metadata Quality:** ~ llm (confidence: 0.70)  

#### `comm_region_code`

**Original Name:** COMM_REGION_CODE  
**Type:** character varying  
**Description:** The code for the Community Region.  
**Search Terms:** region code  
**Metadata Quality:** ~ llm (confidence: 0.70)  

#### `comm_region_name`

**Original Name:** COMM_REGION_NAME  
**Type:** character varying  
**Description:** The name of the Community Region.  
**Search Terms:** region name  
**Metadata Quality:** ~ llm (confidence: 0.70)  

#### `supplier_name`

**Original Name:** SUPPLIER_NAME  
**Type:** character varying  
**Description:** The name of the supplier for the GP practice system.  
**Search Terms:** supplier, system provider  
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

*Generated: 2026-01-10 20:29:23*
*Source: DataWarp v2.1*
