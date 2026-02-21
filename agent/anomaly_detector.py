"""
Anomaly and Crash Detector – monitors Datadog for real-time anomalies and crashes.

When an anomaly or crash is detected, this module:
1. Fetches crash/error details from Datadog
2. Identifies the affected service, feature, and platform
3. Triggers the reproducibility analysis workflow
"""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from typing import Any

from agent.config import DD_API_KEY, DD_APP_KEY, DD_SITE, DD_MOCK_SERVER, AGENT_ENV, KEY_SLIS
from agent.observability import track_dd_query, logger


@track_dd_query
def detect_anomalies(
    service: str,
    lookback_minutes: int = 15,
) -> list[dict[str, Any]]:
    """
    Detect recent anomalies and crashes for a service from Datadog.
    
    Returns a list of detected incidents with:
        - type: "crash" | "anomaly" | "error_spike"
        - severity: "critical" | "high" | "medium"
        - service, platform, feature
        - timestamp, description
        - affected_slis, error_details
    """
    # Use mock server if configured, otherwise check for demo mode
    if DD_MOCK_SERVER:
        # Always use live mode when mock server is configured
        return _detect_anomalies_live(service, lookback_minutes)
    elif AGENT_ENV == "demo" or not DD_API_KEY:
        return _detect_anomalies_demo(service, lookback_minutes)
    
    return _detect_anomalies_live(service, lookback_minutes)


@track_dd_query
def fetch_crash_details(
    service: str,
    platform: str | None = None,
    lookback_minutes: int = 15,
) -> list[dict[str, Any]]:
    """
    Fetch detailed crash information from Datadog.
    
    Returns crash reports with:
        - crash_id, timestamp
        - stack_trace, error_message
        - device_info, app_version
        - user_count, frequency
        - affected_endpoints
    """
    # Use mock server if configured
    if DD_MOCK_SERVER:
        return _fetch_crash_details_live(service, platform, lookback_minutes)
    elif AGENT_ENV == "demo" or not DD_API_KEY:
        return _fetch_crash_details_demo(service, platform, lookback_minutes)
    
    return _fetch_crash_details_live(service, platform, lookback_minutes)


@track_dd_query
def fetch_recent_deployments(
    service: str,
    lookback_hours: int = 24,
) -> list[dict[str, Any]]:
    """
    Fetch recent deployments for a service to correlate with crashes.
    
    Returns deployment info with:
        - deployment_id, timestamp
        - feature_name, version
        - commit_sha, author
        - environment (alpha/production)
    """
    # Use mock server if configured
    if DD_MOCK_SERVER:
        return _fetch_deployments_live(service, lookback_hours)
    elif AGENT_ENV == "demo" or not DD_API_KEY:
        return _fetch_deployments_demo(service, lookback_hours)
    
    return _fetch_deployments_live(service, lookback_hours)


# ──────────────────────────────────────────────────────────────────────
# Live Datadog API implementations
# ──────────────────────────────────────────────────────────────────────

def _mock_config():
    """Build a Configuration pointing at the mock server with dummy keys."""
    from datadog_api_client import Configuration
    from urllib.parse import urlparse
    config = Configuration()
    config.api_key["apiKeyAuth"] = DD_API_KEY or "mock-api-key"
    config.api_key["appKeyAuth"] = DD_APP_KEY or "mock-app-key"
    if DD_MOCK_SERVER:
        parsed = urlparse(DD_MOCK_SERVER)
        config.host = f"{parsed.scheme}://{parsed.netloc}"
        logger.info(f"Using mock Datadog server: {config.host}")
    else:
        config.server_variables["site"] = DD_SITE
    return config


def _detect_anomalies_live(
    service: str,
    lookback_minutes: int,
) -> list[dict[str, Any]]:
    """Detect anomalies using Datadog API (or mock server)."""
    try:
        from datadog_api_client import ApiClient
        from datadog_api_client.v1.api.events_api import EventsApi
        from datadog_api_client.v1.api.metrics_api import MetricsApi
        
        config = _mock_config()
        
        now = int(time.time())
        start = now - (lookback_minutes * 60)
        
        anomalies = []
        
        with ApiClient(config) as api_client:
            # Check for crash_rate anomalies
            metrics_api = MetricsApi(api_client)
            
            for sli in KEY_SLIS:
                if sli not in ["crash_rate", "error_rate"]:
                    continue
                
                query = f"avg:{sli}{{service:{service}}}"
                try:
                    response = metrics_api.query_metrics(_from=start, to=now, query=query)
                    
                    # Get baseline from last 7 days
                    baseline_start = now - (7 * 24 * 60 * 60)
                    baseline_response = metrics_api.query_metrics(
                        _from=baseline_start, to=now, query=query
                    )
                    
                    # Calculate if current value is anomalous
                    current_points = []
                    baseline_points = []
                    
                    for series in (response.series or []):
                        for pt in (series.pointlist or []):
                            if pt.value is not None:
                                current_points.append(pt.value)
                    
                    for series in (baseline_response.series or []):
                        for pt in (series.pointlist or []):
                            if pt.value is not None:
                                baseline_points.append(pt.value)
                    
                    if current_points and baseline_points:
                        import statistics
                        current_avg = statistics.mean(current_points)
                        baseline_avg = statistics.mean(baseline_points)
                        baseline_std = statistics.stdev(baseline_points) if len(baseline_points) > 1 else 0
                        
                        # Anomaly if > 2 standard deviations above baseline
                        threshold = baseline_avg + (2 * baseline_std)
                        if current_avg > threshold and baseline_avg > 0:
                            anomaly_type = "crash" if "crash" in sli else "error_spike"
                            severity = (
                                "critical" if current_avg > baseline_avg * 5
                                else "high" if current_avg > baseline_avg * 3
                                else "medium"
                            )
                            
                            anomalies.append({
                                "type": anomaly_type,
                                "severity": severity,
                                "service": service,
                                "sli": sli,
                                "timestamp": datetime.now(timezone.utc).isoformat(),
                                "current_value": round(current_avg, 4),
                                "baseline_avg": round(baseline_avg, 4),
                                "spike_ratio": round(current_avg / baseline_avg, 2) if baseline_avg > 0 else 0,
                                "description": f"{sli} spike detected: {current_avg:.4f} vs baseline {baseline_avg:.4f}",
                            })
                
                except Exception as e:
                    logger.warning(f"Failed to check {sli} for anomalies: {e}")
            
            # Also check Events API for crash events
            events_api = EventsApi(api_client)
            try:
                response = events_api.list_events(
                    start=start,
                    end=now,
                    tags=f"service:{service}",
                    sources="error,crash,exception",
                )
                
                for ev in (response.events or []):
                    if "crash" in ev.text.lower() or "exception" in ev.text.lower():
                        anomalies.append({
                            "type": "crash",
                            "severity": "high",
                            "service": service,
                            "timestamp": datetime.fromtimestamp(ev.date_happened, tz=timezone.utc).isoformat(),
                            "description": ev.text or "",
                            "event_id": str(ev.id),
                            "tags": ev.tags or [],
                        })
            except Exception as e:
                logger.warning(f"Failed to fetch crash events: {e}")
        
        return anomalies
    
    except Exception as e:
        logger.error(f"Anomaly detection failed: {e}")
        return []


def _fetch_crash_details_live(
    service: str,
    platform: str | None,
    lookback_minutes: int,
) -> list[dict[str, Any]]:
    """Fetch detailed crash information from Datadog (or mock server)."""
    try:
        from datadog_api_client import ApiClient
        from datadog_api_client.v1.api.events_api import EventsApi
        from datadog_api_client.v1.api.logs_api import LogsApi
        
        config = _mock_config()
        
        now = int(time.time())
        start = now - (lookback_minutes * 60)
        
        crashes = []
        
        with ApiClient(config) as api_client:
            # Query logs for crash/exception patterns
            logs_api = LogsApi(api_client)
            
            query = f"service:{service} (crash OR exception OR fatal)"
            if platform:
                query += f" platform:{platform}"
            
            try:
                # Note: This is a simplified version - actual implementation would use
                # Datadog Logs Search API which requires more complex setup
                # For now, we'll use Events API as a proxy
                events_api = EventsApi(api_client)
                response = events_api.list_events(
                    start=start,
                    end=now,
                    tags=f"service:{service}",
                    sources="error,crash",
                )
                
                for ev in (response.events or []):
                    crashes.append({
                        "crash_id": str(ev.id),
                        "timestamp": datetime.fromtimestamp(ev.date_happened, tz=timezone.utc).isoformat(),
                        "service": service,
                        "platform": platform or "unknown",
                        "error_message": ev.text or "",
                        "description": ev.title or "",
                        "tags": ev.tags or [],
                    })
            except Exception as e:
                logger.warning(f"Failed to fetch crash details: {e}")
        
        return crashes
    
    except Exception as e:
        logger.error(f"Crash details fetch failed: {e}")
        return []


def _fetch_deployments_live(
    service: str,
    lookback_hours: int,
) -> list[dict[str, Any]]:
    """Fetch recent deployments from Datadog Events (or mock server)."""
    try:
        from datadog_api_client import ApiClient
        from datadog_api_client.v1.api.events_api import EventsApi
        
        config = _mock_config()
        
        now = int(time.time())
        start = now - (lookback_hours * 3600)
        
        deployments = []
        
        with ApiClient(config) as api_client:
            api = EventsApi(api_client)
            response = api.list_events(
                start=start,
                end=now,
                tags=f"service:{service}",
                sources="deploy,deployment",
            )
            
            for ev in (response.events or []):
                # Extract feature name from tags or title
                feature_name = ev.title or ""
                for tag in (ev.tags or []):
                    if "feature:" in tag or "version:" in tag:
                        feature_name = tag.split(":")[-1]
                        break
                
                deployments.append({
                    "deployment_id": str(ev.id),
                    "timestamp": datetime.fromtimestamp(ev.date_happened, tz=timezone.utc).isoformat(),
                    "service": service,
                    "feature_name": feature_name,
                    "environment": "production" if "prod" in (ev.text or "").lower() else "alpha",
                    "description": ev.text or "",
                    "tags": ev.tags or [],
                })
        
        return deployments
    
    except Exception as e:
        logger.error(f"Deployment fetch failed: {e}")
        return []


# ──────────────────────────────────────────────────────────────────────
# Demo mode implementations
# ──────────────────────────────────────────────────────────────────────

def _detect_anomalies_demo(
    service: str,
    lookback_minutes: int,
) -> list[dict[str, Any]]:
    """Demo mode: return synthetic anomalies."""
    import random
    
    # Simulate occasional anomalies
    if random.random() > 0.7:  # 30% chance of anomaly
        return [{
            "type": "crash",
            "severity": "high",
            "service": service,
            "sli": "crash_rate",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "current_value": 0.05,
            "baseline_avg": 0.01,
            "spike_ratio": 5.0,
            "description": f"Crash rate spike detected in {service}: 5% vs baseline 1%",
        }]
    return []


def _fetch_crash_details_demo(
    service: str,
    platform: str | None,
    lookback_minutes: int,
) -> list[dict[str, Any]]:
    """Demo mode: return synthetic crash details."""
    return [{
        "crash_id": "demo_crash_001",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "service": service,
        "platform": platform or "ios",
        "error_message": "NullPointerException in playback service",
        "description": "Crash in video playback buffer",
        "stack_trace": "at com.example.PlaybackService.processBuffer(PlaybackService.java:123)",
        "tags": ["feature:playback-buffer-v2", "platform:ios"],
    }]


def _fetch_deployments_demo(
    service: str,
    lookback_hours: int,
) -> list[dict[str, Any]]:
    """Demo mode: return synthetic deployments."""
    return [{
        "deployment_id": "demo_deploy_001",
        "timestamp": (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat(),
        "service": service,
        "feature_name": "playback-buffer-v2",
        "environment": "production",
        "description": "Deployed playback-buffer-v2 to production",
        "tags": ["feature:playback-buffer-v2", "env:production"],
    }]

