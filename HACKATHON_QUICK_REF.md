# Hackathon Quick Reference Card

## 🎯 Current Status

✅ **AWS Bedrock**: Integrated in both agents
✅ **Datadog**: Full observability + API integration
❓ **Test Sprite**: Need clarification

## ⚡ Quick Commands

### Verify Setup
```bash
python verify_hackathon_setup.py
```

### Test AWS Bedrock
```bash
# Risk Advisor (uses Bedrock for reports)
python run_risk_advisor.py --feature "test" --service "playback-service"

# Web Cartographer (uses Bedrock for exploration)
python run.py https://www.example.com
```

### Test Datadog
```bash
# Start server (sends metrics to Datadog)
python run_risk_advisor.py --server

# Make API call
curl -X POST http://localhost:8000/api/assess \
  -H "Content-Type: application/json" \
  -d '{"feature_name":"test","service":"playback-service"}'
```

## 📋 Required Environment Variables

```bash
# AWS Bedrock
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=xxx
AWS_SECRET_ACCESS_KEY=xxx
BEDROCK_MODEL_ID=anthropic.claude-3-sonnet-20240229-v1:0

# Datadog
DD_API_KEY=xxx
DD_APP_KEY=xxx
DD_SITE=datadoghq.com
```

## 🔍 Where Each Tech is Used

### AWS Bedrock
- **Risk Advisor**: `agent/bedrock_summarizer.py` - Generates risk reports
- **Web Cartographer**: `src/agent.py` - Agent reasoning and decision-making

### Datadog
- **Observability**: `agent/observability.py` - Custom metrics and logs
- **API Client**: `agent/datadog_client.py` - Fetches historical data
- **LLM Traces**: `run.py` - Web Cartographer telemetry

## ❓ Test Sprite

**Please clarify**: What is "Test Sprite"?
- Is it a specific testing tool?
- A testing framework?
- Part of the hackathon requirements?

Current test capabilities:
- ✅ Web Cartographer generates QA test cases
- ✅ Risk Advisor has evaluation framework
- ✅ Both have demo modes

## 🚨 Common Issues

| Issue | Fix |
|-------|-----|
| Bedrock access denied | Enable models in AWS console |
| Datadog 401 error | Check API key in `.env` |
| Module not found | `pip install -r requirements.txt` |
| Port in use | Use `--port 8001` |

## 📊 Demo Flow

1. **Risk Advisor**: `python run_risk_advisor.py --server`
2. **Web Cartographer**: `python run.py https://example.com --headed`
3. **Check Datadog**: View metrics and logs in dashboard

