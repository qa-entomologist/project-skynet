#!/bin/bash
# Start the Release Revert Risk Advisor server

echo "🚀 Starting Release Revert Risk Advisor server..."
echo "   API will be available at: http://localhost:8000"
echo "   Health check: http://localhost:8000/api/health"
echo ""

cd "$(dirname "$0")"

# Activate virtual environment if it exists
if [ -d ".venv" ]; then
    source .venv/bin/activate
elif [ -d "venv" ]; then
    source venv/bin/activate
fi

# Start the server
python3 run_risk_advisor.py --server --port 8000

