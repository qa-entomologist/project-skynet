#!/usr/bin/env python3
"""Mobile Cartographer - AI-powered mobile app exploration agent.

Supports both Android (emulator) and iOS (simulator).

Prerequisites:
    1. Emulator/simulator running
    2. Appium server running (`appium`)
    3. Driver installed:
       - Android: `appium driver install uiautomator2`
       - iOS:     `appium driver install xcuitest`

Usage:
    # Android APK
    python3 run_mobile.py app.apk

    # Android installed app
    python3 run_mobile.py --package com.tubi.tv

    # iOS .app (simulator)
    python3 run_mobile.py TubiTV.app --platform ios

    # iOS installed app
    python3 run_mobile.py --bundle-id com.tubi.tv --platform ios
"""

import argparse
import importlib
import json
import logging
import os
import sys

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("mobile-cartographer")


def setup_datadog_telemetry():
    """Configure OpenTelemetry to ship traces to Datadog LLM Observability."""
    from src.config import DD_API_KEY, get_otlp_endpoint

    if not DD_API_KEY:
        logger.info("DD_API_KEY not set - skipping Datadog telemetry")
        return

    endpoint = get_otlp_endpoint()
    os.environ["OTEL_SEMCONV_STABILITY_OPT_IN"] = "gen_ai_latest_experimental"
    os.environ["OTEL_EXPORTER_OTLP_TRACES_PROTOCOL"] = "http/protobuf"
    os.environ["OTEL_EXPORTER_OTLP_TRACES_ENDPOINT"] = endpoint
    os.environ["OTEL_EXPORTER_OTLP_TRACES_HEADERS"] = (
        f"dd-api-key={DD_API_KEY},dd-otlp-source=llmobs"
    )

    try:
        from strands.telemetry import StrandsTelemetry

        telemetry = StrandsTelemetry()
        telemetry.setup_otlp_exporter()
        logger.info("Datadog LLM Observability enabled (endpoint: %s)", endpoint)
    except Exception as e:
        logger.warning("Failed to initialize Datadog telemetry: %s", e)


def main():
    parser = argparse.ArgumentParser(
        description="Mobile Cartographer - AI agent that explores mobile apps and generates QA test cases"
    )
    parser.add_argument(
        "app", nargs="?", default=None,
        help="Path to an APK (Android) or .app/.ipa (iOS) file",
    )
    parser.add_argument(
        "--platform", choices=["android", "ios"], default=None,
        help="Target platform (auto-detected from file extension if omitted)",
    )
    parser.add_argument(
        "--package", default=None,
        help="Android package name for an already-installed app (e.g. com.tubi.tv)",
    )
    parser.add_argument(
        "--bundle-id", default=None,
        help="iOS bundle identifier for an already-installed app (e.g. com.tubi.tv)",
    )
    parser.add_argument("--activity", default=None, help="Android launch activity")
    parser.add_argument("--max-depth", type=int, default=None)
    parser.add_argument("--max-pages", type=int, default=None)
    parser.add_argument("--no-datadog", action="store_true", help="Disable Datadog telemetry")
    parser.add_argument("--appium-url", default=None, help="Appium server URL")
    args = parser.parse_args()

    if not args.app and not args.package and not args.bundle_id:
        parser.error("Provide an app path, --package (Android), or --bundle-id (iOS)")

    # Infer platform
    platform = args.platform
    if not platform:
        if args.bundle_id:
            platform = "ios"
        elif args.package:
            platform = "android"
        elif args.app:
            ext = os.path.splitext(args.app)[1].lower()
            platform = "ios" if ext in (".app", ".ipa") else "android"
        else:
            platform = "android"

    # Separate app path by platform
    apk_path = args.app if platform == "android" and args.app else None
    app_path = args.app if platform == "ios" and args.app else None

    if args.max_depth:
        os.environ["MAX_DEPTH"] = str(args.max_depth)
    if args.max_pages:
        os.environ["MAX_PAGES"] = str(args.max_pages)
    if args.appium_url:
        os.environ["APPIUM_URL"] = args.appium_url

    if not args.no_datadog:
        setup_datadog_telemetry()

    import src.config
    importlib.reload(src.config)

    from src.mobile_manager import mobile
    from src.mobile_agent import create_mobile_agent, graph_store

    target = args.app or args.package or args.bundle_id
    logger.info("=" * 60)
    logger.info("  Mobile Cartographer")
    logger.info("  Platform: %s", platform.upper())
    logger.info("  Target: %s", target)
    logger.info("  Max Depth: %s | Max Screens: %s", src.config.MAX_DEPTH, src.config.MAX_PAGES)
    logger.info("=" * 60)

    mobile.start(
        platform=platform,
        apk_path=apk_path,
        app_path=app_path,
        app_package=args.package,
        app_activity=args.activity,
        bundle_id=args.bundle_id,
    )

    try:
        agent = create_mobile_agent()

        prompt = (
            f"Explore the {platform} app that has just been launched. "
            f"Systematically discover all major screens, user flows, and navigation paths. "
            f"For every screen, classify its type and record detailed QA observations. "
            f"For every tap, state what you expect to happen. "
            f"Use swipe to discover hidden content (scroll, carousels). "
            f"When done exploring, call generate_test_cases, then write_test_report, "
            f"then export_testrail_json."
        )

        logger.info("Starting %s exploration...", platform)
        result = agent(prompt)

        logger.info("Exploration complete!")
        logger.info("Final stats: %s", json.dumps(graph_store.get_stats(), indent=2))

        graph_json = graph_store.to_json()
        export_path = os.path.join(os.path.dirname(__file__), "web", "graph_data.json")
        os.makedirs(os.path.dirname(export_path), exist_ok=True)
        with open(export_path, "w") as f:
            f.write(graph_json)
        logger.info("Graph exported to %s", export_path)

        report_path = os.path.join(os.path.dirname(__file__), "test_cases_mobile.md")
        if os.path.exists(report_path):
            logger.info("QA Test Report: %s", report_path)

        testrail_path = os.path.join(os.path.dirname(__file__), "testrail_export_mobile.json")
        if os.path.exists(testrail_path):
            logger.info("TestRail Export: %s", testrail_path)

        logger.info("Screenshots: %s", mobile.run_dir)

    except KeyboardInterrupt:
        logger.info("\nExploration interrupted. Saving progress...")
        graph_json = graph_store.to_json()
        export_path = os.path.join(os.path.dirname(__file__), "web", "graph_data.json")
        with open(export_path, "w") as f:
            f.write(graph_json)
        logger.info("Partial graph saved to %s", export_path)

    except Exception as e:
        logger.error("Exploration failed: %s", e, exc_info=True)
        sys.exit(1)

    finally:
        mobile.stop()
        logger.info("Appium session closed.")


if __name__ == "__main__":
    main()
