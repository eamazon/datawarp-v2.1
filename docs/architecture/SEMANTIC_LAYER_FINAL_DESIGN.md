# Semantic Layer - Final Design Specification

**Created:** 2026-01-17 20:10 UTC
**Status:** Complete specification ready for implementation
**Purpose:** Complete semantic layer design aligned with real ICB scorecard structure

---

## Design Documents Reference

This is the master design. Supporting documents:

1. **`icb_scorecard_structure.md`** - Analysis of real ICB scorecard (485 metrics, 4 lenses)
2. **`metadata_driven_reporting.md`** - Metadata-driven query implementation
3. **`super_dataset_simple.md`** - Alternative approaches considered (reference only)

---

## Executive Summary

**Goal:** Enable ICB commissioning intelligence through 4-layer semantic architecture

**Approach:** Metadata-driven (not materialized views or manual configs)

**Time to implement:** ~10 hours (Steps 6-9 in agentic roadmap)

---

## The 4-Layer Architecture

```
LAYER 4: Executive Intelligence
  └─ Pre-defined business KPIs, RAG ratings, insights
         ↓ "Why is this happening?"

LAYER 3: Analytical Exploration
  └─ Lens-aware flexible querying, drill-down capabilities
         ↓ "What's coming next?"

LAYER 2: Predictive Analytics
  └─ Forecasting, trend analysis, early warnings
         ↓ "What factors drive this?"

LAYER 1: Causal Analysis
  └─ Correlation studies, what-if scenarios, recommendations
```

---

## The 4-Lens Model (Real ICB Structure)

### Organizational Lenses

| Lens | Purpose | Availability | Example Question |
|------|---------|--------------|------------------|
| **Provider** | Contract monitoring | 89% of metrics | "Is Provider X delivering on quality standards?" |
| **ICB** | System performance | 91% of metrics | "How is our ICB performing vs England?" |
| **Sub-ICB** | Locality analysis | 46% of metrics | "Which localities have longest waits?" |
| **GP Practice** | Primary care | 6% of metrics | "Which practices are outliers?" |

**Plus benchmarking:**
- **Region**: Compare to East of England peers
- **National**: Compare to England average

### Lens-Aware Queries

```python
# Same metric, different lens = different insight

# Provider lens - contract monitoring
query_metric(
    metric="adhd_waiting_time_weeks",
    lens="provider",
    provider_code="RNQ",  # Norfolk & Suffolk FT
    period="2024-10"
)
→ "Norfolk & Suffolk FT: 42 weeks (contract target: 18 weeks)"

# ICB lens - system performance
query_metric(
    metric="adhd_waiting_time_weeks",
    lens="icb",
    icb_code="QMM",  # Norfolk & Waveney ICB
    period="2024-10"
)
→ "Norfolk & Waveney ICB: 38 weeks average (national: 24 weeks)"

# Sub-ICB lens - locality analysis
query_metric(
    metric="adhd_waiting_time_weeks",
    lens="sub_icb",
    sub_icb_code="QMM01",  # Great Yarmouth
    period="2024-10"
)
→ "Great Yarmouth: 52 weeks (worst in Norfolk, +37% vs ICB average)"

# GP Practice lens - outlier identification
query_metric(
    metric="adhd_referral_rate_per_1000",
    lens="gp_practice",
    practice_code="X26",
    period="2024-10"
)
→ "Practice X26: 28.4 per 1000 (ICB average: 9.2, outlier flagged)"
```

---

## Performance vs Intelligence Metrics

### Real ICB Scorecard Split

- **37% have targets** → Performance metrics (RAG ratings, alerts)
- **63% are intelligence** → Trend analysis, correlation, exploration

### Design Implications

**Performance Metrics:**
```json
{
  "metric": "rtt_18_weeks_compliance",
  "has_target": true,
  "target_value": 92.0,
  "target_direction": "higher_better",
  "rag_thresholds": {
    "red": "< 85%",
    "amber": "85-92%",
    "green": ">= 92%"
  },
  "alert_on_breach": true
}
```

**Intelligence Metrics:**
```json
{
  "metric": "fft_negative_ae_percentage",
  "has_target": false,
  "metric_type": "intelligence",
  "use_cases": [
    "Trend analysis - is patient experience improving?",
    "Correlation - link to staff satisfaction?",
    "Benchmarking - compare to peers",
    "Early warning - sudden spike indicates quality issue"
  ],
  "do_not_rag_rate": true  // No alerts, just intelligence
}
```

---

## Enhanced Metadata Schema

### Dataset-Level Metadata (tbl_canonical_sources.metadata JSONB)

```json
{
  "domain": "mental_health",
  "scorecard_category": "MHSMS",

  "organizational_lenses": {
    "provider": false,
    "icb": true,
    "sub_icb": true,
    "gp_practice": true,
    "region": true,
    "national": true
  },

  "kpis": [
    {
      "column": "adhd_waiting_time_weeks",
      "label": "ADHD Waiting Time",
      "description": "Average weeks from referral to first assessment",
      "unit": "weeks",
      "aggregation": "weighted_average",

      "has_target": true,
      "target_value": 18,
      "target_direction": "lower_better",
      "target_source": "NHS England Operating Guidance 2024/25",

      "metric_type": "performance",
      "benchmark_sources": ["national_average", "regional_average", "icb_peers"],
      "query_keywords": ["adhd", "waiting", "time", "weeks", "assessment"]
    },
    {
      "column": "adhd_prevalence_rate",
      "label": "ADHD Prevalence Rate",
      "description": "Percentage of registered population with ADHD diagnosis",
      "unit": "percentage",
      "aggregation": "weighted_average",

      "has_target": false,
      "metric_type": "intelligence",
      "benchmark_sources": ["national_average", "regional_average"],
      "query_keywords": ["adhd", "prevalence", "diagnosis", "rate"]
    }
  ],

  "dimensions": [
    {
      "column": "geography_level",
      "type": "organizational_lens",
      "values": ["icb", "sub_icb", "gp_practice"]
    },
    {
      "column": "time_period",
      "type": "temporal",
      "format": "YYYY-MM",
      "frequency": "monthly"
    },
    {
      "column": "age_band",
      "type": "demographic",
      "values": ["0-17", "18-64", "65+", "All"]
    }
  ],

  "data_quality": {
    "completeness": 0.98,
    "timeliness_lag_weeks": 6,
    "last_updated": "2024-10-15"
  }
}
```

---

## MCP Tools - Complete Specification

### Layer 4: Executive Intelligence Tools

#### 1. `get_kpi_status()`

```python
def get_kpi_status(
    kpi: str,
    lens: str,
    lens_value: str,
    period: str = "latest",
    include_trend: bool = True,
    include_benchmark: bool = True
) -> Dict:
    """Get KPI status with RAG rating, trend, and benchmarks."""
```

**Example:**
```python
get_kpi_status(
    kpi="adhd_waiting_time_weeks",
    lens="icb",
    lens_value="QMM",  # Norfolk & Waveney
    period="2024-10"
)

Returns:
{
    "kpi": "ADHD Waiting Time",
    "value": 38,
    "unit": "weeks",
    "period": "2024-10",

    "target": {
        "value": 18,
        "direction": "lower_better",
        "variance": +111,  # 111% above target
        "rag_status": "red"
    },

    "trend": {
        "previous_period": 35,
        "change": +3,
        "change_pct": 8.6,
        "direction": "worsening",
        "12_month_trend": "deteriorating"  # vs 28 weeks in Oct 2023
    },

    "benchmark": {
        "national_average": 24,
        "variance_from_national": +58.3,
        "regional_average": 26,
        "variance_from_regional": +46.2,
        "percentile": 18,  # 18th percentile (worse than 82% of ICBs)
        "ranking": "87th of 106 ICBs"
    },

    "insight": "Critical performance gap. Norfolk 111% above target and 58% above national average. Deteriorating trend (+8.6% from last month). Ranked 87th of 106 ICBs. Urgent intervention required."
}
```

---

#### 2. `get_domain_scorecard()`

```python
def get_domain_scorecard(
    domain: str,
    lens: str,
    lens_value: str,
    period: str = "latest"
) -> Dict:
    """Get executive summary for entire domain (e.g., Mental Health, Cancer)."""
```

**Example:**
```python
get_domain_scorecard(
    domain="mental_health",
    lens="icb",
    lens_value="QMM",
    period="2024-10"
)

Returns:
{
    "domain": "Mental Health",
    "total_metrics": 16,
    "period": "2024-10",

    "rag_summary": {
        "metrics_with_targets": 8,
        "red": 3,
        "amber": 2,
        "green": 3,
        "intelligence_only": 8
    },

    "critical_concerns": [
        {
            "kpi": "ADHD Waiting Time",
            "value": 38,
            "target": 18,
            "rag": "red",
            "variance": "+111%"
        },
        {
            "kpi": "EIP 2 Week Access",
            "value": 52,
            "target": 60,
            "rag": "amber",
            "variance": "-13%"
        }
    ],

    "key_successes": [
        {
            "kpi": "IAPT Recovery Rate",
            "value": 53.2,
            "target": 50,
            "rag": "green",
            "variance": "+6.4%"
        }
    ],

    "overall_assessment": "Mixed performance. 3 critical gaps (ADHD, CYP Eating Disorders, Perinatal Access). 3 areas meeting/exceeding targets. Overall trend: deteriorating on access metrics, improving on outcomes."
}
```

---

### Layer 3: Analytical Exploration Tools

#### 3. `query_metric()` - Lens-aware flexible query

```python
def query_metric(
    metric: str,
    lens: str,
    filters: Dict,
    aggregation: str = None,
    period_range: str = None
) -> Dict:
    """Query any metric at any lens with flexible filters."""
```

**Example - Provider drill-down:**
```python
query_metric(
    metric="adhd_waiting_time_weeks",
    lens="provider",
    filters={
        "icb_code": "QMM",  # All providers in Norfolk ICB
        "period": "2024-10"
    }
)

Returns:
{
    "metric": "ADHD Waiting Time",
    "lens": "provider",
    "period": "2024-10",
    "results": [
        {"provider": "Norfolk & Suffolk FT", "value": 42},
        {"provider": "East Coast Community", "value": 28},
        {"provider": "Primary Care (PCN-managed)", "value": 12}
    ],
    "insight": "Norfolk & Suffolk FT significantly worse than other providers. Primary care managed cases much faster."
}
```

---

#### 4. `drill_down()` - Navigate lens hierarchy

```python
def drill_down(
    metric: str,
    from_lens: str,
    from_value: str,
    to_lens: str,
    period: str
) -> Dict:
    """Drill from ICB → Sub-ICB → Provider → GP Practice."""
```

**Example:**
```python
drill_down(
    metric="adhd_referral_rate_per_1000",
    from_lens="icb",
    from_value="QMM",
    to_lens="sub_icb",
    period="2024-10"
)

Returns:
{
    "metric": "ADHD Referral Rate",
    "drilled_from": "Norfolk & Waveney ICB (9.2 per 1000)",
    "drilled_to": "Sub-ICB localities",
    "results": [
        {"sub_icb": "Great Yarmouth", "value": 14.8, "variance": "+60.9%"},
        {"sub_icb": "Norwich", "value": 11.2, "variance": "+21.7%"},
        {"sub_icb": "West Norfolk", "value": 6.8, "variance": "-26.1%"},
        {"sub_icb": "North Norfolk", "value": 7.1, "variance": "-22.8%"}
    ],
    "insight": "Great Yarmouth 61% above ICB average. Investigate high referral drivers."
}
```

---

### Layer 2: Predictive Analytics Tools

#### 5. `forecast_demand()`

```python
def forecast_demand(
    metric: str,
    lens: str,
    lens_value: str,
    forecast_periods: int = 4
) -> Dict:
    """Time series forecasting with confidence intervals."""
```

**Example:**
```python
forecast_demand(
    metric="adhd_referrals",
    lens="icb",
    lens_value="QMM",
    forecast_periods=4  # Next 4 quarters
)

Returns:
{
    "metric": "ADHD Referrals",
    "historical_trend": {
        "q1_2024": 1800,
        "q2_2024": 1920,
        "q3_2024": 2016,
        "growth_rate": "12% per quarter"
    },

    "forecast": {
        "q4_2024": {"predicted": 2156, "confidence_95": [2020, 2292]},
        "q1_2025": {"predicted": 2298, "confidence_95": [2140, 2456]},
        "q2_2025": {"predicted": 2445, "confidence_95": [2265, 2625]},
        "q3_2025": {"predicted": 2603, "confidence_95": [2395, 2811]}
    },

    "capacity_gap": {
        "current_capacity": 1200,
        "q2_2025_gap": 1245,  # 104% shortfall
        "projected_wait_time": "60+ weeks by Q2 2025"
    },

    "early_warning": "CRITICAL: Demand will double capacity by Q2 2025. System failure imminent without intervention."
}
```

---

#### 6. `detect_anomalies()`

```python
def detect_anomalies(
    metric: str,
    lens: str,
    period_range: str = "last_12_months"
) -> Dict:
    """Statistical outlier detection."""
```

---

### Layer 1: Causal Analysis Tools

#### 7. `analyze_correlation()`

```python
def analyze_correlation(
    metric_x: str,
    metric_y: str,
    lens: str,
    period_range: str
) -> Dict:
    """Multi-variate regression analysis."""
```

**Example:**
```python
analyze_correlation(
    metric_x="gp_fte_per_10k_population",
    metric_y="adhd_waiting_time_weeks",
    lens="icb",  # Analyze across all 106 ICBs
    period_range="2024-q3"
)

Returns:
{
    "correlation": -0.62,
    "p_value": 0.0001,
    "significance": "high",
    "r_squared": 0.38,

    "interpretation": "Strong negative correlation - ICBs with more GPs have significantly shorter ADHD waits. GP staffing explains 38% of variance in wait times.",

    "regression_equation": "wait_time = 85.3 - (7.2 × gp_fte)",

    "practical_impact": "Each additional GP FTE per 10k population reduces wait time by 7.2 weeks on average.",

    "norfolk_analysis": {
        "current_gp_fte": 4.2,
        "current_wait_time": 38,
        "predicted_with_national_avg_gp": 26,  # If had 5.8 FTE like national avg
        "gap_explained_by_gp_staffing": "12 weeks (32% of total wait)"
    }
}
```

---

#### 8. `scenario_model()`

```python
def scenario_model(
    intervention: Dict,
    target_metric: str,
    lens: str,
    lens_value: str,
    forecast_periods: int = 4
) -> Dict:
    """What-if scenario modeling."""
```

**Example:**
```python
scenario_model(
    intervention={
        "type": "workforce_increase",
        "resource": "specialist_nurses",
        "increase_fte": 2.0,
        "cost_per_fte": 42500
    },
    target_metric="adhd_waiting_time_weeks",
    lens="icb",
    lens_value="QMM",
    forecast_periods=4
)

Returns:
{
    "scenario": "Hire 2.0 FTE Specialist Nurses",

    "current_state": {
        "specialist_nurses": 3.2,
        "capacity_per_year": 1200,
        "wait_time": 38
    },

    "projected_state": {
        "specialist_nurses": 5.2,
        "capacity_per_year": 1680,
        "wait_time": 26,
        "improvement": "-31.6%"
    },

    "costs": {
        "annual": 85000,
        "5_year_total": 425000
    },

    "benefits": {
        "patients_cleared_per_year": 480,
        "cost_per_patient": 177,
        "time_to_target": "Still above 18 week target - need 3.5 FTE"
    },

    "recommendation": "Insufficient. Hire 3.5 FTE (not 2.0) to reach target."
}
```

---

## Implementation Roadmap

### Step 6: Populate Metadata (1 hour)

**Script:** `scripts/populate_icb_metadata.py`

```python
def populate_icb_metadata():
    """Extract from tbl_column_metadata, enrich with ICB context."""

    for source_code in get_all_sources():
        # Get measures and dimensions
        measures = get_measures(source_code)
        dimensions = get_dimensions(source_code)

        # Infer organizational lenses from data
        lenses = infer_lenses_from_columns(dimensions)

        # Classify metric type (performance vs intelligence)
        for measure in measures:
            has_target = check_if_has_target(measure)  # Heuristic or manual config

        # Build metadata JSONB
        metadata = {
            "domain": classify_domain(source_code),
            "organizational_lenses": lenses,
            "kpis": enrich_kpis(measures),
            "dimensions": enrich_dimensions(dimensions)
        }

        # Update tbl_canonical_sources
        update_metadata(source_code, metadata)
```

**Run:** `python scripts/populate_icb_metadata.py --all`

---

### Step 7: Enhanced MCP Tools (4 hours)

**File:** `mcp_server/stdio_server.py`

Add 8 new tools (listed above) organized by layer.

---

### Step 8: Predictive Analytics Engine (2 hours)

**File:** `src/datawarp/analytics/forecast.py`

Simple time series forecasting (ARIMA or Prophet library).

---

### Step 9: Causal Analysis Engine (2 hours)

**File:** `src/datawarp/analytics/correlation.py`

Multi-variate regression using scipy/statsmodels.

---

## Testing Strategy

### Unit Tests

```python
def test_lens_aware_query():
    result = query_metric(
        metric="adhd_waiting_time",
        lens="provider",
        filters={"provider_code": "RNQ"}
    )
    assert result["value"] > 0
    assert result["lens"] == "provider"

def test_benchmark_calculation():
    result = get_kpi_status(
        kpi="adhd_waiting_time",
        lens="icb",
        lens_value="QMM",
        include_benchmark=True
    )
    assert "benchmark" in result
    assert "national_average" in result["benchmark"]
```

### Integration Tests

Real-world scenarios using ADHD data:

1. Executive asking "How is Norfolk performing on ADHD?"
2. Commissioner asking "Which locality needs investment?"
3. Analyst asking "What's driving long waits?"
4. Planner asking "What capacity do we need next year?"

---

## Success Metrics

| Capability | Before | After |
|------------|--------|-------|
| MCP calls to answer "How's our performance?" | N/A (manual analysis) | 1 call |
| Time to benchmark ICB vs peers | 30 min (manual Excel) | 10 sec |
| Lens-based analysis | Not possible | 4 lenses × 485 metrics |
| Predictive forecasting | Manual spreadsheets | Automated |
| What-if scenarios | Not available | Automated |

---

## Documentation Complete

This design is ready for implementation. All aspects documented:

- ✅ Real ICB scorecard analysis (`icb_scorecard_structure.md`)
- ✅ 4-lens model specification
- ✅ Performance vs intelligence distinction
- ✅ Enhanced metadata schema
- ✅ Complete MCP tool specifications
- ✅ Implementation roadmap
- ✅ Testing strategy

**Next step:** Implement Step 6 (`populate_icb_metadata.py`)

