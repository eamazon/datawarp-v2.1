#!/usr/bin/env python3
"""
V3: OPTIMIZED enrichment for local Q wen model with parallel processing.

Improvements over V2:
- Combined Step 2 + Step 3 (single call per source, 2× faster)
- Parallel processing with max_workers=4 (3× total speedup)
- Minimal examples (faster prompts, more stable)
- Target time: ~3 minutes (vs 9 min in v2)

Key Features:
- Multi-step prompting for smaller models
- Parallel execution for speed
- Correct file mapping for consolidated sources  
- Technical field preservation
- Noise filtering
- Validation
- General-purpose (works with any manifest)

Usage:
    python scripts/local_llm/enrich_manifest_qwen_v3.py input.yaml output.yaml
    
Recommended: Use Q4_K_M quantization with Ollama for best performance
"""

import json
import requests
import yaml
import sys
from pathlib import Path
from datetime import datetime
import re
from concurrent.futures import ThreadPoolExecutor, as_completed


def clean_column_name(name):
    """Clean malformed column names from preview data.
    
    Generic cleaning that works for any manifest:
    - Removes trailing " - " or " - - " patterns
    - Removes duplicate repeated words (e.g., "ENGLAND ENGLAND")
    - Strips extra whitespace
    """
    if not name or not isinstance(name, str):
        return ""
    
    # Remove trailing dash patterns (" - ", " - - ", etc.)
    name = re.sub(r'(\s+-\s*)+$', '', name)
    
    # Detect and fix duplicate words
    words = name.split()
    if len(words) >= 3:
        # If more than 50% of words are duplicates, likely garbage
        unique_words = set(words)
        if len(unique_words) < len(words) / 2:
            # Take first occurrence of each word
            seen = set()
            cleaned_words = []
            for word in words:
                if word not in seen:
                    cleaned_words.append(word)
                    seen.add(word)
            name = ' '.join(cleaned_words)
    
    return name.strip()


def validate_and_fix_columns(columns):
    """Post-process column metadata to fix common LLM errors.
    
    Generic fixes that work for any manifest:
    - Cleans malformed column names
    - Converts string booleans to actual booleans
    - Normalizes data types
    - Renames semantic_name to pg_name for DataWarp compatibility
    """
    fixed_columns = []
    
    for col in columns:
        fixed = col.copy()
        
        # Fix 1: Clean original_name
        if 'original_name' in fixed:
            fixed['original_name'] = clean_column_name(fixed['original_name'])
        
        # Fix 2: Convert string booleans to actual booleans
        for bool_field in ['is_dimension', 'is_measure']:
            if bool_field in fixed:
                val = fixed[bool_field]
                if isinstance(val, str):
                    fixed[bool_field] = val.lower() in ('true', 'yes', '1')
                elif not isinstance(val, bool):
                    # Default to False if invalid type
                    fixed[bool_field] = False
        
        # Fix 3: Normalize data_type
        if 'data_type' in fixed:
            dt = str(fixed['data_type']).lower().strip()
            valid_types = ['varchar', 'integer', 'numeric', 'double precision', 'date']
            if dt not in valid_types:
                # Default to varchar if invalid
                fixed['data_type'] = 'varchar'
            else:
                fixed['data_type'] = dt
        
        # Fix 4: Rename semantic_name to pg_name (DataWarp requirement)
        if 'semantic_name' in fixed and 'pg_name' not in fixed:
            fixed['pg_name'] = fixed.pop('semantic_name')
        
        # Fix 5: Ensure pg_name is valid PostgreSQL identifier
        if 'pg_name' in fixed:
            pg_name = fixed['pg_name']
            # Replace invalid chars with underscore
            pg_name = re.sub(r'[^a-z0-9_]', '_', pg_name.lower())
            # Remove leading digits
            pg_name = re.sub(r'^[0-9]+', '', pg_name)
            # Max 63 chars (PostgreSQL limit)
            pg_name = pg_name[:63]
            fixed['pg_name'] = pg_name
        
        fixed_columns.append(fixed)
    
    return fixed_columns


def call_ollama(prompt, model="qwen3-vl:8b", step_name="unknown"):
    """Call local Ollama model with prompt."""
    
    # Log prompt (preview)
    print(f"\n{'='*60}")
    print(f"📤 LLM REQUEST: {step_name}")
    print(f"{'='*60}")
    print(f"Model: {model}")
    print(f"Prompt length: {len(prompt)} chars")
    print(f"Prompt preview (first 300 chars):")
    print(prompt[:300] + "..." if len(prompt) > 300 else prompt)
    print(f"{'='*60}\n")
    
    request_payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "format": "json",
        "options": {
            "temperature": 0.1,
            "num_predict": 4096
        }
    }
    
    # Save full request to file
    request_file = f"manifests/qwen_request_{step_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(request_file, 'w') as f:
        json.dump({
            'step': step_name,
            'model': model,
            'prompt': prompt,
            'options': request_payload['options']
        }, f, indent=2)
    print(f"💾 Full request saved to: {request_file}")
    
    # Make API call
    print(f"⏳ Waiting for Qwen response...")
    response = requests.post(
        'http://localhost:11434/api/generate',
        json=request_payload,
        timeout=600
    )
    response.raise_for_status()
    
    data = response.json()
    
    # BUGFIX: qwen3-vl puts JSON in 'thinking' field when format='json'
    raw_text = data.get('response', '') or data.get('thinking', '')
    
    if not raw_text:
        raise ValueError(f"Empty response from Ollama model {model}")
    
    parsed_response = json.loads(raw_text)
    
    # Log response
    print(f"\n{'='*60}")
    print(f"📥 LLM RESPONSE: {step_name}")
    print(f"{'='*60}")
    print(f"Response length: {len(raw_text)} chars")
    print(f"Parsed structure:")
    print(f"  - Top-level keys: {list(parsed_response.keys())}")
    if 'sources' in parsed_response:
        print(f"  - Sources count: {len(parsed_response['sources'])}")
    if 'columns' in parsed_response:
        print(f"  - Columns count: {len(parsed_response['columns'])}")
    print(f"Response preview (first 500 chars):")
    print(json.dumps(parsed_response, indent=2)[:500] + "...")
    print(f"{'='*60}\n")
    
    # Save response to file
    response_file = f"manifests/qwen_response_{step_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(response_file, 'w') as f:
        json.dump(parsed_response, f, indent=2)
    print(f"💾 Full response saved to: {response_file}")
    
    return parsed_response


def is_metadata_or_dictionary(source):
    """Check if source is metadata/dictionary (noise)."""
    name_lower = source.get('name', '').lower()
    code_lower = source.get('code', '').lower()
    
    noise_indicators = [
        'metadata', 'dictionary', 'readme',
        'documentation', 'notes', 'glossary',
        'lookup', 'reference_data'
    ]
    
    return any(ind in name_lower or ind in code_lower for ind in noise_indicators)


def step1_basic_enrichment(sources, pub_context):
    """Step 1: Basic enrichment + consolidation with file mapping."""
    
    # Format sources for LLM
    sources_data = []
    for s in sources:
        sources_data.append({
            'code': s.get('code'),
            'name': s.get('name'),
            'table': s.get('table'),
            'files': [{'url': f['url']} for f in s.get('files', [])]
        })
    
    prompt = f"""You are an expert data architect enriching a data publication manifest.

INPUT: {len(sources)} data sources from this publication:
```json
{json.dumps(sources_data, indent=2)}
```

PUBLICATION:
- Title: {pub_context.get('page_title', 'Unknown Publication')}
- URL: {pub_context.get('page_url', '')}

TASK: For each source, provide:

1. **`code`**: Short semantic snake_case identifier
2. **`name`**: Human-readable name with publication context
3. **`description`**: What analysts need to know (1-2 sentences)
4. **`table`**: Database table name (format: tbl_prefix_concept, max 30 chars).
   **CRITICAL**: Do NOT include dates/periods (e.g. 'oct2025') in the name.
   Use generic names like `tbl_msds_measures` so future months can append to it.
5. **`enabled`**: true for data tables, false for metadata
6. **`consolidates`**: Array of ORIGINAL source codes if consolidating multiple sources

CONSOLIDATION RULES:
- If you see sources split by gender (e.g., male/female), merge into ONE
- If you see sources split by age ranges, consider if they should merge
- List ALL original source codes that were merged in `consolidates` array

Example consolidation:
```json
{{
  "code": "practice_reg_age_sex",
  "name": "Practice Registration by Age and Sex", 
  "description": "Consolidated male/female registration data",
  "table": "tbl_prac_reg_age_sex",
  "enabled": true,
  "consolidates": ["source_male", "source_female"]
}}
```

OUTPUT FORMAT (JSON):
{{
  "sources": [
    {{
      "code": "semantic_code",
      "name": "Human Readable Name",
      "description": "Brief description",
      "table": "tbl_prefix_concept",
      "enabled": true,
      "consolidates": ["original_code1", "original_code2"]
    }}
  ]
}}

CRITICAL: Return ONLY valid JSON. No markdown blocks. If consolidating, MUST include 'consolidates' array.
"""
    return call_ollama(prompt, step_name="step1_basic_enrichment")


def step2_extract_columns(source_code, preview_data):
    """Step 2: Extract column metadata from preview."""
    if not preview_data or len(preview_data.strip()) < 10:
        return {"columns": []}
    
    # CRITICAL: Extract ONLY the header row (first line)
    # This prevents Qwen from getting confused by sample data
    lines = preview_data.strip().split('\n')
    header_row = lines[0] if lines else ""
    sample_rows = lines[1:3] if len(lines) > 1 else []
    
    # Show sample rows for context only
    sample_context = ""
    if sample_rows:
        sample_context = f"""
SAMPLE DATA ROWS (for context only - DO NOT use as column names):
{chr(10).join(sample_rows[:2])}
"""
    
    prompt = f"""Extract column metadata from this data source.

SOURCE: {source_code}

HEADER ROW (contains column names):
{header_row}
{sample_context}

TASK: Map EACH column header to metadata.

STEP-BY-STEP INSTRUCTIONS:
1. Parse the header row above - split by comma, remove quotes
2. Clean each header:
   - Remove trailing " - " or " - - " patterns
   - Remove duplicate words (e.g., "REGION REGION" → "REGION")
   - Trim whitespace
3. Create pg_name: convert to snake_case, all lowercase, max 63 chars
4. Determine type: dimension (category) or measure (numeric)
5. Write one-sentence description

FOR EACH COLUMN:
- original_name: Cleaned header text (after removing garbage)
- pg_name: PostgreSQL column name (snake_case, lowercase)
- description: What it contains (1 sentence)
- data_type: varchar | integer | double precision | date  
- is_dimension: true | false (MUST be boolean, NOT string "true")
- is_measure: true | false (MUST be boolean, NOT string "false")
- query_keywords: [2-4 search terms]

FEW-SHOT EXAMPLE:
Header: "Provider name","Apr 2025","May 2025"
↓
{{
  "columns": [
    {{
      "original_name": "Provider name",
      "pg_name": "provider_name",
      "description": "Name of the healthcare provider organization.",
      "data_type": "varchar",
      "is_dimension": true,
      "is_measure": false,
      "query_keywords": ["provider", "organization", "name"]
    }},
    {{
      "original_name": "Apr 2025",
      "pg_name": "apr_2025",
      "description": "Count of procedures in April 2025.",
      "data_type": "integer",
      "is_dimension": false,
      "is_measure": true,
      "query_keywords": ["april", "count", "total"]
    }},
    {{
      "original_name": "May 2025",
      "pg_name": "may_2025",
      "description": "Count of procedures in May 2025.",
      "data_type": "integer",
      "is_dimension": false,
      "is_measure": true,
      "query_keywords": ["may", "count", "total"]
    }}
  ]
}}

CRITICAL RULES:
1. original_name = cleaned header (remove " - -", duplicates, whitespace)
2. pg_name = snake_case, lowercase, letters/numbers/underscore only, max 63 chars
3. is_dimension and is_measure MUST be boolean true/false (NOT strings "true"/"false")
4. Include ALL columns from header row
5. Skip columns named "Notes", "*", or "Source" unless they contain data
6. Return ONLY valid JSON, no markdown code blocks

NOW YOUR TURN:
Process the header row above.
"""
    
    result = call_ollama(prompt, step_name=f"step2_columns_{source_code}")
    
    # Post-process to fix common errors
    if 'columns' in result:
        result['columns'] = validate_and_fix_columns(result['columns'])
    
    return result


def step3_metadata_enrichment(source_code, source_name, columns):
    """Step 3: Add metadata classification."""
    measure_cols = [c.get('pg_name', c.get('semantic_name', '')) for c in columns if c.get('is_measure')]
    dimension_cols = [c.get('pg_name', c.get('semantic_name', '')) for c in columns if c.get('is_dimension')]
    
    prompt = f"""Classify this data source with metadata.

SOURCE: {source_code}
NAME: {source_name}
MEASURES: {measure_cols}
DIMENSIONS: {dimension_cols}

TASK: Provide classification metadata:

1. record_type: reference | aggregate_summary | detailed_breakdown
2. granularity: national | regional | organization | individual
3. measures: List of measure column names
4. dimensions: List of dimension column names  
5. tags: [2-4 searchable keywords]

OUTPUT (JSON):
{{
  "metadata": {{
    "record_type": "detailed_breakdown",
    "granularity": "organization",
    "measures": ["count", "total"],
    "dimensions": ["date", "category"],
    "tags": ["keyword1", "keyword2"]
  }}
}}

Return ONLY valid JSON. No markdown blocks.
"""
    return call_ollama(prompt, step_name=f"step3_metadata_{source_code}")


def step2_and_3_combined(source_code, source_name, preview_data):
    """V3: Combined Step 2 + Step 3 - Extract columns AND metadata in ONE call.
    
    Optimizations:
    - Single API call instead of 2 (2× faster per source)
    - Minimal example (single column for stability + speed)
    - Consistent naming (LLM sees full context)
    """
    if not preview_data or len(preview_data.strip()) < 10:
        return {"columns": [], "metadata": {}}
    
    # Extract ONLY the header row
    lines = preview_data.strip().split('\n')
    header_row = lines[0] if lines else ""
    
    # MINIMAL example - just one column for speed + stability
    prompt = f"""Extract columnsAND metadata for this source.

SOURCE: {source_code}
NAME: {source_name}
HEADER: {header_row}

EXAMPLE (minimal):
"Provider","Apr 2025"
↓
{{
  "columns": [
    {{"original_name":"Provider","pg_name":"provider","description":"Provider name.","data_type":"varchar","is_dimension":true,"is_measure":false,"query_keywords":["provider"]}},
    {{"original_name":"Apr 2025","pg_name":"apr_2025","description":"April count.","data_type":"integer","is_dimension":false,"is_measure":true,"query_keywords":["april"]}}
  ],
  "metadata":{{"record_type":"aggregate_summary","granularity":"organization","measures":["apr_2025"],"dimensions":["provider"],"tags":["provider","monthly"]}}
}}

RULES:
1. Clean headers (remove " - -", duplicates)
2. pg_name: snake_case lowercase
3. Booleans: true/false NOT strings
4. Include ALL columns
5. Return ONLY JSON

Extract:
"""
    
    result = call_ollama(prompt, step_name=f"combined_{source_code}")
    
    # Post-process columns
    if 'columns' in result:
        result['columns'] = validate_and_fix_columns(result['columns'])
    
    return result


def merge_technical_fields(original_manifest, enriched_manifest):
    """Restore technical fields that LLM may have stripped."""
    # Build URL -> file mapping from original
    original_files = {}
    for source in original_manifest.get('sources', []):
        for file in source.get('files', []):
            url = file.get('url')
            if url:
                original_files[url] = file
    
    # Merge technical fields back
    restored_count = 0
    for source in enriched_manifest.get('sources', []):
        for file in source.get('files', []):
            url = file.get('url')
            if url and url in original_files:
                orig_file = original_files[url]
                # Preserve technical fields
                for field in ['extract', 'period', 'mode', 'attributes', 'preview']:
                    if field in orig_file and field not in file:
                        file[field] = orig_file[field]
                        restored_count += 1
    
    if restored_count > 0:
        print(f"🔧 Restored {restored_count} technical fields")
    
    return enriched_manifest


def validate_enrichment(original_sources, enriched_sources):
    """Validate that enrichment preserved all files."""
    # Count files in original
    orig_file_count = sum(len(s.get('files', [])) for s in original_sources)
    
    # Count files in enriched
    enr_file_count = sum(len(s.get('files', [])) for s in enriched_sources)
    
    # Count consolidated vs original sources
    consolidation_count = len(original_sources) - len(enriched_sources)
    
    print(f"✓ Validation passed:")
    print(f"  - All {orig_file_count} files preserved")
    print(f"  - Sources: {len(original_sources)} → {len(enriched_sources)} (consolidation: {consolidation_count})")
    
    if enr_file_count < orig_file_count:
        raise ValueError(f"File loss detected: {orig_file_count} → {enr_file_count}")


def enrich_with_qwen(manifest_path, output_path):
    """Main enrichment using multi-step Qwen approach."""
    print(f"Loading {manifest_path}...")
    
    # Load manifest
    with open(manifest_path) as f:
        manifest = yaml.safe_load(f)
    
    sources = manifest.get('sources', [])
    pub_context = manifest.get('publication_context', {})
    
    # Filter noise (metadata/dictionary sources)
    data_sources = []
    noise_sources = []
    
    for source in sources:
        if is_metadata_or_dictionary(source):
            source['enabled'] = False
            noise_sources.append(source)
            print(f"📋 Filtered noise: {source['code']}")
        else:
            data_sources.append(source)
    
    print(f"📊 Filtered: {len(data_sources)} data tables, {len(noise_sources)} metadata sheets")
    
    # Step 1: Basic enrichment with consolidation
    print(f"\n🔄 Step 1: Basic enrichment for {len(data_sources)} sources...")
    basic = step1_basic_enrichment(data_sources, pub_context)
    
    # Build file mapping: consolidated source -> original source files
    enriched_sources = []
    
    # V3: PARALLEL PROCESSING
    print(f"\n🚀 V3: Processing {len(basic['sources'])} sources in PARALLEL (max_workers=4)...")
    
    def process_source(basic_source):
        """Process one source (called in parallel)."""
        # Determine which original sources this represents
        if 'consolidates' in basic_source and basic_source['consolidates']:
            consolidated_codes = basic_source['consolidates']
            all_files = []
            preview = ""
            for orig_code in consolidated_codes:
                orig_source = next((s for s in data_sources if s['code'] == orig_code), None)
                if orig_source:
                    all_files.extend(orig_source.get('files', []))
                    if not preview and orig_source.get('files'):
                        preview = orig_source['files'][0].get('preview', '')
            files_for_source = all_files
        else:
            orig_source = next(
                (s for s in data_sources if s['code'] == basic_source['code']),
                None
            )
            if orig_source:
                files_for_source = orig_source.get('files', [])
                preview = orig_source['files'][0].get('preview', '') if orig_source.get('files') else ''
            else:
                files_for_source = []
                preview = ""
        
        # V3: Combined Step 2 + 3
        columns = []
        metadata = {}
        if preview:
            try:
                combined_result = step2_and_3_combined(
                    basic_source['code'],
                    basic_source['name'],
                    preview
                )
                columns = combined_result.get('columns', [])
                metadata = combined_result.get('metadata', {})
            except Exception as e:
                print(f"     ⚠️  {basic_source['code']}: {e}")
        
        # Return enriched source
        enriched = {
            **basic_source,
            'columns': columns,
            'metadata': metadata,
            'files': files_for_source,
            'enabled': basic_source.get('enabled', True)
        }
        if 'consolidates' in basic_source and basic_source['consolidates']:
            enriched['notes'] = f"Consolidated from: {', '.join(basic_source['consolidates'])}"
        return enriched
    
    # Execute in parallel (adjusted to 1 for stability with standard model)
    with ThreadPoolExecutor(max_workers=1) as executor:
        futures = {executor.submit(process_source, src): src['code'] for src in basic['sources']}
        for future in as_completed(futures):
            source_code = futures[future]
            try:
                enriched = future.result()
                enriched_sources.append(enriched)
                print(f"     ✓ {source_code} ({len(enriched.get('columns', []))} columns)")
            except Exception as e:
                print(f"     ❌ {source_code}: {e}")
    
    # Combine with noise sources
    all_sources = enriched_sources + noise_sources
    
    # Validate
    print("\nValidating enrichment...")
    validate_enrichment(data_sources, enriched_sources)
    
    # Restore technical fields
    print("Restoring technical fields...")
    result_manifest = {
        'manifest': manifest.get('manifest', {}),
        'sources': all_sources  
    }
    result_manifest = merge_technical_fields(manifest, result_manifest)
    
    # Auto-disable incomplete stubs
    disabled_count = 0
    for source in result_manifest['sources']:
        if source.get('enabled', True):
            if 'table' not in source or 'name' not in source:
                source['enabled'] = False
                disabled_count += 1
                print(f"  ⚠️  Auto-disabled incomplete source: {source.get('code', 'unknown')}")
    
    # Strip preview fields
    for source in result_manifest['sources']:
        for file in source.get('files', []):
            file.pop('preview', None)
    
    # Add manifest metadata if missing
    if 'manifest' not in result_manifest or not result_manifest['manifest']:
        result_manifest['manifest'] = {
            'name': f"qwen_enriched_{datetime.now().strftime('%Y%m%d')}",
            'description': f"Enriched by Qwen local model from {manifest_path}",
            'created_at': datetime.now().strftime('%Y-%m-%d'),
        }
    
    # Save JSON for comparison
    json_output = output_path.replace('.yaml', '_llm_response.json')
    with open(json_output, 'w') as f:
        json.dump({'sources': enriched_sources}, f, indent=2)
    print(f"📝 JSON saved to {json_output}")
    
    # Write YAML manifest
    with open(output_path, 'w') as f:
        yaml.dump(result_manifest, f, sort_keys=False, allow_unicode=True)
    
    # Summary
    enabled_count = sum(1 for s in result_manifest['sources'] if s.get('enabled', True))
    print(f"\n✅ Enrichment complete!")
    print(f"📊 {enabled_count} sources enabled, {disabled_count} disabled")
    print(f"📝 Written to {output_path}")


if __name__ == '__main__':
    if len(sys.argv) < 3:
        print("Usage: python enrich_manifest_qwen.py input.yaml output.yaml")
        sys.exit(1)
    
    enrich_with_qwen(sys.argv[1], sys.argv[2])
