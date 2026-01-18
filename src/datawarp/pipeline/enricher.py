"""DataWarp Manifest Enrichment Library.

Extracts enrichment logic from scripts/enrich_manifest.py for use as library.
Integrates with EventStore for observability.
"""
import yaml
import os
import json
import re
import time
from pathlib import Path
from dotenv import load_dotenv
from collections import OrderedDict
from datetime import datetime
from dataclasses import dataclass
from typing import Optional, Dict, List, Tuple
import uuid

from datawarp.supervisor.events import EventStore, create_event, EventType, EventLevel
from datawarp.storage.connection import get_connection
from datawarp.pipeline.column_compressor import compress_manifest_for_enrichment, expand_manifest_from_enrichment

load_dotenv()


# === DATABASE OBSERVABILITY FUNCTIONS ===
# Ported from enrich_manifest_old.py to restore full database tracking

def _log_enrichment_start(manifest_name: str, total_sources: int,
                          data_sources: int, noise_sources: int) -> Optional[uuid.UUID]:
    """Log start of enrichment run, return run_id for tracking.

    Writes to datawarp.tbl_enrichment_runs with status='running'.
    """
    try:
        run_id = uuid.uuid4()
        model_name = os.getenv('LLM_MODEL', 'gemini-2.0-flash-exp')

        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO datawarp.tbl_enrichment_runs
                (run_id, manifest_name, started_at, total_sources, data_sources,
                 noise_sources, status, model_name)
                VALUES (%s, %s, NOW(), %s, %s, %s, 'running', %s)
            """, (str(run_id), manifest_name, total_sources, data_sources, noise_sources, model_name))
            conn.commit()

        return run_id
    except Exception as e:
        # Non-fatal: don't fail enrichment if logging fails
        print(f"⚠️  Failed to log enrichment start: {e}")
        return None


def _log_enrichment_complete(run_id: Optional[uuid.UUID], status: str,
                             validation_status: str, duration_ms: int,
                             total_input_tokens: int = 0, total_output_tokens: int = 0,
                             reference_matched: int = 0, error_message: str = None) -> None:
    """Update enrichment run with completion status.

    Updates datawarp.tbl_enrichment_runs with final metrics.
    """
    if not run_id:
        return

    try:
        # Calculate cost (Gemini 2.0 Flash pricing)
        input_cost = total_input_tokens * 0.000001
        output_cost = total_output_tokens * 0.000004
        total_cost = input_cost + output_cost

        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                UPDATE datawarp.tbl_enrichment_runs
                SET completed_at = NOW(),
                    status = %s,
                    validation_status = %s,
                    duration_ms = %s,
                    total_input_tokens = %s,
                    total_output_tokens = %s,
                    total_cost = %s,
                    total_api_calls = 1,
                    reference_matched = %s,
                    error_message = %s
                WHERE run_id = %s
            """, (status, validation_status, duration_ms, total_input_tokens,
                  total_output_tokens, total_cost, reference_matched, error_message, str(run_id)))
            conn.commit()
    except Exception as e:
        print(f"⚠️  Failed to log enrichment completion: {e}")


def _log_api_call(run_id: Optional[uuid.UUID], input_tokens: int, output_tokens: int,
                  latency_ms: int, model_name: str, status: str = 'success',
                  error_message: str = None) -> float:
    """Log individual LLM API call metrics.

    Writes to datawarp.tbl_enrichment_api_calls.
    Returns total cost for this call.
    """
    if not run_id:
        return 0.0

    try:
        # Calculate costs (Gemini 2.0 Flash pricing)
        input_cost = input_tokens * 0.000001
        output_cost = output_tokens * 0.000004
        total_cost = input_cost + output_cost

        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO datawarp.tbl_enrichment_api_calls
                (run_id, call_timestamp, input_tokens, output_tokens, total_tokens,
                 input_cost, output_cost, total_cost, latency_ms, model_name,
                 status, error_message)
                VALUES (%s, NOW(), %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (str(run_id), input_tokens, output_tokens, input_tokens + output_tokens,
                  input_cost, output_cost, total_cost, latency_ms, model_name,
                  status, error_message))
            conn.commit()

        return total_cost
    except Exception as e:
        print(f"⚠️  Failed to log API call: {e}")
        return 0.0

# === END DATABASE OBSERVABILITY ===


@dataclass
class EnrichmentResult:
    """Result of manifest enrichment operation."""
    success: bool
    output_path: str
    sources_enriched: int
    sources_from_reference: int
    sources_total: int
    llm_calls_made: int
    input_tokens: int
    output_tokens: int
    latency_ms: int
    error: Optional[str] = None


# Configure YAML dumper for multiline strings
class YAMLDumper(yaml.SafeDumper):
    pass

def str_presenter(dumper, data):
    if len(data.splitlines()) > 1:
        return dumper.represent_scalar('tag:yaml.org,2002:str', data, style='|')
    return dumper.represent_scalar('tag:yaml.org,2002:str', data)

yaml.add_representer(str, str_presenter, Dumper=YAMLDumper)


def normalize_url(url: str) -> str:
    """Remove date/month/year from URL to create stable pattern for matching.

    Also normalizes common abbreviations (e.g., 'OC' vs 'Online Consultation').
    This enables matching across periods where URLs contain date components.
    """
    from urllib.parse import unquote

    # Decode URL encoding first (%20 → space, etc.)
    filename = unquote(Path(url).name)

    # Normalize common abbreviations to standard form
    pattern = re.sub(r'\bOnline\s+Consultation\b', 'OC', filename, flags=re.IGNORECASE)

    # Remove common date patterns: "April 2025", "april-2025", "Apr25", etc.
    # Handle month+year combinations first (Apr25, May25, etc.) before individual patterns
    pattern = re.sub(r'\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\d{2,4}\b', 'PERIOD', pattern, flags=re.IGNORECASE)
    pattern = re.sub(r'\b(january|february|march|april|may|june|july|august|september|october|november|december)\s*\d{2,4}\b', 'PERIOD', pattern, flags=re.IGNORECASE)

    # Then handle standalone months and years
    pattern = re.sub(r'\b(january|february|march|april|may|june|july|august|september|october|november|december)\b', 'MONTH', pattern, flags=re.IGNORECASE)
    pattern = re.sub(r'\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\b', 'MONTH', pattern, flags=re.IGNORECASE)
    pattern = re.sub(r'\b20\d{2}\b', 'YEAR', pattern)  # 2023, 2024, 2025, etc.
    pattern = re.sub(r'[-_\s]MONTH[-_\s]?YEAR', '-PERIOD', pattern)
    pattern = re.sub(r'MONTH[-_\s]?YEAR', 'PERIOD', pattern)

    # Remove NHS file ID numbers (5-6 digit patterns like -77252, -32711)
    # Common in NHS England URLs: "Incomplete-Provider-Apr25-XLSX-9M-77252.xlsx"
    pattern = re.sub(r'-\d{5,6}(?=\.)', '-FILEID', pattern)

    # Remove common revision suffixes (revised, corrected, updated, v2, etc.)
    # Examples: "...-revised.xlsx", "...-corrected.xlsx", "...-SrRW6y.xlsx" (random IDs)
    pattern = re.sub(r'-(revised|corrected|updated|final)(?=\.)', '-FILEID', pattern, flags=re.IGNORECASE)

    # Remove random alphanumeric IDs (like SrRW6y, 1Xmjkk) - 5-6 mixed chars
    pattern = re.sub(r'-[A-Za-z0-9]{5,7}(?=\.)', '-FILEID', pattern)

    # Clean up extra spaces/dashes
    pattern = re.sub(r'\s+', ' ', pattern).strip()
    pattern = re.sub(r'-+', '-', pattern)

    return pattern


def is_noise_source(source: dict) -> bool:
    """Detect metadata/dictionary sources that don't need LLM enrichment."""
    code = source.get('code', '').lower()
    name = source.get('name', '').lower()

    noise_keywords = ['dictionary', 'definitions', 'notes', 'title_sheet',
                      'contents', 'metadata', 'data_dictionary', 'title and contents',
                      'annex']

    for keyword in noise_keywords:
        if keyword in code or keyword in name:
            return True

    files = source.get('files', [])
    if files and 'sheet' in files[0]:
        sheet = files[0]['sheet'].lower()
        if any(k in sheet for k in noise_keywords):
            return True

    return False


# === ROLLING REFERENCE: Column-Level Matching Functions ===
# These functions enable intelligent matching of columns between draft and reference
# manifests, supporting the rolling reference model where each period inherits from
# the previous one.
#
# EDGE CASES HANDLED:
# 1. New columns in existing sheet → matched columns copied, new columns to LLM
# 2. Removed columns → ignored (only match what exists in draft)
# 3. Renamed columns → fuzzy matching with 80% threshold
# 4. Column type changes → handled at load time (schema drift), not enrichment
# 5. Sheet renamed → fingerprint matching (structure, not name)
# 6. Sheet split/merged → partial matching with 70% column overlap threshold

import hashlib
from difflib import SequenceMatcher


def normalize_column_name(name: str) -> str:
    """Normalize column name for matching.

    Normalizations applied:
    - Lowercase
    - Remove special characters except underscore
    - Replace multiple spaces/underscores with single underscore
    - Strip whitespace

    Examples:
        "Patient Count" -> "patient_count"
        "Total Number of Patients (FTE)" -> "total_number_of_patients_fte"
    """
    if not name:
        return ""
    # Lowercase
    normalized = name.lower()
    # Replace spaces and special chars with underscore
    normalized = re.sub(r'[^a-z0-9_]', '_', normalized)
    # Collapse multiple underscores
    normalized = re.sub(r'_+', '_', normalized)
    # Strip leading/trailing underscores
    normalized = normalized.strip('_')
    return normalized


def fuzzy_match_score(s1: str, s2: str) -> float:
    """Calculate similarity score between two strings.

    Uses SequenceMatcher for fuzzy matching.
    Returns float between 0.0 (no match) and 1.0 (exact match).
    """
    return SequenceMatcher(None, s1, s2).ratio()


def compute_sheet_fingerprint(source: dict) -> str:
    """Compute structural fingerprint for sheet/source matching.

    EDGE CASE: Sheet Renamed
    Fingerprint is based on column structure, NOT sheet name. This allows
    matching even when NHS renames sheets between periods.

    Fingerprint based on:
    - Sorted normalized column names
    - Column count (as tiebreaker)

    Returns:
        12-character hex fingerprint
    """
    # Get columns from files[0].preview.columns or files[0].columns
    columns = []
    files = source.get('files', [])
    if files:
        file_info = files[0]
        preview = file_info.get('preview', {})
        columns = preview.get('columns', file_info.get('columns', []))

    # Extract and normalize column names
    col_names = []
    for col in columns:
        if isinstance(col, dict):
            name = col.get('name', col.get('original_name', ''))
        else:
            name = str(col)
        col_names.append(normalize_column_name(name))

    # Sort for consistency (column order may change)
    col_names = sorted(set(col_names))

    # Create fingerprint
    fingerprint_str = f"{len(col_names)}|{'|'.join(col_names)}"
    return hashlib.md5(fingerprint_str.encode()).hexdigest()[:12]


def match_columns_to_reference(
    draft_columns: List,
    ref_columns: List,
    fuzzy_threshold: float = 0.8
) -> Tuple[List[dict], List[dict]]:
    """Match draft columns against reference columns with fuzzy matching.

    HANDLES MULTIPLE FORMATS:
    - Draft columns: Can be strings (raw names) OR dicts with 'name' key
    - Reference columns: Can be strings OR dicts with 'name'/'code' keys

    EDGE CASES HANDLED:
    - Exact match: Column name matches exactly → copy semantic info
    - Fuzzy match: Column name 80%+ similar → copy semantic info (handles renames)
    - New column: No match found → add to 'new' list for LLM enrichment
    - Removed column: In reference but not draft → ignored (not an error)

    Args:
        draft_columns: Columns from current period's draft manifest
        ref_columns: Columns from reference manifest with semantic names
        fuzzy_threshold: Minimum similarity for fuzzy match (default 0.8 = 80%)

    Returns:
        Tuple of (matched_columns, new_columns)
        - matched_columns: Have semantic names copied from reference
        - new_columns: Need LLM enrichment (no match found)
    """
    matched = []
    new = []

    def get_column_name(col) -> str:
        """Extract column name from string or dict."""
        if isinstance(col, str):
            return col
        elif isinstance(col, dict):
            return col.get('name', col.get('code', col.get('original_name', '')))
        return str(col)

    def to_column_dict(col) -> dict:
        """Convert column to dict format."""
        if isinstance(col, dict):
            return col
        return {'name': str(col)}

    # Build lookup from reference: normalized_name -> column dict
    ref_by_name = {}
    for col in ref_columns:
        name = get_column_name(col)
        norm_name = normalize_column_name(name)
        if norm_name:
            ref_by_name[norm_name] = to_column_dict(col)

    # Track which reference columns have been matched (avoid double-matching)
    matched_ref_names = set()

    for draft_col in draft_columns:
        draft_name = get_column_name(draft_col)
        norm_draft = normalize_column_name(draft_name)
        draft_dict = to_column_dict(draft_col)

        if not norm_draft:
            new.append(draft_dict)
            continue

        # Strategy 1: Exact match
        if norm_draft in ref_by_name and norm_draft not in matched_ref_names:
            ref_col = ref_by_name[norm_draft]
            merged = merge_column_metadata(draft_dict, ref_col)
            matched.append(merged)
            matched_ref_names.add(norm_draft)
            continue

        # Strategy 2: Fuzzy match
        best_match_name = None
        best_score = 0.0

        for ref_name in ref_by_name:
            if ref_name in matched_ref_names:
                continue
            score = fuzzy_match_score(norm_draft, ref_name)
            if score >= fuzzy_threshold and score > best_score:
                best_score = score
                best_match_name = ref_name

        if best_match_name:
            ref_col = ref_by_name[best_match_name]
            merged = merge_column_metadata(draft_dict, ref_col)
            matched.append(merged)
            matched_ref_names.add(best_match_name)
            continue

        # No match found - needs LLM enrichment
        new.append(draft_dict)

    return matched, new


def merge_column_metadata(draft_col: dict, ref_col: dict) -> dict:
    """Merge column metadata, preferring reference for semantic fields.

    Draft provides: raw name, inferred_type (current)
    Reference provides: semantic_name, description, data_type, query_keywords, etc.
    """
    merged = draft_col.copy()

    # Copy semantic fields from reference
    semantic_fields = [
        'semantic_name', 'description', 'data_type',
        'is_dimension', 'is_measure', 'query_keywords'
    ]

    for field in semantic_fields:
        if field in ref_col:
            merged[field] = ref_col[field]

    # Keep original_name from draft (current period's actual header)
    if 'original_name' not in merged and 'name' in draft_col:
        merged['original_name'] = draft_col['name']

    return merged


def match_source_to_reference_by_fingerprint(
    draft_source: dict,
    ref_sources: List[dict],
    overlap_threshold: float = 0.7
) -> Optional[dict]:
    """Find best matching reference source using fingerprint and column overlap.

    EDGE CASES HANDLED:
    - Sheet renamed: Fingerprint matches (same columns, different sheet name)
    - Sheet split: Partial match if >70% columns overlap
    - Sheet merged: Partial match if draft is superset of reference

    Args:
        draft_source: Source from current period's draft
        ref_sources: All sources from reference manifest
        overlap_threshold: Minimum column overlap for partial match (default 0.7 = 70%)

    Returns:
        Best matching reference source, or None if no good match
    """
    draft_fp = compute_sheet_fingerprint(draft_source)
    draft_cols = set()

    # Extract draft column names
    files = draft_source.get('files', [])
    if files:
        preview = files[0].get('preview', {})
        for col in preview.get('columns', []):
            name = col.get('name', col.get('original_name', '')) if isinstance(col, dict) else str(col)
            draft_cols.add(normalize_column_name(name))

    # Strategy 1: Exact fingerprint match
    for ref_src in ref_sources:
        if compute_sheet_fingerprint(ref_src) == draft_fp:
            return ref_src

    # Strategy 2: Column overlap match (for splits/merges/renames)
    best_match = None
    best_overlap = 0.0

    for ref_src in ref_sources:
        ref_cols = set()
        ref_files = ref_src.get('files', [])
        if ref_files:
            ref_preview = ref_files[0].get('preview', {})
            for col in ref_preview.get('columns', []):
                name = col.get('name', col.get('original_name', '')) if isinstance(col, dict) else str(col)
                ref_cols.add(normalize_column_name(name))

        if not draft_cols or not ref_cols:
            continue

        # Calculate overlap ratio
        intersection = len(draft_cols & ref_cols)
        overlap = intersection / max(len(draft_cols), 1)

        if overlap >= overlap_threshold and overlap > best_overlap:
            best_overlap = overlap
            best_match = ref_src

    return best_match


# === END ROLLING REFERENCE FUNCTIONS ===


def clean_yaml_response(text: str) -> str:
    """Attempt to fix common LLM YAML syntax errors."""
    if "```" in text:
        text = text.split("```yaml")[-1].split("```")[0]
        if text.startswith("yaml\n"):
            text = text.replace("yaml\n", "", 1)

    text = text.strip()
    text = text.replace('{{', '{').replace('}}', '}')

    lines = text.split('\n')
    fixed_lines = []

    for line in lines:
        if re.match(r'^\s+(name|description):\s+[^"\'].*:', line):
            match = re.match(r'^(\s+)(name|description):\s+(.+)$', line)
            if match:
                indent, key, value = match.groups()
                if not (value.startswith('"') or value.startswith("'")):
                    line = f'{indent}{key}: "{value}"'
        fixed_lines.append(line)

    return '\n'.join(fixed_lines)


def build_enrichment_prompt(manifest: dict, data_sources_only: List[dict]) -> str:
    """Build enrichment prompt for LLM (simplified version)."""

    pub_url = manifest['manifest']['source_url']
    pub_context = manifest['manifest'].get('publication_context', {})
    sources_count = len(data_sources_only)

    sources_yaml = yaml.dump(data_sources_only, default_flow_style=False)

    pub_title = pub_context.get('page_title', 'Unknown')

    prompt = f"""You are an expert data architect enriching an NHS data publication manifest.

INPUT MANIFEST ({sources_count} DATA TABLES):
```yaml
{sources_yaml}
```

PUBLICATION CONTEXT:
- Title: {pub_title}
- URL: {pub_url}

TASK: Enrich this manifest with semantic codes, names, descriptions, and column metadata.

REQUIREMENTS:

1. **code**: Short, semantic snake_case
   - Create codes based on what the data MEANS, not the filename
   - Good: `rtt_provider_incomplete`, `adhd_prevalence_age`
   - Bad: `xlsx_77252_provider`, `table_1a`

2. **name**: Human-readable with publication prefix

3. **table**: Derive a 3-4 char prefix from the PUBLICATION TITLE, then add concept:
   - Analyze: "{pub_title}"
   - Create prefix (e.g., "RTT Waiting Times" -> `rtt`, "ADHD Management" -> `adhd`)
   - Format: tbl_{{prefix}}_{{concept}} (max 30 chars)
   - CRITICAL: NEVER use filenames, file IDs (77252), or format (xlsx/csv)

   ONE-SHOT EXAMPLE:
   Publication: "RTT Waiting Times - Incomplete Pathways by Provider"
   Prefix: `rtt`
   Tables: `tbl_rtt_provider`, `tbl_rtt_provider_dta`, `tbl_rtt_is_provider`

   BAD examples (NEVER do this):
   - `tbl_xlsx_77252_provider` (contains file ID)
   - `tbl_incomplete_provider_apr25` (contains date)

4. **description**: What analyst needs to know

5. **metadata**: record_type, granularity, measures, dimensions, tags

6. **columns**: Map each column to semantic name with description

OUTPUT:
Return complete enriched manifest as valid YAML.
Start with "manifest:" immediately.
QUOTE ALL NAME AND DESCRIPTION FIELDS.
"""

    return prompt


def call_gemini_api(prompt: str, event_store: Optional[EventStore] = None,
                   publication: str = None, period: str = None,
                   db_run_id: Optional[uuid.UUID] = None) -> Tuple[dict, dict]:
    """Call Gemini API and return parsed response with metadata.

    Args:
        prompt: The enrichment prompt
        event_store: Optional EventStore for file/console logging
        publication: Publication code for event logging
        period: Period for event logging
        db_run_id: Database run ID for tbl_enrichment_api_calls tracking
    """
    import google.generativeai as genai

    api_key = os.getenv('GEMINI_API_KEY')
    if not api_key:
        raise ValueError("GEMINI_API_KEY not found in .env")

    model_name = os.getenv('LLM_MODEL', 'gemini-2.0-flash-exp')

    if event_store:
        event_store.emit(create_event(
            EventType.LLM_CALL,
            event_store.run_id,
            publication=publication,
            period=period,
            stage='enrich',
            level=EventLevel.INFO,
            message=f"Calling {model_name} API",
            context={'prompt_length': len(prompt), 'model': model_name}
        ))

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(
        model_name=model_name,
        generation_config={
            "temperature": 0.1,
            "max_output_tokens": 65536
        }
    )

    start_time = time.time()
    response = model.generate_content(prompt)
    latency_ms = int((time.time() - start_time) * 1000)

    raw_text = response.text.strip()

    input_tokens = 0
    output_tokens = 0
    if hasattr(response, 'usage_metadata'):
        input_tokens = response.usage_metadata.prompt_token_count
        output_tokens = response.usage_metadata.candidates_token_count

    # Log API call to database (tbl_enrichment_api_calls)
    _log_api_call(
        run_id=db_run_id,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        latency_ms=latency_ms,
        model_name=model_name,
        status='success'
    )

    if event_store:
        event_store.emit(create_event(
            EventType.LLM_CALL,
            event_store.run_id,
            publication=publication,
            period=period,
            stage='enrich',
            level=EventLevel.INFO,
            message=f"LLM response received",
            context={
                'input_tokens': input_tokens,
                'output_tokens': output_tokens,
                'latency_ms': latency_ms,
                'model': model_name
            }
        ))

    cleaned_text = clean_yaml_response(raw_text)

    try:
        parsed = yaml.safe_load(cleaned_text)

        metadata = {
            'input_tokens': input_tokens,
            'output_tokens': output_tokens,
            'latency_ms': latency_ms,
            'model_name': model_name
        }
        return parsed, metadata
    except yaml.YAMLError as e:
        if event_store:
            event_store.emit(create_event(
                EventType.ERROR,
                event_store.run_id,
                publication=publication,
                period=period,
                level=EventLevel.ERROR,
                message=f"YAML parse error: {e}",
                context={'raw_output_length': len(raw_text)}
            ))
        raise


def merge_technical_fields(original: dict, enriched: dict) -> dict:
    """Merge technical fields from original files back into enriched manifest."""
    original_files = {}
    for source in original['sources']:
        for file in source.get('files', []):
            url = file['url']
            original_files[url] = file

    restored_count = 0
    for source in enriched['sources']:
        for file in source.get('files', []):
            url = file.get('url')
            if url and url in original_files:
                orig_file = original_files[url]
                for field in ['sheet', 'extract', 'period', 'mode', 'attributes']:
                    if field in orig_file and field not in file:
                        file[field] = orig_file[field]
                        restored_count += 1

    return enriched


def validate_enrichment(original: dict, enriched: dict) -> None:
    """Validate all file URLs preserved."""
    original_urls = set()
    for source in original['sources']:
        for file in source.get('files', []):
            original_urls.add(file['url'])

    enriched_urls = set()
    for source in enriched['sources']:
        for file in source.get('files', []):
            enriched_urls.add(file['url'])

    missing_urls = original_urls - enriched_urls
    if missing_urls:
        raise ValueError(f"Missing URLs in enriched manifest: {missing_urls}")

    extra_urls = enriched_urls - original_urls
    if extra_urls:
        raise ValueError(f"Extra URLs in enriched manifest: {extra_urls}")


def enrich_manifest(
    input_path: str,
    output_path: str,
    reference_path: Optional[str] = None,
    event_store: Optional[EventStore] = None,
    publication: str = None,
    period: str = None
) -> EnrichmentResult:
    """Enrich manifest with LLM-generated semantic metadata.

    Args:
        input_path: Path to raw manifest YAML
        output_path: Path to write enriched manifest
        reference_path: Optional reference manifest for deterministic naming
        event_store: Optional EventStore for observability
        publication: Publication code for event logging
        period: Period identifier for event logging

    Returns:
        EnrichmentResult with success status and metrics
    """
    start_time = time.time()

    try:
        if event_store:
            event_store.emit(create_event(
                EventType.STAGE_STARTED,
                event_store.run_id,
                message="Starting manifest enrichment",
                publication=publication,
                period=period,
                level=EventLevel.INFO,
                context={'input': input_path, 'output': output_path}
            ))

        # Load raw manifest
        with open(input_path) as f:
            original_manifest = yaml.safe_load(f)

        # Filter noise sources
        all_sources = original_manifest['sources']
        data_sources = []
        noise_sources = []

        for source in all_sources:
            if is_noise_source(source):
                source['enabled'] = False
                source['description'] = source.get('description', 'Metadata/Dictionary (auto-disabled)')
                noise_sources.append(source)
            else:
                data_sources.append(source)

        if event_store:
            event_store.emit(create_event(
                EventType.STAGE_COMPLETED,
                event_store.run_id,
                publication=publication,
                period=period,
                stage='filter',
                level=EventLevel.INFO,
                message=f"Filtered sources: {len(data_sources)} data, {len(noise_sources)} metadata",
                context={'data_sources': len(data_sources), 'noise_sources': len(noise_sources)}
            ))

        # Log enrichment start to database (tbl_enrichment_runs)
        manifest_name = original_manifest['manifest'].get('name', Path(input_path).stem)
        db_run_id = _log_enrichment_start(
            manifest_name=manifest_name,
            total_sources=len(all_sources),
            data_sources=len(data_sources),
            noise_sources=len(noise_sources)
        )

        # Reference matching logic - 3 strategy matching for cross-period consistency
        enriched_from_ref = 0
        llm_metadata = None
        reference_enriched_sources = []  # Sources enriched from reference (skip LLM)
        original_data_sources = data_sources.copy()  # Save for validation before reference matching

        # If reference manifest provided, apply intelligent matching
        if reference_path:
            try:
                with open(reference_path) as f:
                    ref_manifest = yaml.safe_load(f)

                # Build THREE maps for hybrid matching:
                # 1. URL -> source (exact match for stable URLs like GP Practice)
                # 2. URL pattern -> source (fuzzy match for variable URLs like Online Consultation)
                # 3. (URL pattern, sheet) -> source (most specific for multi-file publications)
                ref_map_url = {}
                ref_map_pattern = {}
                ref_map_pattern_sheet = {}

                for src in ref_manifest.get('sources', []):
                    files = src.get('files', [])
                    for file in files:
                        if 'url' in file:
                            # Strategy 1: Exact URL matching (stable URLs)
                            url_key = Path(file['url']).name
                            if url_key not in ref_map_url:
                                ref_map_url[url_key] = src

                            # Strategy 2: Pattern-based URL matching (variable URLs)
                            url_pattern = normalize_url(file['url'])
                            if url_pattern not in ref_map_pattern:
                                ref_map_pattern[url_pattern] = src

                            # Strategy 3: Pattern + sheet/extract matching (most specific)
                            if 'sheet' in file:
                                pattern_sheet_key = (url_pattern, file['sheet'])
                                if pattern_sheet_key not in ref_map_pattern_sheet:
                                    ref_map_pattern_sheet[pattern_sheet_key] = src
                            elif 'extract' in file:
                                extract_pattern = normalize_url(file['extract'])
                                pattern_extract_key = (url_pattern, extract_pattern)
                                if pattern_extract_key not in ref_map_pattern_sheet:
                                    ref_map_pattern_sheet[pattern_extract_key] = src

                if event_store:
                    event_store.emit(create_event(
                        EventType.REFERENCE_MATCHED,
                        event_store.run_id,
                        publication=publication,
                        period=period,
                        level=EventLevel.INFO,
                        message=f"Reference loaded: {len(ref_map_url)} URLs, {len(ref_map_pattern)} patterns",
                        context={'exact_urls': len(ref_map_url), 'patterns': len(ref_map_pattern),
                                 'pattern_sheets': len(ref_map_pattern_sheet)}
                    ))

                # Apply matching to data_sources
                new_data_sources = []

                for source in data_sources:
                    matched = False
                    ref_src = None
                    match_method = None

                    if source.get('files'):
                        for file in source['files']:
                            if 'url' in file:
                                # Strategy 1: Exact URL match
                                url_key = Path(file['url']).name
                                if url_key in ref_map_url:
                                    ref_src = ref_map_url[url_key]
                                    matched = True
                                    match_method = 'exact_url'
                                    break

                                # Strategy 2a: Pattern + Sheet match (Excel files)
                                if not matched and 'sheet' in file:
                                    url_pattern = normalize_url(file['url'])
                                    pattern_sheet_key = (url_pattern, file['sheet'])
                                    if pattern_sheet_key in ref_map_pattern_sheet:
                                        ref_src = ref_map_pattern_sheet[pattern_sheet_key]
                                        matched = True
                                        match_method = 'pattern_sheet'
                                        break

                                # Strategy 2b: Pattern + Extract match (ZIP/CSV files)
                                if not matched and 'extract' in file:
                                    url_pattern = normalize_url(file['url'])
                                    extract_pattern = normalize_url(file['extract'])
                                    pattern_extract_key = (url_pattern, extract_pattern)
                                    if pattern_extract_key in ref_map_pattern_sheet:
                                        ref_src = ref_map_pattern_sheet[pattern_extract_key]
                                        matched = True
                                        match_method = 'pattern_extract'
                                        break

                                # Strategy 3: Pattern-only match (fallback)
                                if not matched:
                                    url_pattern = normalize_url(file['url'])
                                    if url_pattern in ref_map_pattern:
                                        ref_src = ref_map_pattern[url_pattern]
                                        matched = True
                                        match_method = 'pattern'
                                        break

                    if matched and ref_src:
                        # Copy source-level semantic fields from reference
                        if 'code' in ref_src:
                            source['code'] = ref_src['code']
                        if 'name' in ref_src:
                            source['name'] = ref_src['name']
                        if 'table' in ref_src:
                            source['table'] = ref_src['table']
                        if 'description' in ref_src:
                            source['description'] = ref_src['description']
                        if 'notes' in ref_src:
                            source['notes'] = ref_src['notes']
                        if 'metadata' in ref_src:
                            source['metadata'] = ref_src['metadata']

                        # COLUMN-LEVEL MATCHING (Rolling Reference Enhancement)
                        # Copy column metadata from reference, track new columns
                        # EDGE CASES: New columns get raw names (schema drift handles at load)
                        #             Renamed columns matched via fuzzy matching (80% threshold)
                        ref_columns = ref_src.get('columns', [])
                        if ref_columns and source.get('files'):
                            # Get draft columns from preview
                            draft_file = source['files'][0]
                            draft_preview = draft_file.get('preview', {})
                            draft_columns = draft_preview.get('columns', [])

                            if draft_columns:
                                matched_cols, new_cols = match_columns_to_reference(
                                    draft_columns, ref_columns, fuzzy_threshold=0.8
                                )

                                # Update preview with matched column metadata
                                if matched_cols or new_cols:
                                    draft_preview['columns'] = matched_cols + new_cols
                                    draft_file['preview'] = draft_preview

                                    # Log column matching stats
                                    if event_store and (matched_cols or new_cols):
                                        event_store.emit(create_event(
                                            EventType.INFO,
                                            event_store.run_id,
                                            publication=publication,
                                            period=period,
                                            level=EventLevel.DEBUG,
                                            message=f"Column matching for {source.get('code', 'unknown')}: {len(matched_cols)} matched, {len(new_cols)} new",
                                            context={'matched': len(matched_cols), 'new': len(new_cols)}
                                        ))

                        # Also copy columns at source level if present in reference
                        if 'columns' in ref_src:
                            # Only copy if source doesn't already have enriched columns
                            if 'columns' not in source:
                                source['columns'] = ref_src['columns']

                        enriched_from_ref += 1
                        reference_enriched_sources.append(source)
                    else:
                        new_data_sources.append(source)

                data_sources = new_data_sources

                if event_store:
                    event_store.emit(create_event(
                        EventType.REFERENCE_MATCHED,
                        event_store.run_id,
                        publication=publication,
                        period=period,
                        level=EventLevel.INFO,
                        message=f"Reference matching: {enriched_from_ref} matched, {len(data_sources)} remaining for LLM",
                        context={'matched': enriched_from_ref, 'remaining': len(data_sources)}
                    ))

            except Exception as e:
                if event_store:
                    event_store.emit(create_event(
                        EventType.WARNING,
                        event_store.run_id,
                        publication=publication,
                        period=period,
                        level=EventLevel.WARNING,
                        message=f"Could not load/apply reference: {str(e)}",
                        context={'error': str(e)}
                    ))

        # Call LLM on remaining data sources (those not matched by reference)
        if data_sources:
            # COMPRESS: Detect repetitive column patterns to avoid token limits
            compressed_sources, compression_map = compress_manifest_for_enrichment(data_sources)

            if compression_map:
                # Log compression stats
                total_cols_before = sum(
                    len(f.get('preview', {}).get('columns', []))
                    for src in data_sources for f in src.get('files', [])
                )
                total_cols_after = sum(
                    len(f.get('preview', {}).get('columns', []))
                    for src in compressed_sources for f in src.get('files', [])
                )
                if event_store:
                    event_store.emit(create_event(
                        EventType.INFO,
                        event_store.run_id,
                        publication=publication,
                        period=period,
                        stage='enrich',
                        message=f"Compressed {total_cols_before} columns → {total_cols_after} ({len(compression_map)} patterns detected)",
                        context={'compression_ratio': f'{total_cols_after}/{total_cols_before}'}
                    ))

            # Send compressed sources to LLM
            prompt = build_enrichment_prompt(original_manifest, compressed_sources)
            enriched_data_sources, llm_metadata = call_gemini_api(
                prompt, event_store, publication, period, db_run_id=db_run_id
            )

            # Handle different response formats
            if isinstance(enriched_data_sources, dict):
                if 'sources' in enriched_data_sources:
                    enriched_data_sources = enriched_data_sources['sources']
                elif 'manifest' in enriched_data_sources:
                    manifest_data = enriched_data_sources['manifest']
                    if isinstance(manifest_data, list):
                        enriched_data_sources = manifest_data
                    elif isinstance(manifest_data, dict):
                        enriched_data_sources = manifest_data.get('sources', [])

            # EXPAND: Restore full column set with pattern-based metadata
            if compression_map:
                enriched_data_sources = expand_manifest_from_enrichment(
                    enriched_data_sources, compression_map
                )
                if event_store:
                    event_store.emit(create_event(
                        EventType.INFO,
                        event_store.run_id,
                        publication=publication,
                        period=period,
                        stage='enrich',
                        message=f"Expanded {len(compression_map)} patterns back to full column set"
                    ))
        else:
            enriched_data_sources = []
            llm_metadata = {'input_tokens': 0, 'output_tokens': 0, 'latency_ms': 0}

        # Combine: reference-matched + LLM-enriched sources
        enriched_data_sources = reference_enriched_sources + enriched_data_sources

        # Merge enriched + noise sources
        all_enriched_sources = enriched_data_sources + noise_sources
        enriched_manifest = {
            'manifest': original_manifest['manifest'],
            'sources': all_enriched_sources
        }

        # Restore technical fields
        enriched_manifest = merge_technical_fields(original_manifest, enriched_manifest)

        # Validate - compare all original data sources against all enriched sources
        original_data_manifest = {'manifest': original_manifest['manifest'], 'sources': original_data_sources}
        enriched_data_manifest = {'manifest': original_manifest['manifest'], 'sources': enriched_data_sources}
        validate_enrichment(original_data_manifest, enriched_data_manifest)

        # Strip preview fields
        for source in enriched_manifest.get('sources', []):
            for file in source.get('files', []):
                if 'preview' in file:
                    del file['preview']

        # Write output
        with open(output_path, 'w') as f:
            yaml.dump(enriched_manifest, f, Dumper=YAMLDumper, sort_keys=False, allow_unicode=True)

        duration_ms = int((time.time() - start_time) * 1000)

        # Log enrichment completion to database (tbl_enrichment_runs)
        _log_enrichment_complete(
            run_id=db_run_id,
            status='success',
            validation_status='passed',
            duration_ms=duration_ms,
            total_input_tokens=llm_metadata.get('input_tokens', 0) if llm_metadata else 0,
            total_output_tokens=llm_metadata.get('output_tokens', 0) if llm_metadata else 0,
            reference_matched=enriched_from_ref
        )

        if event_store:
            event_store.emit(create_event(
                EventType.STAGE_COMPLETED,
                event_store.run_id,
                publication=publication,
                period=period,
                level=EventLevel.INFO,
                message=f"Manifest enrichment completed: {len(enriched_data_sources)} LLM-enriched, {len(noise_sources)} auto-disabled",
                context={
                    'output_path': output_path,
                    'sources_total': len(all_enriched_sources),
                    'sources_enriched': len(enriched_data_sources),
                    'sources_from_reference': enriched_from_ref,
                    'duration_ms': duration_ms,
                    'llm_tokens_in': llm_metadata.get('input_tokens', 0) if llm_metadata else 0,
                    'llm_tokens_out': llm_metadata.get('output_tokens', 0) if llm_metadata else 0
                }
            ))

        return EnrichmentResult(
            success=True,
            output_path=output_path,
            sources_enriched=len(enriched_data_sources),
            sources_from_reference=enriched_from_ref,
            sources_total=len(all_enriched_sources),
            llm_calls_made=1 if data_sources else 0,
            input_tokens=llm_metadata.get('input_tokens', 0) if llm_metadata else 0,
            output_tokens=llm_metadata.get('output_tokens', 0) if llm_metadata else 0,
            latency_ms=llm_metadata.get('latency_ms', 0) if llm_metadata else 0
        )

    except Exception as e:
        duration_ms = int((time.time() - start_time) * 1000)
        error_str = f"{type(e).__name__}: {str(e)}"

        # Log enrichment failure to database (db_run_id may not exist if error was early)
        if 'db_run_id' in locals():
            _log_enrichment_complete(
                run_id=db_run_id,
                status='failed',
                validation_status='failed',
                duration_ms=duration_ms,
                error_message=error_str
            )

        if event_store:
            event_store.emit(create_event(
                EventType.STAGE_FAILED,
                event_store.run_id,
                publication=publication,
                period=period,
                level=EventLevel.ERROR,
                message=f"Enrichment failed: {error_str}",
                context={'error': error_str, 'duration_ms': duration_ms}
            ))

        return EnrichmentResult(
            success=False,
            output_path=output_path,
            sources_enriched=0,
            sources_from_reference=0,
            sources_total=0,
            llm_calls_made=0,
            input_tokens=0,
            output_tokens=0,
            latency_ms=duration_ms,
            error=error_str
        )
