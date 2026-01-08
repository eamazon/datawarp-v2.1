# ADHD Summary: Discharged Referrals by Waiting Time

**Dataset:** `adhd_summary_discharged_referrals_waiting_time`
**Domain:** Clinical - Mental Health
**Rows:** 13
**Columns:** 9

---

## Purpose

No description available.

---

## Coverage

- **Date Range:** 2024-06-01 to 2025-06-01
- **Rows in Export:** 13
- **Load History:** 0 loads, 0 total rows
- **Geographic Scope:** NHS Wales (All Health Boards)

---

## Columns

### Dimensions (Grouping Columns)

#### `date_val`

**Original Name:** Date  
**Type:** character varying  
**Description:** The date of the data recording.  
**Search Terms:** date, period  
**Metadata Quality:** ~ llm (confidence: 0.70)  


### Measures (Numeric Metrics)

#### `waiting_time_up_to_13_weeks_count`

**Original Name:** Waiting time Up to 13 weeks  
**Type:** integer  
**Description:** Number of discharged referrals waiting up to 13 weeks.  
**Search Terms:** waiting time, up to 13 weeks, referrals, discharged, count  
**Metadata Quality:** ~ llm (confidence: 0.70)  

#### `waiting_time_13_to_52_weeks`

**Original Name:** 13 to 52 weeks  
**Type:** integer  
**Description:** Number of discharged referrals waiting between 13 and 52 weeks.  
**Search Terms:** waiting time, 13 to 52 weeks, referrals, discharged, count  
**Metadata Quality:** ~ llm (confidence: 0.70)  

#### `waiting_time_52_to_104_weeks`

**Original Name:** 52 to 104 weeks  
**Type:** integer  
**Description:** Number of discharged referrals waiting between 52 and 104 weeks.  
**Search Terms:** waiting time, 52 to 104 weeks, referrals, discharged, count  
**Metadata Quality:** ~ llm (confidence: 0.70)  

#### `waiting_time_104_weeks_or_more`

**Original Name:** 104 weeks or more  
**Type:** integer  
**Description:** Number of discharged referrals waiting 104 weeks or more.  
**Search Terms:** waiting time, 104+ weeks, referrals, discharged, count  
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

*Generated: 2026-01-08 21:56:09*
*Source: DataWarp v2.1*
