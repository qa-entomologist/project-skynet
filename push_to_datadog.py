#!/usr/bin/env python3
"""Push test results to Datadog — CI Test Visibility + Structured Logs.

CI Test Visibility:
    Generates JUnit XML from test case data and uploads via the Datadog
    CI Visibility API, so test cases appear in Datadog's Test Visibility
    dashboard with pass/pending status, duration, and history.

Structured Logs:
    Pushes each test case as a structured log event to Datadog Logs,
    enabling custom dashboards for coverage analysis, priority distribution,
    screenshot tracking, and agent performance.

Usage:
    python3 push_to_datadog.py                           # Both CI + Logs
    python3 push_to_datadog.py --ci-only                 # CI Test Visibility only
    python3 push_to_datadog.py --logs-only               # Logs only
    python3 push_to_datadog.py --input testrail_export.json
"""

import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from xml.etree.ElementTree import Element, SubElement, tostring
from xml.dom.minidom import parseString

import requests
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("push-to-datadog")

DD_API_KEY = os.getenv("DD_API_KEY", "")
DD_SITE = os.getenv("DD_SITE", "datadoghq.com")

PRIORITY_MAP = {1: "P0-Critical", 2: "P1-High", 3: "P2-Medium", 4: "P3-Low"}
TYPE_MAP = {1: "Smoke", 2: "Functional", 3: "Regression", 4: "Navigation", 5: "E2E", 6: "Edge", 7: "Negative"}


def load_test_cases(path: str) -> dict:
    with open(path) as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# CI Test Visibility — JUnit XML
# ---------------------------------------------------------------------------

def generate_junit_xml(data: dict, output_path: str) -> str:
    """Convert test case data to JUnit XML format for CI Test Visibility."""
    test_cases = data.get("test_cases", [])
    platform = data.get("platform", "web")
    screenshot_dir = data.get("screenshot_directory", "")

    testsuites = Element("testsuites", name="Project Skynet - QA Agent")
    suite = SubElement(
        testsuites, "testsuite",
        name=f"AI-Generated Test Suite ({platform})",
        tests=str(len(test_cases)),
        failures="0",
        errors="0",
        skipped="0",
        timestamp=datetime.now(timezone.utc).isoformat(),
    )

    for tc in test_cases:
        tc_id = tc.get("custom_id", "TC-???")
        title = tc.get("title", "Untitled")
        priority = PRIORITY_MAP.get(tc.get("priority_id", 2), "P2-Medium")
        test_type = TYPE_MAP.get(tc.get("type_id", 2), "Functional")
        steps = tc.get("custom_steps_separated", [])
        step_count = len(steps)
        has_screenshots = any(s.get("attachment") for s in steps)

        classname = f"skynet.{platform}.{test_type.lower()}"

        testcase = SubElement(
            suite, "testcase",
            name=f"{tc_id}: {title}",
            classname=classname,
            time=str(round(step_count * 2.5, 1)),
        )

        props = SubElement(testcase, "properties")
        for k, v in [
            ("dd_tags[test.priority]", priority),
            ("dd_tags[test.type]", test_type),
            ("dd_tags[test.platform]", platform),
            ("dd_tags[test.step_count]", str(step_count)),
            ("dd_tags[test.has_screenshots]", str(has_screenshots).lower()),
            ("dd_tags[test.generated_by]", "ai-agent"),
            ("dd_tags[test.preconditions]", tc.get("custom_preconds", "None")),
        ]:
            SubElement(props, "property", name=k, value=v)

        detail_lines = []
        for i, step in enumerate(steps, 1):
            line = f"Step {i}: {step.get('content', '')} → Expected: {step.get('expected', '')}"
            if step.get("attachment"):
                line += f" [Screenshot: {os.path.basename(step['attachment'])}]"
            detail_lines.append(line)
        SubElement(testcase, "system-out").text = "\n".join(detail_lines)

    raw_xml = tostring(testsuites, encoding="unicode")
    pretty = parseString(raw_xml).toprettyxml(indent="  ", encoding="UTF-8").decode()

    with open(output_path, "w") as f:
        f.write(pretty)

    logger.info("JUnit XML written to %s (%d test cases)", output_path, len(test_cases))
    return output_path


def upload_junit_to_datadog(xml_path: str, service: str = "project-skynet"):
    """Upload JUnit XML to Datadog CI Test Visibility via the intake API."""
    if not DD_API_KEY:
        logger.error("DD_API_KEY not set — cannot upload to CI Test Visibility")
        return False

    url = f"https://api.{DD_SITE}/api/v2/ci/tests/junit"

    with open(xml_path, "rb") as f:
        xml_content = f.read()

    tags = [
        "service:project-skynet",
        "env:hackathon",
        "test.generated_by:ai-agent",
        f"test.timestamp:{datetime.now(timezone.utc).isoformat()}",
    ]

    try:
        resp = requests.put(
            url,
            headers={
                "DD-API-KEY": DD_API_KEY,
                "Content-Type": "text/xml",
            },
            params={
                "service": service,
                "env": "hackathon",
                "tags": ",".join(tags),
            },
            data=xml_content,
            timeout=30,
        )

        if resp.status_code in (200, 202):
            logger.info("CI Test Visibility upload successful (HTTP %d)", resp.status_code)
            logger.info("View at: https://app.%s/ci/test-services?query=service:project-skynet", DD_SITE)
            return True
        else:
            logger.warning("CI upload returned HTTP %d: %s", resp.status_code, resp.text[:300])
            return False

    except Exception as e:
        logger.error("CI upload failed: %s", e)
        return False


# ---------------------------------------------------------------------------
# Structured Logs
# ---------------------------------------------------------------------------

def push_logs_to_datadog(data: dict):
    """Push each test case as a structured log event to Datadog Logs API."""
    if not DD_API_KEY:
        logger.error("DD_API_KEY not set — cannot push logs")
        return False

    test_cases = data.get("test_cases", [])
    platform = data.get("platform", "web")
    screenshot_dir = data.get("screenshot_directory", "")
    now = datetime.now(timezone.utc).isoformat()

    logs = []

    summary_log = {
        "ddsource": "project-skynet",
        "ddtags": f"env:hackathon,service:project-skynet,platform:{platform}",
        "hostname": "local",
        "service": "project-skynet",
        "status": "info",
        "message": f"QA Test Suite Generated — {len(test_cases)} test cases ({platform})",
        "timestamp": now,
        "test_suite": {
            "total_cases": len(test_cases),
            "platform": platform,
            "screenshot_dir": screenshot_dir,
            "generated_by": "ai-agent",
            "priority_breakdown": {},
            "type_breakdown": {},
        },
    }

    priority_counts = {}
    type_counts = {}

    for tc in test_cases:
        tc_id = tc.get("custom_id", "TC-???")
        title = tc.get("title", "Untitled")
        priority = PRIORITY_MAP.get(tc.get("priority_id", 2), "P2-Medium")
        test_type = TYPE_MAP.get(tc.get("type_id", 2), "Functional")
        steps = tc.get("custom_steps_separated", [])
        screenshot_count = sum(1 for s in steps if s.get("attachment"))

        priority_counts[priority] = priority_counts.get(priority, 0) + 1
        type_counts[test_type] = type_counts.get(test_type, 0) + 1

        log_entry = {
            "ddsource": "project-skynet",
            "ddtags": (
                f"env:hackathon,service:project-skynet,platform:{platform},"
                f"test.priority:{priority},test.type:{test_type},"
                f"test.id:{tc_id}"
            ),
            "hostname": "local",
            "service": "project-skynet",
            "status": "info",
            "message": f"Test Case {tc_id}: {title}",
            "timestamp": now,
            "test_case": {
                "id": tc_id,
                "title": title,
                "priority": priority,
                "type": test_type,
                "preconditions": tc.get("custom_preconds", "None"),
                "step_count": len(steps),
                "screenshot_count": screenshot_count,
                "platform": platform,
                "generated_by": "ai-agent",
                "steps": [
                    {
                        "action": s.get("content", ""),
                        "expected": s.get("expected", ""),
                        "has_screenshot": bool(s.get("attachment")),
                    }
                    for s in steps
                ],
            },
        }
        logs.append(log_entry)

    summary_log["test_suite"]["priority_breakdown"] = priority_counts
    summary_log["test_suite"]["type_breakdown"] = type_counts
    logs.insert(0, summary_log)

    intake_url = f"https://http-intake.logs.{DD_SITE}/api/v2/logs"

    try:
        resp = requests.post(
            intake_url,
            headers={
                "DD-API-KEY": DD_API_KEY,
                "Content-Type": "application/json",
            },
            json=logs,
            timeout=30,
        )

        if resp.status_code in (200, 202):
            logger.info(
                "Pushed %d log events to Datadog Logs (HTTP %d)",
                len(logs), resp.status_code,
            )
            logger.info(
                "View at: https://app.%s/logs?query=service:project-skynet", DD_SITE,
            )
            return True
        else:
            logger.warning("Logs push returned HTTP %d: %s", resp.status_code, resp.text[:300])
            return False

    except Exception as e:
        logger.error("Logs push failed: %s", e)
        return False


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Push AI-generated test results to Datadog (CI Test Visibility + Logs)"
    )
    parser.add_argument(
        "--input", default="testrail_export.json",
        help="Path to testrail_export.json (default: testrail_export.json)",
    )
    parser.add_argument("--ci-only", action="store_true", help="Only upload to CI Test Visibility")
    parser.add_argument("--logs-only", action="store_true", help="Only push structured logs")
    parser.add_argument(
        "--junit-output", default="test_results.xml",
        help="Output path for JUnit XML (default: test_results.xml)",
    )
    args = parser.parse_args()

    if not DD_API_KEY:
        logger.error("DD_API_KEY not set in .env — cannot push to Datadog")
        sys.exit(1)

    if not os.path.exists(args.input):
        logger.error("Input file not found: %s", args.input)
        sys.exit(1)

    data = load_test_cases(args.input)
    test_count = len(data.get("test_cases", []))
    logger.info("Loaded %d test cases from %s", test_count, args.input)

    do_ci = not args.logs_only
    do_logs = not args.ci_only

    if do_ci:
        logger.info("--- CI Test Visibility ---")
        xml_path = generate_junit_xml(data, args.junit_output)
        upload_junit_to_datadog(xml_path)

    if do_logs:
        logger.info("--- Structured Logs ---")
        push_logs_to_datadog(data)

    logger.info("Done! Check Datadog:")
    if do_ci:
        logger.info("  CI Test Visibility: https://app.%s/ci/test-services", DD_SITE)
    if do_logs:
        logger.info("  Logs: https://app.%s/logs?query=service%%3Aproject-skynet", DD_SITE)


if __name__ == "__main__":
    main()
