"""Configuration for the Release Revert Risk Advisor agent."""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ── Paths ──
BASE_DIR = Path(__file__).resolve().parent.parent
REVERT_HISTORY_PATH = os.getenv(
    "REVERT_HISTORY_PATH",
    str(BASE_DIR / "data" / "revert_history.yaml"),
)
EVALS_DIR = BASE_DIR / "evals"

# ── Datadog ──
DD_API_KEY = os.getenv("DD_API_KEY", "")
DD_APP_KEY = os.getenv("DD_APP_KEY", "")
DD_SITE = os.getenv("DD_SITE", "datadoghq.com")

# ── AWS Bedrock ──
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
BEDROCK_MODEL_ID = os.getenv(
    "BEDROCK_MODEL_ID",
    "anthropic.claude-3-sonnet-20240229-v1:0",
)

# ── Agent defaults ──
DEFAULT_HISTORY_WINDOW_DAYS = 30
DEFAULT_POST_DEPLOY_MINUTES = 60
AGENT_ENV = os.getenv("AGENT_ENV", "demo")

# ── Risk model weights ──
WEIGHT_SIMILARITY = 50   # similarity to rollback signature (0-50)
WEIGHT_VOLATILITY = 30   # volatility of relevant SLIs   (0-30)
WEIGHT_ANOMALY = 20      # current anomaly presence       (0-20)

# ── SLI definitions ──
KEY_SLIS = [
    "error_rate",
    "crash_rate",
    "p95_latency",
    "p99_latency",
    "playback_start_failures",
    "ad_error_rate",
]

