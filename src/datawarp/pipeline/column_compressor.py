"""Column Pattern Compression for LLM Enrichment.

Handles files with 100+ repetitive columns by:
1. Detecting column patterns (e.g., week_0_1, week_1_2, ..., week_104_plus)
2. Compressing to template representations for LLM
3. Expanding LLM output back to full column set

This prevents token limit errors while preserving full enrichment functionality.
"""
import re
from typing import List, Dict, Tuple, Optional
from collections import defaultdict


def detect_sequential_pattern(column_names: List[str]) -> Optional[Dict]:
    """Detect sequential numeric patterns in column names.

    Examples:
      - week_0_1, week_1_2, ..., week_104_plus
      - quarter_1, quarter_2, quarter_3, quarter_4
      - month_01, month_02, ..., month_12

    Returns:
        Pattern dict if found, else None
        {
            'pattern': 'week_{n}_{n+1}',
            'count': 104,
            'columns': ['week_0_1', 'week_1_2', ...]
        }
    """
    # Group columns by prefix (everything before digits)
    groups = defaultdict(list)

    for col in column_names:
        # Extract prefix (text before numbers)
        match = re.match(r'^([a-z_]+?)_*(\d+)', col, re.IGNORECASE)
        if match:
            prefix = match.group(1)
            groups[prefix].append(col)

    # Find groups with 10+ sequential columns (likely patterns)
    for prefix, cols in groups.items():
        if len(cols) >= 10:  # Threshold: 10+ columns is a pattern
            # Check if they're sequential (week_0_1, week_1_2, ...)
            # or simple sequence (month_01, month_02, ...)
            if _is_sequential(cols):
                return {
                    'pattern': f'{prefix}_{{n}}_{{n+1}}' if '_' in cols[0][len(prefix):] else f'{prefix}_{{n}}',
                    'count': len(cols),
                    'columns': cols,
                    'prefix': prefix
                }

    return None


def _is_sequential(columns: List[str]) -> bool:
    """Check if columns follow a sequential numeric pattern."""
    # Extract numbers from column names
    numbers = []
    for col in sorted(columns):
        nums = re.findall(r'\d+', col)
        if nums:
            numbers.append(int(nums[0]))

    if len(numbers) < 2:
        return False

    # Check if mostly sequential (allow some gaps)
    sequential_count = sum(1 for i in range(len(numbers)-1) if numbers[i+1] - numbers[i] <= 2)
    return sequential_count / len(numbers) > 0.7  # 70% threshold


def compress_columns_for_llm(file_entry: Dict) -> Tuple[Dict, Optional[Dict]]:
    """Compress repetitive columns in file preview for LLM.

    Args:
        file_entry: File entry with 'preview' containing 'columns'

    Returns:
        (compressed_file_entry, pattern_info)
        - compressed_file_entry: Preview with patterns collapsed
        - pattern_info: Pattern metadata for expansion (None if no compression)
    """
    preview = file_entry.get('preview', {})
    columns = preview.get('columns', [])

    if len(columns) < 50:  # Only compress if 50+ columns
        return file_entry, None

    pattern = detect_sequential_pattern(columns)
    if not pattern:
        return file_entry, None

    # Compress: Replace pattern columns with single representative + count
    pattern_cols = set(pattern['columns'])
    non_pattern_cols = [c for c in columns if c not in pattern_cols]

    # Create compressed version
    compressed_entry = file_entry.copy()
    compressed_preview = preview.copy()

    # Keep first 2, last 1 pattern columns as examples + count
    sample_cols = pattern['columns'][:2] + pattern['columns'][-1:]
    compressed_preview['columns'] = non_pattern_cols + sample_cols
    compressed_preview['pattern_info'] = {
        'pattern': pattern['pattern'],
        'count': pattern['count'],
        'sample_columns': sample_cols,
        'prefix': pattern['prefix']
    }

    compressed_entry['preview'] = compressed_preview

    return compressed_entry, pattern


def expand_columns_from_llm(enriched_source: Dict, pattern_info: Optional[Dict]) -> Dict:
    """Expand pattern-compressed columns back to full set.

    Args:
        enriched_source: LLM-enriched source with pattern columns
        pattern_info: Pattern metadata from compression

    Returns:
        Source with all pattern columns expanded with metadata
    """
    if not pattern_info:
        return enriched_source

    columns_metadata = enriched_source.get('columns', {})
    if not columns_metadata:
        return enriched_source

    # Find enriched pattern column (use first sample as template)
    pattern_cols = pattern_info['columns']
    sample_col = pattern_cols[0]

    template_metadata = None
    for col_name, col_meta in columns_metadata.items():
        if col_name == sample_col or col_name.startswith(pattern_info['prefix']):
            template_metadata = col_meta
            break

    if not template_metadata:
        # LLM didn't enrich pattern columns - use defaults
        template_metadata = {
            'pg_name': None,  # Will use original name
            'description': f"Sequential data point in {pattern_info['prefix']} series",
            'metadata': {
                'measure': True,
                'dimension': False,
                'tags': ['time_series', 'sequential']
            }
        }

    # Expand: Add metadata for all pattern columns
    expanded_columns = columns_metadata.copy()
    for col in pattern_cols:
        if col not in expanded_columns:
            # Clone template metadata with column-specific name
            expanded_columns[col] = {
                'pg_name': template_metadata.get('pg_name', col).replace(sample_col, col) if template_metadata.get('pg_name') else col,
                'description': template_metadata.get('description', ''),
                'metadata': template_metadata.get('metadata', {}).copy()
            }

    enriched_source['columns'] = expanded_columns
    return enriched_source


def compress_manifest_for_enrichment(sources: List[Dict]) -> Tuple[List[Dict], Dict]:
    """Compress all sources in manifest for LLM enrichment.

    Args:
        sources: List of source dicts with file previews

    Returns:
        (compressed_sources, compression_map)
        - compressed_sources: Sources with compressed previews
        - compression_map: {source_index: pattern_info} for expansion
    """
    compressed = []
    compression_map = {}

    for idx, source in enumerate(sources):
        files = source.get('files', [])
        compressed_files = []

        for file_entry in files:
            compressed_file, pattern = compress_columns_for_llm(file_entry)
            compressed_files.append(compressed_file)

            if pattern:
                compression_map[f'{idx}_{len(compressed_files)-1}'] = pattern

        compressed_source = source.copy()
        compressed_source['files'] = compressed_files
        compressed.append(compressed_source)

    return compressed, compression_map


def expand_manifest_from_enrichment(enriched_sources: List[Dict],
                                    compression_map: Dict) -> List[Dict]:
    """Expand compressed columns in enriched manifest.

    Args:
        enriched_sources: LLM-enriched sources with compressed columns
        compression_map: Compression metadata from compress step

    Returns:
        Sources with full column metadata expanded
    """
    expanded = []

    for idx, source in enumerate(enriched_sources):
        files = source.get('files', [])

        for file_idx, file_entry in enumerate(files):
            key = f'{idx}_{file_idx}'
            pattern = compression_map.get(key)

            if pattern:
                # Expand this file's columns
                file_entry = expand_columns_from_llm(file_entry, pattern)

        expanded.append(source)

    return expanded
