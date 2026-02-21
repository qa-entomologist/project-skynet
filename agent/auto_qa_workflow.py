"""
Auto-QA Workflow – automatically detects crashes, analyzes code, and tests reproducibility.

This is the main workflow that ties together:
1. Anomaly detection from Datadog
2. Code analysis using Bedrock
3. Reproduction testing in alpha/production

When a crash/anomaly is detected, this workflow:
1. Detects the anomaly from Datadog
2. Analyzes code to determine if reproducible
3. Tests reproduction in alpha/production
4. Generates a comprehensive QA report
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from agent.anomaly_detector import (
    detect_anomalies,
    fetch_crash_details,
    fetch_recent_deployments,
)
from agent.code_analyzer import analyze_crash_reproducibility
from agent.reproduction_tester import test_reproduction, test_web_reproduction
from agent.observability import start_run, logger
from agent.bedrock_summarizer import generate_report
from agent.risk_model import RiskAssessment


def run_auto_qa_workflow(
    service: str,
    platform: str | None = None,
    lookback_minutes: int = 15,
    test_environment: str = "alpha",  # "alpha" or "production"
    code_repo_path: str | None = None,
    base_url: str | None = None,
) -> dict[str, Any]:
    """
    Run the complete auto-QA workflow:
    1. Detect anomalies/crashes
    2. Analyze code for reproducibility
    3. Test reproduction in target environment
    4. Generate QA report
    
    Args:
        service: Service to monitor
        platform: Platform filter (ios/android/web)
        lookback_minutes: How far back to look for anomalies
        test_environment: Environment to test in (alpha/production)
        code_repo_path: Path to code repository for analysis
        base_url: Base URL for website testing (e.g., https://tubi.tv) - enables real browser testing with Playwright
    
    Returns:
        Complete QA report with detection, analysis, and test results
    """
    run_ctx = start_run({
        "workflow": "auto_qa",
        "service": service,
        "platform": platform,
        "test_environment": test_environment,
    })
    
    try:
        logger.info(f"[{run_ctx.run_id}] Starting auto-QA workflow for {service}...")
        
        # ── Step 1: Detect anomalies and crashes ──
        logger.info(f"[{run_ctx.run_id}] Step 1: Detecting anomalies...")
        anomalies = detect_anomalies(service, lookback_minutes)
        
        if not anomalies:
            logger.info(f"[{run_ctx.run_id}] No anomalies detected")
            no_report = {
                "run_id": run_ctx.run_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "status": "no_anomalies",
                "service": service,
                "message": "No anomalies or crashes detected in the specified time window",
            }
            import json, os
            web_report = os.path.join(os.path.dirname(os.path.dirname(__file__)), "web", "auto_qa_report.json")
            try:
                with open(web_report, "w") as f:
                    json.dump(no_report, f, indent=2, default=str)
            except Exception:
                pass
            return no_report
        
        logger.info(f"[{run_ctx.run_id}] Found {len(anomalies)} anomalies")
        
        # Process each anomaly
        results = []
        for anomaly in anomalies:
            logger.info(f"[{run_ctx.run_id}] Processing anomaly: {anomaly.get('type')} - {anomaly.get('description')}")
            
            # Get detailed crash information
            crash_details = fetch_crash_details(
                service=service,
                platform=platform,
                lookback_minutes=lookback_minutes,
            )
            
            if not crash_details:
                # Use anomaly as crash details
                crash_details = [anomaly]
            
            # Get recent deployments
            deployments = fetch_recent_deployments(service, lookback_hours=24)
            recent_deployment = deployments[0] if deployments else None
            
            # Process each crash
            for crash in crash_details:
                result = _process_crash(
                    crash=crash,
                    deployment=recent_deployment,
                    code_repo_path=code_repo_path,
                    test_environment=test_environment,
                    service=service,
                    run_id=run_ctx.run_id,
                    base_url=base_url,
                )
                results.append(result)
        
        # ── Generate summary report ──
        summary = _generate_qa_summary(results, service, run_ctx.run_id)
        
        # ── Finish observability ──
        run_ctx.finish(
            risk_score=summary.get("overall_risk_score", 0),
            recommendation=summary.get("recommendation", "investigate"),
            evidence=[f"Processed {len(results)} crashes"],
        )
        
        report = {
            "run_id": run_ctx.run_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": "completed",
            "service": service,
            "anomalies_detected": len(anomalies),
            "crashes_processed": len(results),
            "results": results,
            "summary": summary,
        }
        
        import json, os
        web_report = os.path.join(os.path.dirname(os.path.dirname(__file__)), "web", "auto_qa_report.json")
        try:
            with open(web_report, "w") as f:
                json.dump(report, f, indent=2, default=str)
            logger.info(f"[{run_ctx.run_id}] Dashboard report written to {web_report}")
        except Exception as e:
            logger.warning(f"Could not write dashboard report: {e}")
        
        return report
    
    except Exception as e:
        logger.error(f"[{run_ctx.run_id}] Auto-QA workflow failed: {e}")
        run_ctx.finish(risk_score=-1, recommendation="error", evidence=[str(e)])
        raise


def _process_crash(
    crash: dict[str, Any],
    deployment: dict[str, Any] | None,
    code_repo_path: str | None,
    test_environment: str,
    service: str,
    run_id: str,
    base_url: str | None = None,
) -> dict[str, Any]:
    """Process a single crash through the full workflow."""
    
    # ── Step 2: Analyze code for reproducibility ──
    logger.info(f"[{run_id}] Analyzing code for crash: {crash.get('crash_id', 'unknown')}")
    code_analysis = analyze_crash_reproducibility(
        crash_details=crash,
        deployment_info=deployment,
        code_repo_path=code_repo_path,
    )
    
    if not code_analysis.get("is_reproducible"):
        logger.info(f"[{run_id}] Crash determined NOT reproducible based on code analysis")
        return {
            "crash_id": crash.get("crash_id", "unknown"),
            "status": "not_reproducible",
            "code_analysis": code_analysis,
            "reproduction_test": None,
            "qa_recommendation": "No action needed - crash not reproducible based on code analysis",
        }
    
    # ── Step 3: Test reproduction ──
    logger.info(f"[{run_id}] Testing reproduction in {test_environment}...")
    
    reproduction_steps = code_analysis.get("reproduction_steps", [])
    if not reproduction_steps:
        # Generate basic steps from crash info
        reproduction_steps = [
            f"Navigate to {service}",
            f"Trigger action that causes: {crash.get('error_message', 'crash')}",
        ]
    
    # Determine test method: use browser testing if base_url is provided
    if base_url:
        # Use real browser testing with Playwright
        logger.info(f"[{run_id}] Using browser automation to test: {base_url}")
        test_result = test_web_reproduction(
            crash_details=crash,
            reproduction_steps=reproduction_steps,
            base_url=base_url,
            environment=test_environment,
        )
    elif "web" in service.lower() or "http" in crash.get("description", "").lower():
        # Fallback: use browser testing with default URL if service appears web-based
        test_result = test_web_reproduction(
            crash_details=crash,
            reproduction_steps=reproduction_steps,
            base_url=f"https://{test_environment}.example.com",
            environment=test_environment,
        )
    else:
        # Use mock/API testing
        test_result = test_reproduction(
            crash_details=crash,
            reproduction_steps=reproduction_steps,
            environment=test_environment,
            service=service,
        )
    
    # ── Step 4: Generate QA recommendation ──
    qa_recommendation = _generate_qa_recommendation(
        code_analysis=code_analysis,
        test_result=test_result,
        crash=crash,
    )
    
    return {
        "crash_id": crash.get("crash_id", "unknown"),
        "status": "processed",
        "code_analysis": code_analysis,
        "reproduction_test": test_result,
        "qa_recommendation": qa_recommendation,
        "severity": crash.get("severity", "medium"),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def _generate_qa_recommendation(
    code_analysis: dict[str, Any],
    test_result: dict[str, Any],
    crash: dict[str, Any],
) -> str:
    """Generate QA recommendation based on analysis and test results."""
    
    reproduced = test_result.get("reproduced", False)
    confidence = code_analysis.get("confidence", 0.5)
    
    if reproduced:
        return (
            f"✅ CONFIRMED REPRODUCIBLE - Crash successfully reproduced in test environment. "
            f"Confidence: {confidence:.0%}. "
            f"Root cause: {code_analysis.get('likely_cause', 'Unknown')}. "
            f"Immediate action: Block release and fix identified issue in {', '.join(code_analysis.get('affected_files', [])[:3])}."
        )
    elif confidence > 0.7:
        return (
            f"⚠️ LIKELY REPRODUCIBLE - High confidence ({confidence:.0%}) based on code analysis, "
            f"but not reproduced in test. Root cause: {code_analysis.get('likely_cause', 'Unknown')}. "
            f"Recommendation: Manual QA verification required. Check: {', '.join(code_analysis.get('affected_files', [])[:3])}."
        )
    elif confidence > 0.4:
        return (
            f"⚠️ POSSIBLY REPRODUCIBLE - Moderate confidence ({confidence:.0%}). "
            f"Code analysis suggests potential issue. Recommendation: Manual QA investigation recommended."
        )
    else:
        return (
            f"ℹ️ UNCLEAR - Low confidence ({confidence:.0%}) that crash is reproducible. "
            f"Code analysis inconclusive. Recommendation: Monitor and investigate if crash rate increases."
        )


def _generate_qa_summary(
    results: list[dict[str, Any]],
    service: str,
    run_id: str,
) -> dict[str, Any]:
    """Generate summary of all processed crashes."""
    
    total = len(results)
    reproduced = sum(1 for r in results if r.get("reproduction_test", {}).get("reproduced", False))
    not_reproducible = sum(1 for r in results if r.get("status") == "not_reproducible")
    needs_manual_qa = total - reproduced - not_reproducible
    
    # Calculate overall risk
    if reproduced > 0:
        overall_risk_score = 80
        recommendation = "BLOCK_RELEASE"
    elif needs_manual_qa > 0:
        overall_risk_score = 50
        recommendation = "MANUAL_QA_REQUIRED"
    else:
        overall_risk_score = 20
        recommendation = "MONITOR"
    
    return {
        "overall_risk_score": overall_risk_score,
        "recommendation": recommendation,
        "total_crashes": total,
        "reproduced": reproduced,
        "not_reproducible": not_reproducible,
        "needs_manual_qa": needs_manual_qa,
        "summary_message": (
            f"Processed {total} crashes: {reproduced} confirmed reproducible, "
            f"{not_reproducible} not reproducible, {needs_manual_qa} need manual QA"
        ),
    }

