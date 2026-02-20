# Fix: Python 3.14 Compatibility Issue

## The Problem

You're using Python 3.14, but `pydantic-core` only supports up to Python 3.13. This causes the build to fail.

## Solution Options

### Option 1: Use Python 3.13 or Earlier (Recommended)

**Check what Python versions you have:**
```bash
python3.13 --version
python3.12 --version
python3.11 --version
```

**Recreate venv with compatible Python:**
```bash
# Remove old venv
rm -rf .venv

# Create new venv with Python 3.13 (or 3.12, 3.11)
python3.13 -m venv .venv
# OR
python3.12 -m venv .venv
# OR  
python3.11 -m venv .venv

# Activate
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Option 2: Install Pre-built pydantic (Quick Fix)

If you must use Python 3.14, try installing pydantic from a pre-built wheel:

```bash
source .venv/bin/activate

# Upgrade pip first
pip install --upgrade pip

# Try installing pydantic with a workaround
pip install pydantic --only-binary :all:

# If that doesn't work, install other dependencies first
pip install python-dotenv fastapi uvicorn requests pyyaml datadog-api-client boto3

# Then try pydantic again
pip install pydantic==2.10.4
```

### Option 3: Use System Python 3.13 (If Available)

**Check if Homebrew has Python 3.13:**
```bash
brew list | grep python
```

**Install Python 3.13 if needed:**
```bash
brew install python@3.13
```

**Then use it:**
```bash
python3.13 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Quick Fix for Demo (Skip pydantic if not critical)

If you just need to run the auto-QA workflow and pydantic isn't critical:

```bash
source .venv/bin/activate

# Install essentials (skip pydantic for now)
pip install python-dotenv requests pyyaml datadog-api-client boto3

# Try running (may work without pydantic for basic functionality)
python3 run_risk_advisor.py --auto-qa --service "playback-service"
```

## Recommended: Use Python 3.13

**Best approach for your demo:**

```bash
# 1. Remove old venv
rm -rf .venv

# 2. Create with Python 3.13
python3.13 -m venv .venv

# 3. Activate
source .venv/bin/activate

# 4. Install
pip install -r requirements.txt

# 5. Run
python3 run_risk_advisor.py --auto-qa --service "playback-service"
```

## Check Your Python Version

```bash
python3 --version
```

If it shows 3.14, you need to use a different version.

