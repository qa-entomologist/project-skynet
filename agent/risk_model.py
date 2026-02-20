"""
Risk Model – computes a 0-100 risk readiness score using weighted rules.

Scoring breakdown:
    • Similarity to rollback signatures   0 – 50  (WEIGHT_SIMILARITY)
    • Volatility of relevant SLIs         0 – 30  (WEIGHT_VOLATILITY)
    • Current anomaly presence            0 – 20  (WEIGHT_ANOMALY)

Recommendation tiers:
    0 – 30   →  ship   (safe to proceed)
    31 – 60  →  ramp   (proceed with ramp + monitoring guardrails)
    61 – 100 →  hold   (hold until validated)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from agent.config import WEIGHT_SIMILARITY, WEIGHT_VOLATILITY, WEIGHT_ANOMALY
from agent.signature_builder import RevertSignature


@dataclass
class RiskAssessment:
    """Complete risk assessment for a release."""

    risk_score: int
    recommendation: str  # ship | ramp | hold
    similarity_score: float
    volatility_score: float
    anomaly_score: float
    top_risk_drivers: list[str]
    matched_signatures: list[dict[str, Any]]
    monitoring_checks: list[str]
    rollback_thresholds: list[dict[str, Any]]
    rollout_guidance: str
    evidence: list[str] = field(default_factory=list)


def compute_risk(
    ranked_signatures: list[tuple[RevertSignature, float]],
    sli_baselines: dict[str, dict[str, Any]],
    sli_current_health: dict[str, dict[str, Any]],
    service: str,
    platform: str | None = None,
) -> RiskAssessment:
    """
    Compute the overall risk score and produce a full assessment.
    """
    # ── 1. Similarity component (0 – 50) ──
    if ranked_signatures:
        top_similarity = ranked_signatures[0][1]
        # Average of top 3 (or fewer)
        top_n = [s for _, s in ranked_signatures[:3]]
        avg_similarity = sum(top_n) / len(top_n)
        # Blend: 60% top match, 40% average
        raw_similarity = 0.6 * top_similarity + 0.4 * avg_similarity
    else:
        raw_similarity = 0.0
    similarity_score = round(raw_similarity * WEIGHT_SIMILARITY, 1)

    # ── 2. Volatility component (0 – 30) ──
    volatility_signals = []
    for sli, baseline in sli_baselines.items():
        stddev = baseline.get("stddev", 0)
        avg = baseline.get("avg", 1) or 1
        cv = stddev / avg  # coefficient of variation
        if cv > 0.3:
            volatility_signals.append((sli, cv, "high"))
        elif cv > 0.15:
            volatility_signals.append((sli, cv, "medium"))
        else:
            volatility_signals.append((sli, cv, "low"))

    high_vol_count = sum(1 for _, _, level in volatility_signals if level == "high")
    med_vol_count = sum(1 for _, _, level in volatility_signals if level == "medium")
    total_slis = max(len(volatility_signals), 1)
    vol_ratio = (high_vol_count * 1.0 + med_vol_count * 0.5) / total_slis
    volatility_score = round(min(vol_ratio, 1.0) * WEIGHT_VOLATILITY, 1)

    # ── 3. Anomaly component (0 – 20) ──
    anomalous_slis = []
    elevated_slis = []
    for sli, health in sli_current_health.items():
        if health.get("is_anomalous"):
            anomalous_slis.append(sli)
        elif health.get("deviation_pct", 0) > 15:
            elevated_slis.append(sli)

    anomaly_ratio = (len(anomalous_slis) * 1.0 + len(elevated_slis) * 0.4) / max(len(sli_current_health), 1)
    anomaly_score = round(min(anomaly_ratio, 1.0) * WEIGHT_ANOMALY, 1)

    # ── Total risk score ──
    risk_score = int(round(similarity_score + volatility_score + anomaly_score))
    risk_score = max(0, min(100, risk_score))

    # ── Recommendation ──
    if risk_score <= 30:
        recommendation = "ship"
        rollout_guidance = (
            "Safe to proceed with standard rollout. "
            "Continue monitoring key SLIs for 30 minutes post-deploy."
        )
    elif risk_score <= 60:
        recommendation = "ramp"
        rollout_guidance = (
            f"Proceed with gradual ramp: 1% → 5% → 25% → 100%. "
            f"Hold at each stage for 15 minutes and validate SLIs. "
            f"Set automatic rollback triggers on anomalous metrics."
        )
    else:
        recommendation = "hold"
        rollout_guidance = (
            f"Hold release until the following are validated: "
            f"{''.join(anomalous_slis[:3]) or 'flagged SLIs'} return to baseline, "
            f"and the similarity to past rollback patterns is addressed. "
            f"Consider additional load testing before proceeding."
        )

    # ── Top risk drivers ──
    risk_drivers = _build_risk_drivers(
        ranked_signatures, anomalous_slis, elevated_slis, volatility_signals
    )

    # ── Matched signatures detail ──
    matched_sigs = []
    for sig, sim in ranked_signatures[:3]:
        matched_sigs.append({
            "revert_id": sig.revert_id,
            "date": sig.date,
            "feature": sig.feature,
            "service": sig.service,
            "platform": sig.platform,
            "similarity": round(sim, 3),
            "severity": sig.severity_tier,
            "root_cause": sig.root_cause,
            "description": sig.description,
            "impacted_slis": list(sig.sli_names),
            "max_spike_ratio": round(sig.max_spike_ratio, 1),
        })

    # ── Monitoring checks & rollback thresholds ──
    monitoring_checks = _build_monitoring_checks(
        anomalous_slis, elevated_slis, sli_baselines, ranked_signatures
    )
    rollback_thresholds = _build_rollback_thresholds(sli_baselines, sli_current_health)

    # ── Evidence trail ──
    evidence = [
        f"Similarity score: {similarity_score}/{WEIGHT_SIMILARITY} "
        f"(top match: {ranked_signatures[0][0].revert_id if ranked_signatures else 'none'})",
        f"Volatility score: {volatility_score}/{WEIGHT_VOLATILITY} "
        f"({high_vol_count} high, {med_vol_count} medium volatility SLIs)",
        f"Anomaly score: {anomaly_score}/{WEIGHT_ANOMALY} "
        f"({len(anomalous_slis)} anomalous, {len(elevated_slis)} elevated SLIs)",
    ]

    return RiskAssessment(
        risk_score=risk_score,
        recommendation=recommendation,
        similarity_score=similarity_score,
        volatility_score=volatility_score,
        anomaly_score=anomaly_score,
        top_risk_drivers=risk_drivers,
        matched_signatures=matched_sigs,
        monitoring_checks=monitoring_checks,
        rollback_thresholds=rollback_thresholds,
        rollout_guidance=rollout_guidance,
        evidence=evidence,
    )


def _build_risk_drivers(
    ranked_sigs: list[tuple[RevertSignature, float]],
    anomalous: list[str],
    elevated: list[str],
    volatility: list[tuple[str, float, str]],
) -> list[str]:
    """Generate human-readable top risk drivers."""
    drivers = []

    if ranked_sigs:
        top = ranked_sigs[0][0]
        drivers.append(
            f"High similarity to past rollback {top.revert_id} "
            f"({top.feature}, {top.date[:10]}): {top.description}"
        )

    if anomalous:
        drivers.append(
            f"Current anomalies detected in: {', '.join(anomalous)}"
        )

    if elevated:
        drivers.append(
            f"Elevated (but not anomalous) metrics: {', '.join(elevated)}"
        )

    high_vol = [sli for sli, _, level in volatility if level == "high"]
    if high_vol:
        drivers.append(
            f"High baseline volatility in: {', '.join(high_vol)} "
            f"(harder to detect regressions quickly)"
        )

    if len(ranked_sigs) >= 2:
        second = ranked_sigs[1][0]
        drivers.append(
            f"Secondary pattern match: {second.revert_id} ({second.feature})"
        )

    return drivers[:5]


def _build_monitoring_checks(
    anomalous: list[str],
    elevated: list[str],
    baselines: dict[str, dict],
    ranked_sigs: list[tuple[RevertSignature, float]],
) -> list[str]:
    """Recommend specific monitoring checks."""
    checks = []

    # Always monitor anomalous SLIs
    for sli in anomalous:
        bl = baselines.get(sli, {})
        checks.append(
            f"CRITICAL: Monitor {sli} — currently anomalous "
            f"(baseline avg: {bl.get('avg', '?')})"
        )

    for sli in elevated:
        bl = baselines.get(sli, {})
        checks.append(
            f"WARNING: Watch {sli} — elevated above baseline "
            f"(baseline avg: {bl.get('avg', '?')})"
        )

    # Add SLIs from top matched signatures
    sig_slis = set()
    for sig, _ in ranked_sigs[:2]:
        sig_slis |= sig.sli_names
    for sli in sig_slis - set(anomalous) - set(elevated):
        checks.append(
            f"WATCH: Monitor {sli} — impacted in similar past rollback"
        )

    if not checks:
        checks.append("Standard monitoring: all key SLIs within normal range")

    return checks


def _build_rollback_thresholds(
    baselines: dict[str, dict],
    current_health: dict[str, dict],
) -> list[dict[str, Any]]:
    """Suggest automatic rollback thresholds."""
    thresholds = []
    for sli, bl in baselines.items():
        avg = bl.get("avg", 0)
        p99 = bl.get("p99", avg * 2)
        stddev = bl.get("stddev", avg * 0.1)
        # Rollback if metric exceeds p99 + 2*stddev
        rollback_at = round(p99 + 2 * stddev, 2)
        # Warning at p99
        warn_at = round(p99, 2)

        current = current_health.get(sli, {}).get("current_value", avg)

        thresholds.append({
            "sli": sli,
            "baseline_avg": avg,
            "warn_threshold": warn_at,
            "rollback_threshold": rollback_at,
            "current_value": current,
            "status": (
                "BREACH" if current > rollback_at
                else "WARNING" if current > warn_at
                else "OK"
            ),
        })
    return thresholds

