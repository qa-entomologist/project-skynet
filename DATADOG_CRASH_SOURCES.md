# Datadog Crash Detection - Data Sources

## Current Implementation

The anomaly detector gets crash details from **3 Datadog APIs**:

### 1. **Metrics API** - Detects Crash Rate Spikes
**Location**: `_detect_anomalies_live()` lines 108-168

**What it does**:
- Queries `crash_rate` and `error_rate` metrics for a service
- Compares current values to 7-day baseline
- Flags anomalies if > 2 standard deviations above baseline

**API Call**:
```python
metrics_api.query_metrics(
    query=f"avg:crash_rate{{service:{service}}}",
    _from=start_time,
    to=now
)
```

**What you get**:
- Current crash rate value
- Baseline average
- Spike ratio
- Severity (critical/high/medium)

**For Demo**: This works if you have `crash_rate` metric in Datadog

---

### 2. **Events API** - Gets Crash Events
**Location**: `_detect_anomalies_live()` lines 170-192 and `_fetch_crash_details_live()` lines 234-251

**What it does**:
- Searches for events with sources: `"error,crash,exception"`
- Filters by service tag
- Extracts crash information from event text

**API Call**:
```python
events_api.list_events(
    start=start_time,
    end=now,
    tags=f"service:{service}",
    sources="error,crash,exception"
)
```

**What you get**:
- Event ID
- Timestamp
- Event text (description)
- Tags (platform, feature, etc.)

**For Demo**: This works if you're sending crash events to Datadog Events API

---

### 3. **Logs API** - Detailed Crash Logs (Currently Not Fully Implemented)
**Location**: `_fetch_crash_details_live()` lines 223-228

**Current Status**: 
- LogsApi is imported but not used
- There's a comment: "Note: This is a simplified version - actual implementation would use Datadog Logs Search API"

**What it SHOULD do**:
- Search logs for crash/exception patterns
- Get stack traces
- Get detailed error messages
- Get user/device context

**For Demo**: This needs to be implemented for full crash details

---

## What Data Sources You Need in Datadog

For the demo to work, you need:

### Option 1: Metrics (Easiest for Demo)
- **Metric**: `crash_rate` or `error_rate`
- **Tags**: `service:your-service-name`
- **How to send**: Your app should emit this metric to Datadog

### Option 2: Events (Good for Demo)
- **Event Source**: `crash`, `error`, or `exception`
- **Tags**: `service:your-service-name`, `platform:ios`, etc.
- **How to send**: Use Datadog Events API to send crash events

### Option 3: Logs (Best for Production)
- **Logs**: Application logs with crash/exception patterns
- **Tags**: `service:your-service-name`
- **How to send**: Use Datadog Logs API or agent

---

## Demo Mode (No Real Datadog Needed)

If you don't have real Datadog data, the code has **demo mode**:

**Location**: `_detect_anomalies_demo()` and `_fetch_crash_details_demo()`

**How to enable**:
```bash
# In .env file
AGENT_ENV=demo
```

**What it does**:
- Returns synthetic crash data
- 30% chance of generating an anomaly
- Perfect for demos without real Datadog setup

---

## Recommended Improvements for Production

1. **Implement Logs Search API** for detailed crash logs:
   ```python
   # Use Logs Search API v2
   from datadog_api_client.v2.api.logs_api import LogsApi
   
   logs_api = LogsApi(api_client)
   response = logs_api.list_logs(
       body={
           "filter": {
               "query": f"service:{service} (crash OR exception)",
               "from": start_time,
               "to": now
           }
       }
   )
   ```

2. **Use RUM (Real User Monitoring)** for frontend crashes:
   - Datadog RUM API provides crash reports with stack traces
   - Better for mobile/web app crashes

3. **Use APM Traces** for backend errors:
   - Get full stack traces from APM
   - Better context for server-side crashes

---

## For Your Demo Today

### Quick Setup Options:

**Option A: Use Demo Mode** (Easiest)
```bash
# Set in .env
AGENT_ENV=demo

# Run
python run_risk_advisor.py --auto-qa --service "playback-service"
```

**Option B: Use Real Datadog** (If you have it)
1. Make sure you have:
   - `crash_rate` metric OR
   - Crash events being sent to Datadog
2. Set service tag: `service:your-service-name`
3. Run with `AGENT_ENV=production`

**Option C: Mock Datadog API** (For demo)
- Create a mock that returns sample crash data
- Point to your mock endpoint

---

## Current Data Flow

```
1. detect_anomalies()
   ↓
   Metrics API → Check crash_rate spikes
   Events API → Find crash events
   ↓
   Returns: List of anomalies

2. fetch_crash_details()
   ↓
   Events API → Get crash event details
   (Logs API → Not fully implemented yet)
   ↓
   Returns: Crash details with error messages

3. fetch_recent_deployments()
   ↓
   Events API → Find deployment events
   ↓
   Returns: Recent deployments with feature names
```

---

## What to Say in Demo

**"We detect crashes from three Datadog sources:"**

1. **Metrics API** - Monitors crash rate spikes in real-time
2. **Events API** - Captures crash events as they happen  
3. **Logs API** - (Future) Will provide detailed stack traces

**"For this demo, we're using [Demo Mode / Real Datadog] to show how the system automatically detects crashes and determines if they're reproducible."**

