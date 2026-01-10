# ADHD Summary: Community Paediatrics Waiting List

**Dataset:** `adhd_summary_community_paediatrics_waiting_list`
**Domain:** Clinical - Mental Health
**Rows:** 26
**Columns:** 11

---

## Purpose

No description available.

---

## Coverage

- **Date Range:** 2024-06-01 to 2025-09-01
- **Rows in Export:** 26
- **Load History:** 0 loads, 0 total rows
- **Geographic Scope:** NHS Wales (All Health Boards)

---

## Columns

### Dimensions (Grouping Columns)

#### `date_val`

**Original Name:** Date  
**Type:** character varying  
**Description:** The date of the data.  
**Search Terms:** date, reporting date  
**Metadata Quality:** ~ llm (confidence: 0.70)  

#### `_period`

**Original Name:** Date  
**Type:** character varying  
**Description:** The date for which the data is reported.  
**Search Terms:** period, date, reporting  
**Metadata Quality:** ~ llm (confidence: 0.70)  


### Measures (Numeric Metrics)

#### `waiting_time_up_to_12_weeks`

**Original Name:** Waiting time Up to 12 weeks  
**Type:** integer  
**Description:** The number of open referrals on the community paediatrics waiting list waiting up to 12 weeks.  
**Search Terms:** waiting time, up to 12 weeks, waiting list, paediatrics  
**Metadata Quality:** ~ llm (confidence: 0.70)  

#### `waiting_time_12_to_52_weeks`

**Original Name:** 12 to 52 weeks  
**Type:** integer  
**Description:** The number of open referrals on the community paediatrics waiting list waiting between 12 and 52 weeks.  
**Search Terms:** waiting time, 12 to 52 weeks, waiting list, paediatrics  
**Metadata Quality:** ~ llm (confidence: 0.70)  

#### `waiting_time_52_to_104_weeks`

**Original Name:** 52 to 104 weeks  
**Type:** integer  
**Description:** The number of open referrals on the community paediatrics waiting list waiting between 52 and 104 weeks.  
**Search Terms:** waiting time, 52 to 104 weeks, waiting list, paediatrics  
**Metadata Quality:** ~ llm (confidence: 0.70)  

#### `waiting_time_over_104_weeks`

**Original Name:** Over 104 weeks  
**Type:** integer  
**Description:** The number of open referrals on the community paediatrics waiting list waiting over 104 weeks.  
**Search Terms:** waiting time, over 104 weeks, waiting list, paediatrics  
**Metadata Quality:** ~ llm (confidence: 0.70)  

#### `waiting_time_over_52_weeks`

**Original Name:** Over 52 weeks  
**Type:** integer  
**Description:** The number of open referrals on the community paediatrics waiting list waiting over 52 weeks (this may be a duplicate or alternative aggregation).  
**Search Terms:** waiting time, over 52 weeks, waiting list, paediatrics  
**Metadata Quality:** ~ llm (confidence: 0.70)  

#### `total_waiting_list`

**Original Name:** Total waiting list  
**Type:** integer  
**Description:** The total number of open referrals on the community paediatrics waiting list.  
**Search Terms:** total, waiting list, paediatrics, overall  
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

*Generated: 2026-01-10 20:28:03*
*Source: DataWarp v2.1*
