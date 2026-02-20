# Web Cartographer

**AI-powered autonomous website explorer that maps user flows using generative AI.**

Built for the AWS x Anthropic x Datadog GenAI Hackathon.

Web Cartographer is a Strands Agent that autonomously navigates any website, systematically discovering every page, button, and user journey — then produces an interactive graph of the entire site's user experience.

## How It Works

1. You give it a URL (e.g. `https://www.ebay.com`)
2. The agent launches a browser and starts exploring like a curious first-time user
3. At each page it:
   - Takes a screenshot
   - Identifies all interactive elements (links, buttons, forms)
   - Decides which path to explore next (depth-first)
   - Records the action and resulting page in a graph
4. When it hits a dead end, it navigates back using the site's own UI (back buttons, breadcrumbs, logo)
5. It continues until it has mapped all major flows or hits configured limits
6. The result is an interactive graph visualization of the website's complete user flow map

## Tech Stack

| Component | Technology |
|-----------|------------|
| **Agent Framework** | [Strands Agents](https://strandsagents.com/) (AWS) |
| **LLM** | Claude via Amazon Bedrock |
| **Browser Automation** | Playwright |
| **Graph Storage** | Neo4j (optional) / In-memory |
| **Observability** | Datadog LLM Observability via OpenTelemetry |
| **Visualization** | vis.js network graph |

## Quick Start

### Prerequisites

- Python 3.10+
- AWS credentials configured (`aws configure`) with Bedrock access
- Claude model enabled in Amazon Bedrock console

### Setup

```bash
# Clone and enter the project
cd "DataDog Hackathon"

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Install Playwright browsers
playwright install chromium

# Copy environment template
cp .env.example .env
# Edit .env with your credentials
```

### Run

```bash
# Basic exploration
python3 run.py https://www.example.com

# With visible browser
python3 run.py https://www.ebay.com --headed

# Custom limits
python3 run.py https://www.amazon.com --max-depth 3 --max-pages 20

# With Neo4j storage (requires Neo4j running)
python3 run.py https://www.ebay.com --neo4j
```

### Visualize

Open `web/index.html` in a browser to see the exploration graph. Enable auto-refresh to watch it build in real-time while the agent explores.

## Datadog Observability

Set your `DD_API_KEY` in `.env` to automatically send traces to Datadog LLM Observability. You'll see:

- Complete agent reasoning traces
- Tool call latencies and success rates
- Token usage per exploration cycle
- End-to-end exploration performance

## Neo4j (Optional)

For persistent graph storage and richer querying:

```bash
# Run Neo4j with Docker
docker run -d \
  --name neo4j \
  -p 7474:7474 -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/password \
  neo4j:latest

# Run with Neo4j flag
python run.py https://www.ebay.com --neo4j
```

Open http://localhost:7474 to explore the graph in Neo4j Browser.

## Architecture

```
┌─────────────────────────────────────────────┐
│  Strands Agent (Claude via Bedrock)         │
│  System Prompt: "Explore like a curious     │
│  first-time user..."                        │
│                                             │
│  Tools:                                     │
│  ├── navigate_to_url    - Go to a page      │
│  ├── scan_page          - Discover elements │
│  ├── click_element      - Click & record    │
│  ├── go_back            - Smart back nav    │
│  ├── get_exploration_status                 │
│  └── export_exploration_graph               │
├─────────────────────────────────────────────┤
│  Browser Manager (Playwright)               │
│  - Screenshots, DOM analysis, click, nav    │
├─────────────────────────────────────────────┤
│  Graph Store (Neo4j / In-Memory)            │
│  - Pages as nodes, actions as edges         │
├─────────────────────────────────────────────┤
│  Datadog LLM Observability (OpenTelemetry)  │
│  - Traces, metrics, token usage             │
└─────────────────────────────────────────────┘
```

## Project Structure

```
├── run.py                  # Entry point / CLI
├── requirements.txt        # Python dependencies
├── .env.example            # Environment template
├── src/
│   ├── agent.py            # Strands Agent + tool definitions
│   ├── browser_manager.py  # Playwright browser wrapper
│   ├── graph_store.py      # Neo4j + in-memory graph backends
│   └── config.py           # Configuration
├── web/
│   └── index.html          # Interactive graph visualization
└── screenshots/            # Captured page screenshots
```
