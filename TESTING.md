# Testing Guide

Comprehensive testing procedures for Web Cartographer features.

## Test Cases

### 1. Basic Exploration

**Test**: Simple site exploration
```bash
python run.py https://www.example.com
```

**Expected**:
- ✅ Agent navigates to site
- ✅ Finds 1 page
- ✅ Correctly skips external links
- ✅ Screenshot captured
- ✅ Graph JSON exported

**Verify**:
```bash
ls screenshots/*.png  # Should have screenshots
cat web/graph_data.json | jq '.nodes | length'  # Should be 1
```

### 2. Multi-Page Navigation

**Test**: Books.toscrape.com
```bash
python run.py https://books.toscrape.com --max-pages 10
```

**Expected**:
- ✅ Agent navigates site
- ✅ Clicks categories
- ✅ Captures screenshots
- ✅ Builds graph with multiple nodes and edges
- ✅ At least 2 nodes + 1 edge

**Verify**:
```bash
cat web/graph_data.json | jq '{nodes: (.nodes | length), edges: (.edges | length)}'
# Should show: {"nodes": 2, "edges": 1} or more
```

### 3. SPA Detection

**Test**: Tubi.tv (React SPA)
```bash
python run.py https://tubi.tv --max-pages 5 --headed
```

**Expected**:
- ✅ Agent identifies SPA structure
- ✅ Catalogues all nav elements
- ✅ Detects DOM changes even if URL doesn't change
- ✅ Records SPA navigation in graph

**Verify**:
- Check `web/graph_data.json` for nodes with `is_spa_navigation: true`
- Screenshots should show different content even if URLs are similar

### 4. Deep Exploration (20-30+ pages)

**Test**: Large site exploration
```bash
python run.py https://www.ebay.com --max-depth 4 --max-pages 25
```

**Expected**:
- ✅ Explores 20-30+ pages
- ✅ Maintains graph structure
- ✅ Doesn't get stuck in loops
- ✅ Screenshots for all pages

**Verify**:
```bash
cat web/graph_data.json | jq '.nodes | length'  # Should be 20+
ls screenshots/*.png | wc -l  # Should match node count
```

### 5. Datadog LLM Observability

**Prerequisites**: `DD_API_KEY` set in `.env`

**Test**:
```bash
python run.py https://www.example.com
```

**Expected**:
- ✅ Traces appear in Datadog within 1-2 minutes
- ✅ LLM traces show reasoning chains
- ✅ Tool calls are instrumented
- ✅ Token usage tracked

**Verify in Datadog**:
1. Go to **APM** → **Traces**
2. Filter: Service = `strands-agent`
3. Look for:
   - Traces with `gen_ai` tags
   - Tool calls (navigate_to_url, scan_page, etc.)
   - Token counts in trace metadata

**Manual Check**:
```bash
# Check if telemetry is configured
python -c "from src.config import DD_API_KEY, get_otlp_endpoint; print(f'DD_API_KEY: {\"SET\" if DD_API_KEY else \"NOT SET\"}'); print(f'Endpoint: {get_otlp_endpoint()}')"
```

### 6. Neo4j Integration

**Prerequisites**: Neo4j running via Docker

**Test**:
```bash
python run.py https://www.example.com --neo4j
```

**Expected**:
- ✅ Graph stored in Neo4j
- ✅ Nodes and edges created
- ✅ Can query via Neo4j Browser

**Verify**:
1. Open http://localhost:7474
2. Login with Neo4j credentials
3. Run:
```cypher
MATCH (n) RETURN count(n) as total_nodes
MATCH ()-[r]->() RETURN count(r) as total_edges
```

**Expected**: Should show nodes and edges matching the exploration

### 7. Graph Export

**Test**: After any exploration
```bash
python run.py https://www.example.com
```

**Expected**:
- ✅ `web/graph_data.json` is created/updated
- ✅ JSON is valid
- ✅ Contains nodes and edges

**Verify**:
```bash
# Check file exists
test -f web/graph_data.json && echo "✅ Graph JSON exists"

# Validate JSON
cat web/graph_data.json | jq '.' > /dev/null && echo "✅ Valid JSON"

# Check structure
cat web/graph_data.json | jq 'has("nodes") and has("edges")'  # Should be true
```

### 8. Screenshot Capture

**Test**: Any exploration
```bash
python run.py https://www.example.com
```

**Expected**:
- ✅ Screenshots saved in `screenshots/` directory
- ✅ One screenshot per page
- ✅ Screenshots are valid PNG files

**Verify**:
```bash
# Count screenshots
ls screenshots/*.png | wc -l

# Verify they're valid PNGs
file screenshots/*.png | grep -c "PNG image"
```

### 9. Visualization

**Test**: Open visualization after exploration
```bash
open web/index.html
# Or: python3 -m http.server 8080 (in web/ directory)
```

**Expected**:
- ✅ Graph visualizes correctly
- ✅ Nodes and edges visible
- ✅ Can click nodes to highlight
- ✅ Stats show correct counts
- ✅ Auto-refresh works (if enabled)

**Verify**:
- Graph loads without errors
- Stats match JSON data
- Clicking nodes highlights them
- Auto-refresh button toggles correctly

### 10. Live Auto-Refresh

**Test**: Run exploration while visualization is open
```bash
# Terminal 1: Open visualization
open web/index.html
# Enable auto-refresh in browser

# Terminal 2: Run exploration
python run.py https://www.example.com --max-pages 10
```

**Expected**:
- ✅ Graph updates every 3 seconds
- ✅ New nodes appear as discovered
- ✅ Stats update in real-time
- ✅ Can watch exploration progress

**Verify**:
- Enable auto-refresh in browser
- Watch graph grow as agent explores
- Stats counter increases

## Integration Tests

### Full Stack Test

```bash
# 1. Start Neo4j
docker run -d --name neo4j -p 7474:7474 -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/test123 neo4j:latest

# 2. Set environment
export DD_API_KEY=your_key
export NEO4J_URI=bolt://localhost:7687
export NEO4J_USER=neo4j
export NEO4J_PASSWORD=test123

# 3. Run exploration
python run.py https://www.example.com --neo4j

# 4. Verify all components
# - Screenshots exist
# - Graph JSON exported
# - Neo4j has data
# - Datadog has traces (check dashboard)
```

## Performance Benchmarks

### Expected Performance

| Site Type | Pages | Time | Notes |
|-----------|-------|------|-------|
| Simple (example.com) | 1 | ~10s | Single page |
| Medium (books.toscrape) | 5-10 | ~2-3min | Static site |
| Complex (ebay.com) | 20-30 | ~10-15min | Large site |
| SPA (tubi.tv) | 5-10 | ~3-5min | React app |

### Optimization Tips

- Use `--max-pages` to limit exploration
- Use `--max-depth` to control depth
- Run `--headed` for debugging
- Increase limits in `.env` for deeper exploration

## Regression Tests

Run these before major changes:

```bash
# Quick smoke test
python run.py https://www.example.com

# Multi-page test
python run.py https://books.toscrape.com --max-pages 5

# SPA test
python run.py https://tubi.tv --max-pages 3

# Deep exploration test
python run.py https://www.ebay.com --max-pages 10 --max-depth 3
```

All should complete without errors and produce valid graph JSON.

