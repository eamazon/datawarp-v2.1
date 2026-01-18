#!/bin/bash
# Toggle between pre-commit hook with/without real E2E test

set -e

HOOKS_DIR=".git/hooks"
CURRENT_HOOK="$HOOKS_DIR/pre-commit"
WITH_E2E="$HOOKS_DIR/pre-commit.with-e2e"
WITHOUT_E2E="$HOOKS_DIR/pre-commit.without-e2e"

# Save current hook if not already saved
if [ -f "$CURRENT_HOOK" ] && [ ! -f "$WITHOUT_E2E" ]; then
    cp "$CURRENT_HOOK" "$WITHOUT_E2E"
    echo "📦 Saved current hook as pre-commit.without-e2e"
fi

# Check current mode
if grep -q "ADHD E2E Pipeline" "$CURRENT_HOOK" 2>/dev/null; then
    CURRENT_MODE="with-e2e"
else
    CURRENT_MODE="without-e2e"
fi

# Toggle mode
if [ "$1" == "enable" ] || [ "$CURRENT_MODE" == "without-e2e" ]; then
    # Enable E2E
    if [ ! -f "$WITH_E2E" ]; then
        echo "❌ Error: pre-commit.with-e2e not found"
        exit 1
    fi

    cp "$WITH_E2E" "$CURRENT_HOOK"
    chmod +x "$CURRENT_HOOK"

    echo "✅ Enabled ADHD E2E in pre-commit hook"
    echo ""
    echo "Pre-commit hook now runs:"
    echo "  1. ADHD E2E Pipeline (~1 second)"
    echo "  2. E2E State Tests (~0.3 seconds)"
    echo "  3. Unit Logic Tests (~0.01 seconds)"
    echo ""
    echo "Total time: ~45 seconds"
    echo ""
    echo "To disable E2E:"
    echo "  bash scripts/toggle_e2e_hook.sh disable"
    echo ""

elif [ "$1" == "disable" ] || [ "$CURRENT_MODE" == "with-e2e" ]; then
    # Disable E2E
    if [ ! -f "$WITHOUT_E2E" ]; then
        echo "❌ Error: pre-commit.without-e2e not found"
        exit 1
    fi

    cp "$WITHOUT_E2E" "$CURRENT_HOOK"
    chmod +x "$CURRENT_HOOK"

    echo "✅ Disabled ADHD E2E in pre-commit hook"
    echo ""
    echo "Pre-commit hook now runs:"
    echo "  1. E2E State Tests (~0.3 seconds)"
    echo "  2. Unit Logic Tests (~0.01 seconds)"
    echo ""
    echo "Total time: ~30 seconds"
    echo ""
    echo "To enable E2E:"
    echo "  bash scripts/toggle_e2e_hook.sh enable"
    echo ""

else
    # Show status
    echo "Current mode: $CURRENT_MODE"
    echo ""
    echo "Usage:"
    echo "  bash scripts/toggle_e2e_hook.sh enable   # Enable ADHD E2E test"
    echo "  bash scripts/toggle_e2e_hook.sh disable  # Disable ADHD E2E test"
    echo ""
fi
