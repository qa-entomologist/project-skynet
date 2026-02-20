"""
Signature Builder – extracts "failure signatures" from historical revert events
and compares them against current feature context.

A signature captures:
    • which SLIs moved and by how much
    • which service / endpoints were involved
    • which platform was impacted
    • time-to-detection / time-to-rollback
    • semantic tags (ads, latency, cache, etc.)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class RevertSignature:
    """Fingerprint of a single historical rollback event."""

    revert_id: str
    date: str
    feature: str
    service: str
    platform: str
    description: str
    root_cause: str
    trigger: str  # monitor_alert | incident_manual
    time_to_detection_min: int
    time_to_rollback_min: int
    impacted_slis: dict[str, dict[str, float]]  # sli → {baseline, peak, unit}
    tags: list[str] = field(default_factory=list)

    # ── Derived metrics ──
    @property
    def sli_names(self) -> set[str]:
        return set(self.impacted_slis.keys())

    @property
    def max_spike_ratio(self) -> float:
        """Largest peak/baseline ratio across all impacted SLIs."""
        ratios = []
        for vals in self.impacted_slis.values():
            baseline = vals.get("baseline", 1) or 1
            peak = vals.get("peak", baseline)
            ratios.append(peak / baseline)
        return max(ratios) if ratios else 1.0

    @property
    def avg_spike_ratio(self) -> float:
        ratios = []
        for vals in self.impacted_slis.values():
            baseline = vals.get("baseline", 1) or 1
            peak = vals.get("peak", baseline)
            ratios.append(peak / baseline)
        return sum(ratios) / len(ratios) if ratios else 1.0

    @property
    def severity_tier(self) -> str:
        """Categorise severity based on spike magnitude."""
        r = self.max_spike_ratio
        if r >= 10:
            return "critical"
        elif r >= 4:
            return "high"
        elif r >= 2:
            return "medium"
        return "low"


def build_signatures(revert_events: list[dict[str, Any]]) -> list[RevertSignature]:
    """
    Convert raw revert event dicts (from Datadog or YAML) into structured
    RevertSignature objects.
    """
    signatures = []
    for ev in revert_events:
        sig = RevertSignature(
            revert_id=ev.get("id", "unknown"),
            date=ev.get("date", ""),
            feature=ev.get("feature", ""),
            service=ev.get("service", ""),
            platform=ev.get("platform", "all"),
            description=ev.get("description", ""),
            root_cause=ev.get("root_cause", ""),
            trigger=ev.get("trigger", "unknown"),
            time_to_detection_min=ev.get("time_to_detection_min", 0),
            time_to_rollback_min=ev.get("time_to_rollback_min", 0),
            impacted_slis=ev.get("impacted_slis", {}),
            tags=ev.get("tags", []),
        )
        signatures.append(sig)
    return signatures


def compute_similarity(
    signature: RevertSignature,
    current_service: str,
    current_platform: str | None,
    current_tags: list[str] | None,
    current_sli_health: dict[str, dict[str, Any]] | None = None,
) -> float:
    """
    Compute a similarity score (0.0 – 1.0) between a historical revert
    signature and the current release context.

    Factors:
        • service match                (0.30 weight)
        • platform match               (0.15 weight)
        • tag overlap                   (0.25 weight)
        • SLI overlap + direction match (0.30 weight)
    """
    score = 0.0

    # ── Service match ──
    if signature.service == current_service:
        score += 0.30
    elif current_service in signature.tags:
        score += 0.15

    # ── Platform match ──
    if current_platform:
        if signature.platform == current_platform or signature.platform == "all":
            score += 0.15
        elif current_platform == "all":
            score += 0.10

    # ── Tag overlap ──
    if current_tags:
        sig_tags = set(signature.tags)
        cur_tags = set(current_tags)
        overlap = sig_tags & cur_tags
        if sig_tags:
            tag_ratio = len(overlap) / len(sig_tags)
            score += 0.25 * tag_ratio

    # ── SLI overlap & direction ──
    if current_sli_health:
        sig_slis = signature.sli_names
        current_slis_elevated = {
            sli for sli, health in current_sli_health.items()
            if health.get("is_anomalous") or health.get("deviation_pct", 0) > 20
        }
        overlap_slis = sig_slis & current_slis_elevated
        if sig_slis:
            sli_ratio = len(overlap_slis) / len(sig_slis)
            score += 0.30 * sli_ratio

    return round(min(score, 1.0), 3)


def rank_signatures(
    signatures: list[RevertSignature],
    current_service: str,
    current_platform: str | None = None,
    current_tags: list[str] | None = None,
    current_sli_health: dict[str, dict[str, Any]] | None = None,
    top_n: int = 5,
) -> list[tuple[RevertSignature, float]]:
    """
    Rank signatures by similarity to current context, return top N.
    Returns list of (signature, similarity_score) tuples.
    """
    scored = []
    for sig in signatures:
        sim = compute_similarity(
            sig, current_service, current_platform, current_tags, current_sli_health
        )
        scored.append((sig, sim))

    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[:top_n]

