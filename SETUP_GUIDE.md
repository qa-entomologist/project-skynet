# Setup Guide - Web Cartographer

Complete setup instructions for all features including Datadog LLM Observability and Neo4j integration.

## Prerequisites

- Python 3.10+ (3.13 recommended)
- AWS credentials configured with Bedrock access
- Claude 3.5 Sonnet v2 enabled in Amazon Bedrock console
- Node.js (for React UI - Risk Advisor only)

## Basic Setup

```bash
# Clone the repository
git clone https://github.com/qa-entomologist/project-skynet.git
cd project-skynet

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Install Playwright browsers
playwright install chromium

# Copy environment template
cp .env.example .env
# Edit .env with your credentials
```

## Environment Variables

Create a `.env` file with the following:

```bash
# AWS Bedrock (Required)
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=your_aws_access_key
AWS_SECRET_ACCESS_KEY=your_aws_secret_key
# Or use AWS SSO:
AWS_PROFILE=your-profile-name

# Datadog LLM Observability (Optional but recommended)
DD_API_KEY=your_datadog_api_key
DD_SITE=datadoghq.com  # or us3.datadoghq.com, datadoghq.eu, etc.

# Neo4j (Optional - for persistent graph storage)
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your_password

# Exploration Limits (Optional)
MAX_DEPTH=5
MAX_PAGES=50
HEADLESS=true
```

## AWS SSO Setup

If using AWS SSO:

```bash
# Configure AWS SSO
aws configure sso

# Login
aws sso login --profile your-profile-name

# Set in .env
AWS_PROFILE=your-profile-name
```

## Datadog LLM Observability Setup

### 1. Get Your Datadog API Key

1. Log in to [Datadog](https://app.datadoghq.com)
2. Go to **Organization Settings** → **API Keys**
3. Create a new API key or copy an existing one
4. Add to `.env`: `DD_API_KEY=your_api_key_here`

### 2. Verify Datadog Site

Check your Datadog site URL:
- US1: `datadoghq.com` (default)
- US3: `us3.datadoghq.com`
- US5: `us5.datadoghq.com`
- EU: `datadoghq.eu`
- AP1: `ap1.datadoghq.com`

Set in `.env`: `DD_SITE=datadoghq.com`

### 3. Test Datadog Integration

```bash
# Run with Datadog enabled
python run.py https://www.example.com

# Check Datadog dashboard
# Navigate to: APM → Traces → Filter by service: "strands-agent"
# You should see:
# - Agent reasoning traces
# - Tool call latencies
# - Token usage per exploration cycle
# - End-to-end exploration performance
```

### 4. View Traces in Datadog

1. Open Datadog → **APM** → **Traces**
2. Filter by:
   - Service: `strands-agent`
   - Resource: `web-cartographer` or tool names
3. Look for:
   - **LLM traces** with full reasoning chains
   - **Tool calls** (navigate_to_url, scan_page, click_element)
   - **Performance metrics** (latency, token counts)

### 5. Troubleshooting

If traces aren't appearing:

```bash
# Check if DD_API_KEY is set
python -c "from src.config import DD_API_KEY; print('DD_API_KEY:', 'SET' if DD_API_KEY else 'NOT SET')"

# Run with verbose logging
python run.py https://www.example.com --no-datadog  # Disable to test without DD

# Check OpenTelemetry endpoint
python -c "from src.config import get_otlp_endpoint; print(get_otlp_endpoint())"
```

## Neo4j Setup

### 1. Start Neo4j with Docker

```bash
# Run Neo4j container
docker run -d \
  --name neo4j \
  -p 7474:7474 \
  -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/your-password \
  -e NEO4J_PLUGINS='["apoc"]' \
  neo4j:latest

# Wait for Neo4j to start (30-60 seconds)
docker logs -f neo4j
# Look for: "Started."
```

### 2. Configure Environment

Add to `.env`:
```bash
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your-password
```

### 3. Test Neo4j Connection

```bash
# Run with Neo4j
python run.py https://www.example.com --neo4j

# Check Neo4j Browser
# Open http://localhost:7474
# Login with: neo4j / your-password
# Run query:
MATCH (n) RETURN n LIMIT 25
```

### 4. Query the Graph

In Neo4j Browser:

```cypher
# All pages
MATCH (p:Page) RETURN p LIMIT 50

# Pages by depth
MATCH (p:Page) 
WHERE p.depth <= 2 
RETURN p.url, p.title, p.depth

# Navigation paths
MATCH path = (start:Page)-[:CLICKED*]->(end:Page)
WHERE start.depth = 0
RETURN path LIMIT 10

# Most connected pages
MATCH (p:Page)-[r]-()
RETURN p.url, count(r) as connections
ORDER BY connections DESC
LIMIT 10
```

### 5. Troubleshooting

```bash
# Check if Neo4j is running
docker ps | grep neo4j

# Check Neo4j logs
docker logs neo4j

# Test connection
python -c "from neo4j import GraphDatabase; driver = GraphDatabase.driver('bolt://localhost:7687', auth=('neo4j', 'your-password')); driver.verify_connectivity(); print('Connected!')"
```

## Running Explorations

### Basic Usage

```bash
# Simple site
python run.py https://www.example.com

# With visible browser
python run.py https://www.ebay.com --headed

# Custom limits
python run.py https://www.amazon.com --max-depth 3 --max-pages 20

# With Neo4j
python run.py https://www.ebay.com --neo4j

# Without Datadog (for testing)
python run.py https://www.example.com --no-datadog
```

### Deep Exploration (20-30+ pages)

```bash
# Increase limits for deeper exploration
python run.py https://www.example.com --max-depth 5 --max-pages 30

# Or set in .env:
MAX_DEPTH=5
MAX_PAGES=30
```

### SPA Sites (React/Vue/Angular)

The agent now detects SPA navigation by monitoring DOM changes:

```bash
# SPA sites work better with longer wait times
# Edit src/_pw_helper.py if needed to increase wait_for_timeout

python run.py https://tubi.tv --max-pages 20
```

## Visualization

### View the Graph

```bash
# After running an exploration
open web/index.html

# Or serve with a local server
cd web
python3 -m http.server 8080
# Open http://localhost:8080
```

### Auto-Refresh

The visualization HTML includes auto-refresh:

1. Open `web/index.html` in your browser
2. Click **"Auto-Refresh: OFF"** to enable
3. The graph will update every 3 seconds while the agent explores
4. Watch the graph build in real-time!

## Testing Checklist

- [ ] Basic exploration works (`python run.py https://www.example.com`)
- [ ] Screenshots are captured in `screenshots/` directory
- [ ] Graph JSON is exported to `web/graph_data.json`
- [ ] Visualization loads in browser
- [ ] Datadog traces appear (if DD_API_KEY set)
- [ ] Neo4j stores graph (if Neo4j running and `--neo4j` flag used)
- [ ] SPA sites detected correctly (DOM changes tracked)
- [ ] Deep exploration works (20-30+ pages)

## Troubleshooting

### Common Issues

**"Browser helper failed to start"**
- Install Playwright: `playwright install chromium`
- Check Python version: `python3 --version` (need 3.10+)

**"No traces in Datadog"**
- Verify `DD_API_KEY` is set in `.env`
- Check Datadog site matches your account
- Wait 1-2 minutes for traces to appear

**"Neo4j connection failed"**
- Ensure Docker container is running: `docker ps | grep neo4j`
- Check credentials in `.env`
- Verify port 7687 is accessible

**"SPA clicks don't work"**
- The agent now detects DOM changes
- Check browser console for errors
- Try increasing wait times in `_pw_helper.py`

## Next Steps

- Read [INTEGRATION.md](INTEGRATION.md) for multi-agent setup
- Check [README.md](README.md) for full documentation
- Review agent code in `src/agent.py` for customization

