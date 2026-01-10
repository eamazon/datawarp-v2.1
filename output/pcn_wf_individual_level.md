# Primary Care Network Workforce Individual Level Data

**Dataset:** `pcn_wf_individual_level`
**Domain:** Unknown
**Rows:** 193,480
**Columns:** 20

---

## Purpose

No description available.

---

## Coverage

- **Date Range:** NWRS Staff to NWRS contracted services
- **Rows in Export:** 193,480
- **Load History:** 0 loads, 0 total rows
- **Geographic Scope:** NHS Wales (All Health Boards)

---

## Columns

### Dimensions (Grouping Columns)

#### `data_source`

**Original Name:** Data_source  
**Type:** character varying  
**Description:** The source of the data.  
**Search Terms:** data source  
**Metadata Quality:** ~ llm (confidence: 0.70)  

#### `census_year`

**Original Name:** CENSUS_YEAR  
**Type:** integer  
**Description:** The year of the workforce census.  
**Search Terms:** census year  
**Metadata Quality:** ~ llm (confidence: 0.70)  

#### `census_month`

**Original Name:** CENSUS_MONTH  
**Type:** integer  
**Description:** The month of the workforce census.  
**Search Terms:** census month  
**Metadata Quality:** ~ llm (confidence: 0.70)  

#### `pcn_code`

**Original Name:** PCN_CODE  
**Type:** character varying  
**Description:** The unique code for the Primary Care Network (PCN).  
**Search Terms:** PCN code  
**Metadata Quality:** ~ llm (confidence: 0.70)  

#### `pcn_name`

**Original Name:** PCN_NAME  
**Type:** character varying  
**Description:** The name of the Primary Care Network (PCN).  
**Search Terms:** PCN name  
**Metadata Quality:** ~ llm (confidence: 0.70)  

#### `sub_icb_code`

**Original Name:** SUB_ICB_CODE  
**Type:** character varying  
**Description:** The unique code for the Sub-Integrated Care Board (Sub-ICB) Location.  
**Search Terms:** Sub ICB code  
**Metadata Quality:** ~ llm (confidence: 0.70)  

#### `sub_icb_name`

**Original Name:** SUB_ICB_NAME  
**Type:** character varying  
**Description:** The name of the Sub-Integrated Care Board (Sub-ICB) Location.  
**Search Terms:** Sub ICB name  
**Metadata Quality:** ~ llm (confidence: 0.70)  

#### `icb_code`

**Original Name:** ICB_CODE  
**Type:** character varying  
**Description:** The unique code for the Integrated Care Board (ICB).  
**Search Terms:** ICB code  
**Metadata Quality:** ~ llm (confidence: 0.70)  

#### `icb_name`

**Original Name:** ICB_NAME  
**Type:** character varying  
**Description:** The name of the Integrated Care Board (ICB).  
**Search Terms:** ICB name  
**Metadata Quality:** ~ llm (confidence: 0.70)  

#### `comm_region_code`

**Original Name:** COMM_REGION_CODE  
**Type:** character varying  
**Description:** The code for the Community Region.  
**Search Terms:** Community Region code  
**Metadata Quality:** ~ llm (confidence: 0.70)  

#### `comm_region_name`

**Original Name:** COMM_REGION_NAME  
**Type:** character varying  
**Description:** The name of the Community Region.  
**Search Terms:** Community Region name  
**Metadata Quality:** ~ llm (confidence: 0.70)  

#### `staff_group`

**Original Name:** STAFF_GROUP  
**Type:** character varying  
**Description:** The broad group to which the staff member belongs.  
**Search Terms:** staff group  
**Metadata Quality:** ~ llm (confidence: 0.70)  

#### `staff_role`

**Original Name:** STAFF_ROLE  
**Type:** character varying  
**Description:** The general role of the staff member.  
**Search Terms:** staff role  
**Metadata Quality:** ~ llm (confidence: 0.70)  

#### `detailed_staff_role`

**Original Name:** DETAILED_STAFF_ROLE  
**Type:** character varying  
**Description:** The specific role of the staff member.  
**Search Terms:** detailed staff role  
**Metadata Quality:** ~ llm (confidence: 0.70)  


### Measures (Numeric Metrics)

#### `fte`

**Original Name:** FTE  
**Type:** numeric  
**Description:** Full-time equivalent (FTE) of the staff member.  
**Search Terms:** FTE, full time equivalent  
**Metadata Quality:** ~ llm (confidence: 0.70)  


### Other Columns

#### `unique_identifier`

**Original Name:** UNIQUE_IDENTIFIER  
**Type:** integer  
**Description:** A unique identifier for the staff record.  
**Search Terms:** unique identifier, ID  
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

*Generated: 2026-01-10 12:31:15*
*Source: DataWarp v2.1*
