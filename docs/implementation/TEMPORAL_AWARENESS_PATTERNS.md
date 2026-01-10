# Temporal Awareness Patterns for Domain-Driven Systems

**Created: 2026-01-10 Evening (Session 7)**
**Context:** Educational discussion following GP Practice fiscal boundary discovery

---

## The Discovery

**What we found:** NHS GP Practice Registrations show a **fiscal boundary effect**:
- March 2025: 6 sources (baseline)
- April 2025: 9 sources (+3 LSOA geographical sources)
- May 2025: 6 sources (LSOA sources disappear)

**The insight:** April isn't just "another month" - it's a **business event** (UK fiscal year start) that triggers predictable schema changes.

**The question:** How do we build this thinking into applications?

---

## Core Concept: Domain Calendars

**Traditional approach (bad):**
- Treat all time periods uniformly
- January = April = December
- Schema changes are "surprises"

**Domain-aware approach (good):**
- Recognize certain dates have special business meaning
- Fiscal boundaries, quarter-ends, annual reporting cycles
- Schema changes are **expected patterns**

---

## Pattern 1: Domain Calendar Encoding

**Principle:** Make implicit temporal rules explicit in code

### Implementation

```python
from datetime import datetime
import calendar

class DomainCalendar:
    """Encode domain-specific temporal knowledge"""

    @staticmethod
    def is_fiscal_boundary(date: datetime) -> bool:
        """April 1st starts UK fiscal year"""
        return date.month == 4 and date.day == 1

    @staticmethod
    def is_quarter_end(date: datetime) -> bool:
        """Last day of quarter"""
        return date.month in [3, 6, 9, 12] and \
               date.day == calendar.monthrange(date.year, date.month)[1]

    @staticmethod
    def is_annual_reporting_period(date: datetime) -> bool:
        """April-May is when annual data gets published"""
        return date.month in [4, 5]

    @staticmethod
    def expected_schema_volatility(date: datetime) -> str:
        """Predict schema stability based on domain calendar"""
        if DomainCalendar.is_fiscal_boundary(date):
            return "HIGH"  # Expect new fields, tables
        elif DomainCalendar.is_quarter_end(date):
            return "MEDIUM"  # Expect some additions
        else:
            return "LOW"  # Schema should be stable
```

**Software Principle:** **Ubiquitous Language** (Domain-Driven Design)
- Encode business knowledge in code
- Make implicit rules explicit
- Industry use: Banking, healthcare, government systems

### Usage Example

```python
from datetime import datetime

date = datetime(2024, 4, 1)
volatility = DomainCalendar.expected_schema_volatility(date)
print(f"Schema volatility for April 1: {volatility}")
# Output: "HIGH"

# Use this to inform load strategies
if volatility == "HIGH":
    load_mode = "REPLACE"  # Safe for fiscal boundaries
elif volatility == "MEDIUM":
    load_mode = "REPLACE_OR_APPEND"  # Check pattern
else:
    load_mode = "APPEND"  # Schema stable
```

---

## Pattern 2: Schema Versioning with Business Context

**Principle:** Version schemas by business events, not sequential numbers

### Bad Approach (Generic Versioning)

```python
# Loses domain context
schema_v1 = "baseline"
schema_v2 = "added_fields"  # When? Why? What triggered this?
schema_v3 = "more_changes"  # No business meaning
```

### Good Approach (Business Event Versioning)

```python
class SchemaVersion:
    """Schema versions tied to business events"""

    BASELINE = "FY2023_Q4"  # Fiscal Year 2023 Q4
    FISCAL_2024 = "FY2024_Q1_FISCAL_EXPANSION"  # April 2024 - LSOA added
    POST_FISCAL_2024 = "FY2024_Q2_STABILIZED"  # May 2024 - LSOA removed

    @classmethod
    def for_date(cls, date: datetime) -> str:
        """Get schema version based on domain calendar"""
        if date < datetime(2024, 4, 1):
            return cls.BASELINE
        elif date.month == 4 and date.year == 2024:
            return cls.FISCAL_2024  # Expect LSOA fields
        else:
            return cls.POST_FISCAL_2024  # LSOA fields gone

# Usage
schema = SchemaVersion.for_date(datetime(2024, 4, 15))
# Returns: "FY2024_Q1_FISCAL_EXPANSION"
# Developer knows: "Ah, April fiscal boundary - expect extra fields"
```

**Benefits:**
- Version names convey business meaning
- Easy to reason about changes
- Self-documenting code
- Clear communication with stakeholders

**Software Principle:** **Semantic Versioning with Domain Context**

---

## Pattern 3: Anticipatory Data Modeling

**Principle:** Model data to handle known periodic variations

### Bad Approach (Flat Schema)

```python
class PatientRegistration:
    practice_code: str
    patient_count: int
    age_bands: dict
    # What happens when LSOA fields appear in April?
    # Schema breaks or requires migration
```

### Good Approach (Anticipatory Schema)

```python
from typing import Optional
from dataclasses import dataclass
from datetime import datetime

@dataclass
class FiscalYearData:
    """April-only data - separate model"""
    lsoa_2011_breakdown: dict
    lsoa_2021_breakdown: dict
    geographic_analysis: dict

    @classmethod
    def is_available(cls, date: datetime) -> bool:
        """LSOA data only published in April"""
        return date.month == 4

@dataclass
class PatientRegistration:
    # Core fields (always present)
    practice_code: str
    patient_count: int
    age_bands: dict

    # Fiscal year extensions (April only)
    fiscal_extensions: Optional[FiscalYearData] = None

    @classmethod
    def from_publication(cls, date: datetime, data: dict):
        """Load data with awareness of fiscal patterns"""
        base = cls(
            practice_code=data['code'],
            patient_count=data['count'],
            age_bands=data['age']
        )

        # Add fiscal data if April
        if FiscalYearData.is_available(date):
            base.fiscal_extensions = FiscalYearData(
                lsoa_2011_breakdown=data.get('lsoa_2011', {}),
                lsoa_2021_breakdown=data.get('lsoa_2021', {}),
                geographic_analysis=data.get('geo_analysis', {})
            )

        return base
```

**Benefits:**
- Schema is **resilient** to known temporal variations
- No migrations needed for predictable changes
- Optional fields make expectations explicit

---

## Pattern 4: Configuration-Driven Temporal Rules

**Principle:** Make temporal rules configurable, not hardcoded

### Publication Schedule Configuration

```yaml
# config/publication_schedule.yaml
publications:
  gp_practice_registrations:
    frequency: monthly
    base_sources: 6

    special_periods:
      - trigger: fiscal_year_start  # April
        additional_sources:
          - code: prac_lsoa_all
            reason: "Annual LSOA geography breakdown"
          - code: prac_lsoa_female
            reason: "Gender-specific LSOA data"
          - code: prac_lsoa_male
            reason: "Gender-specific LSOA data"
        duration: 1_month  # April only

      - trigger: quarter_end  # Mar, Jun, Sep, Dec
        additional_fields:
          - quarterly_summary
          - performance_metrics
        duration: 1_month
```

### Loading Configuration

```python
import yaml
from datetime import datetime

class PublicationSchedule:
    def __init__(self, config_path: str):
        with open(config_path) as f:
            self.config = yaml.safe_load(f)

    def expected_sources(self, publication: str, date: datetime) -> list[str]:
        """Get expected sources for a date"""
        pub_config = self.config['publications'][publication]
        sources = pub_config['base_sources']

        # Check special periods
        for period in pub_config.get('special_periods', []):
            if self._is_trigger_active(period['trigger'], date):
                sources += [s['code'] for s in period['additional_sources']]

        return sources

    def _is_trigger_active(self, trigger: str, date: datetime) -> bool:
        if trigger == 'fiscal_year_start':
            return date.month == 4
        elif trigger == 'quarter_end':
            return date.month in [3, 6, 9, 12]
        return False

# Usage
schedule = PublicationSchedule('config/publication_schedule.yaml')
sources = schedule.expected_sources('gp_practice_registrations', datetime(2024, 4, 1))
print(sources)  # Returns: 9 sources (6 base + 3 LSOA)
```

**Software Principle:** **Configuration Over Convention**
- Business rules live in config, not code
- Easy to update when patterns change
- Non-developers can maintain schedule
- Industry use: Feature flags, A/B testing platforms

---

## Pattern 5: Predictive Schema Validation

**Principle:** Validate against expected patterns, not just structure

```python
from dataclasses import dataclass
from datetime import datetime

@dataclass
class ValidationResult:
    status: str  # PASS, WARNING, FAIL
    message: str

class SchemaValidator:
    def __init__(self, schedule: PublicationSchedule):
        self.schedule = schedule

    def validate_source_count(
        self,
        publication: str,
        date: datetime,
        actual_sources: int
    ) -> ValidationResult:
        """Validate against domain calendar expectations"""
        expected = len(self.schedule.expected_sources(publication, date))

        if actual_sources == expected:
            return ValidationResult(
                status="PASS",
                message=f"Source count matches expectation for {date.strftime('%B %Y')}"
            )
        elif date.month == 4 and actual_sources > expected:
            return ValidationResult(
                status="WARNING",
                message=f"Fiscal boundary month - extra sources may be expected. "
                        f"Got {actual_sources}, baseline is {expected}"
            )
        else:
            return ValidationResult(
                status="FAIL",
                message=f"Unexpected source count: got {actual_sources}, "
                        f"expected {expected} for {date.strftime('%B %Y')}"
            )

# Usage
validator = SchemaValidator(schedule)

# April - fiscal boundary
result = validator.validate_source_count(
    "gp_practice_registrations",
    datetime(2024, 4, 1),
    actual_sources=9
)
print(result)
# Status: PASS (9 expected in April due to LSOA sources)

# March - baseline
result = validator.validate_source_count(
    "gp_practice_registrations",
    datetime(2024, 3, 1),
    actual_sources=9
)
print(result)
# Status: FAIL (only 6 expected in March)
```

**Benefit:** Distinguishes between **expected variation** (April spike) and **actual errors** (unexpected changes)

---

## Pattern 6: Temporal Boundary Testing

**Principle:** Test at temporal boundaries, not just happy paths

```python
import pytest
from datetime import datetime

class TestGPPracticeIngestion:
    """Test suite covering temporal patterns"""

    def test_baseline_month_schema(self):
        """Test January-March schema (baseline)"""
        data = load_publication(datetime(2024, 2, 1))
        assert len(data.sources) == 6
        assert 'prac_lsoa_all' not in data.sources

    def test_fiscal_boundary_schema(self):
        """Test April schema (fiscal spike)"""
        data = load_publication(datetime(2024, 4, 1))
        assert len(data.sources) == 9  # +3 LSOA sources
        assert 'prac_lsoa_all' in data.sources
        assert 'prac_lsoa_female' in data.sources
        assert 'prac_lsoa_male' in data.sources

    def test_post_fiscal_schema(self):
        """Test May+ schema (back to baseline)"""
        data = load_publication(datetime(2024, 5, 1))
        assert len(data.sources) == 6
        assert 'prac_lsoa_all' not in data.sources

    def test_fiscal_year_transition(self):
        """Test March→April→May sequence"""
        march = load_publication(datetime(2024, 3, 1))
        april = load_publication(datetime(2024, 4, 1))
        may = load_publication(datetime(2024, 5, 1))

        # Baseline same before and after
        assert march.sources == may.sources

        # April shows fiscal spike
        assert april.sources != march.sources
        assert len(april.sources) > len(march.sources)

        # Verify specific LSOA sources
        lsoa_sources = {'prac_lsoa_all', 'prac_lsoa_female', 'prac_lsoa_male'}
        assert lsoa_sources.issubset(set(april.sources))
        assert not lsoa_sources.intersection(set(march.sources))
        assert not lsoa_sources.intersection(set(may.sources))
```

**Software Principle:** **Boundary Value Analysis** (Testing)
- Test at points where behavior changes
- Validate transitions between states
- Standard practice in: Aerospace, medical devices, financial systems

---

## Pattern 7: Temporally-Aware LoadModeClassifier

**Practical application for DataWarp**

```python
from datetime import datetime
from enum import Enum

class LoadMode(Enum):
    APPEND = "append"
    REPLACE = "replace"

class TemporallyAwareLoadModeClassifier:
    def __init__(self, domain_calendar: DomainCalendar):
        self.calendar = domain_calendar

    def classify(self, source_code: str, period: datetime) -> LoadMode:
        """Classify with temporal awareness"""

        # Check domain calendar
        volatility = self.calendar.expected_schema_volatility(period)

        if volatility == "HIGH":
            # Fiscal boundary - expect schema changes
            return LoadMode.REPLACE  # Safe default for volatility

        elif volatility == "MEDIUM":
            # Quarter end - some additions expected
            pattern = self._detect_pattern(source_code)
            if pattern == "time_series":
                return LoadMode.APPEND  # Probably safe
            else:
                return LoadMode.REPLACE  # Play safe

        else:
            # Normal period - schema should be stable
            return self._standard_classification(source_code)

    def explain_recommendation(
        self,
        source_code: str,
        period: datetime
    ) -> str:
        """Explain WHY this mode was chosen"""
        volatility = self.calendar.expected_schema_volatility(period)

        if period.month == 4:
            return (
                f"REPLACE mode recommended: {period.strftime('%B')} is fiscal year boundary. "
                f"Expect temporary schema expansion (e.g., LSOA fields). "
                f"REPLACE handles fiscal churn cleanly."
            )
        else:
            return self._standard_explanation(source_code)

    def _detect_pattern(self, source_code: str) -> str:
        # Standard pattern detection logic
        ...

    def _standard_classification(self, source_code: str) -> LoadMode:
        # Standard classification logic
        ...

# Usage
calendar = DomainCalendar()
classifier = TemporallyAwareLoadModeClassifier(calendar)

# April - fiscal boundary
mode = classifier.classify('prac_all', datetime(2024, 4, 1))
print(mode)  # LoadMode.REPLACE
print(classifier.explain_recommendation('prac_all', datetime(2024, 4, 1)))
# "REPLACE mode recommended: April is fiscal year boundary..."

# March - normal month
mode = classifier.classify('prac_all', datetime(2024, 3, 1))
print(mode)  # LoadMode.APPEND (if time_series pattern)
```

---

## Industry Examples: Where This Matters

### Healthcare (NHS Example)
- Fiscal boundaries (April): LSOA data, annual reports
- Quarter-ends: Performance metrics
- Annual cycles: Budget allocations

### Finance
- Quarter-ends: Earnings reports, balance sheets
- Year-end: Annual reports, tax statements
- Month-end: Reconciliation data

### Retail
- Black Friday: Inventory expansions
- Christmas: Gift registry fields
- Back-to-school: Seasonal categories

### Education
- Term start: Enrollment data
- Exam periods: Assessment results
- Graduation: Alumni records

---

## Recommended Reading

1. **Domain-Driven Design** (Eric Evans)
   - Chapter: "Model-Driven Design"
   - Learn: Encoding business knowledge in code

2. **The Data Warehouse Toolkit** (Ralph Kimball)
   - Chapter: "Slowly Changing Dimensions"
   - Learn: Handling temporal data changes

3. **Release It!** (Michael Nygard)
   - Chapter: "Temporal Coupling"
   - Learn: Designing systems that handle time-based changes

4. **Implementing Domain-Driven Design** (Vaughn Vernon)
   - Chapter: "Aggregates"
   - Learn: Bounded contexts with temporal boundaries

---

## Key Takeaways

**The Discovery:**
> "April isn't just another month - it's a fiscal boundary event that triggers predictable schema changes"

**How to Apply This Thinking:**

1. **Identify domain calendars** - What dates matter in your domain?
2. **Encode temporal knowledge** - Make implicit rules explicit in code
3. **Version with context** - FY2024_Q1_FISCAL means something
4. **Test at boundaries** - March→April→May, not just April
5. **Validate predictively** - Expected variations vs actual errors
6. **Configure temporally** - Business rules in config, not code

**The Meta-Lesson:**
> "Every domain has hidden temporal patterns. Surface them, encode them, test them."

---

## Application to DataWarp

**Potential enhancements:**

1. Create `src/datawarp/utils/domain_calendar.py`
2. Update `LoadModeClassifier` with temporal awareness
3. Add `config/publication_schedule.yaml` for temporal rules
4. Implement temporal boundary tests in `tests/test_temporal_patterns.py`
5. Update schema versioning: `FY2024_Q1_FISCAL` vs generic `v2`

**Priority:** Added to IMPLEMENTATION_TASKS.md → "💡 Ideas" section

---

**See also:**
- `docs/testing/FISCAL_TESTING_FINDINGS.md` - Original fiscal boundary discovery
- Session 7 transcript - Full educational discussion
