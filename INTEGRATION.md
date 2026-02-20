# Integration Guide

This document explains how the two agents (Web Cartographer and Release Revert Risk Advisor) are integrated into a single repository.

## Architecture Overview

Both agents are designed to work independently but share common infrastructure:

- **Datadog Observability**: Both agents send telemetry to Datadog
- **AWS Bedrock**: Both use Claude via Bedrock for LLM capabilities
- **Python Environment**: Shared virtual environment with all dependencies

## Directory Structure

```
project-skynet/
├── src/              # Web Cartographer agent
├── agent/            # Release Revert Risk Advisor agent
├── server/           # Risk Advisor FastAPI server
├── ui/               # Risk Advisor React UI
├── data/             # Risk Advisor historical data
├── web/              # Web Cartographer visualization
└── evals/            # Risk Advisor run outputs
```

## Running the Agents

### Option 1: Unified Entry Point

```bash
# Web Cartographer
python run_all.py web-cartographer https://www.ebay.com --headed

# Risk Advisor (CLI)
python run_all.py risk-advisor --feature "my-feature" --service "playback-service"

# Risk Advisor (Server + UI)
python run_all.py risk-advisor --server
```

### Option 2: Direct Scripts

```bash
# Web Cartographer
python run.py https://www.ebay.com

# Risk Advisor
python run_risk_advisor.py --feature "my-feature" --service "playback-service"
python run_risk_advisor.py --server
```

## Shared Configuration

Both agents use the same `.env` file for configuration:

```bash
# Required for both
DD_API_KEY=your_datadog_api_key
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=your_aws_access_key
AWS_SECRET_ACCESS_KEY=your_aws_secret_key
BEDROCK_MODEL_ID=anthropic.claude-3-sonnet-20240229-v1:0

# Risk Advisor specific
DD_APP_KEY=your_datadog_app_key
AGENT_ENV=demo
REVERT_HISTORY_PATH=data/revert_history.yaml

# Web Cartographer specific
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=password
```

## Datadog Integration

### Web Cartographer
- Sends LLM traces via OpenTelemetry
- Tracks agent reasoning, tool calls, token usage
- Endpoint: Datadog LLM Observability

### Risk Advisor
- Sends custom metrics for agent runs
- Tracks risk scores, recommendations, query counts
- Uses Datadog Events and Metrics APIs
- Endpoint: Datadog APM

Both agents can run simultaneously and will send their telemetry to the same Datadog account.

## Development Workflow

1. **Setup once**:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   playwright install chromium
   ```

2. **Run Web Cartographer**:
   ```bash
   python run.py https://www.example.com
   ```

3. **Run Risk Advisor**:
   ```bash
   python run_risk_advisor.py --server
   # Open http://localhost:8000
   ```

4. **View Observability**:
   - Both agents send data to Datadog
   - Check Datadog dashboard for traces and metrics

## Future Integration Ideas

Potential ways to connect the two agents:

1. **Risk Assessment for Web Changes**: Use Web Cartographer to map a site, then assess deployment risk
2. **Shared Graph Store**: Store both website graphs and release dependency graphs in Neo4j
3. **Unified Dashboard**: Combine both agents' visualizations in a single UI
4. **Cross-Agent Insights**: Use website exploration to inform release risk assessment

## Troubleshooting

### Import Errors
Make sure you're in the virtual environment:
```bash
source .venv/bin/activate
```

### Datadog Connection Issues
- Verify `DD_API_KEY` is set in `.env`
- Check Datadog site matches your account (`datadoghq.com`, `us3.datadoghq.com`, etc.)

### Bedrock Access
- Ensure AWS credentials are configured
- Verify Claude model is enabled in Bedrock console
- Check AWS region matches your Bedrock endpoint

### Port Conflicts
- Web Cartographer: No ports (uses browser automation)
- Risk Advisor: Default port 8000 (change with `--port`)

