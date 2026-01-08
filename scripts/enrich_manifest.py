#!/usr/bin/env python3
"""Enrich DataWarp manifest with LLM-generated semantic names and consolidation.

This enrichment script:
- Filters out metadata/dictionary sources (processed locally)
- Consolidates fragmented sources (e.g., merges male/female into single tables)
- Uses shorter, consistent table prefixes
- Adds 'attributes' field for column injection hints (forward-compatible)
- Flags data quality issues

Usage:
    python enrich_manifest.py manifests/raw.yaml manifests/enriched.yaml
    python enrich_manifest.py manifests/raw.yaml manifests/enriched.yaml --dry-run
"""
import sys
import yaml
import os
import json
import re
import time
from pathlib import Path
from dotenv import load_dotenv
from collections import OrderedDict
from datetime import datetime
import uuid
import psycopg2
from psycopg2.extras import Json

# Load environment variables
load_dotenv()

# Configure YAML to use '|' block style for multiline strings
class MyDumper(yaml.SafeDumper):
    pass

def str_presenter(dumper, data):
    if len(data.splitlines()) > 1:  # check for multiline string
        return dumper.represent_scalar('tag:yaml.org,2002:str', data, style='|')
    return dumper.represent_scalar('tag:yaml.org,2002:str', data)

yaml.add_representer(str, str_presenter, Dumper=MyDumper)

# === OBSERVABILITY LOGGING ===

def get_db_connection():
    """Get database connection for observability logging."""
    try:
        # Use POSTGRES_* variables (DataWarp standard pattern)
        host = os.getenv('POSTGRES_HOST', 'localhost')
        port = os.getenv('POSTGRES_PORT', '5432')
        db = os.getenv('POSTGRES_DB', 'datawarp2')
        user = os.getenv('POSTGRES_USER', 'databot')
        password = os.getenv('POSTGRES_PASSWORD', '')
        
        db_url = f"postgresql://{user}:{password}@{host}:{port}/{db}"
        conn = psycopg2.connect(db_url)
        conn.autocommit = True  # Avoid transaction issues with logging
        return conn
    except Exception as e:
        print(f"⚠️  Database connection failed: {e}", file=sys.stderr)
        return None

def log_enrichment_start(manifest_name, total_sources, data_sources, noise_sources):
    """Log start of enrichment run, return run_id."""
    try:
        conn = get_db_connection()
        if not conn:
            return None
            
        run_id = uuid.uuid4()
        model_name = os.getenv('LLM_MODEL', 'gemini-2.0-flash-exp')
        
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO datawarp.tbl_enrichment_runs 
                (run_id, manifest_name, started_at, total_sources, data_sources, 
                 noise_sources, status, model_name)
                VALUES (%s, %s, NOW(), %s, %s, %s, 'running', %s)
            """, (str(run_id), manifest_name, total_sources, data_sources, noise_sources, model_name))
        
        print(f"[DEBUG] Logged enrichment start: {run_id}", file=sys.stderr)
        conn.close()
        return run_id
    except Exception as e:
        print(f"❌ Failed to log enrichment start: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return None

def log_enrichment_complete(run_id, status, validation_status, duration_ms, 
                            total_input_tokens=0, total_output_tokens=0, total_cost=0.0,
                            error_message=None, validation_errors=None):
    """Update enrichment run with completion status."""
    if not run_id:
        return
        
    try:
        conn = get_db_connection()
        if not conn:
            return
            
        with conn.cursor() as cur:
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
                    error_message = %s,
                    validation_errors = %s
                WHERE run_id = %s
            """, (status, validation_status, duration_ms, total_input_tokens, 
                  total_output_tokens, total_cost, error_message, validation_errors, str(run_id)))
        
        conn.close()
    except Exception as e:
        print(f"⚠️  Failed to log enrichment completion: {e}", file=sys.stderr)

def log_api_call(run_id, input_tokens, output_tokens, latency_ms, model_name, 
                 prompt_hash=None, status='success', error_message=None):
    """Log individual API call metrics."""
    if not run_id:
        return
        
    try:
        conn = get_db_connection()
        if not conn:
            return
            
        # Calculate costs (Gemini 2.0 Flash pricing)
        input_cost = input_tokens * 0.000001   # $0.000001 per input token
        output_cost = output_tokens * 0.000004  # $0.000004 per output token
        total_cost = input_cost + output_cost
        
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO datawarp.tbl_enrichment_api_calls
                (run_id, call_timestamp, input_tokens, output_tokens, total_tokens,
                 input_cost, output_cost, total_cost, latency_ms, model_name,
                 prompt_hash, status, error_message, max_output_tokens)
                VALUES (%s, NOW(), %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,16384)
            """, (str(run_id), input_tokens, output_tokens, input_tokens + output_tokens,
                  input_cost, output_cost, total_cost, latency_ms, model_name,
                  prompt_hash, status, error_message))
        
        conn.close()
        return total_cost
    except Exception as e:
        print(f"⚠️  Failed to log API call: {e}", file=sys.stderr)
        return 0.0

# === END OBSERVABILITY ===


def is_noise_source(source):
    """Detect metadata/dictionary sources that don't need LLM enrichment."""
    code = source.get('code', '').lower()
    name = source.get('name', '').lower()
    
    noise_keywords = ['dictionary', 'definitions', 'notes', 'title_sheet', 
                      'contents', 'metadata', 'data_dictionary', 'title and contents',
                      'annex']
    
    # Check if any noise keyword is in code or name
    for keyword in noise_keywords:
        if keyword in code or keyword in name:
            return True
    
    # Check sheet name if it exists
    files = source.get('files', [])
    if files and 'sheet' in files[0]:
        sheet = files[0]['sheet'].lower()
        if any(k in sheet for k in noise_keywords):
            return True
    
    return False

def clean_yaml_response(text):
    """Attempt to fix common LLM YAML syntax errors."""
    # Strip markdown code blocks
    if "```" in text:
        text = text.split("```yaml")[-1].split("```")[0]
        if text.startswith("yaml\n"):
            text = text.replace("yaml\n", "", 1)
    
    text = text.strip()
    
    # Fix unquoted colons in name/description fields
    # This is a heuristic - looks for common patterns
    lines = text.split('\n')
    fixed_lines = []
    
    for line in lines:
        # Check if line contains name: or description: without quotes
        if re.match(r'^\s+(name|description):\s+[^"\'].*:', line):
            # Extract indentation, key, and value
            match = re.match(r'^(\s+)(name|description):\s+(.+)$', line)
            if match:
                indent, key, value = match.groups()
                # Quote the value if not already quoted
                if not (value.startswith('"') or value.startswith("'")):
                    line = f'{indent}{key}: "{value}"'
        
        fixed_lines.append(line)
    
    return '\n'.join(fixed_lines)

def organize_source(source):
    """Reorganize source fields in consistent, logical order."""
    ordered = OrderedDict()
    
    # Logical field order: Semantic → Metadata → Technical
    field_order = [
        'code', 'name', 'description', 'notes',
        'metadata', 'table', 'enabled', 'files'
    ]
    
    for field in field_order:
        if field in source:
            ordered[field] = source[field]
    
    for key, value in source.items():
        if key not in ordered:
            ordered[key] = value
    
    return dict(ordered)

def categorize_source(source):
    """Categorize source by type for logical grouping."""
    metadata = source.get('metadata', {})
    record_type = metadata.get('record_type', 'unknown')
    code = source.get('code', '')
    
    if record_type == 'reference' or 'map' in code or 'definition' in code:
        return ('reference', code)
    elif record_type == 'metadata' or source.get('enabled') == False:
        return ('metadata', code)
    elif record_type == 'aggregate_summary' or 'summary' in code:
        return ('summary', code)
    else:
        return ('breakdown', code)

def organize_manifest(manifest):
    """Reorganize manifest: group by type, order fields consistently."""
    sources = manifest.get('sources', [])
    categorized = {}
    
    for source in sources:
        category, code = categorize_source(source)
        if category not in categorized:
            categorized[category] = []
        categorized[category].append((code, organize_source(source)))
    
    for category in categorized:
        categorized[category].sort(key=lambda x: x[0])
    
    ordered_sources = []
    for category in ['reference', 'metadata', 'summary', 'breakdown']:
        if category in categorized:
            ordered_sources.extend([src for _, src in categorized[category]])
    
    manifest['sources'] = ordered_sources
    return manifest

def build_enrichment_prompt(manifest, data_sources_only):
    """Build aggressive enrichment prompt with consolidation instructions."""
    
    pub_url = manifest['manifest']['source_url']
    pub_context = manifest['manifest'].get('publication_context', {})
    sources_count = len(data_sources_only)
    
    # Show only data sources (metadata/dictionaries filtered out)
    sources_yaml = yaml.dump(data_sources_only, default_flow_style=False)
    
    prompt = f"""You are an expert data architect enriching an NHS data publication manifest.

INPUT MANIFEST ({sources_count} DATA TABLES):
```yaml
{sources_yaml}
```

NOTE: Metadata/dictionary sources have been filtered out. Focus on actual data tables.

PUBLICATION CONTEXT:
- Title: {pub_context.get('page_title', 'Unknown')}
- URL: {pub_url}

"""
    prompt += """
MANDATORY PREVIEW: Map 'Table X' in sheets to Titles below.
NOTE: Only previews for relevant files are shown.
"""
    # Collect relevant file URLs from data_sources
    relevant_urls = set()
    for src in data_sources_only:
        for f in src.get('files', []):
            if 'url' in f:
                relevant_urls.add(f['url'])

    # Inject content previews from Excel files
    for meta in pub_context.get('excel_metadata', []):
        if 'content_preview' in meta and meta.get('file_url') in relevant_urls:
            preview = meta['content_preview'][:5000]  # Limit length per file
            prompt += f"\n--- File: {meta.get('file_url', 'unknown')} ({meta.get('first_sheet', '')}) ---\n{preview}\n"
    
    prompt += """

⚠️  CRITICAL: The 'preview' field above is ONLY for your understanding. 
DO NOT include 'preview' in your output files array. It wastes tokens and bloats the manifest.

TASK: Refactor and consolidate this manifest using data warehousing best practices.

CRITICAL INSTRUCTION FOR RENAMING:
You MUST use the 'CONTENTS PREVIEW' above to find the real names for generic tables.
- If source has `sheet: Table 4`, LOOK at the preview.
- Find line like "Table 4: Dementia diagnosis by age..."
- Use THAT concept for the code/name.
- DO NOT keep "Summary Table 4".

CONSOLIDATION RULES (CRITICAL):

1. **Merge Split Sources**: If you see separate sources for example Male/Female data:
   - Create ONE consolidated source
   - Add `attributes: {{sex: 'M'}}` or `{{sex: 'F'}}` to each file
   - Example:
     ```yaml
     # Before: 2 sources (bad)
     - code: gp_reg_age_female
       files: [female.csv]
     - code: gp_reg_age_male  
       files: [male.csv]
     
     # After: 1 source (good)
     - code: gp_prac_reg_age_sex
       table: tbl_gp_prac_reg_age_sex
       notes: "Consolidated related attributes. Requires 'attributes' support in loader."
       files:
         - url: female.csv
           attributes: {{sex: 'F'}}
         - url: male.csv
           attributes: {{sex: 'M'}}
     ```

2. **Merge Version-Split Sources**: If files extract to same name but different versions:
   - Create ONE source with boundary_version tag
   - Example for LSOA 2011/2021: `attributes: {{boundary_version: '2021'}}`

3. **Short Table Names**: Derive a consistent prefix from the publication name:
   - Analyze the publication: "{pub_context.get('page_title', 'Unknown Publication')}"
   - Create a 3-4 character prefix (e.g., "NHS Workforce Statistics" -> `wfs_`)
   - **CRITICAL: TABLE NAMES MUST BE PERIOD-AGNOSTIC.**
     * BAD: `tbl_wfs_oct2024_summary` (Contains date)
     * GOOD: `tbl_workforce_summary` (Reusable for next month)
   - Apply consistently: `tbl_{{prefix}}_{{concept}}`
   - Max 30 characters total per table name
   
   ONE-SHOT EXAMPLE (for a different publication):
   Publication: "NHS Workforce Statistics, October 2024"
   Prefix chosen: `wfs_`
   Tables: `tbl_wfs_summary`, `tbl_wfs_by_role`, `tbl_wfs_turnover`
   
   NOW YOU: Derive your prefix from the actual publication title above.

4. **Add Notes**: For consolidated sources, add:
   ```yaml
   notes: "Consolidated [male/female|2011/2021 boundaries]. Requires loader support for 'attributes' field."
   ```

ENRICHMENT REQUIREMENTS:

1. **code**: Short, semantic snake_case
   - Good: `gp_practice_pat_registration_age_sex`, `pcn_workforce_summary`
   - Bad: `gp_practice_patient_registration_by_age_and_sex`

2. **name**: Human-readable with publication prefix
   - Good: "GP Practice Patient Registration: Age & Sex"
   - Bad: "GP Practice Patient Registration by Age and Sex"

3. **table**: tbl_{{short_prefix}}_{{concept}}
   - Max 30 chars
   - Consistent prefix per publication

4. **description**: What analyst needs to know

5. **enabled**: false for metadata/title sheets

6. **metadata**:
   - record_type: aggregate_summary|detailed_breakdown|metadata|reference
   - granularity: national|regional|practice|patient
   - measures: [patient_count, headcount, etc.]
   - dimensions: [age_group, sex, boundary_version] (for consolidated sources)
   - related_to: [max 2-3 related codes]
   - tags: [searchable tags]

7. **columns** (MANDATORY for all data tables):
   - Map each column from the raw data to a clean semantic name
   - Use the 'preview' field to see actual column headers
   - For each column, provide:
     * original_name: Exact header text from Excel/CSV (use preview to find this)
     * semantic_name: Clean snake_case name (e.g., "smokers_count", "reporting_period")
     * description: What the column contains (1 sentence)
     * data_type: varchar|integer|double precision|date
     * is_dimension: true|false (is this a grouping/category column?)
     * is_measure: true|false (is this a numeric metric?)
     * query_keywords: [2-4 searchable terms users might use]

   Example:
   ```yaml
   columns:
   - original_name: "Women known to be smokers at time of delivery - Number"
     semantic_name: "smokers_count"
     description: "Number of women who were known to be smokers at delivery."
     data_type: "integer"
     is_dimension: false
     is_measure: true
     query_keywords: ["smoker count", "number of smokers", "total smokers"]
   - original_name: "Year and quarter"
     semantic_name: "reporting_period"
     description: "Financial year and quarter identifier for the data."
     data_type: "varchar"
     is_dimension: true
     is_measure: false
     query_keywords: ["period", "quarter", "year", "date"]
   ```

   CRITICAL:
   - Match original_name EXACTLY to what's in the preview
   - Include ALL columns from the data (dimensions + measures)
   - Skip columns with generic names like "Notes", "Source", "*" unless they contain data

8. **notes** (REQUIRED for consolidated sources):
   - Flag consolidation
   - Warn about loader requirements
   - Note any data quality issues

9. **CRITICAL - Preserve technical file fields**:
   - MUST preserve these fields from input: extract, period, mode, attributes
   - Only 'preview' should be excluded (it's for your understanding only)
   - Example: if input has `extract: file.csv`, keep it in output
   
10. **CRITICAL - DO NOT include 'preview' in your output**:
   - Preview is only for YOUR understanding of the data structure
   - DO NOT echo it back in the files array
   - Outputting preview wastes tokens and bloats the manifest

CRITICAL YAML FORMATTING RULES:
- **ALWAYS quote string values containing colons**
- **ALWAYS quote string values containing special characters (&, *, etc.)**

Examples:
[CORRECT]:
  name: "GP Patients: Age & Sex"
  description: "Contains patient counts for ages 0-100"

[WRONG] (breaks YAML parser):
  name: GP Patients: Age & Sex
  description: Contains patient counts for ages 0-100

OUTPUT:
Return complete enriched manifest as valid YAML.
DO NOT include publication_context.
Start with "manifest:" immediately.
QUOTE ALL NAME AND DESCRIPTION FIELDS.
INCLUDE 'columns' ARRAY FOR EVERY DATA SOURCE (use preview to extract headers).

SOURCE ORDER: reference -> summary -> breakdowns (alphabetically within each group)

EXAMPLE OUTPUT STRUCTURE:
```yaml
manifest:
- code: example_source
  name: "Example Source Name"
  description: "What this source contains"
  table: tbl_example
  enabled: true
  metadata:
    record_type: aggregate_summary
    granularity: national
    measures: [count]
    dimensions: [period]
    tags: [example]
  columns:
  - original_name: "Column Header from Preview"
    semantic_name: "clean_name"
    description: "What this column contains"
    data_type: "varchar"
    is_dimension: true
    is_measure: false
    query_keywords: ["keyword1", "keyword2"]
  files:
  - url: https://example.com/file.csv
```
"""
    
    return prompt

def call_gemini_yaml(prompt, debug_path=None):
    """Call Gemini and return YAML response with error repair."""
    import google.generativeai as genai
    
    api_key = os.getenv('GEMINI_API_KEY')
    if not api_key:
        raise ValueError("GEMINI_API_KEY not found in .env")
    
    model_name = os.getenv('LLM_MODEL', 'gemini-2.0-flash-exp')
    
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(
        model_name=model_name,
        generation_config={
            "temperature": 0.1,
            "max_output_tokens": 16384  # Hard limit: prevent runaway generation (normal is ~8-10K)
        }
    )
    
    # Call API with timing
    start_time = time.time()
    response = model.generate_content(prompt)
    latency_ms = int((time.time() - start_time) * 1000)
    
    raw_text = response.text.strip()
    
    # Extract token usage
    input_tokens = 0
    output_tokens = 0
    if hasattr(response, 'usage_metadata'):
        input_tokens = response.usage_metadata.prompt_token_count
        output_tokens = response.usage_metadata.candidates_token_count
        ratio = output_tokens / max(input_tokens, 1)
        
        # Warn if output is >5× input (normal is 2-3×)
        if ratio > 5.0:
            print(f"⚠️  WARNING: High output/input ratio ({ratio:.1f}×) - possible runaway generation!", file=sys.stderr)
            print(f"   Input: {input_tokens:,} tokens | Output: {output_tokens:,} tokens", file=sys.stderr)
    
    # DEBUG: Always save raw text
    # if debug_path:
    #     raw_path = debug_path.replace('_error.txt', '_raw.txt')
    #     with open(raw_path, 'w') as f:
    #         f.write(raw_text)
            
    # Attempt YAML repair
    cleaned_text = clean_yaml_response(raw_text)
    
    try:
        parsed = yaml.safe_load(cleaned_text)
        
        # ALWAYS save LLM JSON response for debugging (until system is stable)
        if debug_path:
            json_debug_path = debug_path.replace('_error.txt', '_llm_response.json')
            with open(json_debug_path, 'w') as f:
                json.dump(parsed, f, indent=2)
            print(f"[DEBUG] Raw LLM JSON saved to {json_debug_path}", file=sys.stderr)
        
        # Return both parsed data and metadata for observability
        metadata = {
            'input_tokens': input_tokens,
            'output_tokens': output_tokens,
            'latency_ms': latency_ms,
            'model_name': model_name
        }
        return parsed, metadata
    except yaml.YAMLError as e:
        # Dump error for debugging
        error_file = debug_path or "llm_error_dump.txt"
        with open(error_file, 'w') as f:
            f.write("="*80 + "\n")
            f.write("LLM RAW OUTPUT (YAML Parse Error)\n")
            f.write("="*80 + "\n\n")
            f.write(raw_text)
            f.write("\n\n" + "="*80 + "\n")
            f.write("CLEANED VERSION:\n")
            f.write("="*80 + "\n\n")
            f.write(cleaned_text)
            f.write("\n\n" + "="*80 + "\n")
            f.write(f"ERROR: {e}\n")
            f.write("="*80 + "\n")
        
        print(f"⚠️  YAML parse error. Raw output saved to {error_file}", file=sys.stderr)
        raise

def call_gemini_json(prompt, debug_path=None):
    """EXPERIMENTAL: Call Gemini and return JSON response.
    
    This is a parallel implementation to test JSON vs YAML output.
    Does NOT modify the existing call_gemini_yaml() function.
    """
    import google.generativeai as genai
    
    api_key = os.getenv('GEMINI_API_KEY')
    if not api_key:
        raise ValueError("GEMINI_API_KEY not found in .env")
    
    model_name = os.getenv('LLM_MODEL', 'gemini-2.0-flash-exp')
    
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(
        model_name=model_name,
        generation_config={
            "temperature": 0.1,
            "max_output_tokens": 16384,
            "response_mime_type": "application/json"  # Force JSON output
        }
    )
    
    # Modify prompt to request JSON instead of YAML
    json_prompt = prompt.replace(
        "Return complete enriched manifest as valid YAML.",
        "Return complete enriched manifest as valid JSON."
    ).replace(
        "EXAMPLE OUTPUT STRUCTURE:\n```yaml",
        "EXAMPLE OUTPUT STRUCTURE:\n```json"
    ).replace(
        "Start with \"manifest:\" immediately.",
        "Return a JSON object with 'manifest' key containing the sources array."
    )
    
    # Save the modified JSON prompt for inspection
    if debug_path:
        json_prompt_path = debug_path.replace('_error.txt', '_json_prompt.txt')
        with open(json_prompt_path, 'w') as f:
            f.write("="*80 + "\n")
            f.write("JSON MODE PROMPT (Modified from YAML)\n")
            f.write("="*80 + "\n\n")
            f.write(json_prompt)
        print(f"[DEBUG] JSON prompt saved to {json_prompt_path}", file=sys.stderr)
    
    # Call API with timing
    start_time = time.time()
    response = model.generate_content(json_prompt)
    latency_ms = int((time.time() - start_time) * 1000)
    
    raw_text = response.text.strip()
    
    # Save raw JSON response for inspection
    if debug_path:
        raw_json_path = debug_path.replace('_error.txt', '_raw_llm_output.json')
        with open(raw_json_path, 'w') as f:
            f.write(raw_text)
        print(f"[DEBUG] Raw LLM JSON output saved to {raw_json_path}", file=sys.stderr)
    
    # Extract token usage
    input_tokens = 0
    output_tokens = 0
    if hasattr(response, 'usage_metadata'):
        input_tokens = response.usage_metadata.prompt_token_count
        output_tokens = response.usage_metadata.candidates_token_count
        ratio = output_tokens / max(input_tokens, 1)
        
        if ratio > 5.0:
            print(f"⚠️  WARNING: High output/input ratio ({ratio:.1f}×) - possible runaway generation!", file=sys.stderr)
            print(f"   Input: {input_tokens:,} tokens | Output: {output_tokens:,} tokens", file=sys.stderr)
    
    # Parse JSON
    try:
        parsed = json.loads(raw_text)
        
        # Save raw JSON response for debugging
        if debug_path:
            json_debug_path = debug_path.replace('_error.txt', '_llm_response.json')
            with open(json_debug_path, 'w') as f:
                json.dump(parsed, f, indent=2)
            print(f"[DEBUG] Raw LLM JSON saved to {json_debug_path}", file=sys.stderr)
        
        # Return both parsed data and metadata
        metadata = {
            'input_tokens': input_tokens,
            'output_tokens': output_tokens,
            'latency_ms': latency_ms,
            'model_name': model_name
        }
        return parsed, metadata
        
    except json.JSONDecodeError as e:
        # Dump error for debugging
        error_file = debug_path or "llm_error_dump.txt"
        with open(error_file, 'w') as f:
            f.write("="*80 + "\n")
            f.write("LLM RAW OUTPUT (JSON Parse Error)\n")
            f.write("="*80 + "\n\n")
            f.write(raw_text)
            f.write("\n\n" + "="*80 + "\n")
            f.write(f"ERROR: {e}\n")
            f.write("="*80 + "\n")
        
        print(f"⚠️  JSON parse error. Raw output saved to {error_file}", file=sys.stderr)
        raise


def merge_technical_fields(original, enriched):
    """Merge technical fields from original files back into enriched manifest.

    Preserves: sheet, extract, period, mode, attributes
    This ensures the LLM doesn't accidentally strip critical loader fields.
    """
    # Build URL -> file mapping from original
    original_files = {}
    for source in original['sources']:
        for file in source.get('files', []):
            url = file['url']
            original_files[url] = file

    # Merge technical fields back into enriched files
    restored_count = 0
    for source in enriched['sources']:
        for file in source.get('files', []):
            url = file.get('url')
            if url and url in original_files:
                orig_file = original_files[url]
                # Preserve technical fields (prioritize 'sheet' for XLSX over 'extract')
                for field in ['sheet', 'extract', 'period', 'mode', 'attributes']:
                    if field in orig_file and field not in file:
                        file[field] = orig_file[field]
                        restored_count += 1
    
    if restored_count > 0:
        print(f"🔧 Restored {restored_count} technical fields from original manifest", file=sys.stderr)
    
    return enriched

def validate_enrichment(original, enriched):
    """Validate all file URLs preserved (source count may change)."""
    
    # Extract all file URLs from original
    original_urls = set()
    for source in original['sources']:
        for file in source.get('files', []):
            original_urls.add(file['url'])
    
    # Extract all file URLs from enriched
    enriched_urls = set()
    for source in enriched['sources']:
        for file in source.get('files', []):
            enriched_urls.add(file['url'])
    
    # Check no URLs lost
    missing_urls = original_urls - enriched_urls
    if missing_urls:
        raise ValueError(f"Missing URLs in enriched manifest: {missing_urls}")
    
    extra_urls = enriched_urls - original_urls
    if extra_urls:
        raise ValueError(f"Extra URLs in enriched manifest: {extra_urls}")
    
    orig_count = len(original['sources'])
    enr_count = len(enriched['sources'])
    
    print(f"✓ Validation passed:", file=sys.stderr)
    print(f"  - All {len(original_urls)} files preserved", file=sys.stderr)
    print(f"  - Sources: {orig_count} → {enr_count} (consolidation: {orig_count - enr_count})", file=sys.stderr)

def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Enrich DataWarp manifest with semantic metadata using Gemini LLM',
        epilog='Example: python enrich_manifest.py input.yaml [output.yaml]'
    )
    parser.add_argument('input', help='Input manifest YAML file')
    parser.add_argument('output', nargs='?', help='Output manifest YAML file (default: input_enriched.yaml)')
    parser.add_argument('--reference', help='Reference manifest for comparison (e.g., previous version)')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be done without writing output')
    parser.add_argument('--use-json', action='store_true', help='EXPERIMENTAL: Use JSON mode instead of YAML for LLM')
    
    args = parser.parse_args()
    
    # Auto-generate output filename if not provided
    if args.output is None:
        input_path = Path(args.input)
        output_name = input_path.stem + '_enriched' + input_path.suffix
        args.output = str(input_path.parent / output_name)
        print(f"📝 Output file not specified, using: {args.output}")
    
    # Validate output filename
    if args.output == 'output':
        print("❌ Error: 'output' is not a valid filename. Please specify a proper output file.")
        print(f"   Suggestion: {Path(args.input).stem}_enriched.yaml")
        sys.exit(1)
    
    input_path = args.input
    output_path = args.output
    
    # Load raw manifest
    print(f"Loading {input_path}...", file=sys.stderr)
    with open(input_path) as f:
        original_manifest = yaml.safe_load(f)
    
    # FILTER: Split into data sources and noise sources
    all_sources = original_manifest['sources']
    data_sources = []
    noise_sources = []
    
    for source in all_sources:
        if is_noise_source(source):
            # Auto-process noise sources locally
            source['enabled'] = False
            source['description'] = source.get('description', 'Metadata/Dictionary (auto-disabled)')
            noise_sources.append(source)
        else:
            data_sources.append(source)
    
    print(f"📊 Filtered: {len(data_sources)} data tables, {len(noise_sources)} metadata sheets (auto-disabled)", file=sys.stderr)
    
    # Start observability logging
    manifest_name = Path(input_path).stem
    run_id = log_enrichment_start(manifest_name, len(all_sources), len(data_sources), len(noise_sources))
    start_time_ms = time.time() * 1000
    
    # REFERENCE LOGIC: Load reference manifest for deterministic naming
    if args.reference:
        try:
            from url_to_manifest import extract_base_pattern
            print(f"Loading reference {args.reference}...", file=sys.stderr)
            with open(args.reference) as f:
                ref_manifest = yaml.safe_load(f)
            
            # Build map: pattern -> source
            ref_map = {}
            for src in ref_manifest.get('sources', []):
                # Only map if source has files (to extract pattern)
                files = src.get('files', [])
                if files and 'url' in files[0]:
                    # Need to extract pattern from URL/File name just like url_to_manifest does
                    # Use the first file to identify the source pattern
                    file_url = files[0]['url']
                    # CRITICAL: For XLSX files, use sheet name as pattern (not filename)
                    filename = files[0].get('sheet') or files[0].get('extract', Path(file_url).name)
                    pattern = extract_base_pattern(filename)
                    ref_map[pattern] = src
            
            print(f"Reference loaded: {len(ref_map)} patterns mapped", file=sys.stderr)
            
            # Apply to data_sources
            new_data_sources = []
            enriched_from_ref = 0
            
            for source in data_sources:
                # Get pattern from current source (it should be in raw manifest)
                current_pattern = source.get('pattern')

                # If pattern missing (e.g. manual edit), try to re-derive
                if not current_pattern and source.get('files'):
                    f0 = source['files'][0]
                    # CRITICAL: For XLSX files, use sheet name as pattern (not filename)
                    fname = f0.get('sheet') or f0.get('extract', Path(f0['url']).name)
                    current_pattern = extract_base_pattern(fname)
                
                if current_pattern and current_pattern in ref_map:
                    # MATCH! Deterministic overwrite
                    ref_src = ref_map[current_pattern]
                    
                    # Copy semantic fields
                    source['code'] = ref_src['code']
                    source['name'] = ref_src['name']
                    source['table'] = ref_src['table']
                    source['description'] = ref_src['description']
                    
                    # Notes and Metadata: merge carefuly
                    # If reference has notes (e.g. "Consolidated..."), keep them
                    if 'notes' in ref_src:
                        source['notes'] = ref_src['notes']
                        
                    # Metadata: Trust reference unless record_type is different? Assume safe to copy.
                    if 'metadata' in ref_src:
                        source['metadata'] = ref_src['metadata']
                        
                    # Files: Keep CURRENT source's files (Apr data), just use Ref structure
                    # BUT if Ref was consolidated (multiple files), and Current is too, 
                    # we must ensure we aren't losing the consolidation logic.
                    # This is complex for consolidated sources. 
                    # SIMPLIFICATION: If pattern matches, assume 1-to-1 or same grouping logic applied by url_to_manifest.
                    
                    enriched_from_ref += 1
                    # Add to 'noise_sources' list effectively (bypassing LLM), 
                    # but we want them in final output. 
                    # We'll add them to a 'pre_enriched_sources' list or just append to final list later.
                    # Best to add to a separate list and NOT include in 'new_data_sources' (which go to LLM)
                    noise_sources.append(source) # Abuse noise_sources list to skip LLM, but 'enabled' is True!
                else:
                    new_data_sources.append(source)
            
            data_sources = new_data_sources
            print(f"♻️  Deterministic Match: Enriched {enriched_from_ref} sources from reference (Skipping LLM)", file=sys.stderr)
            print(f"    Remaining for LLM: {len(data_sources)} sources", file=sys.stderr)
            
        except Exception as e:
            print(f"⚠️  Could not load/apply reference: {e}", file=sys.stderr)
    
    # Check if anything left for LLM
    if not data_sources:
        print("🎉 All sources enriched from reference! Skipping LLM entirely.", file=sys.stderr)
        enriched_data_sources = []
    else:
        # Build prompt for DATA sources only
        prompt = build_enrichment_prompt(original_manifest, data_sources)
    
    # DRY RUN: Save prompt and exit
    if args.dry_run:
        prompt_file = output_path.replace('.yaml', '_prompt.txt')
        with open(prompt_file, 'w') as f:
            f.write("=" * 80 + "\n")
            f.write("ENRICHMENT PROMPT FOR LLM\n")
            f.write("=" * 80 + "\n\n")
            f.write(prompt)
            f.write("\n\n" + "=" * 80 + "\n")
            f.write(f"Prompt character count: {len(prompt)}\n")
            f.write(f"Estimated tokens: ~{len(prompt) // 4}\n")
            f.write(f"Data sources: {len(data_sources)}\n")
            f.write(f"Noise sources (filtered): {len(noise_sources)}\n")
            f.write("=" * 80 + "\n")
        
        print(f"\n📄 Dry run: Prompt saved to {prompt_file}", file=sys.stderr)
        print(f"📊 Prompt stats:", file=sys.stderr)
        print(f"   - Characters: {len(prompt):,}", file=sys.stderr)
        print(f"   - Estimated tokens: ~{len(prompt) // 4:,}", file=sys.stderr)
        print(f"   - Data sources: {len(data_sources)}", file=sys.stderr)
        print(f"   - Noise filtered: {len(noise_sources)}", file=sys.stderr)
        return
    
    # Call LLM on data sources only
    llm_mode = "JSON" if args.use_json else "YAML"
    print(f"Calling Gemini API on {len(data_sources)} data sources... (mode: {llm_mode})", file=sys.stderr)
    llm_metadata = None  # Track for observability
    try:
        error_dump = output_path.replace('.yaml', '_error.txt')
        
        # EXPERIMENTAL: Use JSON or YAML mode
        if args.use_json:
            print("  🧪 Using EXPERIMENTAL JSON mode", file=sys.stderr)
            enriched_data_sources, llm_metadata = call_gemini_json(prompt, error_dump)
        else:
            enriched_data_sources, llm_metadata = call_gemini_yaml(prompt, error_dump)
        
        # Log API call metrics
        if run_id and llm_metadata:
            total_cost = log_api_call(
                run_id,
                llm_metadata['input_tokens'],
                llm_metadata['output_tokens'],
                llm_metadata['latency_ms'],
                llm_metadata['model_name']
            )
        
        print(f"DEBUG: Parsed type: {type(enriched_data_sources)}", file=sys.stderr)
        if isinstance(enriched_data_sources, dict):
             print(f"DEBUG: Keys: {list(enriched_data_sources.keys())}", file=sys.stderr)
        elif isinstance(enriched_data_sources, list):
             print(f"DEBUG: List length: {len(enriched_data_sources)}", file=sys.stderr)

        # Handle different LLM response formats
        if isinstance(enriched_data_sources, list):
            # Perfect, just a list of sources
            pass
        elif isinstance(enriched_data_sources, dict):
            # Case 1: {'sources': [...]}
            if 'sources' in enriched_data_sources:
                enriched_data_sources = enriched_data_sources['sources']
            # Case 2: {'manifest': {'sources': [...]}}
            elif 'manifest' in enriched_data_sources and isinstance(enriched_data_sources['manifest'], dict):
                 enriched_data_sources = enriched_data_sources['manifest'].get('sources', data_sources)
            # Case 3: {'manifest': [...]} (List directly inside manifest key)
            elif 'manifest' in enriched_data_sources and isinstance(enriched_data_sources['manifest'], list):
                 enriched_data_sources = enriched_data_sources['manifest']
            else:
                 print(f"⚠️  LLM returned dict without 'sources' key, using empty list", file=sys.stderr)
                 enriched_data_sources = []
        else:
             raise ValueError(f"LLM response is not a list or dict: {type(enriched_data_sources)}")
        
        # Ensure it's a list
        if not isinstance(enriched_data_sources, list):
             print(f"⚠️  Expected list, got {type(enriched_data_sources)}, using original data", file=sys.stderr)
             enriched_data_sources = data_sources
        
        # DEBUG: Save LLM response
        # debug_path = output_path.replace('.yaml', '_debug.yaml')
        # with open(debug_path, 'w') as f:
        #     yaml.dump(enriched_data_sources, f, sort_keys=False, allow_unicode=True)
        # print(f"Debug: LLM response saved to {debug_path}", file=sys.stderr)
        
    except Exception as e:
        print(f"❌ LLM call failed: {e}", file=sys.stderr)
        print(f"⚠️  Falling back to original data sources", file=sys.stderr)
        enriched_data_sources = data_sources
    
    # MERGE: Combine enriched data sources + auto-processed noise sources
    all_enriched_sources = enriched_data_sources + noise_sources
    enriched_manifest = {'manifest': original_manifest['manifest'], 'sources': all_enriched_sources}
    
    # CRITICAL FIX: Restore technical fields that LLM may have stripped
    print("Restoring technical fields...", file=sys.stderr)
    enriched_manifest = merge_technical_fields(original_manifest, enriched_manifest)
    
    # Validate (check data sources only, noise sources don't need validation)
    try:
        # Create temp manifests for validation
        original_data_manifest = {'manifest': original_manifest['manifest'], 'sources': data_sources}
        enriched_data_manifest = {'manifest': original_manifest['manifest'], 'sources': enriched_data_sources}
        validate_enrichment(original_data_manifest, enriched_data_manifest)
    except Exception as e:
        print(f"❌ Validation failed: {e}", file=sys.stderr)
        print(f"⚠  Falling back to original manifest", file=sys.stderr)
        enriched_manifest = original_manifest
    
    # Organize for readability
    print("Organizing manifest...", file=sys.stderr)
    enriched_manifest = organize_manifest(enriched_manifest)
    
    # FIX: Auto-disable stub sources from consolidation
    # When LLM consolidates sources, it may leave stubs without 'table' or 'name'
    # These should be disabled to prevent load errors
    disabled_count = 0
    for source in enriched_manifest.get('sources', []):
        # Check if source is missing required fields
        if source.get('enabled', True):  # Only check enabled sources
            missing_fields = []
            
            if 'table' not in source:
                missing_fields.append('table')
            if 'name' not in source:
                missing_fields.append('name')
            
            if missing_fields:
                # This is a stub from consolidation - disable it
                source['enabled'] = False
                disabled_count += 1
                print(f"  ⚠️  Auto-disabled stub source '{source.get('code', 'unknown')}' (missing: {', '.join(missing_fields)})", file=sys.stderr)
    
    if disabled_count > 0:
        print(f"  ✓ Disabled {disabled_count} incomplete source(s) from consolidation", file=sys.stderr)
    
    # Strip preview fields (they're only needed during enrichment, not in final manifest)
    for source in enriched_manifest.get('sources', []):
        for file in source.get('files', []):
            if 'preview' in file:
                del file['preview']
    
    # Write output
    print(f"Writing enriched manifest to {output_path}...", file=sys.stderr)
    with open(output_path, 'w') as f:
        yaml.dump(enriched_manifest, f, Dumper=MyDumper, sort_keys=False, allow_unicode=True)
    
    # Log completion
    if run_id:
        duration_ms = int(time.time() * 1000 - start_time_ms)
        total_cost = 0.0
        input_tokens = 0
        output_tokens = 0
        
        if llm_metadata:
            input_tokens = llm_metadata.get('input_tokens', 0)
            output_tokens = llm_metadata.get('output_tokens', 0)
            # Recalculate cost
            total_cost = (input_tokens * 0.000001) + (output_tokens * 0.000004)
        
        log_enrichment_complete(
            run_id,
            status='success',
            validation_status='passed',
            duration_ms=duration_ms,
            total_input_tokens=input_tokens,
            total_output_tokens=output_tokens,
            total_cost=total_cost
        )
    
    # Summary
    enabled_count = sum(1 for s in enriched_manifest['sources'] if s.get('enabled', True))
    disabled_count = len(enriched_manifest['sources']) - enabled_count
    
    print(f"\n✅ Enrichment complete!", file=sys.stderr)
    print(f"📊 {enabled_count} sources enabled, {disabled_count} disabled", file=sys.stderr)
    print(f"🔄 Consolidation applied (check 'notes' fields)", file=sys.stderr)
    print(f"📋 Organized: reference → summary → breakdowns", file=sys.stderr)
    print(f"📝 Written to {output_path}", file=sys.stderr)

if __name__ == '__main__':
    main()
