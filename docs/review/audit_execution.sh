#!/bin/bash

# AUDIT EXECUTION - QUICK START PATHWAY
# This script tests the exact steps from USERGUIDE.md Section "Quick Start (5 Minutes)"

echo "================================================================================"
echo "AUDIT: QUICK START PATHWAY (USERGUIDE.md Section 2)"
echo "================================================================================"
echo ""

cd /Users/speddi/projectx/datawarp-v2.1

# Create audit log
AUDIT_LOG="/tmp/audit_quickstart_$(date +%Y%m%d_%H%M%S).log"
exec > >(tee -a "$AUDIT_LOG") 2>&1

echo "📋 TEST PLAN: Execute exact Quick Start steps from USERGUIDE.md"
echo ""
echo "Steps to test:"
echo "  1. Virtual environment activated ✓ (prerequisite)"
echo "  2. Load ADHD data (3 periods)"
echo "  3. Check loaded data with 'datawarp list'"
echo "  4. Query data with SQL"
echo ""
echo "────────────────────────────────────────────────────────────────────────────"
echo ""

# Ensure clean state for reproducible test
echo "🧹 SETUP: Clean state for reproducible test"
echo "Clearing state file..."
rm -f state/state.json
echo "✓ State cleared"
echo ""

echo "────────────────────────────────────────────────────────────────────────────"
echo "STEP 1: Activate virtual environment"
echo "────────────────────────────────────────────────────────────────────────────"
source .venv/bin/activate
python --version
echo "✓ Virtual environment active"
echo ""

echo "────────────────────────────────────────────────────────────────────────────"
echo "STEP 2: Load ADHD data"
echo "Command: python scripts/backfill.py --pub adhd"
echo "────────────────────────────────────────────────────────────────────────────"
echo ""

START_TIME=$(date +%s)
python scripts/backfill.py --pub adhd 2>&1
EXIT_CODE=$?
END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))

echo ""
echo "Exit code: $EXIT_CODE"
echo "Duration: ${DURATION}s"

if [ $EXIT_CODE -eq 0 ]; then
    echo "✅ STEP 2 PASSED"
else
    echo "❌ STEP 2 FAILED"
fi
echo ""

echo "────────────────────────────────────────────────────────────────────────────"
echo "STEP 3: Check loaded data with 'datawarp list'"
echo "Command: datawarp list"
echo "────────────────────────────────────────────────────────────────────────────"
echo ""

datawarp list 2>&1
EXIT_CODE=$?

if [ $EXIT_CODE -eq 0 ]; then
    echo "✅ STEP 3 PASSED"
else
    echo "❌ STEP 3 FAILED"
fi
echo ""

echo "────────────────────────────────────────────────────────────────────────────"
echo "STEP 4: Query data with SQL"
echo "Command: psql -d databot_dev -c \"SELECT COUNT(*) FROM staging.tbl_adhd\""
echo "────────────────────────────────────────────────────────────────────────────"
echo ""

psql -h localhost -U databot_dev_user -d databot_dev -c "SELECT COUNT(*) FROM staging.tbl_adhd" 2>&1
EXIT_CODE=$?

if [ $EXIT_CODE -eq 0 ]; then
    echo "✅ STEP 4 PASSED"
else
    echo "❌ STEP 4 FAILED"
fi
echo ""

echo "================================================================================"
echo "QUICK START AUDIT COMPLETE"
echo "================================================================================"
echo ""
echo "Audit log saved to: $AUDIT_LOG"
echo ""

