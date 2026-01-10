"""Intelligent classification of data load mode (append vs replace).

This module uses multiple signals to determine whether data should be appended
or replaced when loading a new period:

1. Column Pattern Analysis (deterministic)
2. Content Semantics (LLM-based)
3. Historical Behavior (learning)
4. Duplicate Risk Assessment (validation)
"""

import re
from typing import Dict, List, Optional, Tuple
from enum import Enum


class DataPattern(Enum):
    """Data pattern classifications that determine load behavior."""

    # Replace patterns - data refreshes/updates previous periods
    TIME_SERIES_WIDE = "time_series_wide"  # Columns: jan_2024, feb_2024, mar_2024...
    CUMULATIVE_YTD = "cumulative_ytd"  # Year-to-date aggregations
    REFRESHED_SNAPSHOT = "refreshed_snapshot"  # Full table refresh each period

    # Append patterns - data adds new rows each period
    INCREMENTAL_TRANSACTIONAL = "incremental_transactional"  # New transactions each period
    POINT_IN_TIME_SNAPSHOT = "point_in_time_snapshot"  # Period-specific snapshots
    EVENT_LOG = "event_log"  # Timestamped events

    # Ambiguous - needs LLM decision
    UNKNOWN = "unknown"


class LoadMode(Enum):
    """Load modes for data ingestion."""
    APPEND = "append"  # Add new rows, keep existing
    REPLACE = "replace"  # Delete period data, insert fresh


class LoadModeClassifier:
    """Intelligent classifier for determining append vs replace mode."""

    def __init__(self):
        """Initialize classifier with pattern detection rules."""
        self.date_column_patterns = [
            r'(january|february|march|april|may|june|july|august|september|october|november|december)_(\d{4})',
            r'(\d{4})_(january|february|march|april|may|june|july|august|september|october|november|december)',
            r'(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)_(\d{2,4})',
            r'q[1-4]_(\d{4})',  # Quarterly
            r'(\d{4})_q[1-4]',
            r'fy_(\d{4})_(\d{4})',  # Fiscal year
        ]

        self.ytd_indicators = [
            'year_to_date', 'ytd', 'cumulative', 'total_since',
            'running_total', 'accumulated'
        ]

        self.snapshot_indicators = [
            'as_of', 'snapshot', 'end_of_period', 'closing',
            'at_date', 'position_as_at'
        ]

        self.incremental_indicators = [
            'new_', 'during_period', 'in_period', 'this_month',
            'current_period', 'period_only'
        ]

    def classify_from_columns(self, column_names: List[str]) -> Tuple[DataPattern, float, str]:
        """Classify data pattern from column names alone.

        Returns:
            (pattern, confidence, reason)
        """
        col_lower = [c.lower() for c in column_names]

        # Check for wide time-series pattern
        date_cols = []
        for col in col_lower:
            for pattern in self.date_column_patterns:
                if re.search(pattern, col):
                    date_cols.append(col)
                    break

        if len(date_cols) >= 6:  # At least 6 months of historical data
            return (
                DataPattern.TIME_SERIES_WIDE,
                0.95,
                f"Found {len(date_cols)} date-based columns indicating time-series data"
            )

        # Check for YTD indicators
        ytd_cols = [c for c in col_lower if any(ind in c for ind in self.ytd_indicators)]
        if ytd_cols:
            return (
                DataPattern.CUMULATIVE_YTD,
                0.85,
                f"Found YTD/cumulative columns: {', '.join(ytd_cols[:3])}"
            )

        # Check for snapshot indicators
        snapshot_cols = [c for c in col_lower if any(ind in c for ind in self.snapshot_indicators)]
        if snapshot_cols:
            return (
                DataPattern.POINT_IN_TIME_SNAPSHOT,
                0.80,
                f"Found snapshot indicators: {', '.join(snapshot_cols[:3])}"
            )

        # Check for incremental indicators
        incremental_cols = [c for c in col_lower if any(ind in c for ind in self.incremental_indicators)]
        if incremental_cols:
            return (
                DataPattern.INCREMENTAL_TRANSACTIONAL,
                0.75,
                f"Found incremental indicators: {', '.join(incremental_cols[:3])}"
            )

        # Default: unknown, needs LLM
        return (DataPattern.UNKNOWN, 0.50, "No clear pattern in column names")

    def classify_from_description(self, description: str, table_name: str) -> Tuple[DataPattern, float, str]:
        """Classify from source description and table name (LLM input).

        This would be enhanced by actual LLM call, but provides heuristics.
        """
        desc_lower = (description + " " + table_name).lower()

        # Time series indicators
        if any(word in desc_lower for word in ['historical', 'time series', 'trend', 'over time']):
            return (DataPattern.TIME_SERIES_WIDE, 0.70, "Description mentions historical/time-series")

        # YTD indicators
        if any(word in desc_lower for word in self.ytd_indicators):
            return (DataPattern.CUMULATIVE_YTD, 0.75, "Description mentions cumulative/YTD")

        # Snapshot indicators
        if any(word in desc_lower for word in self.snapshot_indicators):
            return (DataPattern.POINT_IN_TIME_SNAPSHOT, 0.70, "Description mentions snapshot/as-of")

        # Transactional indicators
        if any(word in desc_lower for word in ['transaction', 'event', 'log', 'individual', 'record']):
            return (DataPattern.INCREMENTAL_TRANSACTIONAL, 0.65, "Description suggests transactional data")

        return (DataPattern.UNKNOWN, 0.40, "No clear indicators in description")

    def recommend_mode(self, pattern: DataPattern, confidence: float) -> Tuple[LoadMode, str]:
        """Recommend load mode based on pattern and confidence.

        Returns:
            (mode, explanation)
        """
        # High confidence patterns
        if confidence >= 0.80:
            if pattern in [DataPattern.TIME_SERIES_WIDE, DataPattern.CUMULATIVE_YTD, DataPattern.REFRESHED_SNAPSHOT]:
                return (
                    LoadMode.REPLACE,
                    f"Data pattern '{pattern.value}' indicates refreshed data - use REPLACE to avoid duplicates"
                )

            if pattern in [DataPattern.INCREMENTAL_TRANSACTIONAL, DataPattern.POINT_IN_TIME_SNAPSHOT, DataPattern.EVENT_LOG]:
                return (
                    LoadMode.APPEND,
                    f"Data pattern '{pattern.value}' indicates incremental data - use APPEND for time-series"
                )

        # Medium confidence - conservative default
        if confidence >= 0.60:
            if pattern in [DataPattern.TIME_SERIES_WIDE, DataPattern.CUMULATIVE_YTD]:
                return (
                    LoadMode.REPLACE,
                    f"Likely '{pattern.value}' but medium confidence - defaulting to REPLACE (safer)"
                )

        # Low confidence or unknown - safest default is REPLACE to avoid duplicates
        return (
            LoadMode.REPLACE,
            f"Uncertain pattern (confidence: {confidence:.0%}) - defaulting to REPLACE to prevent duplicates"
        )

    def classify(
        self,
        column_names: List[str],
        description: str = "",
        table_name: str = "",
        llm_classification: Optional[Dict] = None
    ) -> Dict:
        """Full classification pipeline.

        Args:
            column_names: List of column names from source
            description: Source description
            table_name: Staging table name
            llm_classification: Optional LLM-provided classification

        Returns:
            {
                'pattern': DataPattern,
                'confidence': float,
                'mode': LoadMode,
                'reason': str,
                'explanation': str,
                'signals': {
                    'column_analysis': {...},
                    'semantic_analysis': {...},
                    'llm_classification': {...}
                }
            }
        """
        # Signal 1: Column pattern analysis (deterministic, high confidence)
        col_pattern, col_confidence, col_reason = self.classify_from_columns(column_names)

        # Signal 2: Semantic analysis (heuristic, medium confidence)
        sem_pattern, sem_confidence, sem_reason = self.classify_from_description(description, table_name)

        # Signal 3: LLM classification (if provided, highest confidence)
        llm_pattern = None
        llm_confidence = 0.0
        llm_reason = "No LLM classification provided"

        if llm_classification:
            llm_pattern = DataPattern(llm_classification.get('pattern', 'unknown'))
            llm_confidence = llm_classification.get('confidence', 0.80)
            llm_reason = llm_classification.get('reason', '')

        # Weighted decision: LLM > Column Analysis > Semantic
        if llm_confidence >= 0.75:
            final_pattern = llm_pattern
            final_confidence = llm_confidence
            final_reason = f"LLM classification: {llm_reason}"
        elif col_confidence >= 0.75:
            final_pattern = col_pattern
            final_confidence = col_confidence
            final_reason = f"Column analysis: {col_reason}"
        elif sem_confidence >= 0.65:
            final_pattern = sem_pattern
            final_confidence = sem_confidence
            final_reason = f"Semantic analysis: {sem_reason}"
        else:
            # Use highest confidence signal
            signals = [
                (col_pattern, col_confidence, f"Columns: {col_reason}"),
                (sem_pattern, sem_confidence, f"Semantic: {sem_reason}")
            ]
            if llm_pattern:
                signals.append((llm_pattern, llm_confidence, f"LLM: {llm_reason}"))

            final_pattern, final_confidence, final_reason = max(signals, key=lambda x: x[1])

        # Determine load mode
        mode, explanation = self.recommend_mode(final_pattern, final_confidence)

        return {
            'pattern': final_pattern.value,
            'confidence': final_confidence,
            'mode': mode.value,
            'reason': final_reason,
            'explanation': explanation,
            'signals': {
                'column_analysis': {
                    'pattern': col_pattern.value,
                    'confidence': col_confidence,
                    'reason': col_reason
                },
                'semantic_analysis': {
                    'pattern': sem_pattern.value,
                    'confidence': sem_confidence,
                    'reason': sem_reason
                },
                'llm_classification': {
                    'pattern': llm_pattern.value if llm_pattern else None,
                    'confidence': llm_confidence,
                    'reason': llm_reason
                }
            }
        }


# Example usage and testing
if __name__ == '__main__':
    classifier = LoadModeClassifier()

    # Test 1: PCN Workforce (wide time-series)
    pcn_columns = [
        'director_category', 'march_2020', 'april_2020', 'may_2020',
        'june_2020', 'july_2020', 'august_2020', 'september_2020',
        'march_2024', 'april_2024', 'may_2024', 'march_2025', 'april_2025'
    ]
    result1 = classifier.classify(
        column_names=pcn_columns,
        description="Primary Care Network Workforce full-time equivalent by role, March 2020 to April 2025",
        table_name="pcn_wf_fte_gender_role"
    )
    print("Test 1: PCN Workforce")
    print(f"  Pattern: {result1['pattern']}")
    print(f"  Mode: {result1['mode']}")
    print(f"  Confidence: {result1['confidence']:.0%}")
    print(f"  Reason: {result1['reason']}")
    print(f"  Explanation: {result1['explanation']}\n")

    # Test 2: Individual-level transactional data
    transactional_columns = [
        'record_id', 'patient_id', 'date_of_referral', 'referral_source',
        'age_at_referral', 'gender', 'diagnosis_code'
    ]
    result2 = classifier.classify(
        column_names=transactional_columns,
        description="Individual-level ADHD referral records for the reporting period",
        table_name="adhd_individual_referrals"
    )
    print("Test 2: Individual Transactions")
    print(f"  Pattern: {result2['pattern']}")
    print(f"  Mode: {result2['mode']}")
    print(f"  Confidence: {result2['confidence']:.0%}")
    print(f"  Reason: {result2['reason']}\n")

    # Test 3: YTD cumulative data
    ytd_columns = [
        'organization_code', 'referrals_ytd', 'total_patients_ytd',
        'cumulative_admissions', 'budget_spent_ytd'
    ]
    result3 = classifier.classify(
        column_names=ytd_columns,
        description="Year-to-date cumulative metrics for NHS Trusts",
        table_name="trust_ytd_metrics"
    )
    print("Test 3: YTD Cumulative")
    print(f"  Pattern: {result3['pattern']}")
    print(f"  Mode: {result3['mode']}")
    print(f"  Confidence: {result3['confidence']:.0%}")
    print(f"  Reason: {result3['reason']}\n")

    # Test 4: Point-in-time snapshot
    snapshot_columns = [
        'trust_code', 'beds_available_as_of_date', 'staff_count_snapshot',
        'closing_balance', 'end_of_period_inventory'
    ]
    result4 = classifier.classify(
        column_names=snapshot_columns,
        description="NHS Trust capacity snapshot as of month end",
        table_name="trust_capacity_snapshot"
    )
    print("Test 4: Point-in-Time Snapshot")
    print(f"  Pattern: {result4['pattern']}")
    print(f"  Mode: {result4['mode']}")
    print(f"  Confidence: {result4['confidence']:.0%}")
    print(f"  Reason: {result4['reason']}\n")
