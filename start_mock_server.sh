#!/bin/bash
# Quick script to start the mock Datadog server

echo "🚀 Starting Mock Datadog API Server..."
echo ""

# Check if port 8080 is in use
if lsof -Pi :8080 -sTCP:LISTEN -t >/dev/null ; then
    echo "⚠️  Port 8080 is already in use!"
    echo "   Either stop the existing process or use a different port:"
    echo "   python3 mock_datadog_server.py --port 8081"
    exit 1
fi

# Start the server
python3 mock_datadog_server.py --port 8080

