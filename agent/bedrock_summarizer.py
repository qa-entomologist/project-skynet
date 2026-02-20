"""
Bedrock Summarizer – generates evidence-backed risk reports using
Amazon Bedrock (Claude). Falls back to a template-based summary
in demo mode or when Bedrock is unavailable.
"""

from __future__ import annotations

import json
from typing import Any

from agent.config import AWS_REGION, BEDROCK_MODEL_ID, AGENT_ENV
from agent.risk_model import RiskAssessment


def generate_report(
    assessment: RiskAssessment,
    feature_name: str,
    service: str,
    platform: str | None = None,
) -> dict[str, Any]:
    """
    Produce the final risk report.

    Returns a dict with:
        risk_score, recommendation, summary, risk_drivers,
        monitoring_checks, rollback_thresholds, rollout_guidance,
        matched_patterns, evidence
    """
    # Try Bedrock first; fall back to template
    summary = _generate_bedrock_summary(assessment, feature_name, service, platform)
    if summary is None:
        summary = _generate_template_summary(assessment, feature_name, service, platform)

    return {
        "feature_name": feature_name,
        "service": service,
        "platform": platform or "all",
        "risk_score": assessment.risk_score,
        "recommendation": assessment.recommendation,
        "summary": summary,
        "risk_drivers": assessment.top_risk_drivers,
        "monitoring_checks": assessment.monitoring_checks,
        "rollback_thresholds": assessment.rollback_thresholds,
        "rollout_guidance": assessment.rollout_guidance,
        "matched_patterns": assessment.matched_signatures,
        "scoring_breakdown": {
            "similarity": assessment.similarity_score,
            "volatility": assessment.volatility_score,
            "anomaly": assessment.anomaly_score,
        },
        "evidence": assessment.evidence,
    }


# ──────────────────────────────────────────────────────────────────────
# Bedrock (Claude) summarisation
# ──────────────────────────────────────────────────────────────────────

def _generate_bedrock_summary(
    assessment: RiskAssessment,
    feature_name: str,
    service: str,
    platform: str | None,
) -> str | None:
    """Call Amazon Bedrock to generate a natural-language risk summary."""
    if AGENT_ENV == "demo":
        return None  # Skip in demo mode

    try:
        import boto3

        client = boto3.client("bedrock-runtime", region_name=AWS_REGION)

        prompt = _build_prompt(assessment, feature_name, service, platform)

        body = json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 1024,
            "messages": [
                {"role": "user", "content": prompt}
            ],
        })

        response = client.invoke_model(
            modelId=BEDROCK_MODEL_ID,
            contentType="application/json",
            accept="application/json",
            body=body,
        )

        result = json.loads(response["body"].read())
        return result.get("content", [{}])[0].get("text", "")

    except Exception as e:
        print(f"[BedrockSummarizer] Failed: {e}")
        return None


def _build_prompt(
    assessment: RiskAssessment,
    feature_name: str,
    service: str,
    platform: str | None,
) -> str:
    matched = assessment.matched_signatures[:3]
    matched_text = "\n".join(
        f"  - {m['revert_id']} ({m['feature']}, {m['date'][:10]}): "
        f"{m['description']} [similarity: {m['similarity']}]"
        for m in matched
    )

    return f"""You are a Release Risk Advisor AI. Given the following data about a
pending release, produce a concise risk summary in 3-5 sentences.

Feature: {feature_name}
Service: {service}
Platform: {platform or 'all'}
Risk Score: {assessment.risk_score}/100
Recommendation: {assessment.recommendation}

Score Breakdown:
  - Similarity to past rollbacks: {assessment.similarity_score}/50
  - SLI volatility: {assessment.volatility_score}/30
  - Current anomalies: {assessment.anomaly_score}/20

Top Risk Drivers:
{chr(10).join(f'  - {d}' for d in assessment.top_risk_drivers)}

Matched Historical Rollback Patterns:
{matched_text or '  None found'}

Provide:
1. A plain-English summary of the risk
2. The single most important thing to watch
3. Whether this looks similar to a specific past incident and why
"""


# ──────────────────────────────────────────────────────────────────────
# Template fallback (no Bedrock required)
# ──────────────────────────────────────────────────────────────────────

def _generate_template_summary(
    assessment: RiskAssessment,
    feature_name: str,
    service: str,
    platform: str | None,
) -> str:
    """Generate a structured summary without LLM."""
    lines = []

    # Risk headline
    risk_label = {
        "ship": "LOW RISK",
        "ramp": "MODERATE RISK",
        "hold": "HIGH RISK",
    }.get(assessment.recommendation, "UNKNOWN")

    lines.append(
        f"🔍 Risk Assessment for \"{feature_name}\" on {service} "
        f"({platform or 'all platforms'}): "
        f"**{risk_label}** — Score {assessment.risk_score}/100"
    )
    lines.append("")

    # Recommendation
    rec_emoji = {"ship": "🟢", "ramp": "🟡", "hold": "🔴"}.get(assessment.recommendation, "⚪")
    lines.append(f"{rec_emoji} **Recommendation: {assessment.recommendation.upper()}**")
    lines.append(f"   {assessment.rollout_guidance}")
    lines.append("")

    # Top risk drivers
    if assessment.top_risk_drivers:
        lines.append("📊 **Top Risk Drivers:**")
        for i, driver in enumerate(assessment.top_risk_drivers[:3], 1):
            lines.append(f"   {i}. {driver}")
        lines.append("")

    # Similar incidents
    if assessment.matched_signatures:
        lines.append("🔄 **Similar Past Incidents:**")
        for m in assessment.matched_signatures[:2]:
            lines.append(
                f"   • {m['revert_id']} — \"{m['feature']}\" ({m['date'][:10]})"
            )
            lines.append(
                f"     Similarity: {m['similarity']:.0%} | "
                f"Severity: {m['severity']} | "
                f"Impacted: {', '.join(m['impacted_slis'])}"
            )
        lines.append("")

    # Score breakdown
    lines.append("📈 **Score Breakdown:**")
    lines.append(f"   • Pattern similarity: {assessment.similarity_score}/50")
    lines.append(f"   • SLI volatility: {assessment.volatility_score}/30")
    lines.append(f"   • Current anomalies: {assessment.anomaly_score}/20")

    return "\n".join(lines)

