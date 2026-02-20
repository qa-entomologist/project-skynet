# Auto-QA Feature: Automatic Crash Detection & Reproducibility Testing

## Overview

The Release Revert Risk Advisor now includes an **Auto-QA Workflow** that automatically:

1. **Detects crashes and anomalies** from Datadog in real-time
2. **Analyzes code** using AWS Bedrock to determine if crashes are reproducible
3. **Tests reproduction** in alpha/production environments
4. **Generates QA reports** with actionable recommendations

This eliminates the manual step where QA engineers are first contacted to check if crashes are reproducible.

## How It Works

### Workflow Steps

```
Datadog Anomaly Detected
    ↓
Fetch Crash Details & Recent Deployments
    ↓
Analyze Code with Bedrock (Is it reproducible?)
    ↓
If Reproducible → Test in Alpha/Production
    ↓
Generate QA Report with Recommendation
```

### Components

1. **`agent/anomaly_detector.py`**
   - Monitors Datadog for crashes, anomalies, and error spikes
   - Fetches detailed crash information
   - Identifies recent deployments that might be related

2. **`agent/code_analyzer.py`**
   - Uses AWS Bedrock to analyze code changes
   - Determines if crash is likely reproducible based on code
   - Identifies root cause and affected files
   - Generates reproduction steps

3. **`agent/reproduction_tester.py`**
   - Executes reproduction steps in target environment
   - Tests in alpha or production
   - Captures evidence (screenshots, logs, metrics)
   - Verifies if crash actually occurs

4. **`agent/auto_qa_workflow.py`**
   - Orchestrates the complete workflow
   - Ties all components together
   - Generates comprehensive QA reports

## Usage

### CLI

```bash
# Run auto-QA workflow
python run_risk_advisor.py --auto-qa \
  --service "playback-service" \
  --platform "ios" \
  --lookback-minutes 15 \
  --test-environment alpha \
  --code-repo-path /path/to/repo
```

### API

```bash
# POST to auto-QA endpoint
curl -X POST http://localhost:8000/api/auto-qa \
  -H "Content-Type: application/json" \
  -d '{
    "service": "playback-service",
    "platform": "ios",
    "lookback_minutes": 15,
    "test_environment": "alpha",
    "code_repo_path": "/path/to/repo"
  }'
```

### Python

```python
from agent.auto_qa_workflow import run_auto_qa_workflow

result = run_auto_qa_workflow(
    service="playback-service",
    platform="ios",
    lookback_minutes=15,
    test_environment="alpha",
    code_repo_path="/path/to/repo",
)

print(f"Anomalies detected: {result['anomalies_detected']}")
print(f"Crashes processed: {result['crashes_processed']}")
```

## Response Format

```json
{
  "run_id": "abc123",
  "timestamp": "2024-02-20T...",
  "status": "completed",
  "service": "playback-service",
  "anomalies_detected": 2,
  "crashes_processed": 2,
  "results": [
    {
      "crash_id": "crash_001",
      "status": "processed",
      "code_analysis": {
        "is_reproducible": true,
        "confidence": 0.85,
        "likely_cause": "Null pointer exception in playback buffer",
        "affected_files": ["PlaybackService.java", "BufferManager.java"],
        "reproduction_steps": [
          "1. Navigate to video playback page",
          "2. Start playback with empty buffer",
          "3. Crash occurs when buffer.process() is called"
        ]
      },
      "reproduction_test": {
        "reproduced": true,
        "test_duration_seconds": 12.5,
        "error_encountered": "NullPointerException in playback buffer",
        "environment": "alpha"
      },
      "qa_recommendation": "✅ CONFIRMED REPRODUCIBLE - Block release and fix..."
    }
  ],
  "summary": {
    "overall_risk_score": 80,
    "recommendation": "BLOCK_RELEASE",
    "total_crashes": 2,
    "reproduced": 1,
    "not_reproducible": 0,
    "needs_manual_qa": 1
  }
}
```

## QA Recommendations

The workflow generates one of these recommendations:

- **✅ CONFIRMED REPRODUCIBLE**: Crash successfully reproduced → Block release
- **⚠️ LIKELY REPRODUCIBLE**: High confidence but not reproduced → Manual QA needed
- **⚠️ POSSIBLY REPRODUCIBLE**: Moderate confidence → Manual investigation
- **ℹ️ UNCLEAR**: Low confidence → Monitor and investigate if rate increases

## Integration with Existing Workflow

The auto-QA workflow integrates seamlessly with the existing Risk Advisor:

1. **When anomaly detected** → Auto-QA runs automatically
2. **If reproducible** → Risk score increases, recommendation changes to "HOLD"
3. **QA report** → Included in risk assessment evidence

## Configuration

Add to `.env`:

```bash
# Optional: Path to code repository for analysis
CODE_REPO_PATH=/path/to/your/repo

# Optional: Test environment URLs
ALPHA_BASE_URL=https://alpha.example.com
PRODUCTION_BASE_URL=https://example.com
```

## Demo Mode

In demo mode (`AGENT_ENV=demo`), the workflow:
- Generates synthetic anomalies
- Uses demo code analysis
- Simulates reproduction tests

Perfect for testing without real Datadog/Bedrock access.

## Next Steps

To make this production-ready:

1. **Real-time monitoring**: Set up Datadog webhooks to trigger auto-QA on anomalies
2. **Git integration**: Connect to your Git provider to fetch code changes
3. **Enhanced testing**: Add support for mobile app testing, API testing, etc.
4. **Notification**: Send results to Slack/PagerDuty when crashes are confirmed

## Example Use Case

**Scenario**: Crash detected in production

1. **Before**: 
   - Datadog alerts QA team
   - QA manually checks if reproducible
   - Takes 30-60 minutes

2. **After**:
   - Auto-QA detects crash automatically
   - Analyzes code in 30 seconds
   - Tests reproduction in 1-2 minutes
   - Generates report: "✅ CONFIRMED REPRODUCIBLE - Block release"
   - **Total time: < 3 minutes**

## Files Added

- `agent/anomaly_detector.py` - Datadog anomaly detection
- `agent/code_analyzer.py` - Bedrock code analysis
- `agent/reproduction_tester.py` - Automated testing
- `agent/auto_qa_workflow.py` - Main workflow orchestrator

## Files Modified

- `server/app.py` - Added `/api/auto-qa` endpoint
- `run_risk_advisor.py` - Added `--auto-qa` CLI command

