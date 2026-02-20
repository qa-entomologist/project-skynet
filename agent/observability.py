"""
Agent self-observability instrumentation.

Tracks agent runs, latency, Datadog query counts, risk scores, and
recommendations — all emitted as structured logs and (optionally)
Datadog custom metrics.

This satisfies the "Observability for AI" hackathon requirement.
"""

from __future__ import annotations

import functools
import json
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Callable

from agent.config import DD_API_KEY, DD_SITE, AGENT_ENV

# ── Structured logger ──
logger = logging.getLogger("revert_risk_advisor")
logger.setLevel(logging.INFO)
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(
        "%(asctime)s | %(levelname)s | %(message)s"
    ))
    logger.addHandler(handler)


# ──────────────────────────────────────────────────────────────────────
# In-memory telemetry store (per-process; reset on restart)
# ──────────────────────────────────────────────────────────────────────

_telemetry: dict[str, list[dict]] = {
    "runs": [],
    "dd_queries": [],
}


def get_telemetry() -> dict[str, list[dict]]:
    """Return collected telemetry data."""
    return _telemetry


def reset_telemetry() -> None:
    _telemetry["runs"].clear()
    _telemetry["dd_queries"].clear()


# ──────────────────────────────────────────────────────────────────────
# Run-level tracking
# ──────────────────────────────────────────────────────────────────────

class RunContext:
    """Captures metadata for a single agent run."""

    def __init__(self, inputs: dict[str, Any]):
        self.run_id = str(uuid.uuid4())[:12]
        self.inputs = inputs
        self.start_time = time.time()
        self.end_time: float | None = None
        self.dd_query_count = 0
        self.signatures_matched = 0
        self.risk_score: int | None = None
        self.recommendation: str | None = None

    def finish(self, risk_score: int, recommendation: str, evidence: list[str] | None = None):
        self.end_time = time.time()
        self.risk_score = risk_score
        self.recommendation = recommendation
        record = self._to_dict()
        record["evidence"] = evidence or []
        _telemetry["runs"].append(record)
        _emit_structured_log(record)
        _emit_metrics(record)

    @property
    def latency_ms(self) -> float:
        end = self.end_time or time.time()
        return round((end - self.start_time) * 1000, 1)

    def _to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "inputs": self.inputs,
            "latency_ms": self.latency_ms,
            "dd_query_count": self.dd_query_count,
            "signatures_matched": self.signatures_matched,
            "risk_score": self.risk_score,
            "recommendation": self.recommendation,
        }


# Global per-request context
_current_run: RunContext | None = None


def start_run(inputs: dict[str, Any]) -> RunContext:
    global _current_run
    _current_run = RunContext(inputs)
    logger.info(f"[RUN {_current_run.run_id}] Started | inputs={json.dumps(inputs)}")
    return _current_run


def current_run() -> RunContext | None:
    return _current_run


# ──────────────────────────────────────────────────────────────────────
# Datadog-query decorator
# ──────────────────────────────────────────────────────────────────────

def track_dd_query(fn: Callable) -> Callable:
    """Decorator that counts Datadog queries for the current run."""

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        start = time.time()
        result = fn(*args, **kwargs)
        elapsed = round((time.time() - start) * 1000, 1)

        query_record = {
            "function": fn.__name__,
            "latency_ms": elapsed,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "run_id": _current_run.run_id if _current_run else None,
        }
        _telemetry["dd_queries"].append(query_record)

        if _current_run:
            _current_run.dd_query_count += 1

        logger.debug(f"[DD Query] {fn.__name__} completed in {elapsed}ms")
        return result

    return wrapper


# ──────────────────────────────────────────────────────────────────────
# Emission helpers
# ──────────────────────────────────────────────────────────────────────

def _emit_structured_log(record: dict[str, Any]) -> None:
    """Emit a structured JSON log line for the agent run."""
    logger.info(
        f"[RUN {record['run_id']}] Completed | "
        f"risk={record['risk_score']} "
        f"rec={record['recommendation']} "
        f"latency={record['latency_ms']}ms "
        f"dd_queries={record['dd_query_count']} "
        f"signatures_matched={record['signatures_matched']}"
    )
    # Full JSON for log aggregation
    logger.info(json.dumps(record, default=str))


def _emit_metrics(record: dict[str, Any]) -> None:
    """
    Send custom metrics to Datadog (if API key is configured).
    In demo mode, this is a no-op — metrics stay in-memory only.
    """
    if AGENT_ENV == "demo" or not DD_API_KEY:
        return

    try:
        from datadog_api_client import Configuration, ApiClient
        from datadog_api_client.v2.api.metrics_api import MetricsApi
        from datadog_api_client.v2.model.metric_intake_type import MetricIntakeType
        from datadog_api_client.v2.model.metric_payload import MetricPayload
        from datadog_api_client.v2.model.metric_point import MetricPoint
        from datadog_api_client.v2.model.metric_series import MetricSeries

        config = Configuration()
        config.api_key["apiKeyAuth"] = DD_API_KEY
        config.server_variables["site"] = DD_SITE

        now = int(time.time())
        tags = [f"env:{AGENT_ENV}"]

        series = [
            MetricSeries(
                metric="agent.run.count",
                type=MetricIntakeType.COUNT,
                points=[MetricPoint(timestamp=now, value=1)],
                tags=tags,
            ),
            MetricSeries(
                metric="agent.run.latency_ms",
                type=MetricIntakeType.GAUGE,
                points=[MetricPoint(timestamp=now, value=record["latency_ms"])],
                tags=tags,
            ),
            MetricSeries(
                metric="agent.datadog_queries.count",
                type=MetricIntakeType.COUNT,
                points=[MetricPoint(timestamp=now, value=record["dd_query_count"])],
                tags=tags,
            ),
            MetricSeries(
                metric="agent.revert_signatures.matched",
                type=MetricIntakeType.GAUGE,
                points=[MetricPoint(timestamp=now, value=record["signatures_matched"])],
                tags=tags,
            ),
            MetricSeries(
                metric="agent.risk_score",
                type=MetricIntakeType.GAUGE,
                points=[MetricPoint(timestamp=now, value=record["risk_score"] or 0)],
                tags=tags,
            ),
        ]

        with ApiClient(config) as api_client:
            api = MetricsApi(api_client)
            api.submit_metrics(body=MetricPayload(series=series))
            logger.info(f"[Observability] Metrics sent to Datadog for run {record['run_id']}")
    except Exception as e:
        logger.warning(f"[Observability] Failed to send metrics: {e}")

