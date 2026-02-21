#!/usr/bin/env python3
"""
Mock Datadog API Server for Demo

This server mimics Datadog's Metrics, Events, and Logs APIs
to provide realistic sample data for demos without requiring
real Datadog data.

Usage:
    python mock_datadog_server.py --port 8080

Then set in .env:
    DD_MOCK_SERVER=http://localhost:8080
    AGENT_ENV=mock
"""

import json
import random
import time
from datetime import datetime, timedelta, timezone
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse

# Sample crash data for demo
SAMPLE_CRASHES = [
    {
        "id": "crash_001",
        "timestamp": int((datetime.now(timezone.utc) - timedelta(minutes=5)).timestamp()),
        "service": "playback-service",
        "platform": "ios",
        "error_message": "NullPointerException in PlaybackService.processBuffer()",
        "stack_trace": "at com.example.PlaybackService.processBuffer(PlaybackService.java:123)\nat com.example.BufferManager.handleRequest(BufferManager.java:45)",
        "feature": "playback-buffer-v2",
        "severity": "high",
        "user_count": 42,
    },
    {
        "id": "crash_002",
        "timestamp": int((datetime.now(timezone.utc) - timedelta(minutes=12)).timestamp()),
        "service": "playback-service",
        "platform": "android",
        "error_message": "OutOfMemoryError in video decoder",
        "stack_trace": "at android.media.MediaCodec.native_dequeueOutputBuffer(Native Method)",
        "feature": "video-decoder-v3",
        "severity": "critical",
        "user_count": 128,
    },
    {
        "id": "crash_003",
        "timestamp": int((datetime.now(timezone.utc) - timedelta(minutes=2)).timestamp()),
        "service": "playback-service",
        "platform": "ios",
        "error_message": "IndexOutOfBoundsException in buffer management",
        "stack_trace": "at com.example.BufferManager.getBuffer(BufferManager.java:78)",
        "feature": "playback-buffer-v2",
        "severity": "medium",
        "user_count": 15,
    },
]

SAMPLE_DEPLOYMENTS = [
    {
        "id": "deploy_001",
        "timestamp": int((datetime.now(timezone.utc) - timedelta(hours=2)).timestamp()),
        "service": "playback-service",
        "feature": "playback-buffer-v2",
        "environment": "production",
        "version": "v2.1.3",
        "commit": "abc123def",
    },
    {
        "id": "deploy_002",
        "timestamp": int((datetime.now(timezone.utc) - timedelta(hours=6)).timestamp()),
        "service": "playback-service",
        "feature": "video-decoder-v3",
        "environment": "production",
        "version": "v3.0.1",
        "commit": "xyz789ghi",
    },
]


SERVER_START_TIME = time.time()
CRASH_DELAY_SECONDS = 0


class MockDatadogHandler(BaseHTTPRequestHandler):
    """HTTP handler that mimics Datadog API endpoints."""
    
    def _crashes_active(self):
        return (time.time() - SERVER_START_TIME) >= CRASH_DELAY_SECONDS

    def log_request(self, code='-', size='-'):
        """Override to log requests for debugging."""
        elapsed = int(time.time() - SERVER_START_TIME)
        status = "CRASHES ACTIVE" if self._crashes_active() else f"waiting {CRASH_DELAY_SECONDS - elapsed}s"
        print(f"[{datetime.now().strftime('%H:%M:%S')}] [{status}] {self.command} {self.path} - {code}")
    
    def do_GET(self):
        """Handle GET requests (Metrics API, Events API)."""
        parsed = urlparse(self.path)
        path = parsed.path
        query_params = parse_qs(parsed.query)
        
        # Check authentication - Datadog client sends API key in query params or headers
        api_key = (
            query_params.get("api_key", [None])[0] or  # Query param
            self.headers.get("DD-API-KEY") or  # Header
            self.headers.get("apiKeyAuth") or  # Alternative header
            (self.headers.get("Authorization", "").replace("Bearer ", "").replace("ApiKey ", ""))
        )
        
        # Debug: Print headers for troubleshooting
        if not api_key:
            print(f"[DEBUG] No API key found. Headers: {dict(self.headers)}")
            print(f"[DEBUG] Query params: {query_params}")
        
        # For demo purposes, accept any non-empty API key OR skip auth check
        # In production, you'd validate against your real API key
        if not api_key or api_key == "":
            # For demo, allow requests without API key (comment out for production)
            print(f"[WARNING] No API key provided, but allowing for demo purposes")
            # Uncomment below to enforce API key:
            # self.send_error(401, "Missing API key")
            # return
        
        # Root endpoint - Show available endpoints
        if path == "/" or path == "":
            self.send_json_response({
                "status": "ok",
                "message": "Mock Datadog API Server",
                "endpoints": {
                    "GET /api/v1/query": "Query metrics (e.g., crash_rate, error_rate)",
                    "GET /api/v1/events": "List events (crashes, deployments)",
                    "POST /api/v2/logs/events/search": "Search logs",
                },
                "sample_usage": {
                    "events": "/api/v1/events?start=0&end=$(date +%s)",
                    "metrics": "/api/v1/query?query=avg:crash_rate{service:playback-service}&from=0&to=$(date +%s)",
                }
            })
            return
        
        # Metrics API - Query metrics
        elif path.startswith("/api/v1/query"):
            self.handle_metrics_query(query_params)
        
        # Events API - List events
        elif path.startswith("/api/v1/events"):
            self.handle_events_list(query_params)
        
        else:
            self.send_error(404, f"Endpoint not found: {path}")
    
    def do_POST(self):
        """Handle POST requests."""
        parsed = urlparse(self.path)
        path = parsed.path
        query_params = parse_qs(parsed.query)
        
        # Check authentication - Datadog client sends API key in query params or headers
        api_key = (
            query_params.get("api_key", [None])[0] or  # Query param
            self.headers.get("DD-API-KEY") or  # Header
            self.headers.get("apiKeyAuth") or  # Alternative header
            (self.headers.get("Authorization", "").replace("Bearer ", "").replace("ApiKey ", ""))
        )
        
        # For demo purposes, skip auth check (comment out for production)
        if not api_key or api_key == "":
            print(f"[WARNING] No API key provided, but allowing for demo purposes")
            # Uncomment below to enforce API key:
            # self.send_error(401, "Missing API key")
            # return
        
        # Logs API - Search logs
        if path.startswith("/api/v2/logs/events/search"):
            self.handle_logs_search()
        
        else:
            self.send_error(404, f"Endpoint not found: {path}")
    
    def handle_metrics_query(self, query_params):
        """Handle Metrics API query."""
        query = query_params.get("query", [""])[0]
        start = int(query_params.get("from", [0])[0])
        end = int(query_params.get("to", [int(time.time())])[0])
        
        if not self._crashes_active():
            self.send_json_response({"status": "ok", "res_type": "time_series", "series": [{"metric": "crash_rate", "pointlist": [[end * 1000, 0.001]], "start": start * 1000, "end": end * 1000, "interval": 60, "length": 1}]})
            return

        if "crash_rate" in query:
            # Return crash rate data
            # Simulate: baseline 0.01 (1%), current spike to 0.05 (5%)
            baseline = 0.01
            current = 0.05 if random.random() > 0.3 else baseline  # 70% chance of spike
            
            # Generate time series points
            points = []
            current_time = start
            while current_time <= end:
                # Add some variation
                value = current + random.uniform(-0.01, 0.01)
                points.append([current_time * 1000, value])  # Datadog uses milliseconds
                current_time += 60  # 1 minute intervals
            
            response = {
                "status": "ok",
                "res_type": "time_series",
                "series": [{
                    "metric": "crash_rate",
                    "display_name": "crash_rate",
                    "unit": None,
                    "pointlist": points,
                    "start": start * 1000,
                    "end": end * 1000,
                    "interval": 60,
                    "length": len(points),
                }]
            }
        
        elif "error_rate" in query:
            # Similar for error_rate
            baseline = 0.02
            current = 0.08 if random.random() > 0.4 else baseline
            
            points = []
            current_time = start
            while current_time <= end:
                value = current + random.uniform(-0.02, 0.02)
                points.append([current_time * 1000, value])
                current_time += 60
            
            response = {
                "status": "ok",
                "res_type": "time_series",
                "series": [{
                    "metric": "error_rate",
                    "display_name": "error_rate",
                    "unit": None,
                    "pointlist": points,
                    "start": start * 1000,
                    "end": end * 1000,
                    "interval": 60,
                    "length": len(points),
                }]
            }
        
        else:
            # Default: return empty series
            response = {
                "status": "ok",
                "res_type": "time_series",
                "series": []
            }
        
        self.send_json_response(response)
    
    def handle_events_list(self, query_params):
        """Handle Events API list_events."""
        start = int(query_params.get("start", [0])[0])
        end = int(query_params.get("end", [int(time.time())])[0])
        tags = query_params.get("tags", [""])[0]
        sources = query_params.get("sources", [""])[0]
        
        events = []
        
        if not self._crashes_active():
            self.send_json_response({"events": [], "status": "ok"})
            return

        service_filter = None
        if tags and "service:" in tags:
            service_filter = tags.split("service:")[1].split(",")[0].strip()
        
        # Filter crashes based on time window
        for crash in SAMPLE_CRASHES:
            # For demo, always include crashes if within time window (or if time window is very wide)
            # Real implementation would check: start <= crash["timestamp"] <= end
            # But for demo, we'll return recent crashes regardless
            crash_time = crash["timestamp"]
            current_time = int(time.time())
            
            # Include if crash is within last 24 hours OR if no time filter specified
            if start == 0 or (current_time - crash_time) < (24 * 3600):
                # Check service filter if provided
                if not service_filter or crash["service"] == service_filter:
                    events.append({
                        "id": crash["id"],
                        "date_happened": crash["timestamp"],
                        "title": f"Crash in {crash['service']}",
                        "text": crash["error_message"],
                        "tags": [
                            f"service:{crash['service']}",
                            f"platform:{crash['platform']}",
                            f"feature:{crash['feature']}",
                            f"severity:{crash['severity']}",
                        ],
                        "source": "crash",
                    })
        
        # Add deployment events
        if "deploy" in sources or "deployment" in sources or not sources:
            for deploy in SAMPLE_DEPLOYMENTS:
                deploy_time = deploy["timestamp"]
                current_time = int(time.time())
                
                # Include if deployment is within last 24 hours OR if no time filter
                if start == 0 or (current_time - deploy_time) < (24 * 3600):
                    if not service_filter or deploy["service"] == service_filter:
                        events.append({
                            "id": deploy["id"],
                            "date_happened": deploy["timestamp"],
                            "title": f"Deployment: {deploy['feature']}",
                            "text": f"Deployed {deploy['feature']} to {deploy['environment']}",
                            "tags": [
                                f"service:{deploy['service']}",
                                f"feature:{deploy['feature']}",
                                f"env:{deploy['environment']}",
                                f"version:{deploy['version']}",
                            ],
                            "source": "deploy",
                        })
        
        response = {
            "events": events,
            "status": "ok"
        }
        
        self.send_json_response(response)
    
    def handle_logs_search(self):
        """Handle Logs API search (simplified)."""
        # Read request body
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)
        
        try:
            request_data = json.loads(body.decode())
            filter_query = request_data.get("filter", {}).get("query", "")
            
            # Return sample log entries that match crash patterns
            logs = []
            for crash in SAMPLE_CRASHES:
                if "crash" in filter_query.lower() or "exception" in filter_query.lower():
                    logs.append({
                        "id": f"log_{crash['id']}",
                        "attributes": {
                            "message": crash["error_message"],
                            "status": "error",
                            "service": crash["service"],
                            "platform": crash["platform"],
                            "timestamp": datetime.fromtimestamp(crash["timestamp"], tz=timezone.utc).isoformat(),
                        }
                    })
            
            response = {
                "data": logs,
                "meta": {
                    "page": {"after": None}
                }
            }
            
            self.send_json_response(response)
        
        except Exception as e:
            self.send_error(400, f"Invalid request: {e}")
    
    def send_json_response(self, data):
        """Send JSON response."""
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())
    
    def log_message(self, format, *args):
        """Override to reduce logging noise."""
        pass


def run_server(port=8080):
    """Run the mock Datadog server."""
    server_address = ("", port)
    httpd = HTTPServer(server_address, MockDatadogHandler)
    print(f"Mock Datadog API Server running on http://localhost:{port}")
    if CRASH_DELAY_SECONDS > 0:
        print(f"   Crash delay: {CRASH_DELAY_SECONDS}s (crashes will appear after delay)")
    else:
        print(f"   Crashes active immediately")
    print(f"   DD_MOCK_SERVER=http://localhost:{port}")
    print(f"   Press Ctrl+C to stop\n")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n\nStopping server...")
        httpd.shutdown()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Mock Datadog API Server")
    parser.add_argument("--port", type=int, default=8080, help="Port to run on (default: 8080)")
    parser.add_argument("--delay", type=int, default=0, help="Seconds before crashes appear (simulates crash happening mid-demo)")
    args = parser.parse_args()
    CRASH_DELAY_SECONDS = args.delay
    run_server(args.port)

