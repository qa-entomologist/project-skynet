"""
Datadog client for the Release Revert Risk Advisor.

In production this talks to Datadog APIs (Events, Metrics, Incidents).
In demo mode it reads from the local revert-history YAML and synthesises
realistic metric payloads so the agent can run without credentials.
"""

from __future__ import annotations

import random
import time
from datetime import datetime, timedelta, timezone
from typing import Any

import yaml

from agent.config import (
    DD_API_KEY,
    DD_APP_KEY,
    DD_SITE,
    REVERT_HISTORY_PATH,
    AGENT_ENV,
    KEY_SLIS,
    DEFAULT_HISTORY_WINDOW_DAYS,
    DEFAULT_POST_DEPLOY_MINUTES,
)
from agent.observability import track_dd_query


# ──────────────────────────────────────────────────────────────────────
# Data loader (YAML file for demo, Datadog API for prod)
# ──────────────────────────────────────────────────────────────────────

def _load_revert_history() -> dict:
    """Load revert history from the YAML file."""
    with open(REVERT_HISTORY_PATH, "r") as f:
        return yaml.safe_load(f)


def _is_live_mode() -> bool:
    return AGENT_ENV != "demo" and DD_API_KEY and DD_APP_KEY


# ──────────────────────────────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────────────────────────────

@track_dd_query
def fetch_revert_events(
    service: str,
    platform: str | None = None,
    window_days: int = DEFAULT_HISTORY_WINDOW_DAYS,
) -> list[dict[str, Any]]:
    """
    Retrieve past revert/rollback events for a service.

    Returns a list of revert event dicts with keys:
        id, date, feature, service, platform, description, trigger,
        time_to_detection_min, time_to_rollback_min, impacted_slis,
        root_cause, tags
    """
    if _is_live_mode():
        return _fetch_revert_events_live(service, platform, window_days)

    # ── Demo mode: filter YAML data ──
    data = _load_revert_history()
    # In demo mode, use a very wide window so all sample data is included
    cutoff = datetime.now(timezone.utc) - timedelta(days=max(window_days * 24, 3650))
    results = []
    for rev in data.get("reverts", []):
        rev_date = datetime.fromisoformat(rev["date"].replace("Z", "+00:00"))
        if rev_date < cutoff:
            continue
        # Match on service name OR any matching tag
        service_match = (
            rev.get("service") == service
            or service in rev.get("tags", [])
            or any(t in service for t in rev.get("tags", []))
        )
        if not service_match:
            continue
        if platform and platform != "all" and rev.get("platform") not in (platform, "all"):
            continue
        results.append(rev)
    return results


@track_dd_query
def fetch_metric_baseline(
    service: str,
    sli: str,
    window_days: int = DEFAULT_HISTORY_WINDOW_DAYS,
) -> dict[str, Any]:
    """
    Fetch the baseline (avg, p95, p99) for a given SLI over a time window.
    """
    if _is_live_mode():
        return _fetch_metric_baseline_live(service, sli, window_days)

    # ── Demo mode ──
    data = _load_revert_history()
    baselines = data.get("baselines", {}).get(service, {})
    base_val = baselines.get(sli, 0)
    # Synthesise a realistic spread
    return {
        "sli": sli,
        "service": service,
        "window_days": window_days,
        "avg": round(base_val, 3),
        "p95": round(base_val * 1.3, 3),
        "p99": round(base_val * 1.8, 3),
        "stddev": round(base_val * 0.15, 3),
    }


@track_dd_query
def fetch_current_health(
    service: str,
    sli: str,
    post_deploy_minutes: int = DEFAULT_POST_DEPLOY_MINUTES,
) -> dict[str, Any]:
    """
    Fetch current (post-deploy) value for an SLI.
    Returns current value + whether it is anomalous vs baseline.
    """
    if _is_live_mode():
        return _fetch_current_health_live(service, sli, post_deploy_minutes)

    # ── Demo mode: simulate slight perturbation from baseline ──
    data = _load_revert_history()
    baselines = data.get("baselines", {}).get(service, {})
    base_val = baselines.get(sli, 0)
    # Random perturbation: sometimes normal, sometimes elevated
    jitter = random.uniform(0.85, 1.6)
    current_val = round(base_val * jitter, 3)
    is_anomalous = jitter > 1.35
    return {
        "sli": sli,
        "service": service,
        "current_value": current_val,
        "baseline_avg": round(base_val, 3),
        "deviation_pct": round((jitter - 1.0) * 100, 1),
        "is_anomalous": is_anomalous,
        "window_minutes": post_deploy_minutes,
    }


@track_dd_query
def fetch_all_baselines(service: str) -> dict[str, float]:
    """Return all SLI baselines for a service."""
    data = _load_revert_history()
    return data.get("baselines", {}).get(service, {})


# ──────────────────────────────────────────────────────────────────────
# Live Datadog API calls (production mode)
# ──────────────────────────────────────────────────────────────────────

def _fetch_revert_events_live(
    service: str,
    platform: str | None,
    window_days: int,
) -> list[dict]:
    """Query Datadog Events API for rollback/revert events."""
    try:
        from datadog_api_client import Configuration, ApiClient
        from datadog_api_client.v1.api.events_api import EventsApi

        config = Configuration()
        config.api_key["apiKeyAuth"] = DD_API_KEY
        config.api_key["appKeyAuth"] = DD_APP_KEY
        config.server_variables["site"] = DD_SITE

        now = int(time.time())
        start = now - (window_days * 86400)

        with ApiClient(config) as api_client:
            api = EventsApi(api_client)
            tags_filter = f"service:{service}"
            if platform:
                tags_filter += f",platform:{platform}"
            response = api.list_events(
                start=start,
                end=now,
                tags=tags_filter,
                sources="rollback,revert,deploy",
            )
            events = []
            for ev in (response.events or []):
                events.append({
                    "id": str(ev.id),
                    "date": str(ev.date_happened),
                    "feature": ev.title or "",
                    "service": service,
                    "platform": platform or "all",
                    "description": ev.text or "",
                    "trigger": "datadog_event",
                    "tags": ev.tags or [],
                })
            return events
    except Exception as e:
        print(f"[DatadogClient] Live event fetch failed: {e}")
        return []


def _fetch_metric_baseline_live(
    service: str,
    sli: str,
    window_days: int,
) -> dict:
    """Query Datadog Metrics API for baseline values."""
    try:
        from datadog_api_client import Configuration, ApiClient
        from datadog_api_client.v1.api.metrics_api import MetricsApi

        config = Configuration()
        config.api_key["apiKeyAuth"] = DD_API_KEY
        config.api_key["appKeyAuth"] = DD_APP_KEY
        config.server_variables["site"] = DD_SITE

        now = int(time.time())
        start = now - (window_days * 86400)

        with ApiClient(config) as api_client:
            api = MetricsApi(api_client)
            query = f"avg:{sli}{{service:{service}}}"
            response = api.query_metrics(
                _from=start,
                to=now,
                query=query,
            )
            points = []
            for series in (response.series or []):
                for pt in (series.pointlist or []):
                    if pt.value is not None:
                        points.append(pt.value)
            if points:
                import statistics
                avg = statistics.mean(points)
                return {
                    "sli": sli,
                    "service": service,
                    "window_days": window_days,
                    "avg": round(avg, 3),
                    "p95": round(sorted(points)[int(len(points) * 0.95)], 3),
                    "p99": round(sorted(points)[int(len(points) * 0.99)], 3),
                    "stddev": round(statistics.stdev(points) if len(points) > 1 else 0, 3),
                }
            return {"sli": sli, "service": service, "avg": 0, "p95": 0, "p99": 0, "stddev": 0}
    except Exception as e:
        print(f"[DatadogClient] Live metric fetch failed: {e}")
        return {"sli": sli, "service": service, "avg": 0, "p95": 0, "p99": 0, "stddev": 0}


def _fetch_current_health_live(
    service: str,
    sli: str,
    post_deploy_minutes: int,
) -> dict:
    """Query Datadog for current metric health."""
    baseline = _fetch_metric_baseline_live(service, sli, 30)
    try:
        from datadog_api_client import Configuration, ApiClient
        from datadog_api_client.v1.api.metrics_api import MetricsApi

        config = Configuration()
        config.api_key["apiKeyAuth"] = DD_API_KEY
        config.api_key["appKeyAuth"] = DD_APP_KEY
        config.server_variables["site"] = DD_SITE

        now = int(time.time())
        start = now - (post_deploy_minutes * 60)

        with ApiClient(config) as api_client:
            api = MetricsApi(api_client)
            query = f"avg:{sli}{{service:{service}}}"
            response = api.query_metrics(_from=start, to=now, query=query)
            points = []
            for series in (response.series or []):
                for pt in (series.pointlist or []):
                    if pt.value is not None:
                        points.append(pt.value)
            if points:
                import statistics
                current = statistics.mean(points)
                base_avg = baseline.get("avg", 1) or 1
                deviation = ((current - base_avg) / base_avg) * 100
                return {
                    "sli": sli,
                    "service": service,
                    "current_value": round(current, 3),
                    "baseline_avg": round(base_avg, 3),
                    "deviation_pct": round(deviation, 1),
                    "is_anomalous": abs(deviation) > 35,
                    "window_minutes": post_deploy_minutes,
                }
    except Exception as e:
        print(f"[DatadogClient] Live health fetch failed: {e}")

    return {
        "sli": sli,
        "service": service,
        "current_value": 0,
        "baseline_avg": baseline.get("avg", 0),
        "deviation_pct": 0,
        "is_anomalous": False,
        "window_minutes": post_deploy_minutes,
    }

