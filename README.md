# Project Skynet - Multi-Agent AI Platform

**A collection of AI-powered agents built for production observability and risk management.**

Built for the AWS x Anthropic x Datadog GenAI Hackathon.

This repository contains two powerful AI agents:

1. **Web Cartographer** - Autonomous website explorer that maps user flows
2. **Release Revert Risk Advisor** - AI agent that assesses release risk based on historical patterns

---

## 🤖 Agent 1: Web Cartographer

**AI-powered autonomous website explorer that maps user flows using generative AI.**

Web Cartographer is a Strands Agent that autonomously navigates any website, systematically discovering every page, button, and user journey — then produces an interactive graph of the entire site's user experience.

### How It Works

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

### Run Web Cartographer

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

---

## 🛡️ Agent 2: Release Revert Risk Advisor

**AI agent that answers: "Based on our historical revert patterns and current signals, how risky is this release?"**

The Release Revert Risk Advisor analyzes past rollback incidents, compares them to current release context, and provides evidence-backed risk assessments with actionable recommendations.

### How It Works

1. **Identify comparable historical incidents** - Retrieves past rollback/revert events from Datadog
2. **Pull current context** - Fetches current SLI baselines and post-deploy health
3. **Compare patterns** - Computes similarity scores to prior rollback scenarios
4. **Generate risk report** - Produces risk score (0-100), top risk drivers, monitoring checks, and rollout guidance

### Features

- **Pattern Matching**: Compares current releases to historical failure signatures
- **SLI Analysis**: Monitors error rates, latency, crash rates, and service-specific metrics
- **Evidence-Based Scoring**: Weighted risk model (similarity + volatility + anomalies)
- **Actionable Recommendations**: Ship / Ramp / Hold with specific guidance
- **Self-Observability**: Full telemetry instrumentation into Datadog

### Run Release Revert Risk Advisor

**Important**: For the web UI to work, you need to start the API server first!

```bash
# Terminal 1: Start the API server
python3 run_risk_advisor.py --server --port 8000
# Or use the helper script:
./start_server.sh

# Terminal 2: Start the React UI (optional, if you want dev mode)
cd ui
npm start
# Opens on http://localhost:3000

# CLI mode (no server needed)
python3 run_risk_advisor.py --feature "playback-buffer-v2" --service "playback-service" --platform "ios"
```

**Note**: The React UI connects to `http://localhost:8000/api`. Make sure the server is running before using the web interface.

### API Endpoints

- `POST /api/assess` - Run a risk assessment
- `GET /api/runs` - List past assessment runs
- `GET /api/runs/{run_id}` - Get a specific run
- `GET /api/telemetry` - Agent observability data
- `GET /api/services` - Available services
- `GET /api/health` - Health check

---

## 🚀 Quick Start

### Prerequisites

- Python 3.10+ (3.13 recommended)
- AWS credentials configured (`aws configure`) with Bedrock access
- Claude model enabled in Amazon Bedrock console
- Datadog API key (for observability and risk advisor)

### Setup

```bash
# Clone and enter the project
git clone https://github.com/qa-entomologist/project-skynet.git
cd project-skynet

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Install Playwright browsers (for Web Cartographer)
playwright install chromium

# Configure environment
# Copy .env.example to .env and fill in your credentials
# Required: DD_API_KEY, AWS credentials
```

### Environment Variables

Create a `.env` file with:

```bash
# Datadog
DD_API_KEY=your_datadog_api_key
DD_APP_KEY=your_datadog_app_key  # For Risk Advisor
DD_SITE=datadoghq.com

# AWS Bedrock
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=your_aws_access_key
AWS_SECRET_ACCESS_KEY=your_aws_secret_key
BEDROCK_MODEL_ID=anthropic.claude-3-sonnet-20240229-v1:0

# Risk Advisor (optional)
AGENT_ENV=demo  # or 'production'
REVERT_HISTORY_PATH=data/revert_history.yaml

# Web Cartographer (optional)
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=password
```

---

## 📊 Datadog Observability

Both agents are fully instrumented with Datadog observability:

### Web Cartographer
- Complete agent reasoning traces
- Tool call latencies and success rates
- Token usage per exploration cycle
- End-to-end exploration performance

### Release Revert Risk Advisor
- Agent run metrics (`agent.run.count`, `agent.run.latency_ms`)
- Datadog query counts (`agent.datadog_queries.count`)
- Risk score distribution (`agent.risk_score`)
- Recommendation distribution (`agent.recommendation`)
- Structured logs with run_id, inputs, evidence references

Set your `DD_API_KEY` in `.env` to automatically send traces to Datadog.

---

## 🗂️ Project Structure

```
project-skynet/
├── run.py                  # Web Cartographer entry point
├── run_risk_advisor.py     # Risk Advisor entry point
├── requirements.txt         # Python dependencies
├── .env.example            # Environment template
│
├── src/                    # Web Cartographer
│   ├── agent.py            # Strands Agent + tool definitions
│   ├── browser_manager.py  # Playwright browser wrapper
│   ├── graph_store.py      # Neo4j + in-memory graph backends
│   └── config.py           # Configuration
│
├── agent/                   # Release Revert Risk Advisor
│   ├── main.py             # Agent orchestrator
│   ├── datadog_client.py   # Datadog API client
│   ├── signature_builder.py # Failure signature matching
│   ├── risk_model.py       # Risk scoring engine
│   ├── bedrock_summarizer.py # Report generation
│   ├── observability.py    # Self-instrumentation
│   └── config.py            # Configuration
│
├── server/                  # Risk Advisor API
│   └── app.py              # FastAPI server
│
├── ui/                      # Risk Advisor React UI
│   ├── src/
│   │   ├── App.jsx         # Main React app
│   │   └── components/     # UI components
│   └── package.json
│
├── data/                    # Risk Advisor data
│   └── revert_history.yaml # Historical revert events
│
├── evals/                   # Risk Advisor run outputs
│
├── web/                     # Web Cartographer visualization
│   └── index.html          # Interactive graph visualization
│
└── screenshots/             # Web Cartographer screenshots
```

---

## 🏗️ Architecture

### Web Cartographer

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

### Release Revert Risk Advisor

```
┌─────────────────────────────────────────────┐
│  Agent Orchestrator                         │
│  ├── Fetch historical revert events         │
│  ├── Build failure signatures               │
│  ├── Fetch current SLI baselines           │
│  ├── Compute risk score                    │
│  └── Generate evidence-backed report        │
├─────────────────────────────────────────────┤
│  Datadog Client                             │
│  - Events/Incidents API                     │
│  - Metrics API                              │
│  - Demo mode (YAML fallback)                │
├─────────────────────────────────────────────┤
│  Risk Model                                 │
│  - Similarity scoring (0-50)                │
│  - Volatility analysis (0-30)                │
│  - Anomaly detection (0-20)                  │
├─────────────────────────────────────────────┤
│  Bedrock Summarizer                         │
│  - Natural language risk reports            │
│  - Template fallback                       │
├─────────────────────────────────────────────┤
│  Observability                              │
│  - Structured logging                       │
│  - Datadog custom metrics                   │
│  - Run telemetry                            │
└─────────────────────────────────────────────┘
```

---

## 🧪 Neo4j (Optional - Web Cartographer)

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

---

## 📝 License

MIT

---

## 🤝 Contributing

This is a hackathon project. Contributions welcome!

---

## 📧 Contact

Built for the AWS x Anthropic x Datadog GenAI Hackathon.
