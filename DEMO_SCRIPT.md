# Demo Script: Showing Crash Detection from Datadog

## Demo Flow

### Step 1: Show the Mock Server (Represents Datadog)

**What to say:**
> "This mock server represents Datadog's API. In production, this would be your actual Datadog account monitoring your services in real-time."

**What to show:**
```bash
# Terminal 1: Show mock server running
python3 mock_datadog_server.py --port 8080
```

**Show the crashes available:**
```bash
# Terminal 2: Show what Datadog has detected
curl "http://localhost:8080/api/v1/events?start=0&end=$(date +%s)" | python3 -m json.tool
```

**Point out:**
- "Here we can see 3 crashes detected in the last few minutes"
- "These are coming from Datadog's Events API"
- "Each crash has details: error message, service, platform, severity"

### Step 2: Show the Auto-QA Workflow Detecting Crashes

**What to say:**
> "Now let's run our Auto-QA agent. It will automatically query Datadog, detect these crashes, analyze the code, and test if they're reproducible."

**What to show:**
```bash
python3 run_risk_advisor.py --auto-qa \
  --service "playback-service" \
  --platform "ios" \
  --lookback-minutes 15
```

**What happens:**
1. Agent connects to "Datadog" (mock server)
2. Queries for anomalies/crashes
3. Finds the 3 crashes
4. Analyzes code with Bedrock
5. Tests reproduction
6. Generates QA report

### Step 3: Show the Results

**What to point out:**
- "The agent detected 3 crashes from Datadog"
- "It analyzed the code and determined crash_001 is reproducible"
- "It automatically tested it and confirmed the crash"
- "Generated a QA report recommending to block the release"

## Talking Points

### Option A: Using Mock Server (Recommended for Demo)

**Say:**
> "For this demo, we're using a mock Datadog API server that simulates what your production Datadog account would see. The mock server accepts real API keys and returns realistic crash data, allowing us to demonstrate the full workflow consistently."

**Show:**
1. Mock server running (represents Datadog)
2. Crashes available in "Datadog"
3. Agent querying "Datadog" and detecting crashes
4. Full workflow executing

### Option B: Using Real Datadog (If You Have Crash Data)

**Say:**
> "In production, this connects directly to your Datadog account. Let me show you real crashes from our monitoring."

**Configuration:**
```bash
# In .env - remove or comment out DD_MOCK_SERVER
# DD_MOCK_SERVER=http://localhost:8080  # Commented out

# Use real Datadog
DD_API_KEY=your_real_key
DD_APP_KEY=your_real_key
AGENT_ENV=production
```

**Show:**
1. Real Datadog dashboard with crashes
2. Agent connecting to real Datadog
3. Detecting real crashes
4. Analyzing and testing

## Visual Demo Flow

```
1. Show "Datadog" (mock server)
   └─> curl shows 3 crashes detected

2. Run Auto-QA Agent
   └─> "Connecting to Datadog..."
   └─> "Detected 3 anomalies"
   └─> "Analyzing code..."
   └─> "Testing reproduction..."
   └─> "Generated QA report"

3. Show Results
   └─> "Crash crash_001: CONFIRMED REPRODUCIBLE"
   └─> "Recommendation: BLOCK RELEASE"
```

## Key Points to Emphasize

1. **"Automatic Detection"**: "As soon as Datadog detects a crash, our agent automatically picks it up"

2. **"No Manual Intervention"**: "QA doesn't need to be manually notified - the agent handles it"

3. **"Code Analysis"**: "The agent uses AWS Bedrock to analyze code changes and determine if the crash is reproducible"

4. **"Automated Testing"**: "It automatically tests the crash in alpha/production to confirm"

5. **"Actionable Report"**: "Generates a clear QA report with recommendations"

## Demo Checklist

- [ ] Mock server running (Terminal 1)
- [ ] Show crashes in "Datadog" (curl command)
- [ ] .env configured with API keys
- [ ] Run auto-QA workflow (Terminal 2)
- [ ] Show detection of crashes
- [ ] Show code analysis results
- [ ] Show reproduction test results
- [ ] Show final QA report

## Quick Demo Commands

```bash
# Terminal 1: Mock Datadog
python3 mock_datadog_server.py --port 8080

# Terminal 2: Show crashes
curl "http://localhost:8080/api/v1/events?start=0&end=$(date +%s)" | python3 -m json.tool

# Terminal 3: Run agent
python3 run_risk_advisor.py --auto-qa --service "playback-service"
```

