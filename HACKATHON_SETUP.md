# Hackathon Setup Guide

Quick setup guide for AWS Bedrock + Datadog hackathon integration.

## ✅ Required Technologies

- ✅ **AWS Bedrock** - Already integrated
- ✅ **Datadog** - Already integrated  
- ❓ **Test Sprite** - Need clarification (see below)

## 🚀 Quick Setup

### 1. Verify Your Setup

Run the verification script:

```bash
python verify_hackathon_setup.py
```

This will check:
- AWS Bedrock configuration and access
- Datadog API keys and client setup
- All required Python dependencies
- Project structure integrity

### 2. Configure Environment Variables

Make sure your `.env` file has:

```bash
# AWS Bedrock (REQUIRED)
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=your_aws_access_key
AWS_SECRET_ACCESS_KEY=your_aws_secret_key
# OR use AWS SSO:
AWS_PROFILE=your-profile-name

BEDROCK_MODEL_ID=anthropic.claude-3-sonnet-20240229-v1:0

# Datadog (REQUIRED)
DD_API_KEY=your_datadog_api_key
DD_APP_KEY=your_datadog_app_key  # For full API access
DD_SITE=datadoghq.com  # or us3.datadoghq.com, datadoghq.eu

# Agent Configuration
AGENT_ENV=production  # or 'demo' for testing without real APIs
```

### 3. Install Dependencies

```bash
# Activate virtual environment
source .venv/bin/activate  # or .venv\Scripts\activate on Windows

# Install all dependencies
pip install -r requirements.txt
```

### 4. Enable AWS Bedrock Models

1. Go to [AWS Bedrock Console](https://console.aws.amazon.com/bedrock/)
2. Navigate to **Model access**
3. Request access to:
   - **Claude 3 Sonnet** (anthropic.claude-3-sonnet-20240229-v1:0)
   - **Claude 3.5 Sonnet** (for Web Cartographer)
4. Wait for approval (usually instant for hackathons)

### 5. Get Datadog API Keys

1. Log in to [Datadog](https://app.datadoghq.com)
2. Go to **Organization Settings** → **API Keys**
3. Create or copy an API key → Add to `.env` as `DD_API_KEY`
4. Go to **Application Keys** → Create an app key → Add to `.env` as `DD_APP_KEY`

## 🧪 Testing Your Integration

### Test AWS Bedrock

```bash
# Test Risk Advisor (uses Bedrock for report generation)
python run_risk_advisor.py --feature "test-feature" --service "playback-service" --platform "ios"
```

### Test Datadog

```bash
# Start the Risk Advisor server (sends metrics to Datadog)
python run_risk_advisor.py --server --port 8000

# In another terminal, make a request
curl -X POST http://localhost:8000/api/assess \
  -H "Content-Type: application/json" \
  -d '{
    "feature_name": "test-feature",
    "service": "playback-service",
    "platform": "ios"
  }'
```

Check Datadog dashboard for:
- Custom metrics: `agent.run.count`, `agent.risk_score`
- Logs with structured JSON

### Test Web Cartographer (Bedrock + Datadog)

```bash
# Run with Datadog observability
python run.py https://www.example.com
```

Check Datadog LLM Observability for:
- Agent reasoning traces
- Token usage
- Tool call latencies

## 📊 Current Integration Status

### ✅ AWS Bedrock Integration

**Location**: `agent/bedrock_summarizer.py`, `src/agent.py`

**Usage**:
- **Risk Advisor**: Generates natural-language risk reports using Claude
- **Web Cartographer**: Uses Claude via Strands framework for autonomous exploration

**Models Used**:
- `anthropic.claude-3-sonnet-20240229-v1:0` (Risk Advisor)
- `anthropic.claude-3-5-sonnet-20241022-v2:0` (Web Cartographer)

### ✅ Datadog Integration

**Location**: `agent/observability.py`, `agent/datadog_client.py`, `run.py`

**Features**:
- **Custom Metrics**: Agent runs, latency, risk scores, recommendations
- **Structured Logging**: JSON logs with run IDs, evidence, inputs
- **LLM Observability**: Full traces for Web Cartographer agent
- **API Integration**: Fetches historical revert events and metrics

**Metrics Sent**:
- `agent.run.count`
- `agent.run.latency_ms`
- `agent.risk_score`
- `agent.datadog_queries.count`
- `agent.revert_signatures.matched`

## ❓ Test Sprite Integration

**Question**: What is "Test Sprite" in your hackathon context?

Possible interpretations:
1. **Testing Framework**: A specific testing tool required by the hackathon
2. **Test Generation**: Automated test case generation (which Web Cartographer already does!)
3. **Sprite Testing**: Visual regression testing or screenshot comparison
4. **Typo/Autocorrect**: Could it be "Test Spire" or another tool?

**Current Test Capabilities**:
- Web Cartographer generates comprehensive QA test cases
- Risk Advisor has evaluation runs saved in `evals/`
- Both agents have demo modes for testing

**If Test Sprite is a specific tool**, please provide:
- Documentation link
- Installation instructions
- Integration requirements

I can help integrate it once we know what it is!

## 🎯 Hackathon Demo Flow

### Option 1: Risk Advisor Demo

```bash
# Terminal 1: Start server
python run_risk_advisor.py --server

# Terminal 2: Start UI (optional)
cd ui && npm start

# Make assessment requests via API or UI
```

### Option 2: Web Cartographer Demo

```bash
# Run exploration with visible browser
python run.py https://www.ebay.com --headed

# View results
open web/index.html
```

### Option 3: Both Agents

```bash
# Use unified entry point
python run_all.py risk-advisor --server
python run_all.py web-cartographer https://www.example.com
```

## 🔍 Troubleshooting

### AWS Bedrock Issues

**Error**: `AccessDeniedException` or `Model not found`
- **Fix**: Enable model access in Bedrock console
- **Fix**: Check AWS credentials are valid
- **Fix**: Verify region matches your Bedrock endpoint

**Error**: `boto3` import fails
- **Fix**: `pip install boto3`

### Datadog Issues

**Error**: `401 Unauthorized`
- **Fix**: Verify `DD_API_KEY` is correct
- **Fix**: Check `DD_SITE` matches your Datadog account

**Error**: Metrics not appearing
- **Fix**: Wait 1-2 minutes for metrics to appear
- **Fix**: Check Datadog dashboard filters
- **Fix**: Verify `AGENT_ENV` is not set to "demo"

### General Issues

**Error**: Module not found
- **Fix**: `pip install -r requirements.txt`
- **Fix**: Activate virtual environment

**Error**: Port already in use
- **Fix**: Change port: `--port 8001`
- **Fix**: Kill existing process: `lsof -ti:8000 | xargs kill`

## 📝 Next Steps

1. ✅ Run `verify_hackathon_setup.py` to check everything
2. ✅ Configure `.env` with your credentials
3. ✅ Test Bedrock and Datadog integrations
4. ❓ Clarify Test Sprite requirements
5. 🚀 Build your hackathon demo!

## 💡 Pro Tips

- Use `AGENT_ENV=demo` for testing without real API calls
- Check Datadog logs in real-time: `tail -f` or Datadog Log Explorer
- Web Cartographer screenshots are saved in `screenshots/`
- Risk Advisor runs are saved in `evals/` for review

---

**Need Help?** Check:
- `README.md` - Full project documentation
- `SETUP_GUIDE.md` - Detailed setup instructions
- `INTEGRATION.md` - Architecture overview

