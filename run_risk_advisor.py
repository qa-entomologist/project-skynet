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


def main():
    parser = argparse.ArgumentParser(
        description="Release Revert Risk Advisor — AI Agent"
    )
    parser.add_argument("--server", action="store_true", help="Start the API server")
    parser.add_argument("--port", type=int, default=8000, help="Server port (default: 8000)")
    parser.add_argument("--feature", default="playback-buffer-v2", help="Feature name")
    parser.add_argument("--service", default="playback-service", help="Service tag")
    parser.add_argument("--platform", default=None, help="Platform (ios/android/web)")
    parser.add_argument("--window", type=int, default=30, help="History window in days")
    parser.add_argument("--tags", default=None, help="Comma-separated tags")
    parser.add_argument("--post-deploy", type=int, default=60, help="Post-deploy minutes")

    args = parser.parse_args()

    if args.server:
        start_server(args)
    else:
        run_assessment(args)


if __name__ == "__main__":
    main()

