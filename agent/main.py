"""
Release Revert Risk Advisor – Main Agent Orchestrator

This is the entry point that ties together all agent components:
    1. Fetch historical revert events (Datadog / YAML)
    2. Build failure signatures
    3. Fetch current SLI baselines and health
    4. Compute risk score
    5. Generate evidence-backed report (Bedrock / template)
    6. Emit observability telemetry

Usage:
    from agent.main import run_agent

    result = run_agent(
        feature_name="playback-buffer-v2",
        service="playback-service",
        platform="ios",
    )
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from agent.config import KEY_SLIS, EVALS_DIR, DEFAULT_HISTORY_WINDOW_DAYS
from agent.datadog_client import (
    fetch_revert_events,
    fetch_metric_baseline,
    fetch_current_health,
    fetch_all_baselines,
)
from agent.signature_builder import build_signatures, rank_signatures
from agent.risk_model import compute_risk
from agent.bedrock_summarizer import generate_report
from agent.observability import start_run, logger


def run_agent(
    feature_name: str,
    service: str,
    platform: str | None = None,
    time_window_days: int = DEFAULT_HISTORY_WINDOW_DAYS,
    tags: list[str] | None = None,
    post_deploy_minutes: int = 60,
    save_eval: bool = True,
) -> dict[str, Any]:
    """
    Execute a full risk assessment run.

    Args:
        feature_name:       Name of the experiment / feature being released
        service:            Service tag (e.g. "playback-service")
        platform:           Target platform (ios/android/web/all)
        time_window_days:   How far back to look for revert history
        tags:               Optional tags to help with similarity matching
        post_deploy_minutes: Minutes of post-deploy data to consider
        save_eval:          Whether to save the run output to evals/

    Returns:
        Complete risk report dict
    """
    # ── Start observability tracking ──
    run_ctx = start_run({
        "feature_name": feature_name,
        "service": service,
        "platform": platform,
        "time_window_days": time_window_days,
        "tags": tags,
    })

    try:
        # ── Step 1: Fetch historical revert events ──
        logger.info(f"[{run_ctx.run_id}] Step 1: Fetching revert history for {service}...")
        revert_events = fetch_revert_events(
            service=service,
            platform=platform,
            window_days=time_window_days,
        )
        logger.info(f"[{run_ctx.run_id}] Found {len(revert_events)} revert events")

        # If no events for this exact service, broaden search
        if not revert_events:
            logger.info(f"[{run_ctx.run_id}] Broadening search to all services...")
            revert_events = fetch_revert_events(
                service=service,
                platform=None,
                window_days=time_window_days * 4,  # Look further back
            )
            # Also fetch events for related tags
            if tags:
                for tag in tags[:3]:
                    extra = fetch_revert_events(service=tag, window_days=time_window_days * 4)
                    revert_events.extend(extra)

        # ── Step 2: Build failure signatures ──
        logger.info(f"[{run_ctx.run_id}] Step 2: Building failure signatures...")
        signatures = build_signatures(revert_events)
        run_ctx.signatures_matched = len(signatures)
        logger.info(f"[{run_ctx.run_id}] Built {len(signatures)} signatures")

        # ── Step 3: Fetch current SLI baselines ──
        logger.info(f"[{run_ctx.run_id}] Step 3: Fetching SLI baselines for {service}...")
        sli_baselines: dict[str, dict[str, Any]] = {}
        for sli in KEY_SLIS:
            baseline = fetch_metric_baseline(service, sli, time_window_days)
            if baseline.get("avg", 0) > 0:  # Only include non-zero SLIs
                sli_baselines[sli] = baseline

        # ── Step 4: Fetch current health ──
        logger.info(f"[{run_ctx.run_id}] Step 4: Fetching current health...")
        sli_current_health: dict[str, dict[str, Any]] = {}
        for sli in KEY_SLIS:
            health = fetch_current_health(service, sli, post_deploy_minutes)
            if health.get("baseline_avg", 0) > 0:
                sli_current_health[sli] = health

        # ── Step 5: Rank signatures by similarity ──
        logger.info(f"[{run_ctx.run_id}] Step 5: Ranking signatures by similarity...")
        ranked = rank_signatures(
            signatures=signatures,
            current_service=service,
            current_platform=platform,
            current_tags=tags,
            current_sli_health=sli_current_health,
        )

        # ── Step 6: Compute risk score ──
        logger.info(f"[{run_ctx.run_id}] Step 6: Computing risk score...")
        assessment = compute_risk(
            ranked_signatures=ranked,
            sli_baselines=sli_baselines,
            sli_current_health=sli_current_health,
            service=service,
            platform=platform,
        )

        # ── Step 7: Generate report ──
        logger.info(f"[{run_ctx.run_id}] Step 7: Generating report...")
        report = generate_report(
            assessment=assessment,
            feature_name=feature_name,
            service=service,
            platform=platform,
        )

        # Add run metadata
        report["run_id"] = run_ctx.run_id
        report["timestamp"] = datetime.now(timezone.utc).isoformat()
        report["agent_metrics"] = {
            "latency_ms": run_ctx.latency_ms,
            "dd_query_count": run_ctx.dd_query_count,
            "signatures_matched": run_ctx.signatures_matched,
        }

        # ── Finish observability ──
        run_ctx.finish(
            risk_score=assessment.risk_score,
            recommendation=assessment.recommendation,
            evidence=assessment.evidence,
        )

        # ── Save eval output ──
        if save_eval:
            _save_eval(report, run_ctx.run_id)

        return report

    except Exception as e:
        logger.error(f"[{run_ctx.run_id}] Agent run failed: {e}")
        run_ctx.finish(risk_score=-1, recommendation="error", evidence=[str(e)])
        raise


def _save_eval(report: dict, run_id: str) -> None:
    """Persist the run output for evaluation/audit."""
    EVALS_DIR.mkdir(parents=True, exist_ok=True)
    path = EVALS_DIR / f"run_{run_id}.json"
    with open(path, "w") as f:
        json.dump(report, f, indent=2, default=str)
    logger.info(f"[Eval] Saved to {path}")

