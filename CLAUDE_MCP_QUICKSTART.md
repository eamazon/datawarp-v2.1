# Claude MCP Quick Start Guide

## ✅ Configuration Installed

Your Claude Desktop is now configured to access the DataWarp MCP server!

**Location:** `~/Library/Application Support/Claude/claude_desktop_config.json`

---

## 🚀 Next Steps

### 1. Restart Claude Desktop

**Important:** Completely quit and reopen Claude Desktop for the configuration to take effect.

```bash
# Force quit Claude Desktop
killall Claude 2>/dev/null

# Then manually reopen Claude Desktop from Applications
```

### 2. Test the Connection

Open **Claude Desktop** and try these queries:

#### **Discovery Query:**
```
What NHS datasets are available in the DataWarp system?
```

Claude should respond with a list of 181 datasets.

#### **Specific Search:**
```
Show me datasets about online consultation submissions
```

#### **Metadata Exploration:**
```
Tell me about the practice_oc_submissions dataset - 
how many rows and what columns does it have?
```

#### **Data Query:**
```
Query practice_oc_submissions and show me a sample of 5 records
```

---

## 📊 Available Data

**Total Datasets:** 181 sources  
**Total Rows:** 75.8M rows  
**Categories:**
- Online Consultation Systems (9.6M rows, 7 sources)
- GP Practice Registrations (66M rows, 170+ sources)
- ADHD Prevalence & Waiting Lists (13 sources)

**Key Datasets:**
- `practice_oc_submissions` - 8.5M rows (online consultation data)
- `icb_location_csv` - 29.8M rows (ICB location data)
- `oc_submissions_day_time` - 521K rows (day/time patterns)
- `gp_submissions_by_practice` - 56K rows (practice-level data)

---

## 🔍 Example Queries for Claude

### Discovery Queries
- "What data sources contain information about GP practices?"
- "List all datasets with more than 1 million rows"
- "Find datasets related to patient submissions"

### Analysis Queries
- "What are the trends in online consultation submissions from March to November 2025?"
- "Compare submission volumes across different regions"
- "Show me the distribution of submissions by day of week"

### Metadata Queries
- "What columns are available in the oc_submissions_day_time dataset?"
- "How fresh is the online consultation data?"
- "What's the date range covered by practice_oc_submissions?"

---

## 🛠 Troubleshooting

### Claude doesn't respond to data queries

**Check 1:** Verify MCP server is working
```bash
curl http://localhost:8000/
# Should return: {"service":"DataWarp MCP Server","status":"running"...}
```

**Check 2:** Check Claude Desktop logs
```bash
tail -f ~/Library/Logs/Claude/mcp*.log
```

**Check 3:** Restart PostgreSQL if needed
```bash
# Check if PostgreSQL is running
pg_isready -h localhost -p 5432

# If not, start it (adjust command based on your installation)
brew services start postgresql@14
```

### Python environment issues

**Verify Python can access DataWarp:**
```bash
cd /Users/speddi/projectx/datawarp-v2.1
source .venv/bin/activate
python -c "from datawarp.storage.connection import get_connection; print('✓ DataWarp accessible')"
```

### Database connection errors

**Test database directly:**
```bash
source /Users/speddi/projectx/datawarp-v2.1/.env
psql -h $POSTGRES_HOST -p $POSTGRES_PORT -U $POSTGRES_USER -d $POSTGRES_DB -c "SELECT 'Connected!' as status;"
```

---

## 📚 MCP Methods Available to Claude

Claude can call these methods automatically:

1. **`list_datasets`** - Discover available datasets
   - Parameters: `domain`, `keyword`, `min_rows`, `limit`
   - Returns: List of matching datasets with row counts

2. **`get_metadata`** - Examine dataset structure
   - Parameters: `dataset` (source code)
   - Returns: Columns, types, descriptions, sample values

3. **`query`** - Execute natural language queries
   - Parameters: `dataset`, `question`
   - Returns: Query results as JSON records

---

## 🎯 Success Indicators

When working correctly, you'll see:

- ✅ Claude responds with actual data from DataWarp
- ✅ Claude references specific row counts (e.g., "8.5M rows")
- ✅ Claude shows you column names from the datasets
- ✅ Claude can answer questions about data trends

When NOT working:

- ❌ Claude says "I don't have access to that data"
- ❌ Claude gives generic responses without specifics
- ❌ Claude doesn't mention DataWarp or NHS datasets

---

## 📖 Learn More

- **MCP Documentation:** https://modelcontextprotocol.io/
- **DataWarp Source:** `/Users/speddi/projectx/datawarp-v2.1/`
- **MCP Server Code:** `/Users/speddi/projectx/datawarp-v2.1/mcp_server/server.py`
- **E2E Test Results:** `/tmp/e2e_summary.md`

---

**Ready to explore your NHS data with Claude!** 🚀
