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

publications:
  online_consultation:
    name: "Online Consultation Systems in General Practice"
    frequency: monthly
    urls:
      - period: oct25
        url: https://digital.nhs.uk/data-and-information/publications/statistical/submissions-via-online-consultation-systems-in-general-practice/october-2025

  adhd:
    name: "ADHD Management Information"
    frequency: monthly
    urls:
      # Add URLs here
      # - period: nov25
      #   url: https://digital.nhs.uk/data-and-information/publications/statistical/adult-adhd/november-2025

# Add more publications as needed
EOF
log_success "Publications config created"
echo ""

# ============================================================================
# MCP SERVER SETUP
# ============================================================================
echo ""
log_info "Setting up MCP Server for agent querying..."
echo ""

# Install MCP dependencies
log_info "Installing MCP server dependencies..."
pip install mcp duckdb -q
log_success "MCP dependencies installed"
echo ""

# Create MCP server systemd service file (for Linux deployments)
log_info "Creating MCP server service configuration..."
cat > config/mcp-server.service << 'EOF'
[Unit]
Description=DataWarp MCP Server - NHS Data Query API
After=network.target postgresql.service

[Service]
Type=simple
User=datawarp
WorkingDirectory=/opt/datawarp
Environment="PATH=/opt/datawarp/.venv/bin"
Environment="MCP_MODE=postgres"
ExecStart=/opt/datawarp/.venv/bin/python mcp_server/server.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF
log_success "MCP service file created"
echo ""

# Create MCP startup script
log_info "Creating MCP startup script..."
cat > scripts/start_mcp.sh << 'EOF'
#!/bin/bash
# Start MCP Server
# Usage: ./scripts/start_mcp.sh [mode]
# Modes: postgres (default), parquet

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"
source .venv/bin/activate

# Set mode (default: postgres)
export MCP_MODE="${1:-postgres}"

echo "Starting DataWarp MCP Server..."
echo "Mode: $MCP_MODE"
echo "Port: 8000"
echo ""

# Check if database is reachable (for postgres mode)
if [ "$MCP_MODE" = "postgres" ]; then
    echo "Testing database connection..."
    python -c "from datawarp.storage.connection import get_connection; get_connection()" 2>/dev/null || {
        echo "WARNING: Database connection failed. Falling back to parquet mode."
        export MCP_MODE=parquet
    }
fi

# Start server
python mcp_server/server.py
EOF
chmod +x scripts/start_mcp.sh
log_success "MCP startup script created"
echo ""

# Create MCP test script
log_info "Creating MCP test script..."
cat > scripts/test_mcp.sh << 'EOF'
#!/bin/bash
# Test MCP Server Endpoints
# Usage: ./scripts/test_mcp.sh [host]

set -e

HOST="${1:-http://localhost:8000}"

echo "Testing MCP Server at $HOST"
echo "═══════════════════════════════════════════════════════════════"
echo ""

# Test 1: Health check
echo "TEST 1: Health Check"
echo "--------------------"
curl -s "$HOST/" | python -m json.tool
echo ""

# Test 2: List datasets
echo "TEST 2: List Datasets"
echo "---------------------"
curl -s -X POST "$HOST/mcp" \
  -H "Content-Type: application/json" \
  -d '{"method": "list_datasets", "params": {"limit": 5}}' | python -m json.tool
echo ""

# Test 3: Get metadata
echo "TEST 3: Get Metadata (first dataset)"
echo "------------------------------------"
FIRST_DATASET=$(curl -s -X POST "$HOST/mcp" \
  -H "Content-Type: application/json" \
  -d '{"method": "list_datasets", "params": {"limit": 1}}' | \
  python -c "import sys,json; d=json.load(sys.stdin); print(d['result']['datasets'][0]['code'] if d.get('result',{}).get('datasets') else '')")

if [ -n "$FIRST_DATASET" ]; then
    echo "Querying metadata for: $FIRST_DATASET"
    curl -s -X POST "$HOST/mcp" \
      -H "Content-Type: application/json" \
      -d "{\"method\": \"get_metadata\", \"params\": {\"dataset\": \"$FIRST_DATASET\"}}" | python -m json.tool
else
    echo "No datasets found"
fi
echo ""

# Test 4: Complex query
echo "TEST 4: Complex Query (row count)"
echo "----------------------------------"
if [ -n "$FIRST_DATASET" ]; then
    curl -s -X POST "$HOST/mcp" \
      -H "Content-Type: application/json" \
      -d "{\"method\": \"query\", \"params\": {\"dataset\": \"$FIRST_DATASET\", \"question\": \"how many rows\"}}" | python -m json.tool
fi
echo ""

echo "═══════════════════════════════════════════════════════════════"
echo "✅ MCP Server tests complete"
EOF
chmod +x scripts/test_mcp.sh
log_success "MCP test script created"
echo ""

# Create Claude Desktop configuration
log_info "Creating Claude Desktop MCP configuration..."
mkdir -p config/claude-desktop
cat > config/claude-desktop/mcp-config.json << 'EOF'
{
  "mcpServers": {
    "nhs-datawarp": {
      "command": "python",
      "args": ["-m", "uvicorn", "mcp_server.server:app", "--host", "127.0.0.1", "--port", "8000"],
      "cwd": "/PATH/TO/DATAWARP",
      "env": {
        "MCP_MODE": "parquet"
      }
    }
  }
}
EOF
log_success "Claude Desktop config template created"
echo ""

# ============================================================================
# PARQUET EXPORT SETUP
# ============================================================================
log_info "Creating Parquet export script..."
cat > scripts/export_and_catalog.sh << 'EOF'
#!/bin/bash
# Export data to Parquet and rebuild catalog
# Usage: ./scripts/export_and_catalog.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"
source .venv/bin/activate

echo "Exporting data to Parquet format..."
echo "═══════════════════════════════════════════════════════════════"

# Export all sources to Parquet
python scripts/export_to_parquet.py --all output/

# Rebuild catalog
echo ""
echo "Rebuilding catalog.parquet..."
python scripts/rebuild_catalog.py

# Show results
echo ""
echo "Export complete. Files created:"
ls -la output/*.parquet 2>/dev/null || echo "  No parquet files found"
echo ""
echo "Metadata files:"
ls -la output/*.md 2>/dev/null || echo "  No metadata files found"
echo ""

# Show catalog summary
echo "Catalog summary:"
python -c "
import duckdb
df = duckdb.execute('SELECT source_code, row_count, column_count FROM \"output/catalog.parquet\"').df()
print(df.to_string(index=False))
print(f'\nTotal datasets: {len(df)}')
print(f'Total rows: {df[\"row_count\"].sum():,}')
"
EOF
chmod +x scripts/export_and_catalog.sh
log_success "Export script created"
echo ""

# ============================================================================
# FULL DEPLOYMENT SCRIPT
# ============================================================================
log_info "Creating full deployment script..."
cat > scripts/deploy.sh << 'EOF'
#!/bin/bash
# Full DataWarp Deployment
# Usage: ./scripts/deploy.sh [publication]
# Example: ./scripts/deploy.sh online_consultation

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"
source .venv/bin/activate

PUBLICATION="${1:-all}"

echo "═══════════════════════════════════════════════════════════════"
echo "DataWarp Full Deployment"
echo "═══════════════════════════════════════════════════════════════"
echo "Publication: $PUBLICATION"
echo "Started: $(date)"
echo ""

# Step 1: Load data
echo "STEP 1: Loading NHS data..."
echo "----------------------------"
if [ "$PUBLICATION" = "all" ]; then
    python scripts/backfill.py --config config/publications.yaml
else
    python scripts/backfill.py --config config/publications.yaml --publication "$PUBLICATION"
fi
echo ""

# Step 2: Export to Parquet
echo "STEP 2: Exporting to Parquet..."
echo "--------------------------------"
./scripts/export_and_catalog.sh
echo ""

# Step 3: Test MCP
echo "STEP 3: Testing MCP Server..."
echo "------------------------------"
# Start MCP in background
python mcp_server/server.py &
MCP_PID=$!
sleep 3

# Run tests
./scripts/test_mcp.sh || true

# Stop MCP
kill $MCP_PID 2>/dev/null || true
echo ""

# Summary
echo "═══════════════════════════════════════════════════════════════"
echo "✅ Deployment complete!"
echo "═══════════════════════════════════════════════════════════════"
echo ""
echo "Data loaded to PostgreSQL:"
datawarp list 2>/dev/null | head -20 || echo "  Run 'datawarp list' to see sources"
echo ""
echo "Parquet files in output/:"
ls -la output/*.parquet 2>/dev/null | head -10 || echo "  No files yet"
echo ""
echo "To start MCP server:"
echo "  ./scripts/start_mcp.sh"
echo ""
echo "To test MCP server:"
echo "  ./scripts/test_mcp.sh"
echo ""
echo "Finished: $(date)"
EOF
chmod +x scripts/deploy.sh
log_success "Full deployment script created"
echo ""

# Summary
echo ""
echo "═══════════════════════════════════════════════════════════════"
log_success "Production environment setup complete!"
echo "═══════════════════════════════════════════════════════════════"
echo ""
echo "📂 Location: $PROD_DIR"
echo ""
echo "🔧 Quick Start:"
echo ""
echo "1. Edit .env file and add your Gemini API key:"
echo "   nano $PROD_DIR/.env"
echo ""
echo "2. Activate the production environment:"
echo "   cd $PROD_DIR"
echo "   source .venv/bin/activate"
echo ""
echo "3. Run full deployment (load data + export + test MCP):"
echo "   ./scripts/deploy.sh online_consultation"
echo ""
echo "═══════════════════════════════════════════════════════════════"
echo ""
echo "📡 MCP Server Commands:"
echo ""
echo "   Start MCP:     ./scripts/start_mcp.sh"
echo "   Test MCP:      ./scripts/test_mcp.sh"
echo "   Export data:   ./scripts/export_and_catalog.sh"
echo ""
echo "═══════════════════════════════════════════════════════════════"
echo ""
echo "🖥️  Claude Desktop Integration:"
echo ""
echo "   1. Copy config/claude-desktop/mcp-config.json"
echo "   2. Update /PATH/TO/DATAWARP to: $PROD_DIR"
echo "   3. Add to Claude Desktop settings"
echo ""
echo "═══════════════════════════════════════════════════════════════"
echo ""
log_info "Happy DataWarping! 🚀"
