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

load_dotenv()


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

    # Simplified prompt (full version is 530 lines - keeping concise for library)
    prompt = f"""You are an expert data architect enriching an NHS data publication manifest.

INPUT MANIFEST ({sources_count} DATA TABLES):
```yaml
{sources_yaml}
```

PUBLICATION CONTEXT:
- Title: {pub_context.get('page_title', 'Unknown')}
- URL: {pub_url}

TASK: Enrich this manifest with semantic codes, names, descriptions, and column metadata.

REQUIREMENTS:
1. **code**: Short, semantic snake_case (e.g., pcn_wf_fte_gender)
2. **name**: Human-readable with publication prefix
3. **table**: tbl_{{prefix}}_{{concept}} (max 30 chars, period-agnostic)
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
                   publication: str = None, period: str = None) -> Tuple[dict, dict]:
    """Call Gemini API and return parsed response with metadata."""
    import google.generativeai as genai

    api_key = os.getenv('GEMINI_API_KEY')
    if not api_key:
        raise ValueError("GEMINI_API_KEY not found in .env")

    model_name = os.getenv('LLM_MODEL', 'gemini-2.0-flash-exp')

    if event_store:
        event_store.emit(create_event(
            EventType.WARNING,
            event_store.run_id,
            publication=publication,
            period=period,
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

    if event_store:
        event_store.emit(create_event(
            EventType.WARNING,
            event_store.run_id,
            publication=publication,
            period=period,
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
                EventType.WARNING,
                event_store.run_id,
                publication=publication,
                period=period,
                level=EventLevel.INFO,
                message=f"Filtered sources: {len(data_sources)} data, {len(noise_sources)} metadata",
                context={'data_sources': len(data_sources), 'noise_sources': len(noise_sources)}
            ))

        # Reference matching logic (simplified - keeping it basic for now)
        enriched_from_ref = 0
        llm_metadata = None

        # TODO: Add reference matching logic from original script (lines 1037-1202)
        # For now, skip reference matching and go straight to LLM

        # Call LLM on data sources
        if data_sources:
            prompt = build_enrichment_prompt(original_manifest, data_sources)
            enriched_data_sources, llm_metadata = call_gemini_api(
                prompt, event_store, publication, period
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
        else:
            enriched_data_sources = []
            llm_metadata = {'input_tokens': 0, 'output_tokens': 0, 'latency_ms': 0}

        # Merge enriched + noise sources
        all_enriched_sources = enriched_data_sources + noise_sources
        enriched_manifest = {
            'manifest': original_manifest['manifest'],
            'sources': all_enriched_sources
        }

        # Restore technical fields
        enriched_manifest = merge_technical_fields(original_manifest, enriched_manifest)

        # Validate
        original_data_manifest = {'manifest': original_manifest['manifest'], 'sources': data_sources}
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

        # Debug: print full traceback
        import traceback
        traceback.print_exc()

        error_str = f"{type(e).__name__}: {str(e)}"

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
