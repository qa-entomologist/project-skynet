#!/usr/bin/env python3
"""
Quick CLI runner for the Release Revert Risk Advisor agent.

Usage:
    python run.py                                  # Demo with defaults
    python run.py --feature "my-feature" --service "playback-service"
    python run.py --server                         # Start the FastAPI server
"""

import argparse
import json
import sys


def run_assessment(args):
    """Run the agent directly."""
    from agent.main import run_agent

    print("\n" + "═" * 60)
    print("  🛡️  Release Revert Risk Advisor")
    print("═" * 60 + "\n")

    result = run_agent(
        feature_name=args.feature,
        service=args.service,
        platform=args.platform,
        time_window_days=args.window,
        tags=args.tags.split(",") if args.tags else None,
        post_deploy_minutes=args.post_deploy,
    )

    # Pretty print key results
    print("\n" + "─" * 60)
    score = result["risk_score"]
    rec = result["recommendation"].upper()
    color = "\033[92m" if rec == "SHIP" else "\033[93m" if rec == "RAMP" else "\033[91m"
    reset = "\033[0m"

    print(f"\n  Risk Score: {color}{score}/100{reset}")
    print(f"  Recommendation: {color}{rec}{reset}")
    print(f"\n  Feature: {result['feature_name']}")
    print(f"  Service: {result['service']}")
    print(f"  Platform: {result['platform']}")

    print(f"\n  📊 Score Breakdown:")
    sb = result["scoring_breakdown"]
    print(f"     Similarity: {sb['similarity']}/50")
    print(f"     Volatility: {sb['volatility']}/30")
    print(f"     Anomaly:    {sb['anomaly']}/20")

    if result.get("risk_drivers"):
        print(f"\n  ⚡ Top Risk Drivers:")
        for i, d in enumerate(result["risk_drivers"][:3], 1):
            print(f"     {i}. {d}")

    if result.get("matched_patterns"):
        print(f"\n  🔄 Similar Past Incidents:")
        for m in result["matched_patterns"][:2]:
            print(f"     • {m['revert_id']} - {m['feature']} ({m['similarity']:.0%} match)")

    print(f"\n  🚀 Rollout Guidance:")
    print(f"     {result['rollout_guidance']}")

    print(f"\n  🤖 Agent Metrics:")
    am = result.get("agent_metrics", {})
    print(f"     Latency: {am.get('latency_ms', '?')}ms")
    print(f"     DD Queries: {am.get('dd_query_count', '?')}")
    print(f"     Signatures Matched: {am.get('signatures_matched', '?')}")

    print("\n" + "═" * 60)
    print(f"  📄 Full report saved to: evals/run_{result['run_id']}.json")
    print("═" * 60 + "\n")

    return result


def start_server(args):
    """Start the FastAPI server."""
    import uvicorn
    print("\n🚀 Starting Release Revert Risk Advisor server...")
    print(f"   API: http://localhost:{args.port}/api/health")
    print(f"   UI:  http://localhost:{args.port}/")
    print()
    uvicorn.run("server.app:app", host="0.0.0.0", port=args.port, reload=True)


def run_auto_qa(args):
    """Run the auto-QA workflow."""
    from agent.auto_qa_workflow import run_auto_qa_workflow
    
    print("\n" + "═" * 70)
    print("  🤖 Auto-QA Workflow — Automatic Crash Detection & Testing")
    print("═" * 70 + "\n")
    
    # Show configuration
    print("📋 Configuration:")
    print(f"   Service:        {args.service}")
    print(f"   Platform:       {args.platform or 'all'}")
    print(f"   Environment:    {args.test_environment}")
    print(f"   Lookback:       {args.lookback_minutes} minutes")
    print(f"   Code Repo:      {args.code_repo_path or 'Not specified'}")
    print(f"   Base URL:       {args.base_url or 'Not specified (will use mock testing)'}")
    print()
    
    result = run_auto_qa_workflow(
        service=args.service,
        platform=args.platform,
        lookback_minutes=args.lookback_minutes,
        test_environment=args.test_environment,
        code_repo_path=args.code_repo_path,
        base_url=args.base_url,
    )
    
    # Pretty print results with visual indicators
    print("\n" + "─" * 70)
    status_emoji = "✅" if result.get('status') == 'completed' else "⚠️" if result.get('status') == 'no_anomalies' else "❌"
    print(f"  {status_emoji} Status: {result.get('status', 'unknown')}")
    print(f"  📦 Service: {result.get('service', 'unknown')}")
    print(f"  🔍 Anomalies Detected: {result.get('anomalies_detected', 0)}")
    print(f"  💥 Crashes Processed: {result.get('crashes_processed', 0)}")
    print()
    
    if result.get("summary"):
        summary = result["summary"]
        print(f"\n  📊 Summary:")
        print(f"     Overall Risk Score: {summary.get('overall_risk_score', 0)}/100")
        print(f"     Recommendation: {summary.get('recommendation', 'N/A')}")
        print(f"     {summary.get('summary_message', '')}")
    
    if result.get("results"):
        print(f"  🔍 Crash Analysis Results:")
        print("  " + "─" * 68)
        for i, crash_result in enumerate(result["results"][:3], 1):
            crash_id = crash_result.get('crash_id', 'unknown')
            status = crash_result.get('status', 'unknown')
            status_icon = "✅" if status == "processed" else "⏸️" if status == "not_reproducible" else "🔄"
            
            print(f"\n  {i}. {status_icon} Crash ID: {crash_id}")
            print(f"     Status: {status}")
            
            if crash_result.get("code_analysis"):
                ca = crash_result["code_analysis"]
                repro_icon = "✅" if ca.get('is_reproducible', False) else "❌"
                print(f"     📝 Code Analysis:")
                print(f"        • Reproducible: {repro_icon} {ca.get('is_reproducible', False)}")
                print(f"        • Confidence: {ca.get('confidence', 0):.0%}")
                if ca.get('likely_cause'):
                    print(f"        • Root Cause: {ca.get('likely_cause', 'Unknown')[:60]}...")
                if ca.get('affected_files'):
                    print(f"        • Affected Files: {', '.join(ca.get('affected_files', [])[:3])}")
            
            if crash_result.get("reproduction_test"):
                rt = crash_result["reproduction_test"]
                env = rt.get('environment', 'unknown')
                repro_icon = "✅" if rt.get('reproduced') else "❌"
                print(f"     🧪 Reproduction Test ({env} environment):")
                print(f"        • Result: {repro_icon} {'REPRODUCED' if rt.get('reproduced') else 'NOT REPRODUCED'}")
                if rt.get('error_encountered'):
                    print(f"        • Error: {rt.get('error_encountered', '')[:60]}...")
                if rt.get('test_duration_seconds'):
                    print(f"        • Duration: {rt.get('test_duration_seconds', 0)}s")
            
            if crash_result.get("qa_recommendation"):
                rec = crash_result['qa_recommendation']
                rec_icon = "🚨" if "CONFIRMED" in rec else "⚠️" if "LIKELY" in rec else "ℹ️"
                print(f"     {rec_icon} QA Recommendation:")
                print(f"        {rec[:80]}...")
    
    print("\n" + "═" * 60)
    print(f"  📄 Full report saved to: evals/run_{result['run_id']}.json")
    print("═" * 60 + "\n")
    
    return result


def main():
    parser = argparse.ArgumentParser(
        description="Release Revert Risk Advisor — AI Agent"
    )
    parser.add_argument("--server", action="store_true", help="Start the API server")
    parser.add_argument("--port", type=int, default=8000, help="Server port (default: 8000)")
    parser.add_argument("--auto-qa", action="store_true", help="Run auto-QA workflow (detect & test crashes)")
    
    # Risk assessment args
    parser.add_argument("--feature", default="playback-buffer-v2", help="Feature name")
    parser.add_argument("--service", default="playback-service", help="Service tag")
    parser.add_argument("--platform", default=None, help="Platform (ios/android/web)")
    parser.add_argument("--window", type=int, default=30, help="History window in days")
    parser.add_argument("--tags", default=None, help="Comma-separated tags")
    parser.add_argument("--post-deploy", type=int, default=60, help="Post-deploy minutes")
    
    # Auto-QA args
    parser.add_argument("--lookback-minutes", type=int, default=15, help="Lookback window for anomalies (minutes)")
    parser.add_argument("--test-environment", default="alpha", help="Test environment (alpha/production)")
    parser.add_argument("--code-repo-path", default=None, help="Path to code repository for analysis")
    parser.add_argument("--base-url", default=None, help="Base URL for website testing (e.g., https://tubi.tv) - enables real browser testing")

    args = parser.parse_args()

    if args.server:
        start_server(args)
    elif args.auto_qa:
        run_auto_qa(args)
    else:
        run_assessment(args)


if __name__ == "__main__":
    main()

