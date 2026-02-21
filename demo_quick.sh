#!/bin/bash
# Quick demo script

echo "🎬 Starting Auto-QA Demo"
echo ""
echo "Step 1: Showing crashes in Datadog..."
echo ""
curl -s "http://localhost:8080/api/v1/events?start=0&end=$(date +%s)" | python3 -m json.tool | head -30
echo ""
echo "Step 2: Running Auto-QA Agent..."
echo ""
python3 run_risk_advisor.py --auto-qa --service "playback-service" --platform "ios"
