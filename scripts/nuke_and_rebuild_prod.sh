#!/bin/bash
# Nuke and rebuild datawarp-prod cleanly
# Usage: ./scripts/nuke_and_rebuild_prod.sh /path/to/datawarp-prod

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() { echo -e "${BLUE}ℹ️  $1${NC}"; }
log_success() { echo -e "${GREEN}✅ $1${NC}"; }
log_warning() { echo -e "${YELLOW}⚠️  $1${NC}"; }
log_error() { echo -e "${RED}❌ $1${NC}"; }

if [ -z "$1" ]; then
    log_error "Usage: $0 /path/to/datawarp-prod"
    exit 1
fi

PROD_DIR="$1"

echo "═══════════════════════════════════════════════════════════════"
log_warning "NUKE AND REBUILD: $PROD_DIR"
echo "═══════════════════════════════════════════════════════════════"
echo ""
log_warning "This will:"
echo "  1. Delete all files in $PROD_DIR (except .env)"
echo "  2. Pull latest code from git"
echo "  3. Reinstall packages"
echo "  4. Drop and recreate datawarp_prod database"
echo "  5. Initialize clean schema"
echo ""
read -p "Are you sure? (type 'yes' to confirm): " confirm

if [ "$confirm" != "yes" ]; then
    log_info "Aborted"
    exit 0
fi

echo ""
log_info "Starting nuke and rebuild..."
echo ""

# Save .env if it exists
if [ -f "$PROD_DIR/.env" ]; then
    log_info "Backing up .env file..."
    cp "$PROD_DIR/.env" /tmp/datawarp_prod_env_backup
    log_success ".env backed up to /tmp/datawarp_prod_env_backup"
fi

# Delete everything except .env
log_info "Deleting all files in $PROD_DIR..."
cd "$PROD_DIR"
find . -mindepth 1 -maxdepth 1 ! -name '.env' -exec rm -rf {} +
log_success "Directory cleaned"

# Pull latest code
log_info "Pulling latest code from git..."
git clone --depth 1 --branch main https://github.com/eamazon/datawarp-v2.1.git temp_clone
mv temp_clone/* temp_clone/.* . 2>/dev/null || true
rm -rf temp_clone
log_success "Latest code pulled"

# Restore .env
if [ -f "/tmp/datawarp_prod_env_backup" ]; then
    log_info "Restoring .env file..."
    cp /tmp/datawarp_prod_env_backup .env
    rm /tmp/datawarp_prod_env_backup
    log_success ".env restored"
fi

# Create directories
log_info "Creating directory structure..."
mkdir -p logs output state manifests/production config
log_success "Directories created"

# Create venv and install
log_info "Creating virtual environment..."
python3 -m venv .venv
log_success "Virtual environment created"

log_info "Installing packages..."
.venv/bin/pip install --upgrade pip -q
.venv/bin/pip install -e . -q
.venv/bin/pip install fastapi uvicorn httpx jsonschema pydantic-settings -q
.venv/bin/pip install beautifulsoup4 lxml python-dotenv duckdb pyarrow mcp -q
.venv/bin/pip install google-generativeai -q
log_success "Packages installed"

# Drop and recreate database
log_info "Dropping datawarp_prod database..."
docker exec databot-postgres psql -U databot -c "DROP DATABASE IF EXISTS datawarp_prod;" 2>/dev/null || true
log_success "Database dropped"

log_info "Creating fresh datawarp_prod database..."
docker exec databot-postgres psql -U databot -c "CREATE DATABASE datawarp_prod OWNER databot;"
log_success "Database created"

# Initialize schema
log_info "Initializing schema..."
.venv/bin/python scripts/reset_db.py << EOF
yes
EOF
log_success "Schema initialized"

# Create state file
log_info "Creating state file..."
echo '{"processed": {}, "failed": {}}' > state/state.json
log_success "State file created"

# Summary
echo ""
echo "═══════════════════════════════════════════════════════════════"
log_success "NUKE AND REBUILD COMPLETE!"
echo "═══════════════════════════════════════════════════════════════"
echo ""
echo "📂 Production rebuilt at: $PROD_DIR"
echo "📊 Database: datawarp_prod (clean slate)"
echo "📦 Packages: installed and ready"
echo ""
echo "⚠️  You are still in your current directory"
echo "   Run these commands to switch to production:"
echo ""
echo "   cd $PROD_DIR"
echo "   source .venv/bin/activate"
echo "   python scripts/backfill.py --pub adhd"
echo ""
echo "   Or stay in dev and continue working"
echo ""
