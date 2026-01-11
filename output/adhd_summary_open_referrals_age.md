# ADHD Summary: Open Referrals by Age

**Dataset:** `adhd_summary_open_referrals_age`
**Domain:** Clinical - Mental Health
**Rows:** 26
**Columns:** 12

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


### Measures (Numeric Metrics)

#### `age_0_to_4_referral_count`

**Original Name:** Age 0 to 4  
**Type:** integer  
**Description:** The number of open referrals for individuals aged 0 to 4.  
**Search Terms:** age 0 to 4, children, referrals  
**Metadata Quality:** ~ llm (confidence: 0.70)  

#### `age_5_to_17`

**Original Name:** 5 to 17  
**Type:** integer  
**Description:** The number of open referrals for individuals aged 5 to 17.  
**Search Terms:** age 5 to 17, children, referrals  
**Metadata Quality:** ~ llm (confidence: 0.70)  

#### `age_18_to_24`

**Original Name:** 18 to 24  
**Type:** integer  
**Description:** The number of open referrals for individuals aged 18 to 24.  
**Search Terms:** age 18 to 24, young adults, referrals  
**Metadata Quality:** ~ llm (confidence: 0.70)  

#### `age_25`

**Original Name:** 25+  
**Type:** integer  
**Description:** The number of open referrals for individuals aged 25 and over.  
**Search Terms:** age 25+, adults, referrals  
**Metadata Quality:** ~ llm (confidence: 0.70)  

#### `unknown`

**Original Name:** Unknown  
**Type:** integer  
**Description:** The number of open referrals where the age group is unknown.  
**Search Terms:** unknown age, referrals  
**Metadata Quality:** ~ llm (confidence: 0.70)  

#### `total`

**Original Name:** Total  
**Type:** integer  
**Description:** The total number of open referrals.  
**Search Terms:** total, open referrals, overall  
**Metadata Quality:** ~ llm (confidence: 0.70)  

#### `age_0_to_4`

**Original Name:** Age 0 to 4  
**Type:** integer  
**Description:** The number of open referrals for individuals aged 0 to 4.  
**Search Terms:** age 0 to 4, children, referrals  
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

*Generated: 2026-01-11 16:58:53*
*Source: DataWarp v2.1*
