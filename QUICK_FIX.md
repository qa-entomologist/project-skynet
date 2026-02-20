# Quick Fix: ModuleNotFoundError

## The Problem

You're seeing `ModuleNotFoundError: No module named 'dotenv'` because:
1. Virtual environment is not activated
2. Dependencies are not installed

## The Solution

### Step 1: Create Virtual Environment (if needed)

```bash
cd /Users/kjayadevan/project-skynet
python3 -m venv .venv
```

### Step 2: Activate Virtual Environment

```bash
source .venv/bin/activate
```

You should see `(.venv)` in your terminal prompt.

### Step 3: Install Dependencies

```bash
pip install -r requirements.txt
```

Or install just the essentials:
```bash
pip install python-dotenv fastapi uvicorn pydantic requests pyyaml datadog-api-client boto3
```

### Step 4: Run the Command

Now with venv activated:
```bash
python3 run_risk_advisor.py --auto-qa --service "playback-service" --platform "ios"
```

## For Your Demo

**Always activate the virtual environment first:**

```bash
# Terminal 1: Mock server (no venv needed)
python3 mock_datadog_server.py --port 8080

# Terminal 2: Agent (venv required)
cd /Users/kjayadevan/project-skynet
source .venv/bin/activate
python3 run_risk_advisor.py --auto-qa --service "playback-service"
```

## Quick Check

To verify venv is active:
```bash
which python3
# Should show: /Users/kjayadevan/project-skynet/.venv/bin/python3
```

If it shows system Python, activate venv again.

