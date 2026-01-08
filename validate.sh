#!/bin/bash
# Validation helper - automatically activates venv and runs validator
#
# Usage:
#   ./validate.sh adhd_summary_new_referrals_age   # Validate single export
#   ./validate.sh --all                             # Validate all exports
#   ./validate.sh --self-test                       # Run meta-tests

cd "$(dirname "$0")"
source .venv/bin/activate
python scripts/validate_parquet_export.py "$@"
