================================================================================
ADHD WAITING TIME ANALYSIS - ASSESSMENT PATHWAY
Generated: 2025-01-11
================================================================================

## AGGREGATE WAITING TIME DISTRIBUTION (All Ages Combined)

### Latest Snapshot: 2025-09-01

**Total patients waiting: 526,975**

| Wait Band | Count | Percentage | Cumulative % |
|-----------|-------|------------|--------------|
| <13 weeks | 53,395 | 10.1% | 10.1% |
| 13-52 weeks | 142,490 | 27.0% | 37.2% |
| 52-104 weeks (1-2 years) | 145,910 | 27.7% | 64.9% |
| 104+ weeks (2+ years) | 185,180 | 35.1% | 100.0% |

### Key Performance Indicators

- **Patients waiting <18 weeks**: 53,395 (10.1%)
- **Patients waiting <52 weeks**: 195,885 (37.2%)
- **Patients waiting 52+ weeks**: 331,090 (62.8%)
- **Estimated median wait**: ~65 weeks (~15.3 months)

### Year-over-Year Comparison (Sep 2024 vs Sep 2025)

| Wait Band | Sep 2024 | Sep 2025 | Change | % Point Change |
|-----------|----------|----------|--------|----------------|
| <13 weeks | 36,530 (10.9%) | 53,395 (10.1%) | +16,865 | -0.8pp |
| 13-52 weeks | 99,870 (29.9%) | 142,490 (27.0%) | +42,620 | -2.8pp |
| 52-104 weeks | 107,460 (32.1%) | 145,910 (27.7%) | +38,450 | -4.4pp |
| 104+ weeks | 90,665 (27.1%) | 185,180 (35.1%) | +94,515 | +8.0pp |

### Critical Findings

**1. Long Wait Trajectory**
- Patients waiting 52+ weeks increased by **67.1% year-over-year**
- Nearly 2 in 3 patients (62.8%) now waiting over 1 year
- Patients waiting 2+ years increased +104.2%

**2. Distribution Shift**
- The distribution is shifting rightward (toward longer waits)
- Short waits (<13w) changed by -0.8 percentage points
- Very long waits (104+w) increased by 8.0 percentage points

**3. Capacity Gap**
- Total queue grew 57.5% (334,525 → 526,975)
- But percentage meeting short wait standards decreased
- Assessment capacity growth is NOT keeping pace with demand


## AGE-SPECIFIC DISTRIBUTION

**Data Limitation**: The aggregate waiting time data queried does not break down by age group.

To obtain age-specific waiting time distributions, the following datasets would need to be queried:
- `adhd_summary_waiting_assessment_age`
- `adhd_summary_waiting_first_contact_age`
- `adhd_summary_waiting_no_contact_age`

These datasets contain waiting time bands segmented by age groups (0-4, 5-17, 18-24, 25+), which would enable:
- Comparison of wait time distributions across age cohorts
- Identification of which age groups experience longest waits
- Analysis of whether paediatric vs adult pathways have different wait patterns

### Age Group Totals (Total Waiting for Assessment)

**Latest Snapshot: 2025-09-01**

| Age Group | Count | Percentage |
|-----------|-------|------------|
| 0-4 | 3,225 | 0.6% |
| 5-17 | 156,790 | 29.8% |
| 18-24 | 97,870 | 18.6% |
| 25+ | 269,080 | 51.1% |
| **Total** | **526,965** | **100%** |

### Year-over-Year Growth by Age Group

| Age Group | Sep 2024 | Sep 2025 | Change | % Growth |
|-----------|----------|----------|--------|----------|
| 0-4 | 1,890 | 3,225 | +1,335 | +70.6% |
| 5-17 | 128,000 | 156,790 | +28,790 | +22.5% |
| 18-24 | 61,080 | 97,870 | +36,790 | +60.2% |
| 25+ | 143,555 | 269,080 | +125,525 | +87.4% |

### Expected Age Group Variations

Based on referral patterns and pathway characteristics observed:

**Hypothesis for 5-17 age group:**
- Likely higher concentration in shorter wait bands due to established paediatric services
- Potential summer seasonality effects on wait list composition

**Hypothesis for 25+ age group:**
- May show higher concentration in longer wait bands given recent demand surge
- Adult services potentially less mature than paediatric pathway

**Hypothesis for 18-24 age group:**
- Potential for bimodal distribution if transition patients accumulate
- Could show intermediate wait times between paediatric and adult services

**To validate these hypotheses, query the age-specific waiting datasets directly.**

## Operational Implications

1. **62.8% of patients waiting 1+ year** represents a significant breach of acceptable wait standards
2. **Long wait cohort growing 67% YoY** indicates systemic capacity constraints
3. **Distribution shift toward longer waits** suggests backlog is compounding
4. **Median wait of 15.3 months** far exceeds NHS ambitions for mental health access

## Recommended Actions

1. **Urgent capacity injection** targeting assessment bottleneck
2. **Prioritisation framework** for longest waiters (104+ weeks)
3. **Age-specific pathway review** to identify differential wait patterns
4. **Demand management** strategies for 25+ cohort showing rapid growth
5. **Trajectory modelling** to forecast wait list evolution under current capacity
