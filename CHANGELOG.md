# Changelog

All notable changes to Project Skynet (Web Cartographer) must be documented in this file.

> **REQUIRED**: Every commit MUST include an update to this file. See [CONTRIBUTING.md](CONTRIBUTING.md).

## [Unreleased]

## [0.4.0] - 2026-02-20
### Added
- **Screenshot capture system** with meaningful, sequential naming (`step_001_homepage.png`)
- **Before/after screenshots** on every click action for visual diff evidence
- **Screenshots organized per run** in `screenshots/run_YYYYMMDD_HHMMSS/`
- **Screenshot references in test cases** — each test step links to its screenshot
- **TestRail-compatible JSON export** (`testrail_export.json`) with attachment paths per step
- `export_testrail_json` agent tool for structured test management export
- 3-phase agent workflow: Explore → Generate Test Cases → Export to TestRail

### Changed
- `scan_page` tool now uses descriptive screenshot labels based on page type
- `click_element` tool now captures before/after screenshots automatically
- System prompt updated with screenshot and TestRail export instructions

## [0.3.0] - 2026-02-20
### Added
- **QA test case generation** from autonomous website exploration
- `generate_test_cases` tool — extracts all user flows from the exploration graph
- `write_test_report` tool — outputs structured markdown test suite
- Page observations and classifications recorded during exploration
- Expected vs actual behavior tracking on each click action
- Test cases include: priority levels (P0-P3), type labels, preconditions, step-by-step actions, expected results
- Edge case and negative test cases generated from observations
- Coverage matrix mapping pages to test cases
- `PageNode.observations` and `PageNode.available_actions` fields
- `ActionEdge.observation` field for expected behavior recording
- Flow extraction (`get_flows()`) from exploration graph via DFS

## [0.2.0] - 2026-02-20
### Added
- Release Revert Risk Advisor agent (`agent/`) — KirtiJayadev
- React UI dashboard (`ui/`) with risk score gauge, recommendations, run history
- Flask API server (`server/app.py`)
- Setup guides (`SETUP_GUIDE.md`, `TESTING.md`, `INTEGRATION.md`)

### Fixed
- Playwright threading issue — moved to subprocess IPC model (`src/_pw_helper.py`)
- React UI proxy error — switched to full API URL
- SPA detection improvements

### Changed
- Bedrock model switched to `claude-3-5-sonnet-v2` (on-demand compatible)
- Browser manager rewritten to use subprocess communication

## [0.1.0] - 2026-02-20
### Added
- **Initial release** — Web Cartographer AI agent
- Strands Agent with 6 custom tools: `navigate_to_url`, `scan_page`, `click_element`, `go_back`, `get_exploration_status`, `export_exploration_graph`
- Playwright browser automation (headless + headed modes)
- In-memory graph store with `PageNode` and `ActionEdge` models
- Neo4j graph store backend (optional)
- Interactive graph visualization (`web/index.html`) using vis.js
- Datadog LLM Observability integration via OpenTelemetry
- CLI entry point with configurable depth, page limits, and browser mode
- Amazon Bedrock (Claude) as LLM provider via Strands SDK
