"""Test column compression for files with 100+ repetitive columns."""
import pytest
from datawarp.pipeline.column_compressor import (
    detect_sequential_pattern,
    compress_columns_for_llm,
    expand_columns_from_llm,
    compress_manifest_for_enrichment,
    expand_manifest_from_enrichment
)


def test_detect_sequential_pattern_rtt_style():
    """Test detection of RTT weekly breakdown pattern."""
    # Simulate RTT provider file columns
    columns = [
        'provider_code',
        'provider_name',
        'treatment_function_code',
        'treatment_function',
        'the_number_of_incomplete_pathways_by_week_since_referral_0_1',
        'the_number_of_incomplete_pathways_by_week_since_referral_1_2',
        'the_number_of_incomplete_pathways_by_week_since_referral_2_3',
        # ... (simulate 104 weekly columns)
    ] + [f'the_number_of_incomplete_pathways_by_week_since_referral_{i}_{i+1}' for i in range(3, 104)] + [
        'the_number_of_incomplete_pathways_by_week_since_referral_104_plus',
        'total_number_of_incomplete_pathways',
        'total_within_18_weeks'
    ]

    pattern = detect_sequential_pattern(columns)

    assert pattern is not None
    assert 'the_number_of_incomplete_pathways_by_week_since_referral' in pattern['prefix']
    assert pattern['count'] >= 100  # Should detect the 104 weekly columns


def test_compress_columns_for_llm():
    """Test compression reduces column count while preserving samples."""
    file_entry = {
        'url': 'https://example.com/file.xlsx',
        'sheet': 'Provider',
        'preview': {
            'columns': [
                'provider_code',
                'provider_name'
            ] + [f'week_{i}_{i+1}' for i in range(0, 104)] + [
                'week_104_plus',
                'total'
            ]
        }
    }

    compressed, pattern = compress_columns_for_llm(file_entry)

    assert pattern is not None
    assert pattern['count'] == 105  # 104 + week_104_plus
    assert len(compressed['preview']['columns']) < len(file_entry['preview']['columns'])
    # Should keep provider columns + samples (first 2 + last 1) + total
    assert len(compressed['preview']['columns']) <= 6  # 2 provider + 3 samples + 1 total


def test_expand_columns_from_llm():
    """Test expansion restores full column set with metadata."""
    # Simulate LLM-enriched source with compressed columns
    enriched_source = {
        'code': 'rtt_provider',
        'columns': {
            'provider_code': {
                'pg_name': 'provider_code',
                'description': 'NHS provider code',
                'metadata': {'dimension': True, 'measure': False}
            },
            'week_0_1': {
                'pg_name': 'incomplete_pathways_week_0_to_1',
                'description': 'Number of incomplete pathways waiting 0-1 weeks',
                'metadata': {'dimension': False, 'measure': True, 'tags': ['waiting_time']}
            }
        }
    }

    pattern_info = {
        'pattern': 'week_{n}_{n+1}',
        'count': 104,
        'columns': [f'week_{i}_{i+1}' for i in range(0, 104)],
        'prefix': 'week'
    }

    expanded = expand_columns_from_llm(enriched_source, pattern_info)

    # Should have all 104 week columns + provider_code
    assert len(expanded['columns']) >= 104
    assert 'week_0_1' in expanded['columns']
    assert 'week_50_51' in expanded['columns']
    assert 'week_103_104' in expanded['columns']

    # All week columns should have metadata
    week_col = expanded['columns']['week_50_51']
    assert 'description' in week_col
    assert week_col['metadata']['measure'] is True


def test_compress_manifest_for_enrichment():
    """Test manifest-level compression."""
    sources = [
        {
            'code': 'rtt_provider',
            'files': [
                {
                    'url': 'https://example.com/file.xlsx',
                    'preview': {
                        'columns': ['provider_code'] + [f'week_{i}_{i+1}' for i in range(0, 104)] + ['total']
                    }
                }
            ]
        }
    ]

    compressed, compression_map = compress_manifest_for_enrichment(sources)

    assert len(compression_map) == 1  # One file compressed
    assert '0_0' in compression_map  # Source 0, file 0
    assert compression_map['0_0']['count'] == 104


def test_expand_manifest_from_enrichment():
    """Test manifest-level expansion."""
    enriched_sources = [
        {
            'code': 'rtt_provider',
            'files': [
                {
                    'url': 'https://example.com/file.xlsx',
                    'columns': {
                        'provider_code': {'pg_name': 'provider_code', 'description': 'Provider'},
                        'week_0_1': {'pg_name': 'week_0_1', 'description': 'Week 0-1'}
                    }
                }
            ]
        }
    ]

    compression_map = {
        '0_0': {
            'pattern': 'week_{n}_{n+1}',
            'count': 104,
            'columns': [f'week_{i}_{i+1}' for i in range(0, 104)],
            'prefix': 'week'
        }
    }

    expanded = expand_manifest_from_enrichment(enriched_sources, compression_map)

    # All 104 columns should be present
    file_entry = expanded[0]['files'][0]
    assert len(file_entry['columns']) >= 104


def test_no_compression_for_small_files():
    """Test that files with <50 columns are not compressed."""
    file_entry = {
        'url': 'https://example.com/small.xlsx',
        'preview': {
            'columns': [f'col_{i}' for i in range(30)]  # Only 30 columns
        }
    }

    compressed, pattern = compress_columns_for_llm(file_entry)

    assert pattern is None  # No compression applied
    assert compressed == file_entry  # Unchanged


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
