# Why "No Anomalies Detected"?

## The Problem

You're seeing "No anomalies detected" because the agent is running in **demo mode**, which only returns anomalies 30% of the time (random chance).

## Where is the Agent Running?

The Auto-QA agent is:
- **NOT testing a website** - It's monitoring a service (playback-service)
- **Querying Datadog** (or mock server) for crash metrics and events
- **Not actually testing a website** - It's analyzing crash data from monitoring

## How to Fix: Use Mock Server

### Step 1: Check Your .env

Make sure your `.env` has:

```bash
# Required: Set API key (even placeholder works)
DD_API_KEY=your_key_here

# Required: Point to mock server
DD_MOCK_SERVER=http://localhost:8080

# Required: Use production mode (NOT "demo")
AGENT_ENV=production
```

**The key issue:** If `AGENT_ENV=demo` or `DD_API_KEY` is empty, it uses demo mode which randomly returns no anomalies.

### Step 2: Start Mock Server

```bash
# Terminal 1
python3 mock_datadog_server.py --port 8080
```

### Step 3: Run Agent

```bash
# Terminal 2 (with venv activated)
source .venv/bin/activate
python3 run_risk_advisor.py --auto-qa --service "playback-service"
```

## What Environment/Website is Being Tested?

**Important:** The agent is NOT testing a website. It's:

1. **Monitoring Datadog** for crash metrics and events
   - Source: Mock server at `localhost:8080` (represents Datadog)
   - Service: `playback-service` (a backend service, not a website)

2. **Testing in Alpha Environment**
   - Environment: `alpha` (test environment)
   - Platform: `ios` (iOS mobile app)
   - Service: `playback-service` (video playback backend service)

3. **Reproduction Testing**
   - When it says "Navigate to video playback page" - this is in the iOS app
   - When it says "Start playback" - this is testing the playback service API
   - It's NOT testing a website URL

## For Your Demo

**Say:**
> "The agent is monitoring Datadog for crashes in the playback-service. When a crash is detected, it analyzes the code and tests if it's reproducible in the alpha environment. This is a backend service, not a website - it's the video playback service that powers our mobile app."

## Quick Fix

1. **Set in .env:**
   ```bash
   DD_API_KEY=demo_key
   DD_MOCK_SERVER=http://localhost:8080
   AGENT_ENV=production
   ```

2. **Start mock server:**
   ```bash
   python3 mock_datadog_server.py --port 8080
   ```

3. **Run agent:**
   ```bash
   python3 run_risk_advisor.py --auto-qa --service "playback-service"
   ```

Now it should detect the 3 crashes from the mock server!

