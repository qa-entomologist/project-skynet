#!/bin/bash
# Start the Auto-QA Dashboard

echo "🚀 Starting Auto-QA Dashboard..."
echo ""
echo "Opening dashboard in browser..."
echo ""

# Open the dashboard HTML file
if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS
    open web/auto_qa_dashboard.html
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    # Linux
    xdg-open web/auto_qa_dashboard.html
else
    echo "Please open: web/auto_qa_dashboard.html in your browser"
fi

echo "Dashboard URL: file://$(pwd)/web/auto_qa_dashboard.html"
echo ""
echo "To customize, add query parameters:"
echo "  ?service=playback-service&platform=ios&environment=alpha"

