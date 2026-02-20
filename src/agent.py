"""Web Cartographer Agent - explores websites autonomously and maps user flows."""

import hashlib
import json
import logging
from urllib.parse import urlparse, urljoin

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
def scan_page() -> str:
    """Scan the current page to discover all interactive elements (links, buttons, etc).
    Also takes a screenshot for the exploration map. Call this after navigating to a new page.
    """
    screenshot_path = browser.take_screenshot()
    elements = browser.get_interactive_elements()
    back_nav = browser.detect_back_button()

    page_id = _page_id(browser.url)
    graph_store.update_page(
        page_id,
        screenshot_path=screenshot_path,
        element_count=len(elements),
        visited=True,
    )

    element_summary = []
    for el in elements:
        desc = f"[{el['index']}] <{el['tag']}> \"{el['text']}\""
        if el["href"]:
            desc += f" -> {el['href']}"
        element_summary.append(desc)

    result = {
        "page_title": browser.title,
        "page_url": browser.url,
        "page_id": page_id,
        "screenshot_saved": screenshot_path,
        "interactive_elements_count": len(elements),
        "interactive_elements": element_summary[:40],
        "back_navigation": back_nav,
        "graph_stats": graph_store.get_stats(),
    }
    return json.dumps(result, indent=2)


@tool
def click_element(element_index: int, reason: str) -> str:
    """Click an interactive element on the current page by its index number
    (from scan_page results). Records the action in the exploration graph.

    Args:
        element_index: The index number of the element to click (from scan_page)
        reason: Why you chose to click this element (for the exploration log)
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
        return json.dumps({"error": "MAX_PAGES limit reached. Stop exploring and summarize findings."})

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
def export_exploration_graph() -> str:
    """Export the complete exploration graph as JSON. Call this when you're done
    exploring to produce the final sitemap/flow graph.
    """
    graph_json = graph_store.to_json()

    export_path = "/Users/dgapuz/DataDog Hackathon/web/graph_data.json"
    with open(export_path, "w") as f:
        f.write(graph_json)

    stats = graph_store.get_stats()
    return json.dumps({
        "status": "exported",
        "file": export_path,
        "stats": stats,
    })


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are the Web Cartographer, an AI agent that autonomously explores websites to map out all possible user flows and interactions.

## Your Mission
Given a starting URL, systematically explore the website like a curious first-time user. Your goal is to discover and map every distinct page and user journey.

## Exploration Strategy
1. Start by navigating to the provided URL
2. Scan the page to discover all interactive elements
3. Methodically click through different paths using a depth-first approach:
   - Pick an unvisited link/button and click it
   - Scan the new page
   - Continue deeper until you hit a dead end or max depth
   - Then go back and try the next unexplored path
4. Prioritize variety - explore different CATEGORIES of navigation:
   - Main navigation links (top nav, sidebar)
   - Category/section links
   - Call-to-action buttons
   - Footer links
   - Search functionality
5. Stay on the same domain - don't follow external links
6. When you've explored enough paths or hit limits, navigate back to the homepage

## Navigation Rules
- When going back, try to use the website's own UI (back buttons, breadcrumbs, logo) before using browser back
- Recognize common UI patterns: logos link home, breadcrumbs show path, back arrows go up one level
- Skip duplicate pages (same URL or near-identical content)
- Skip login/signup/auth flows (just note they exist)
- Skip downloads, mailto links, tel links
- Be mindful of the depth limit ({max_depth}) and page limit ({max_pages})

## What to Observe and Report
For each page, note:
- What type of page it is (homepage, listing, detail, form, etc.)
- Key interactive elements available
- How it connects to other pages

## Workflow
1. navigate_to_url → scan_page → pick element → click_element → scan_page → ...
2. When at a dead end or max depth: go_back → scan_page → pick next unexplored element
3. Periodically check get_exploration_status
4. When done: export_exploration_graph and provide a summary

Start exploring now!
""".format(max_depth=MAX_DEPTH, max_pages=MAX_PAGES)


def create_explorer_agent() -> Agent:
    """Create and return the Web Cartographer agent."""
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
            export_exploration_graph,
        ],
    )
    return agent
