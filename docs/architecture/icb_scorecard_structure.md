# ICB Scorecard Structure - Real-World Reference

**Created:** 2026-01-17 19:50 UTC
**Source:** Scorecard Reference.xlsx analysis
**Purpose:** Document the actual ICB scorecard structure to inform semantic layer design

---

## Executive Summary

**485 metrics** across **40+ domains** tracked at multiple organizational levels.

**Key Insight:** Only **37% have performance targets** - the rest are intelligence metrics for understanding patterns, identifying gaps, and benchmarking.

---

## The 4 Operational Lenses

### Lens Availability

| Lens | Metrics Available | % of Total | Purpose |
|------|-------------------|------------|---------|
| **Provider** | 432 / 485 | 89% | Monitor commissioned services performance |
| **ICB** | 445 / 485 | 91% | System-wide ICB performance |
| **Sub-ICB** | 224 / 485 | 46% | Locality/place-based analysis |
| **GP Practice** | 30 / 485 | 6% | Primary care performance |

**Plus 2 Benchmarking Lenses:**
- **Region** (94% of metrics) - Compare to regional peers
- **National** (94% of metrics) - Compare to England average

---

## Major Metric Domains

### Top 20 Domains by Metric Count

| Domain | Count | Has Targets? | Example Metrics |
|--------|-------|--------------|-----------------|
| **Cancer Waiting Times** | 85 | Yes (many) | 2 Week Classic, 28 Day Faster Diagnosis, 31 Day Combined |
| **Diagnostics** | 49 | Yes | 6 Weeks Diagnostics, 13+ Weeks Diagnostics, Audiology |
| **Ambulance Quality Indicators** | 38 | Yes | C1/C2 Response Times, Handover Times |
| **Infection Control** | 30 | Yes | C.Diff, E.Coli, MRSA |
| **FFT (Friends & Family Test)** | 27 | No | % Negative responses across services |
| **Bed Occupancy** | 22 | Yes | % Discharged on Ready Date, LoS metrics |
| **Integrated Urgent Care** | 20 | Some | 111 call handling, clinical assessment times |
| **Community Services** | 18 | Some | Virtual Ward Occupancy, Waiting Lists |
| **MHSMS (Mental Health)** | 16 | Some | CYP Eating Disorders, IAPT, Perinatal |
| **RTT (Referral to Treatment)** | 16 | Yes | 18 Week RTT, 52+ Week Waits |
| **Learning Disability Health Check** | 16 | Yes | Annual health checks, uptake rates |
| **Autism** | 13 | Some | Waiting times, assessments |
| **GP Appointments** | 12 | Some | Appointment availability, DNA rates |
| **NHS Staff Survey** | 11 | No | Staff engagement, recommendation scores |
| **Talking Therapies** | 16 | Yes | IAPT access, recovery rates |
| **DQMI (Data Quality)** | 9 | No | Completeness, timeliness indicators |
| **LAS Handovers** | 9 | Yes | Ambulance handover delays |
| **Operational Planning** | 8 | Yes | Capacity planning metrics |
| **MH Core Data Pack** | 7 | Some | Broader mental health indicators |
| **Accident & Emergency** | 7 | Yes | 4-hour waits, conversion rates, trolley waits |

---

## Mental Health / ADHD Coverage

### Current Scorecard Coverage

**Mental Health metrics (31 total):**
- **MHSMS**: 16 metrics (CYP Eating Disorders, Perinatal MH, IAPT, Early Intervention Psychosis)
- **Autism**: 13 metrics (waiting times, assessments completed)
- **Talking Therapies**: 10 monthly + 6 quarterly
- **MH Core Data Pack**: 7 metrics
- **Out of Area Placements**: 5 metrics

**ADHD specific:** Not explicitly listed in current scorecard
- **Implication:** ADHD is likely tracked within:
  - Autism metrics (diagnostic assessment overlap)
  - MH Core Data Pack (broader mental health)
  - RTT metrics (if commissioned as separate service)
  - Local ICB custom metrics (not in national template)

---

## Performance Targets vs Intelligence Metrics

### Metrics with Planning/Contract Targets: 181 / 485 (37%)

**Domains with HIGH target coverage (>75%):**
- Cancer Waiting Times
- RTT (Referral to Treatment)
- Diagnostics
- Ambulance Response Times
- A&E 4-hour waits
- Infection Control

**Domains with LOW/NO target coverage (<25%):**
- FFT (Friends & Family Test) - intelligence only
- NHS Staff Survey - engagement tracking
- DQMI - data quality monitoring
- Bed Occupancy - some targets, many intelligence
- Community - emerging standards

**Implication for Semantic Layer:**
Not every metric needs a "RAG rating" - many exist for:
- **Trend analysis** (is it improving or declining?)
- **Benchmarking** (how do we compare?)
- **Gap identification** (where do we lack capacity?)
- **Correlation analysis** (what factors drive performance?)

---

## Lens-Specific Analysis Patterns

### Provider Lens (432 metrics, 89%)

**Purpose:** Contract performance monitoring

**Key Questions:**
- Is Provider X delivering contracted volumes?
- Are they meeting quality standards?
- Cost per case vs contract price?
- Trend: improving or declining?

**Example:**
```
Provider: Norfolk & Suffolk Foundation Trust
Domain: Cancer Waiting Times
Metrics available:
  - 2 Week Classic (provider level)
  - 28 Day Faster Diagnosis (provider level)
  - 31 Day Treatment (provider level)
  - 62 Day Treatment (provider level)

Analysis:
  - Are they meeting national standards?
  - How do they compare to other cancer providers in region?
  - Trend over last 12 months?
```

---

### ICB Lens (445 metrics, 91%)

**Purpose:** System-wide performance

**Key Questions:**
- How is Norfolk ICB performing overall?
- Where do we rank nationally?
- Which areas need investment?
- Are we improving or declining?

**Example:**
```
ICB: Norfolk and Waveney
Domain: Diagnostics
Metrics:
  - 6 Weeks Diagnostics (ICB aggregate)
  - 13+ Weeks Diagnostics (ICB aggregate)

Analysis:
  - System-wide diagnostic wait times
  - Aggregate across all diagnostic providers
  - Benchmark vs East of England region
  - Benchmark vs England
  - Identify which diagnostic tests have longest waits
```

---

### Sub-ICB Lens (224 metrics, 46%)

**Purpose:** Locality/place-based commissioning

**Key Questions:**
- Which localities have longest waits?
- Where are health inequalities greatest?
- Do we need to redistribute resources between localities?

**Example:**
```
Sub-ICBs in Norfolk and Waveney:
  - Norwich
  - Great Yarmouth & Waveney
  - North Norfolk
  - West Norfolk

Metric: 28 Day Faster Diagnosis (Cancer)
Analysis:
  - Great Yarmouth: 68% (worst)
  - Norwich: 74%
  - North Norfolk: 76%
  - West Norfolk: 79% (best)

Insight: "Great Yarmouth 11 percentage points behind West Norfolk.
         Higher deprivation + distance to diagnostic center.
         Action: Mobile diagnostic unit or transport support?"
```

---

### GP Practice Lens (30 metrics, 6%)

**Purpose:** Primary care performance management

**Key Questions:**
- Which practices have high referral rates?
- Are practices delivering enhanced services?
- Patient experience at practice level?

**Example:**
```
Metric: GP Appointments - DNA Rate
Available at: GP Practice level

Analysis:
  - Practice X26: 28% DNA rate (system avg: 12%)
  - Why? Deprivation, language barriers, transport?
  - Action: Targeted support, text reminders, flexible booking
```

---

## Period Types

**Monthly:** 90% of metrics
**Quarterly:** 10% of metrics (e.g., Ambulance C1 quarterly average, Talking Therapies quarterly)

**Implication:** Semantic layer must handle:
- Month-to-month comparisons
- Quarterly rolling averages
- Year-on-year trends
- Year-to-date aggregations

---

## Semantic Layer Requirements Based on Real Scorecard

### 1. Multi-Lens Navigation

Agents must query by lens:
```python
# Provider lens
query_metric(
    metric="A&E Type 1 - 4 Hour Wait",
    lens="provider",
    provider="Norfolk and Norwich University Hospital",
    period="2024-10"
)

# ICB lens (aggregated)
query_metric(
    metric="A&E Type 1 - 4 Hour Wait",
    lens="icb",
    icb="Norfolk and Waveney",
    period="2024-10"
)

# Sub-ICB lens
query_metric(
    metric="28 Day Faster Diagnosis",
    lens="sub_icb",
    sub_icb="Great Yarmouth & Waveney",
    period="2024-10"
)
```

---

### 2. Benchmarking at Every Level

```python
benchmark_metric(
    metric="RTT 18 Weeks",
    lens="icb",
    icb="Norfolk and Waveney",
    benchmark_against=["region", "national", "similar_icbs"]
)

Returns:
{
    "icb_value": 68.5,
    "regional_average": 72.3,
    "national_average": 71.8,
    "similar_icbs": {
        "Suffolk": 70.2,
        "Cambridgeshire": 74.1,
        "Lincolnshire": 69.8
    },
    "percentile": 42,  # 42nd percentile nationally
    "ranking": "62nd of 106 ICBs"
}
```

---

### 3. Domain-Level Intelligence

```python
get_domain_summary(
    domain="Cancer Waiting Times",
    lens="icb",
    icb="Norfolk and Waveney",
    period="2024-10"
)

Returns:
{
    "domain": "Cancer Waiting Times",
    "total_metrics": 85,
    "metrics_with_targets": 67,
    "rag_summary": {
        "red": 12,  # Missing target
        "amber": 23,  # Close to target
        "green": 32,  # Meeting target
        "no_target": 18  # Intelligence metrics only
    },
    "key_concerns": [
        "2 Week Breast Symptomatic: 78.2% (target 93%)",
        "62 Day Treatment: 64.1% (target 85%)"
    ],
    "key_successes": [
        "28 Day Faster Diagnosis: 89.3% (target 75%)",
        "31 Day Treatment: 97.8% (target 96%)"
    ]
}
```

---

### 4. Intelligence vs Performance Distinction

```yaml
metric_definition:
  name: "FFT % Negative AE"
  domain: "FFT"
  has_target: false
  purpose: "intelligence"  # NOT performance management
  use_cases:
    - "Identify services with declining patient experience"
    - "Correlate with other quality metrics"
    - "Trend analysis"
    - "Early warning of quality issues"

  # Don't RAG rate this
  # Don't trigger alerts on thresholds
  # DO use for correlation analysis
  # DO use for trend detection
```

---

### 5. Cross-Domain Analysis

```python
# "Is there correlation between staff satisfaction and patient outcomes?"

analyze_correlation(
    metric_x="NHS Staff Survey - Recommendation Score",
    metric_y="FFT % Negative AE",
    lens="provider",
    period_range="2023-01 to 2024-10"
)

Returns:
{
    "correlation": -0.58,
    "p_value": 0.002,
    "interpretation": "Moderate negative correlation - providers with higher staff satisfaction have lower negative FFT scores (better patient experience)",
    "providers_analyzed": 18,
    "insight": "Staff engagement programs may improve patient experience"
}
```

---

## DataWarp Mapping Challenge

### Current DataWarp Coverage

From existing publications in publications_v2.yaml:
- ✅ ADHD (custom data, not in standard scorecard)
- ✅ PCN Workforce (custom, not in scorecard)
- ✅ GP Appointments (12 metrics in scorecard - partial coverage)
- ✅ Online Consultations (not in standard scorecard)
- ❌ A&E (7 metrics - not covered)
- ❌ Cancer (85 metrics - not covered)
- ❌ Diagnostics (49 metrics - not covered)
- ❌ RTT (16 metrics - not covered)
- ❌ Ambulance (38 metrics - not covered)

**Gap:** DataWarp currently covers ~5% of standard ICB scorecard metrics

**Opportunity:** The semantic layer design must work for:
1. Current custom metrics (ADHD, Workforce, GP Appts)
2. Future standard scorecard metrics (485 total)
3. Mix of targeted and intelligence metrics

---

## Key Insights for Semantic Layer Design

### 1. Don't Force RAG Ratings

63% of metrics have no targets - they're for intelligence:
- Trend analysis
- Benchmarking
- Gap identification
- Correlation studies

**Design for both:**
- Performance metrics (with targets, RAG, alerts)
- Intelligence metrics (trends, correlations, exploration)

---

### 2. Lens-Aware Query Tools

Same metric, different lens = different question:

**Provider lens:** "Is this provider delivering?"
**ICB lens:** "How is the system performing?"
**Sub-ICB lens:** "Which localities need support?"
**GP Practice lens:** "Which practices are outliers?"

**MCP tools must accept `lens` parameter**

---

### 3. Benchmarking is Core, Not Optional

Almost all metrics available at Region/National level → benchmarking is fundamental to ICB analysis

**Every metric query should optionally return benchmarks**

---

### 4. Domain Summaries Over Individual Metrics

85 cancer metrics, 49 diagnostic metrics → users need domain-level dashboards, not 485 individual charts

**Provide domain aggregation tools**

---

### 5. Period Handling

Monthly/Quarterly/YTD variations → semantic layer must handle:
- `get_latest_period(metric)`
- `compare_periods(metric, ["2024-09", "2024-10"])`
- `ytd_aggregate(metric, year=2024)`

---

## Next Steps for Semantic Layer

1. **Extend Step 6 (Populate Metadata)** to include:
   - Lens availability flags
   - Has target (yes/no)
   - Purpose (performance/intelligence)
   - Domain classification
   - Benchmark availability

2. **Extend Step 7 (Query Tools)** to include:
   - Lens-aware queries
   - Benchmarking functions
   - Domain summaries
   - Correlation analysis

3. **Create mapping** from DataWarp sources → Scorecard metrics
   - Which ADHD tables map to which (potential) scorecard metrics?
   - How to extend to cover standard scorecard in future?

---

**Key Takeaway:** ICB scorecards are multi-dimensional intelligence systems, not just performance dashboards. The semantic layer must enable exploration and correlation analysis, not just RAG ratings.

