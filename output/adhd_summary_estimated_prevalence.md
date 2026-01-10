# ADHD Summary: Estimated Prevalence

**Dataset:** `adhd_summary_estimated_prevalence`
**Domain:** Clinical - Mental Health
**Rows:** 5
**Columns:** 11

---

## Purpose

No description available.

---

## Coverage

- **Date Range:** 2024-08-01 to 2025-08-01
- **Rows in Export:** 5
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

#### `age_0_to_4_count`

**Original Name:** Age 0 to 4  
**Type:** integer  
**Description:** The estimated number of individuals aged 0 to 4 with ADHD.  
**Search Terms:** age 0 to 4, children, prevalence  
**Metadata Quality:** ~ llm (confidence: 0.70)  

#### `age_5_to_17`

**Original Name:** 5 to 17  
**Type:** integer  
**Description:** The estimated number of individuals aged 5 to 17 with ADHD.  
**Search Terms:** age 5 to 17, children, prevalence  
**Metadata Quality:** ~ llm (confidence: 0.70)  

#### `age_18_to_24`

**Original Name:** 18 to 24  
**Type:** integer  
**Description:** The estimated number of individuals aged 18 to 24 with ADHD.  
**Search Terms:** age 18 to 24, young adults, prevalence  
**Metadata Quality:** ~ llm (confidence: 0.70)  

#### `age_25`

**Original Name:** 25+  
**Type:** integer  
**Description:** The estimated number of individuals aged 25 and over with ADHD.  
**Search Terms:** age 25+, adults, prevalence  
**Metadata Quality:** ~ llm (confidence: 0.70)  

#### `total`

**Original Name:** Total  
**Type:** integer  
**Description:** The total estimated number of individuals with ADHD.  
**Search Terms:** total, count, prevalence  
**Metadata Quality:** ~ llm (confidence: 0.70)  

#### `age_0_to_4`

**Original Name:** Age 0 to 4  
**Type:** integer  
**Description:** The estimated number of individuals aged 0 to 4 with ADHD.  
**Search Terms:** age 0 to 4, children, prevalence  
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

*Generated: 2026-01-10 00:24:48*
*Source: DataWarp v2.1*
