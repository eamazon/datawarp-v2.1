#!/usr/bin/env python3
"""
Manifest Enrichment Router
Routes to proven enrichment paths based on .env configuration.
Supports single or dual (concurrent local+external) execution.
"""
import os
import sys
import subprocess
from pathlib import Path
from dotenv import load_dotenv

# Setup
sys.path.append(str(Path(__file__).parent))
load_dotenv()

def run_enrichment(provider_type: str, input_path: str, output_path: str):
    """Run single enrichment (local or external)."""
    if provider_type == "external":
        model = os.getenv("LLM_MODEL")
        if not model:
            raise ValueError("LLM_MODEL not set in .env")
        
        print(f"🚀 External enrichment (Model: {model})", file=sys.stderr)
        from enrich_manifest import main as enrich_external
        sys.argv = ["enrich_manifest.py", input_path, output_path]
        enrich_external()
    
    else:  # local
        model = os.getenv("LOCAL_LLM_PROVIDER")
        if not model:
            raise ValueError("LOCAL_LLM_PROVIDER not set in .env")
        
        print(f"🚀 Local enrichment (Model: {model})", file=sys.stderr)
        from local_llm.enrich_manifest_qwen_v3 import enrich_with_qwen
        enrich_with_qwen(input_path, output_path)

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Manifest Enrichment Router")
    parser.add_argument("input", help="Input manifest YAML")
    parser.add_argument("output", help="Output manifest YAML (or base name for dual)")
    args = parser.parse_args()
    
    # Read .env flags
    use_local = os.getenv("USE_LOCAL_LLM", "false").lower() == "true"
    use_external = os.getenv("USE_EXTERNAL_LLM", "false").lower() == "true"
    
    # Validation
    if not use_local and not use_external:
        print("❌ ERROR: Set USE_LOCAL_LLM=true or USE_EXTERNAL_LLM=true in .env", 
              file=sys.stderr)
        sys.exit(1)
    
    # DUAL EXECUTION: Both flags enabled
    if use_local and use_external:
        base = Path(args.output).stem
        print("🔀 Dual execution mode (concurrent)", file=sys.stderr)
        
        # Run both in parallel via subprocess
        procs = []
        
        # Local
        local_out = f"{base}_local.yaml"
        env_local = os.environ.copy()
        env_local["USE_EXTERNAL_LLM"] = "false"
        proc_local = subprocess.Popen(
            ["python3", __file__, args.input, local_out],
            env=env_local
        )
        procs.append(("Local", proc_local))
        
        # External
        ext_out = f"{base}_external.yaml"
        env_ext = os.environ.copy()
        env_ext["USE_LOCAL_LLM"] = "false"
        proc_ext = subprocess.Popen(
            ["python3", __file__, args.input, ext_out],
            env=env_ext
        )
        procs.append(("External", proc_ext))
        
        # Wait for both
        for name, proc in procs:
            proc.wait()
            status = "✅" if proc.returncode == 0 else "❌"
            print(f"{status} {name} enrichment complete", file=sys.stderr)
        
        sys.exit(max(p.returncode for _, p in procs))
    
    # SINGLE EXECUTION
    provider = "external" if use_external else "local"
    run_enrichment(provider, args.input, args.output)

if __name__ == "__main__":
    main()
