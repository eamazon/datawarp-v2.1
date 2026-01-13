#!/bin/bash
# DataWarp Repository Cleanup Script
# Removes generated files from git tracking while keeping them locally
# Run with --dry-run to preview changes, or --execute to apply

set -e

DRY_RUN=true
if [[ "$1" == "--execute" ]]; then
    DRY_RUN=false
    echo "⚠️  EXECUTING CLEANUP - Files will be removed from git tracking"
else
    echo "🔍 DRY RUN MODE - Showing what would be cleaned up"
    echo "   Run with --execute to apply changes"
fi

echo ""
echo "=== Repository Cleanup Assessment ==="
echo ""

# Count files to be removed from tracking
OUTPUT_COUNT=$(git ls-files output/ 2>/dev/null | wc -l | tr -d ' ')
MANIFEST_ARCHIVE_COUNT=$(git ls-files manifests/archive/ 2>/dev/null | wc -l | tr -d ' ')
MANIFEST_TEST_COUNT=$(git ls-files manifests/test/ 2>/dev/null | wc -l | tr -d ' ')
MANIFEST_E2E_COUNT=$(git ls-files manifests/e2e_test/ 2>/dev/null | wc -l | tr -d ' ')
STATE_COUNT=$(git ls-files state/ 2>/dev/null | wc -l | tr -d ' ')

echo "Files to remove from git tracking (kept locally):"
echo "  output/            : $OUTPUT_COUNT files (parquet + metadata)"
echo "  manifests/archive/ : $MANIFEST_ARCHIVE_COUNT files"
echo "  manifests/test/    : $MANIFEST_TEST_COUNT files"
echo "  manifests/e2e_test/: $MANIFEST_E2E_COUNT files"
echo "  state/             : $STATE_COUNT files"
echo ""

TOTAL=$((OUTPUT_COUNT + MANIFEST_ARCHIVE_COUNT + MANIFEST_TEST_COUNT + MANIFEST_E2E_COUNT + STATE_COUNT))
echo "Total: $TOTAL files will be untracked"
echo ""

if [[ "$DRY_RUN" == true ]]; then
    echo "=== .gitignore additions needed ==="
    echo ""
    echo "# Generated data (don't track)"
    echo "output/"
    echo "state/"
    echo "logs/"
    echo ""
    echo "# Test manifests (don't track)"
    echo "manifests/archive/"
    echo "manifests/test/"
    echo "manifests/e2e_test/"
    echo "manifests/backfill/"
    echo ""
    echo "# Keep only production manifests"
    echo "!manifests/production/"
    echo ""
    exit 0
fi

# === EXECUTE MODE ===

echo "Step 1: Updating .gitignore..."

# Backup current .gitignore
cp .gitignore .gitignore.backup

# Add new exclusions
cat >> .gitignore << 'EOF'

# === GENERATED DATA (Added by cleanup_repo.sh) ===

# Output files (parquet, metadata) - regenerated from database
output/

# State tracking - machine-specific
state/

# Event logs - regenerated each run
logs/

# Test and archive manifests - not needed in repo
manifests/archive/
manifests/test/
manifests/e2e_test/
manifests/backfill/

# Keep production manifests
!manifests/production/
EOF

echo "  ✅ .gitignore updated"

echo ""
echo "Step 2: Removing files from git tracking (keeping locally)..."

# Remove from git index but keep files
git rm -r --cached output/ 2>/dev/null || echo "  (output/ not in index)"
git rm -r --cached state/ 2>/dev/null || echo "  (state/ not in index)"
git rm -r --cached manifests/archive/ 2>/dev/null || echo "  (manifests/archive/ not in index)"
git rm -r --cached manifests/test/ 2>/dev/null || echo "  (manifests/test/ not in index)"
git rm -r --cached manifests/e2e_test/ 2>/dev/null || echo "  (manifests/e2e_test/ not in index)"

echo "  ✅ Files removed from git tracking"

echo ""
echo "Step 3: Creating .env.example..."

cat > .env.example << 'EOF'
# DataWarp Environment Configuration
# Copy this to .env and fill in your values
# NEVER commit .env with real credentials!

# Database Configuration (required)
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=datawarp_prod
POSTGRES_USER=datawarp_user
POSTGRES_PASSWORD=your-secure-password-here
DATABASE_TYPE=postgres

# LLM Provider Configuration
# Options: "external" (Gemini API) or "local" (Qwen)
LLM_PROVIDER=external

# Gemini API Key (if LLM_PROVIDER=external)
# Get your key at: https://aistudio.google.com/apikey
GEMINI_API_KEY=your-gemini-api-key-here

# Anthropic API Key (optional, for Claude-based features)
# ANTHROPIC_API_KEY=your-anthropic-key-here

# Qwen Local Model (if LLM_PROVIDER=local)
# QWEN_MODEL_PATH=/path/to/qwen-model
EOF

echo "  ✅ .env.example created"

echo ""
echo "=== Cleanup Complete ==="
echo ""
echo "Next steps:"
echo "  1. Review changes: git status"
echo "  2. Commit cleanup: git add -A && git commit -m 'chore: Remove generated files from tracking'"
echo "  3. Verify .env is not tracked: git ls-files .env (should be empty)"
echo ""
echo "Your local files are preserved - only git tracking was changed."
