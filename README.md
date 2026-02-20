# Project Skynet

**AI-powered agents for production observability and QA automation.**

Built for the AWS x Anthropic x Datadog GenAI Hackathon.

---

## Agents

### 1. Web Cartographer (QA Agent)

Autonomous website explorer that maps every user flow, captures visual evidence, and generates comprehensive QA test cases ready for TestRail.

**How it works:**

1. Give it a URL (e.g. `https://www.ebay.com`)
2. The agent launches a browser and explores like a first-time user
3. At each page it screenshots, identifies interactive elements, and decides which path to take
4. It records QA observations, classifies page types, and logs expected vs actual behavior
5. When done, it generates a full test suite with prioritized test cases, steps, expected results, and screenshot attachments
6. Outputs: markdown report (`test_cases.md`), TestRail JSON (`testrail_export.json`), interactive graph (`web/index.html`)

### 2. Mobile Cartographer (QA Agent — Android & iOS)

Same AI agent architecture as Web Cartographer, but explores **native mobile apps** on an Android emulator or iOS simulator via Appium. Taps through screens, swipes through carousels, maps every flow, and generates the same structured test suite output. Supports both platforms with a single codebase.

### 3. Release Revert Risk Advisor

AI agent that answers: "Based on our historical revert patterns, how risky is this release?"

Analyzes past rollback incidents, compares them to current release context, and provides evidence-backed risk assessments with actionable recommendations (Ship / Ramp / Hold).

---

## Quick Start

### Prerequisites

- Python 3.10+
- AWS credentials with Bedrock access (Claude model enabled)
- Datadog API key (for observability)
- Node.js (for Appium and Risk Advisor React UI)
- For mobile: Android SDK + emulator and/or Xcode + iOS simulator

### Setup

```bash
git clone https://github.com/qa-entomologist/project-skynet.git
cd project-skynet

python3 -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt
playwright install chromium

cp .env.example .env
# Edit .env with your credentials (see Environment Variables below)
```

### Run Web Cartographer

```bash
# Basic exploration
python3 run.py https://www.example.com

# With visible browser
python3 run.py https://www.ebay.com --headed

# Custom limits
python3 run.py https://www.amazon.com --max-depth 3 --max-pages 20

# With Neo4j graph storage
python3 run.py https://www.ebay.com --neo4j

# Without Datadog (for local testing)
python3 run.py https://www.example.com --no-datadog
```

**Outputs:**
- `test_cases.md` — QA test suite with steps, expected results, screenshot references
- `testrail_export.json` — TestRail-compatible import with attachment paths
- `web/graph_data.json` — exploration graph (open `web/index.html` to visualize)
- `screenshots/run_YYYYMMDD_HHMMSS/` — all captured screenshots, named sequentially

### Run Mobile Cartographer

**Additional prerequisites:** Appium server running + emulator (Android) or simulator (iOS).

```bash
# Install Appium and drivers (one-time)
npm install -g appium
appium driver install uiautomator2   # Android
appium driver install xcuitest        # iOS

# Start Appium server (separate terminal)
appium
```

**Android:**
```bash
# Start emulator (via Android Studio or CLI)
emulator -avd Pixel_6_API_34 &

# Explore an APK
python3 run_mobile.py path/to/app.apk

# Or an already-installed app
python3 run_mobile.py --package com.tubi.tv
```

**iOS:**
```bash
# Start simulator (via Xcode or CLI)
open -a Simulator

# Explore a .app file (simulator build)
python3 run_mobile.py path/to/TubiTV.app --platform ios

# Or an already-installed app
python3 run_mobile.py --bundle-id com.tubi.tv --platform ios
```

**Common options:**
```bash
python3 run_mobile.py app.apk --max-pages 30 --max-depth 4
python3 run_mobile.py --package com.tubi.tv --appium-url http://localhost:4723
```

**Outputs:**
- `test_cases_mobile.md` — QA test suite with mobile-specific steps and screenshot references
- `testrail_export_mobile.json` — TestRail-compatible import
- `screenshots/mobile_{platform}_run_YYYYMMDD_HHMMSS/` — all captured screenshots

### Run Release Revert Risk Advisor

```bash
# Start the API server
python3 run_risk_advisor.py --server --port 8000

# In another terminal, start the React UI
cd ui && npm install && npm start
# Opens http://localhost:3000

# Or use CLI mode directly
python3 run_risk_advisor.py --feature "playback-buffer-v2" --service "playback-service" --platform "ios"
```

---

## Environment Variables

Create a `.env` file (see `.env.example`):

```bash
# AWS Bedrock (required)
AWS_PROFILE=your-profile-name        # If using AWS SSO
AWS_DEFAULT_REGION=us-west-2
# Or use explicit keys:
# AWS_ACCESS_KEY_ID=...
# AWS_SECRET_ACCESS_KEY=...

# Datadog (required for observability, Risk Advisor)
DD_API_KEY=your_datadog_api_key
DD_APP_KEY=your_datadog_app_key      # For Risk Advisor
DD_SITE=datadoghq.com                # us3.datadoghq.com, datadoghq.eu, etc.

# Neo4j (optional — falls back to in-memory graph)
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=password

# Web Cartographer limits (optional)
MAX_DEPTH=5
MAX_PAGES=50
HEADLESS=true

# Risk Advisor (optional)
AGENT_ENV=demo
REVERT_HISTORY_PATH=data/revert_history.yaml
```

### AWS SSO Login

```bash
aws sso login --profile your-profile-name
```

---

## Datadog LLM Observability

Both agents ship traces to Datadog automatically when `DD_API_KEY` is set.

**Web Cartographer traces include:**
- Agent reasoning chains
- Tool call latencies (navigate, scan, click, go_back)
- Token usage per exploration cycle
- End-to-end exploration performance

**Risk Advisor metrics include:**
- `agent.run.count`, `agent.run.latency_ms`
- `agent.risk_score`, `agent.recommendation`
- Datadog query counts, structured logs

**To view traces:**
1. Open Datadog → APM → Traces
2. Filter by service: `strands-agent`
3. Look for LLM traces with tool calls, token counts, latency

### Push Test Results to Datadog

After running an exploration, push the generated test cases to Datadog for tracking and dashboarding:

```bash
# Push to both CI Test Visibility + Logs
python3 push_to_datadog.py

# CI Test Visibility only (JUnit XML upload)
python3 push_to_datadog.py --ci-only

# Structured Logs only (for custom dashboards)
python3 push_to_datadog.py --logs-only

# Use mobile test results
python3 push_to_datadog.py --input testrail_export_mobile.json
```

**What you get:**

| Datadog Feature | What It Shows |
|----------------|---------------|
| **CI Test Visibility** | Per-test pass/pending status, duration, history across runs |
| **Logs** | Test case details with priority, type, step count, screenshot count |
| **Dashboard** | Coverage by feature area, priority distribution, agent performance |

View results at:
- CI Test Visibility: `https://app.datadoghq.com/ci/test-services`
- Logs: `https://app.datadoghq.com/logs?query=service:project-skynet`

**Troubleshooting:**
```bash
# Verify API key is set
python3 -c "from src.config import DD_API_KEY; print('SET' if DD_API_KEY else 'NOT SET')"

# Check OTLP endpoint
python3 -c "from src.config import get_otlp_endpoint; print(get_otlp_endpoint())"
```

---

## Neo4j (Optional)

For persistent graph storage and Cypher querying:

```bash
# Start Neo4j
docker run -d --name neo4j \
  -p 7474:7474 -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/password \
  neo4j:latest

# Run with Neo4j flag
python3 run.py https://www.ebay.com --neo4j

# Browse at http://localhost:7474
```

Example Cypher queries:
```cypher
MATCH (p:Page) RETURN p.url, p.title, p.depth LIMIT 50;

MATCH path = (start:Page)-[:ACTION*]->(end:Page)
WHERE start.depth = 0
RETURN path LIMIT 10;
```

---

## Architecture

### Web Cartographer

```
┌──────────────────────────────────────────────────┐
│  Strands Agent (Claude via Amazon Bedrock)        │
│                                                   │
│  Tools:                                           │
│  ├── navigate_to_url       Go to a page           │
│  ├── scan_page             Screenshot + classify  │
│  ├── click_element         Before/after capture   │
│  ├── go_back               Smart back navigation  │
│  ├── generate_test_cases   Extract flows          │
│  ├── write_test_report     Markdown test suite    │
│  └── export_testrail_json  TestRail import file   │
├──────────────────────────────────────────────────┤
│  Browser (Playwright subprocess)                  │
│  Graph Store (Neo4j / In-Memory)                  │
│  Datadog LLM Observability (OpenTelemetry)        │
└──────────────────────────────────────────────────┘
```

### Mobile Cartographer

```
┌──────────────────────────────────────────────────┐
│  Strands Agent (Claude via Amazon Bedrock)        │
│                                                   │
│  Tools:                                           │
│  ├── scan_screen           Screenshot + UI tree   │
│  ├── tap_element           Before/after capture   │
│  ├── swipe_screen          Scroll / carousel      │
│  ├── press_back            Back (system / swipe)  │
│  ├── type_text             Keyboard input         │
│  ├── generate_test_cases   Extract flows          │
│  ├── write_test_report     Markdown test suite    │
│  └── export_testrail_json  TestRail import file   │
├──────────────────────────────────────────────────┤
│  Appium (unified driver)                          │
│  ├── Android: UiAutomator2 + emulator             │
│  └── iOS:     XCUITest + simulator                │
│  Graph Store (shared with Web Cartographer)        │
│  Datadog LLM Observability (OpenTelemetry)        │
└──────────────────────────────────────────────────┘
```

### Risk Advisor

```
┌──────────────────────────────────────────────────┐
│  Agent Orchestrator                               │
│  ├── Fetch historical reverts (Datadog/YAML)      │
│  ├── Build failure signatures                     │
│  ├── Compute risk score (similarity + volatility) │
│  └── Generate report (Bedrock)                    │
├──────────────────────────────────────────────────┤
│  Flask API → React Dashboard                      │
│  Datadog custom metrics + structured logs         │
└──────────────────────────────────────────────────┘
```

---

## Project Structure

```
project-skynet/
├── run.py                    # Web Cartographer CLI
├── run_mobile.py             # Mobile Cartographer CLI
├── push_to_datadog.py        # Push results to DD CI + Logs
├── run_risk_advisor.py       # Risk Advisor CLI
├── run_all.py                # Unified entry point
├── requirements.txt
├── .env.example
├── CHANGELOG.md              # ← Must be updated on every commit
├── CONTRIBUTING.md           # Contribution rules
│
├── src/                      # Web Cartographer
│   ├── agent.py              # Strands Agent + tools + system prompt
│   ├── _pw_helper.py         # Playwright subprocess
│   ├── browser_manager.py    # Browser IPC wrapper
│   ├── mobile_manager.py     # Appium wrapper
│   ├── mobile_agent.py       # Mobile agent + tools
│   ├── graph_store.py        # Neo4j + in-memory graph
│   └── config.py
│
├── agent/                    # Release Revert Risk Advisor
│   ├── main.py               # Orchestrator
│   ├── datadog_client.py     # Datadog API
│   ├── risk_model.py         # Scoring engine
│   ├── bedrock_summarizer.py # Report generation
│   └── observability.py      # Self-instrumentation
│
├── server/app.py             # Risk Advisor API
├── ui/                       # Risk Advisor React UI
├── data/                     # Historical revert data
├── web/index.html            # Graph visualization
├── screenshots/              # Captured screenshots per run
├── test_cases.md             # Generated QA test suite (web)
├── test_cases_mobile.md      # Generated QA test suite (mobile)
├── testrail_export.json      # TestRail import file (web)
└── testrail_export_mobile.json # TestRail import file (mobile)
```

---

## API Endpoints (Risk Advisor)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/assess` | Run a risk assessment |
| GET | `/api/runs` | List past assessment runs |
| GET | `/api/runs/{id}` | Get a specific run |
| GET | `/api/telemetry` | Agent observability data |
| GET | `/api/services` | Available services |
| GET | `/api/health` | Health check |

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `Browser helper failed to start` | Run `playwright install chromium` |
| `Token has expired` | Run `aws sso login` |
| `on-demand throughput isn't supported` | Use `claude-3-5-sonnet-v2` model ID (not Claude 4) |
| No Datadog traces | Check `DD_API_KEY` in `.env`, wait 1-2 min |
| Neo4j connection failed | `docker ps \| grep neo4j`, check `.env` credentials |
| SPA clicks don't navigate | Agent detects DOM changes; increase wait times in `_pw_helper.py` |
| `Appium connection refused` | Start Appium server: `appium`. Start emulator/simulator first. |
| `Could not locate element` | UI may have changed; agent will retry with fresh `scan_screen` |
| iOS: `xcodebuild failed` | Ensure Xcode CLI tools installed: `xcode-select --install` |
| iOS: no simulator | Open Xcode > Window > Devices and Simulators, or `open -a Simulator` |

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Key rules:

1. **Update `CHANGELOG.md`** on every commit — no exceptions
2. **Pull before push** — always
3. **AI agents must follow the same rules**
