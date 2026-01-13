#!/bin/bash
# DataWarp Production Setup Script
# Creates a clean production environment from scratch
#
# Usage: ./scripts/setup_production.sh /path/to/production/directory

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Helper functions
log_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

log_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

log_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

log_error() {
    echo -e "${RED}❌ $1${NC}"
}

# Check if production directory is provided
if [ -z "$1" ]; then
    log_error "Usage: $0 /path/to/production/directory"
    echo "Example: $0 ~/projectx/datawarp-prod"
    exit 1
fi

PROD_DIR="$1"

log_info "DataWarp Production Setup"
echo "Target directory: $PROD_DIR"
echo ""

# Check prerequisites
log_info "Checking prerequisites..."

if ! command -v python3 &> /dev/null; then
    log_error "python3 not found. Please install Python 3.10+"
    exit 1
fi

if ! command -v git &> /dev/null; then
    log_error "git not found. Please install git"
    exit 1
fi

if ! command -v docker &> /dev/null; then
    log_error "docker not found. Please install Docker Desktop"
    exit 1
fi

log_success "Prerequisites OK"
echo ""

# Create production directory
log_info "Creating production directory..."
mkdir -p "$PROD_DIR"
cd "$PROD_DIR"
log_success "Directory created: $PROD_DIR"
echo ""

# Clone repository (shallow clone for production)
log_info "Cloning DataWarp repository (latest version only)..."
if [ -d ".git" ]; then
    log_warning "Repository already exists. Pulling latest..."
    git pull origin main
else
    git clone --depth 1 --branch main https://github.com/eamazon/datawarp-v2.1.git .
fi
log_success "Repository cloned"
echo ""

# Create production folders
log_info "Creating production data folders..."
mkdir -p logs output state manifests/production config
log_success "Data folders created"
echo ""

# Create Python virtual environment
log_info "Creating Python virtual environment..."
python3 -m venv .venv
log_success "Virtual environment created"
echo ""

# Activate venv and install dependencies
log_info "Installing DataWarp and dependencies..."
source .venv/bin/activate
pip install --upgrade pip -q
pip install -e . -q
pip install fastapi uvicorn httpx jsonschema pydantic-settings -q
pip install beautifulsoup4 lxml python-dotenv duckdb pyarrow -q
log_success "Dependencies installed"
echo ""

# Create .env file template
log_info "Creating .env configuration file..."
cat > .env << 'EOF'
# ============================================================================
# PRODUCTION ENVIRONMENT CONFIGURATION
# ============================================================================

# Production Database (Docker PostgreSQL)
DATABASE_TYPE=postgres
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=datawarp_prod
POSTGRES_USER=databot
POSTGRES_PASSWORD=databot_dev_password
POSTGRES_SCHEMA=datawarp
DEFAULT_SCHEMA=datawarp

# LLM Provider (for manifest enrichment)
LLM_PROVIDER=gemini
LLM_MODEL=gemini-2.5-flash-lite
GEMINI_API_KEY=REPLACE_WITH_YOUR_GEMINI_API_KEY
LLM_MAX_OUTPUT_TOKENS=15000
LLM_TEMPERATURE=0.1
LLM_TIMEOUT=600

# Production Mode
DEV_MODE=false
DATAWARP_ENABLE_ENRICHMENT=true

# Paths (relative to installation)
DATAWARP_TEMP_DIR=./temp
DATAWARP_ARCHIVE_ROOT=./archive
EOF

chmod 600 .env
log_success ".env file created (remember to add your API key!)"
echo ""

# Check if PostgreSQL container is running
log_info "Checking PostgreSQL container..."
if docker ps --filter "name=databot-postgres" --format "{{.Names}}" | grep -q "databot-postgres"; then
    log_success "PostgreSQL container found: databot-postgres"

    # Create production database
    log_info "Creating production database (datawarp_prod)..."
    if docker exec databot-postgres psql -U databot -lqt | cut -d \| -f 1 | grep -qw datawarp_prod; then
        log_warning "Database datawarp_prod already exists"
    else
        docker exec databot-postgres psql -U databot -c "CREATE DATABASE datawarp_prod OWNER databot;" > /dev/null
        log_success "Database datawarp_prod created"
    fi
    echo ""

    # Initialize database schema
    log_info "Initializing database schema..."
    python scripts/reset_db.py << EOF
yes
EOF
    log_success "Database schema initialized"
    echo ""
else
    log_warning "PostgreSQL container not found!"
    log_info "Please start your PostgreSQL container first"
    echo "If using Docker:"
    echo "  docker-compose up -d postgres"
    echo ""
fi

# Create initial state file
log_info "Creating state tracking file..."
echo '{"processed": {}, "failed": {}}' > state/state.json
log_success "State file created"
echo ""

# Create publications config template
log_info "Creating publications config template..."
cat > config/publications.yaml << 'EOF'
# Production NHS Data Sources
# Add your NHS publication URLs here

adhd:
  name: "ADHD Management Information"
  landing_page: "https://digital.nhs.uk/data-and-information/publications/statistical/adult-adhd"
  urls:
    # Add URLs here
    # - "https://digital.nhs.uk/data-and-information/publications/statistical/adult-adhd/august-2025"

# Add more publications as needed
EOF
log_success "Publications config created"
echo ""

# Summary
echo ""
echo "═══════════════════════════════════════════════════════════════"
log_success "Production environment setup complete!"
echo "═══════════════════════════════════════════════════════════════"
echo ""
echo "📂 Location: $PROD_DIR"
echo ""
echo "🔧 Next Steps:"
echo ""
echo "1. Edit .env file and add your Gemini API key:"
echo "   nano $PROD_DIR/.env"
echo ""
echo "2. Activate the production environment:"
echo "   cd $PROD_DIR"
echo "   source .venv/bin/activate"
echo ""
echo "3. Verify setup:"
echo "   datawarp list"
echo "   # Should show: No sources registered."
echo ""
echo "4. Add NHS URLs to config/publications.yaml and run:"
echo "   python scripts/backfill.py"
echo ""
echo "═══════════════════════════════════════════════════════════════"
echo ""
log_info "Happy DataWarping! 🚀"
