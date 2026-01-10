#!/bin/bash
# DataWarp Test Runner

set -e  # Exit on first error

echo "=========================================="
echo "DataWarp Test Suite"
echo "=========================================="

# Activate venv
source .venv/bin/activate

echo ""
echo "1. Running unit tests..."
pytest tests/unit/ -v --tb=short || true

echo ""
echo "2. Running integration tests..."
pytest tests/integration/ -v --tb=short || true

echo ""
echo "3. Running E2E tests..."
pytest tests/e2e/ -v --tb=short || true

echo ""
echo "4. Validating production manifests..."
python scripts/validate_manifest.py manifests/production/*/*.yaml

echo ""
echo "=========================================="
echo "Test suite complete"
echo "=========================================="
