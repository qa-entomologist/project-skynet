"""Web Cartographer Agent - explores websites and generates QA test cases."""

import hashlib
import json
import logging
import os
import time
from urllib.parse import urlparse

from strands import Agent, tool
from strands.models import BedrockModel

from src.config import AWS_REGION, MAX_DEPTH, MAX_PAGES
from src.browser_manager import browser
from src.graph_store import (
    PageNode,
    ActionEdge,
    MemoryGraphStore,
    Neo4jGraphStore,
    create_graph_store,
)

logger = logging.getLogger(__name__)

PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))

graph_store: MemoryGraphStore | Neo4jGraphStore = create_graph_store()
_current_depth = 0
_start_domain = ""


def _page_id(url: str) -> str:
    """Stable ID from a normalized URL."""
    parsed = urlparse(url)
    normalized = f"{parsed.scheme}://{parsed.netloc}{parsed.path}".rstrip("/")
    return hashlib.md5(normalized.encode()).hexdigest()[:12]


# ---------------------------------------------------------------------------
# Agent tools
# ---------------------------------------------------------------------------

@tool
def navigate_to_url(url: str) -> str:
    """Navigate the browser to a URL. Use this to start exploring a website
    or to go to a specific page.

    Args:
        url: The full URL to navigate to (e.g. https://www.ebay.com)
    """
    global _start_domain, _current_depth
    try:
        meta = browser.navigate(url)
    except Exception as e:
        return json.dumps({"error": f"Navigation failed: {e}"})

    if not _start_domain:
        _start_domain = meta["domain"]

    page_id = _page_id(meta["url"])
    page = PageNode(
        id=page_id,
        url=meta["url"],
        title=meta["title"],
        domain=meta["domain"],
        path=meta["path"],
        depth=_current_depth,
    )
    is_new = graph_store.add_page(page)

    return json.dumps({
        "status": "ok",
        "is_new_page": is_new,
        "page_id": page_id,
        **meta,
        "graph_stats": graph_store.get_stats(),
    })


@tool
def scan_page(page_type: str, observations: str) -> str:
    """Scan the current page to discover all interactive elements.
    Also takes a screenshot and records your QA observations.

    Args:
        page_type: What type of page this is (e.g. "homepage", "product_listing", "product_detail", "cart", "checkout", "login", "search_results", "category", "settings", "error_page", "form")
        observations: Your detailed QA observations about this page. Include: what content is displayed, what state the page is in, any notable UI elements, forms, error messages, loading states, accessibility concerns, or anything a QA tester should verify.
    """
    screenshot_path = browser.take_screenshot()
    elements = browser.get_interactive_elements()
    back_nav = browser.detect_back_button()

    page_id = _page_id(browser.url)

    element_summary = []
    for el in elements:
        desc = f"[{el['index']}] <{el['tag']}> \"{el['text']}\""
        if el["href"]:
            desc += f" -> {el['href']}"
        element_summary.append(desc)

    actions_text = "\n".join(element_summary[:40])

    graph_store.update_page(
        page_id,
        screenshot_path=screenshot_path,
        element_count=len(elements),
        visited=True,
        page_type=page_type,
        observations=observations,
        available_actions=actions_text,
    )

    result = {
        "page_title": browser.title,
        "page_url": browser.url,
        "page_id": page_id,
        "page_type": page_type,
        "screenshot_saved": screenshot_path,
        "interactive_elements_count": len(elements),
        "interactive_elements": element_summary[:40],
        "back_navigation": back_nav,
        "graph_stats": graph_store.get_stats(),
    }
    return json.dumps(result, indent=2)


@tool
def click_element(element_index: int, reason: str, expected_result: str) -> str:
    """Click an interactive element on the current page by its index number
    (from scan_page results). Records the action and your expectation in the graph.

    Args:
        element_index: The index number of the element to click (from scan_page)
        reason: Why you chose to click this element (for the exploration log)
        expected_result: What you expect to happen after clicking (e.g. "Should navigate to product detail page", "Should open a modal", "Should add item to cart")
    """
    global _current_depth

    elements = browser.get_interactive_elements()
    target = None
    for el in elements:
        if el["index"] == element_index:
            target = el
            break

    if not target:
        return json.dumps({"error": f"Element index {element_index} not found on page"})

    old_url = browser.url
    old_page_id = _page_id(old_url)

    if graph_store.page_count() >= MAX_PAGES:
        return json.dumps({"error": "MAX_PAGES limit reached. Stop exploring and generate test cases."})

    try:
        meta = browser.click_element(target["selector"])
    except Exception as e:
        return json.dumps({"error": f"Click failed: {e}"})

    new_url = meta["url"]
    new_page_id = _page_id(new_url)
    url_changed = (new_page_id != old_page_id)

    if url_changed:
        _current_depth += 1
        page = PageNode(
            id=new_page_id,
            url=new_url,
            title=meta["title"],
            domain=meta["domain"],
            path=meta["path"],
            depth=_current_depth,
        )
        is_new = graph_store.add_page(page)

        edge = ActionEdge(
            from_id=old_page_id,
            to_id=new_page_id,
            action_type="click",
            element_text=target["text"],
            element_selector=target["selector"],
            observation=f"Expected: {expected_result}",
        )
        graph_store.add_edge(edge)
    else:
        is_new = False

    parsed = urlparse(new_url)
    same_domain = parsed.netloc == _start_domain or parsed.netloc.endswith(f".{_start_domain}")

    result = {
        "status": "ok",
        "clicked": target["text"],
        "reason": reason,
        "expected_result": expected_result,
        "url_changed": url_changed,
        "is_new_page": is_new,
        "new_url": new_url,
        "new_title": meta["title"],
        "same_domain": same_domain,
        "current_depth": _current_depth,
        "at_max_depth": _current_depth >= MAX_DEPTH,
        "graph_stats": graph_store.get_stats(),
    }
    return json.dumps(result, indent=2)


@tool
def go_back(method: str = "auto") -> str:
    """Navigate back to the previous page. Tries UI back button first,
    then logo/home link, then browser back.

    Args:
        method: How to go back - "auto" (tries UI first), "browser" (browser back), "logo" (click logo/home)
    """
    global _current_depth

    old_url = browser.url
    old_page_id = _page_id(old_url)

    if method == "auto":
        back_nav = browser.detect_back_button()
        if back_nav and back_nav["type"] == "back_button":
            try:
                browser.click_element(back_nav["selector"])
                method_used = f"ui_back_button ({back_nav['text']})"
            except Exception:
                browser.go_back()
                method_used = "browser_back (fallback)"
        else:
            browser.go_back()
            method_used = "browser_back"
    elif method == "logo":
        back_nav = browser.detect_back_button()
        if back_nav and back_nav["type"] == "logo_home":
            browser.click_element(back_nav["selector"])
            method_used = f"logo_home ({back_nav['text']})"
        else:
            browser.go_back()
            method_used = "browser_back (no logo found)"
    else:
        browser.go_back()
        method_used = "browser_back"

    meta = {"url": browser.url, "title": browser.title}
    new_page_id = _page_id(meta["url"])

    if _current_depth > 0:
        _current_depth -= 1

    edge = ActionEdge(
        from_id=old_page_id,
        to_id=new_page_id,
        action_type="back",
        element_text=method_used,
    )
    graph_store.add_edge(edge)

    return json.dumps({
        "status": "ok",
        "method": method_used,
        "now_at": meta["url"],
        "title": meta["title"],
        "current_depth": _current_depth,
        "graph_stats": graph_store.get_stats(),
    })


@tool
def get_exploration_status() -> str:
    """Get the current status of the exploration - how many pages discovered,
    visited, current depth, etc. Use this to decide when to stop.
    """
    stats = graph_store.get_stats()
    return json.dumps({
        **stats,
        "current_depth": _current_depth,
        "max_depth": MAX_DEPTH,
        "max_pages": MAX_PAGES,
        "current_url": browser.url,
        "current_title": browser.title,
    }, indent=2)


@tool
def generate_test_cases() -> str:
    """Extract all discovered user flows from the exploration graph and return them
    as structured data. Call this after exploration is complete. You MUST then
    write the full test case report using write_test_report.
    """
    flows = graph_store.get_flows()
    pages = {pid: graph_store.get_page(pid) for pid in graph_store.pages}

    flow_descriptions = []
    for i, flow in enumerate(flows):
        steps = []
        for item in flow:
            if "url" in item:
                page = pages.get(item["page_id"])
                steps.append({
                    "type": "page",
                    "url": item["url"],
                    "title": item["title"],
                    "page_type": item["page_type"],
                    "observations": item["observations"],
                })
            elif "action" in item:
                steps.append({
                    "type": "action",
                    "action": item["action"],
                    "element": item["element_text"],
                    "expected": item.get("observation", ""),
                })
        flow_descriptions.append({"flow_id": i + 1, "steps": steps})

    page_inventory = []
    for p in pages.values():
        if p:
            page_inventory.append({
                "url": p.url,
                "title": p.title,
                "page_type": p.page_type,
                "observations": p.observations,
                "element_count": p.element_count,
            })

    # Also export the graph
    graph_json = graph_store.to_json()
    graph_path = os.path.join(PROJECT_ROOT, "web", "graph_data.json")
    with open(graph_path, "w") as f:
        f.write(graph_json)

    result = {
        "total_flows": len(flow_descriptions),
        "total_pages": len(page_inventory),
        "flows": flow_descriptions,
        "page_inventory": page_inventory,
        "graph_exported": graph_path,
        "instruction": (
            "Now write comprehensive QA test cases using write_test_report. "
            "For EACH flow, create a test case with: ID, title, preconditions, "
            "numbered steps with specific actions, and expected results for each step. "
            "Also add edge-case and negative test cases based on the pages you observed."
        ),
    }
    return json.dumps(result, indent=2)


@tool
def write_test_report(markdown_content: str) -> str:
    """Write the final QA test case report as a markdown file.

    Args:
        markdown_content: The complete test case report in markdown format. Must include: test suite summary, individual test cases with IDs/steps/expected results, and a coverage matrix.
    """
    report_path = os.path.join(PROJECT_ROOT, "test_cases.md")
    with open(report_path, "w") as f:
        f.write(markdown_content)

    stats = graph_store.get_stats()
    return json.dumps({
        "status": "report_written",
        "file": report_path,
        "stats": stats,
    })


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are the Web Cartographer QA Agent — an autonomous AI that explores websites and produces comprehensive QA test cases.

## Your Mission
Given a starting URL, systematically explore the website to discover all user flows, then generate a complete QA test suite with detailed test cases, steps, and expected results.

## Phase 1: Exploration
1. Navigate to the provided URL
2. Scan each page — classify its type and record detailed QA observations:
   - What content is displayed and its state
   - Forms, inputs, and validation behavior
   - Error states, empty states, loading indicators
   - Navigation elements and their destinations
   - Accessibility concerns (missing labels, contrast, keyboard nav)
3. Click through different paths using depth-first exploration:
   - For each click, state what you EXPECT to happen (this becomes the test assertion)
   - Scan the resulting page and note what ACTUALLY happened
   - Continue deeper until dead end or max depth, then go back
4. Prioritize diverse flow coverage:
   - Happy path flows (main user journeys)
   - Navigation flows (header, sidebar, footer, breadcrumbs)
   - Category/filter/search flows
   - Account/auth flows (note existence even if you skip login)
   - Error/edge case triggers (404 pages, empty states)

## Phase 2: Test Case Generation
After exploration, call generate_test_cases to extract all flows, then call write_test_report with a comprehensive markdown report containing:

### Report Structure
1. **Test Suite Summary** — site overview, pages discovered, flows mapped
2. **Test Cases** — one per discovered flow, formatted as:

```
### TC-XXX: [Test Case Title]
**Priority:** P0/P1/P2/P3
**Type:** Smoke / Functional / Navigation / E2E
**Preconditions:** [What must be true before starting]

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1    | Navigate to [URL] | Page loads, title is "[title]" |
| 2    | Click "[element text]" | Navigates to [expected page] |
| ...  | ... | ... |
```

3. **Edge Case & Negative Test Cases** — based on your observations:
   - What happens with invalid input?
   - What if a page is accessed directly by URL?
   - What about broken links or missing content?
   - What about browser back/forward behavior?

4. **Coverage Matrix** — table mapping pages to test cases that cover them

## Navigation Rules
- Stay on the same domain — don't follow external links
- Use the site's own back buttons/logo before browser back
- Skip login/signup actions but note they exist as test cases
- Skip downloads, mailto, tel links
- Depth limit: {max_depth} | Page limit: {max_pages}

## Workflow
1. navigate_to_url → scan_page (with observations) → click_element (with expected result) → repeat
2. When at dead end: go_back → scan_page → try next path
3. Periodically: get_exploration_status
4. When done exploring: generate_test_cases → write_test_report

Start exploring now!
""".format(max_depth=MAX_DEPTH, max_pages=MAX_PAGES)


def create_explorer_agent() -> Agent:
    """Create and return the Web Cartographer QA agent."""
    model = BedrockModel(
        model_id="anthropic.claude-3-5-sonnet-20241022-v2:0",
        region_name=AWS_REGION,
    )

    agent = Agent(
        model=model,
        system_prompt=SYSTEM_PROMPT,
        tools=[
            navigate_to_url,
            scan_page,
            click_element,
            go_back,
            get_exploration_status,
            generate_test_cases,
            write_test_report,
        ],
    )
    return agent
