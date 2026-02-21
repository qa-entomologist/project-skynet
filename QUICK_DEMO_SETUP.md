# Quick Demo Setup - Mock Datadog API

## 🚀 3-Step Setup for Your Demo

### Step 1: Start Mock Server

```bash
# Terminal 1
python mock_datadog_server.py --port 8080
```

Keep this running during your demo.

### Step 2: Configure .env

Add to your `.env` file:

```bash
# Your real Datadog API key (for authentication)
DD_API_KEY=your_real_api_key_here
DD_APP_KEY=your_real_app_key_here

# Point to mock server
DD_MOCK_SERVER=http://localhost:8080

# Use production mode (not demo)
AGENT_ENV=production
```

### Step 3: Run Demo

```bash
# Terminal 2
python run_risk_advisor.py --auto-qa \
  --service "playback-service" \
  --platform "ios" \
  --lookback-minutes 15
```

## What You'll See

The workflow will:
1. ✅ Connect to mock server (using your real API key)
2. ✅ Detect 3 sample crashes
3. ✅ Analyze code with Bedrock
4. ✅ Test reproduction
5. ✅ Generate QA report

## Sample Output

```
🤖 Auto-QA Workflow — Automatic Crash Detection & Testing
════════════════════════════════════════════════════════════

  Status: completed
  Service: playback-service
  Anomalies Detected: 3
  Crashes Processed: 3

  📊 Summary:
     Overall Risk Score: 80/100
     Recommendation: BLOCK_RELEASE
     3 crashes processed: 1 confirmed reproducible, 0 not reproducible, 2 need manual QA

  🔍 Crash Analysis Results:

     1. Crash ID: crash_001
        Status: processed
        Reproducible: True
        Confidence: 85%
        Test Result: ✅ Reproduced
        QA Recommendation: ✅ CONFIRMED REPRODUCIBLE - Block release...
```

## Troubleshooting

**"Missing API key"**: Make sure `DD_API_KEY` is in `.env`

**"Connection refused"**: Make sure mock server is running on port 8080

**No crashes detected**: 
- Check service name: `--service "playback-service"`
- Verify `DD_MOCK_SERVER=http://localhost:8080` in `.env`
- Make sure `AGENT_ENV=production` (not "demo")

## Demo Talking Points

1. **"We're using a mock Datadog API that accepts real API keys"**
2. **"It returns realistic sample crash data for consistent demos"**
3. **"The workflow automatically detects crashes, analyzes code, and tests reproduction"**
4. **"In production, this connects directly to your Datadog account"**

## Next Steps After Demo

To use with real Datadog:
1. Remove `DD_MOCK_SERVER` from `.env`
2. Make sure you have crash metrics/events in Datadog
3. Run the same command - it will use real data

