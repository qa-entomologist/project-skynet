#!/usr/bin/env python3
"""Web Cartographer - AI-powered website exploration agent.

Usage:
    python run.py https://www.example.com
    python run.py https://www.ebay.com --max-depth 3 --max-pages 20 --neo4j
"""

import argparse
import json
import logging
import os
import sys
import threading
import webbrowser
from functools import partial
from http.server import SimpleHTTPRequestHandler, HTTPServer

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("web-cartographer")


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


def start_viz_server(web_dir: str, port: int = 8080) -> HTTPServer | None:
    """Start a background HTTP server to serve the visualization at web_dir."""
    handler = partial(SimpleHTTPRequestHandler, directory=web_dir)
    handler.log_message = lambda *_args, **_kwargs: None  # silence request logs

    try:
        server = HTTPServer(("127.0.0.1", port), handler)
    except OSError:
        for fallback_port in range(port + 1, port + 10):
            try:
                server = HTTPServer(("127.0.0.1", fallback_port), handler)
                port = fallback_port
                break
            except OSError:
                continue
        else:
            logger.warning("Could not find an open port for the visualization server")
            return None

    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    logger.info("Live visualization: http://127.0.0.1:%d", port)
    return server


def main():
    parser = argparse.ArgumentParser(
        description="Web Cartographer - AI agent that explores websites and maps user flows"
    )
    parser.add_argument("url", help="Starting URL to explore (e.g. https://www.ebay.com)")
    parser.add_argument("--max-depth", type=int, default=None, help="Maximum exploration depth (default: 5)")
    parser.add_argument("--max-pages", type=int, default=None, help="Maximum pages to discover (default: 50)")
    parser.add_argument("--neo4j", action="store_true", help="Use Neo4j for graph storage")
    parser.add_argument("--headed", action="store_true", help="Run browser in headed mode (visible)")
    parser.add_argument("--no-datadog", action="store_true", help="Disable Datadog telemetry")
    parser.add_argument("--no-viz", action="store_true", help="Disable live visualization server")
    parser.add_argument("--viz-port", type=int, default=8080, help="Port for visualization server (default: 8080)")
    args = parser.parse_args()

    if args.max_depth:
        os.environ["MAX_DEPTH"] = str(args.max_depth)
    if args.max_pages:
        os.environ["MAX_PAGES"] = str(args.max_pages)
    if args.headed:
        os.environ["HEADLESS"] = "false"

    if not args.no_datadog:
        setup_datadog_telemetry()

    # Reload config after env overrides
    import importlib
    import src.config
    importlib.reload(src.config)

    if args.neo4j:
        import src.graph_store as gs
        import src.agent as agent_mod
        agent_mod.graph_store = gs.create_graph_store(use_neo4j=True)

    from src.browser_manager import browser
    from src.agent import create_explorer_agent, graph_store

    url = args.url
    if not url.startswith("http"):
        url = f"https://{url}"

    logger.info("=" * 60)
    logger.info("  Web Cartographer")
    logger.info("  Target: %s", url)
    logger.info("  Max Depth: %s | Max Pages: %s", src.config.MAX_DEPTH, src.config.MAX_PAGES)
    logger.info("=" * 60)

    viz_server = None
    web_dir = os.path.join(os.path.dirname(__file__), "web")
    if not args.no_viz:
        viz_server = start_viz_server(web_dir, port=args.viz_port)
        if viz_server:
            viz_url = f"http://127.0.0.1:{viz_server.server_address[1]}"
            webbrowser.open(viz_url)

    browser.start()
    try:
        agent = create_explorer_agent()

        prompt = (
            f"Explore the website at {url}. Systematically discover all major user flows, "
            f"page types, and navigation paths. For every page you visit, classify its type "
            f"and record detailed QA observations. For every click, state what you expect to happen. "
            f"When done exploring, call generate_test_cases, then call write_test_report with "
            f"a comprehensive QA test suite covering all discovered flows."
        )

        logger.info("Starting exploration...")
        result = agent(prompt)

        logger.info("Exploration complete!")
        logger.info("Final stats: %s", json.dumps(graph_store.get_stats(), indent=2))

        # Ensure graph is exported
        graph_json = graph_store.to_json()
        export_path = os.path.join(os.path.dirname(__file__), "web", "graph_data.json")
        with open(export_path, "w") as f:
            f.write(graph_json)
        logger.info("Graph exported to %s", export_path)
        if viz_server:
            logger.info("Visualization: http://127.0.0.1:%d", viz_server.server_address[1])
        else:
            logger.info("Open web/index.html in a browser to visualize the exploration graph.")

        report_path = os.path.join(os.path.dirname(__file__), "test_cases.md")
        if os.path.exists(report_path):
            logger.info("QA Test Report: %s", report_path)

        testrail_path = os.path.join(os.path.dirname(__file__), "testrail_export.json")
        if os.path.exists(testrail_path):
            logger.info("TestRail Export: %s", testrail_path)

        logger.info("Screenshots: %s", browser.run_dir)

    except KeyboardInterrupt:
        logger.info("\nExploration interrupted. Saving current progress...")
        graph_json = graph_store.to_json()
        export_path = os.path.join(os.path.dirname(__file__), "web", "graph_data.json")
        with open(export_path, "w") as f:
            f.write(graph_json)
        logger.info("Partial graph saved to %s", export_path)

    except Exception as e:
        logger.error("Exploration failed: %s", e, exc_info=True)
        sys.exit(1)

    finally:
        browser.stop()
        if viz_server:
            viz_server.shutdown()
        logger.info("Browser closed.")


if __name__ == "__main__":
    main()
