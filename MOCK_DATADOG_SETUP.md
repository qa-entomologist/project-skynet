# Mock Datadog API Setup for Demo

## Quick Start

### 1. Start the Mock Server

```bash
# Terminal 1: Start mock Datadog server
python mock_datadog_server.py --port 8080
```

You should see:
```
🚀 Mock Datadog API Server running on http://localhost:8080
   Use this URL in your .env: DD_MOCK_SERVER=http://localhost:8080
```

### 2. Configure Your .env

Add to your `.env` file:

```bash
# Your real Datadog API key (for authentication)
DD_API_KEY=your_real_datadog_api_key_here
DD_APP_KEY=your_real_datadog_app_key_here

# Point to mock server instead of real Datadog
DD_MOCK_SERVER=http://localhost:8080

# Keep other settings
DD_SITE=datadoghq.com
AGENT_ENV=production  # Use "production" not "demo" to use mock server
```

### 3. Run Auto-QA Workflow

```bash
# Terminal 2: Run the auto-QA workflow
python run_risk_advisor.py --auto-qa \
  --service "playback-service" \
  --platform "ios" \
  --lookback-minutes 15
```

## How It Works

The mock server:
- ✅ Accepts your **real Datadog API key** for authentication
- ✅ Returns **realistic sample crash data** instead of querying real Datadog
- ✅ Mimics Datadog's API endpoints (Metrics, Events, Logs)
- ✅ Provides consistent demo data

## Sample Data Provided

### Crashes
- **crash_001**: NullPointerException in playback buffer (iOS, 5 min ago)
- **crash_002**: OutOfMemoryError in video decoder (Android, 12 min ago)
- **crash_003**: IndexOutOfBoundsException (iOS, 2 min ago)

### Deployments
- **deploy_001**: playback-buffer-v2 to production (2 hours ago)
- **deploy_002**: video-decoder-v3 to production (6 hours ago)

### Metrics
- **crash_rate**: Simulates spike from 1% baseline to 5%
- **error_rate**: Simulates spike from 2% baseline to 8%

## API Endpoints Mocked

1. **GET /api/v1/query** - Metrics API
   - Returns time series data for crash_rate, error_rate
   - Simulates baseline vs current spikes

2. **GET /api/v1/events** - Events API
   - Returns crash events and deployment events
   - Filters by service, time window, sources

3. **POST /api/v2/logs/events/search** - Logs API
   - Returns log entries matching crash patterns
   - Includes stack traces and error messages

## Customizing Sample Data

Edit `mock_datadog_server.py` to customize:

```python
# Add more crashes
SAMPLE_CRASHES.append({
    "id": "crash_004",
    "timestamp": int(time.time()),
    "service": "your-service",
    "platform": "ios",
    "error_message": "Your error message",
    ...
})

# Add more deployments
SAMPLE_DEPLOYMENTS.append({
    "id": "deploy_003",
    "timestamp": int(time.time()),
    "service": "your-service",
    "feature": "your-feature",
    ...
})
```

## Troubleshooting

### Server won't start
```bash
# Check if port is in use
lsof -i :8080

# Use different port
python mock_datadog_server.py --port 8081
# Then update .env: DD_MOCK_SERVER=http://localhost:8081
```

### "Missing API key" error
- Make sure `DD_API_KEY` is set in `.env`
- The mock server validates the API key (uses your real key)

### No crashes detected
- Check that mock server is running
- Verify `DD_MOCK_SERVER` is set in `.env`
- Make sure `AGENT_ENV=production` (not "demo")
- Check service name matches: `--service "playback-service"`

## For Your Demo

**Talking Points:**
- "We're using a mock Datadog API server that accepts real API keys but returns sample data"
- "This allows us to demo the full workflow without needing real crash data in production"
- "The mock server mimics Datadog's Metrics, Events, and Logs APIs"
- "In production, this would connect directly to your Datadog account"

**Demo Flow:**
1. Show mock server running: `python mock_datadog_server.py`
2. Show .env with real API key + mock server URL
3. Run auto-QA workflow
4. Show it detecting crashes from mock server
5. Show code analysis and reproduction testing

## Switching Back to Real Datadog

Just remove or comment out `DD_MOCK_SERVER` in `.env`:

```bash
# DD_MOCK_SERVER=http://localhost:8080  # Commented out
```

The agent will automatically use real Datadog APIs.

