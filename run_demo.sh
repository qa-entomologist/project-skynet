#!/usr/bin/env bash
# =============================================================
#  QA Entomologist — Full Demo Script
#  Runs all 3 acts simultaneously:
#    1. Dashboard (background)
#    2. Mock Datadog with delayed crash (background)
#    3. Web Agent exploring tubi.tv (foreground, visible browser)
#    4. Auto-QA crash detection (triggered after delay)
# =============================================================

set -e

CRASH_DELAY=${1:-45}
TARGET_URL=${2:-https://www.tubi.tv}
DASHBOARD_PORT=8081
MOCK_DD_PORT=9090

echo "============================================================"
echo "  QA Entomologist — Demo Mode"
echo "  Target:       $TARGET_URL"
echo "  Crash delay:  ${CRASH_DELAY}s"
echo "  Dashboard:    http://localhost:$DASHBOARD_PORT/web/index.html"
echo "============================================================"
echo ""

cd "$(dirname "$0")"
source .venv/bin/activate

# Clear previous run data so dashboard starts fresh
echo "[0/4] Clearing previous data..."
rm -f test_cases.md test_cases_mobile.md
rm -f testrail_export.json testrail_export_mobile.json
rm -f web/graph_data.json web/auto_qa_report.json
echo '{"nodes":[],"edges":[]}' > web/graph_data.json

cleanup() {
    echo ""
    echo "Shutting down demo..."
    kill $DASH_PID $MOCK_PID $QA_PID 2>/dev/null
    exit 0
}
trap cleanup SIGINT SIGTERM

# 1. Start dashboard server
echo "[1/4] Starting dashboard on port $DASHBOARD_PORT..."
python3 -m http.server $DASHBOARD_PORT --bind 127.0.0.1 > /dev/null 2>&1 &
DASH_PID=$!

# 2. Start mock Datadog with crash delay
echo "[2/4] Starting mock Datadog on port $MOCK_DD_PORT (crash in ${CRASH_DELAY}s)..."
python3 mock_datadog_server.py --port $MOCK_DD_PORT --delay $CRASH_DELAY > /dev/null 2>&1 &
MOCK_PID=$!

sleep 1
open "http://localhost:$DASHBOARD_PORT/web/index.html"

# 3. Start auto-QA poller in background (polls every 10s, picks up crash after delay)
echo "[3/4] Starting anomaly monitor (will detect crash after ${CRASH_DELAY}s)..."
(
    sleep $((CRASH_DELAY + 5))
    echo ""
    echo "*** CRASH DETECTED — Running Auto-QA Workflow ***"
    echo ""
    DD_MOCK_SERVER=http://localhost:$MOCK_DD_PORT python3 run_risk_advisor.py --auto-qa --service playback-service
) &
QA_PID=$!

# 4. Run web agent (foreground — visible browser)
echo "[4/4] Launching web agent on $TARGET_URL (headed browser)..."
echo ""
export HEADLESS=false
python3 run.py "$TARGET_URL" --headed --viz-port $((DASHBOARD_PORT + 1)) --no-viz

echo ""
echo "Web exploration complete. Waiting for anomaly detection..."
wait $QA_PID 2>/dev/null

echo ""
echo "============================================================"
echo "  Demo complete!"
echo "  Dashboard: http://localhost:$DASHBOARD_PORT/web/index.html"
echo "============================================================"

wait
