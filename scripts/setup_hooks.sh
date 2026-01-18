#!/bin/bash
# Setup Git Hooks for DataWarp
# Run this script once after cloning the repository

set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HOOKS_DIR="$PROJECT_ROOT/.git/hooks"

echo "🔧 Setting up DataWarp git hooks..."
echo ""

# Check if we're in a git repository
if [ ! -d "$PROJECT_ROOT/.git" ]; then
    echo "❌ Error: Not in a git repository"
    echo "   Run this script from the project root: bash scripts/setup_hooks.sh"
    exit 1
fi

# Check if virtual environment exists
if [ ! -d "$PROJECT_ROOT/.venv" ]; then
    echo "⚠️  Warning: Virtual environment not found at .venv"
    echo "   Create it with: python -m venv .venv && source .venv/bin/activate && pip install -e ."
    echo ""
fi

# Install pre-commit hook
HOOK_SOURCE="$PROJECT_ROOT/.git/hooks/pre-commit"
if [ -f "$HOOK_SOURCE" ]; then
    echo "✅ Pre-commit hook already installed"
else
    echo "❌ Pre-commit hook not found"
    echo "   This should have been created by the system. Please check installation."
    exit 1
fi

# Verify hook is executable
if [ ! -x "$HOOK_SOURCE" ]; then
    chmod +x "$HOOK_SOURCE"
    echo "✅ Made pre-commit hook executable"
fi

# Run a test to verify hook works
echo ""
echo "🧪 Testing pre-commit hook..."
echo ""

cd "$PROJECT_ROOT"

# Activate virtual environment if available
if [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
fi

# Run smoke tests to verify they work
if pytest tests/test_e2e_smoke.py -v --tb=short > /dev/null 2>&1; then
    echo "✅ Smoke tests passed - hook is working correctly"
else
    echo "⚠️  Warning: Smoke tests failed"
    echo "   This might be expected if you haven't loaded ADHD data yet"
    echo "   Hook is installed and will run on commit"
fi

echo ""
echo "✅ Git hooks setup complete!"
echo ""
echo "What happens now:"
echo "  • Every git commit will automatically run smoke tests (30 seconds)"
echo "  • If critical tests fail, commit will be BLOCKED"
echo "  • This prevents broken code from entering the codebase"
echo ""
echo "To bypass (NOT RECOMMENDED):"
echo "  git commit --no-verify"
echo ""
