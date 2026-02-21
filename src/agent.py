"""Web Cartographer Agent - explores websites and generates QA test cases."""

import hashlib
import json
import logging
import os
import time
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

PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))

graph_store: MemoryGraphStore | Neo4jGraphStore = create_graph_store()
_current_depth = 0
_start_domain = ""
_last_inventory: dict | None = None
_inventory_history: list[dict] = []


def _export_graph_live():
    """Export graph data and preliminary test cases for real-time dashboard updates."""
    try:
        export_path = os.path.join(PROJECT_ROOT, "web", "graph_data.json")
        with open(export_path, "w") as f:
            f.write(graph_store.to_json())
    except Exception:
        pass

    try:
        pages = [graph_store.get_page(pid) for pid in graph_store.pages]
        pages = [p for p in pages if p and p.visited]
        if not pages:
            return

        _type_map = {
            "homepage": "Navigation", "category": "Navigation", "content_detail": "Functional",
            "login": "Authentication", "signup": "Authentication", "search_results": "Functional",
            "spa_view": "Functional", "player": "E2E", "settings": "Functional",
        }
        _prio_map = {
            "homepage": "P0", "player": "P0", "content_detail": "P1",
            "login": "P1", "signup": "P1", "search_results": "P1",
            "category": "P1", "spa_view": "P2",
        }

        cases = []
        for i, p in enumerate(pages, 1):
            pt = p.page_type or "unknown"
            steps = [{"step": 1, "action": f"Navigate to {p.url}", "expected": f"{p.title} loads successfully"}]
            if p.observations:
                steps.append({"step": 2, "action": "Inspect page content", "expected": p.observations[:200]})
            if p.element_count:
                steps.append({"step": len(steps) + 1, "action": f"Verify interactive elements", "expected": f"{p.element_count} interactive elements present and functional"})

            cases.append({
                "id": f"TC-{i:03d}",
                "title": f"{p.title or p.url} — {pt.replace('_', ' ').title()}",
                "priority": _prio_map.get(pt, "P2"),
                "type": _type_map.get(pt, "Smoke"),
                "steps": steps,
                "screenshot": p.screenshot_path or "",
            })

        testrail_path = os.path.join(PROJECT_ROOT, "testrail_export.json")
        with open(testrail_path, "w") as f:
            import json as _json
            _json.dump({"test_cases": cases, "status": "in_progress", "total": len(cases)}, f, indent=2)
    except Exception:
        pass


def _page_id(url: str) -> str:
    """Stable ID from a normalized URL. Includes hash fragments for SPA routing."""
    parsed = urlparse(url)
    normalized = f"{parsed.scheme}://{parsed.netloc}{parsed.path}".rstrip("/")
    if parsed.fragment:
        normalized += f"#{parsed.fragment}"
    return hashlib.md5(normalized.encode()).hexdigest()[:12]


def _diff_inventories(old: dict | None, new: dict) -> dict:
    """Compare two page inventories and return what changed."""
    if old is None:
        return {"is_first_scan": True, "changes": []}

    changes = []
    old_header = set(old.get("header_items", []))
    new_header = set(new.get("header_items", []))
    added_header = new_header - old_header
    removed_header = old_header - new_header
    if added_header:
        changes.append(f"Header ADDED: {', '.join(sorted(added_header))}")
    if removed_header:
        changes.append(f"Header REMOVED: {', '.join(sorted(removed_header))}")
    if old.get("header_count", 0) != new.get("header_count", 0):
        changes.append(f"Header item count changed: {old.get('header_count', 0)} → {new.get('header_count', 0)}")

    old_buttons = set(old.get("buttons", []))
    new_buttons = set(new.get("buttons", []))
    added_buttons = new_buttons - old_buttons
    removed_buttons = old_buttons - new_buttons
    if added_buttons:
        changes.append(f"Buttons ADDED: {', '.join(sorted(added_buttons))}")
    if removed_buttons:
        changes.append(f"Buttons REMOVED: {', '.join(sorted(removed_buttons))}")

    old_sections = set(old.get("content_sections", []))
    new_sections = set(new.get("content_sections", []))
    added_sections = new_sections - old_sections
    if added_sections:
        changes.append(f"Content sections ADDED: {', '.join(sorted(added_sections))}")
    if old.get("content_section_count", 0) != new.get("content_section_count", 0):
        changes.append(f"Content section count: {old.get('content_section_count', 0)} → {new.get('content_section_count', 0)}")

    if old.get("form_field_count", 0) != new.get("form_field_count", 0):
        changes.append(f"Form fields: {old.get('form_field_count', 0)} → {new.get('form_field_count', 0)}")

    if old.get("active_modal") != new.get("active_modal"):
        if new.get("active_modal"):
            changes.append(f"Modal appeared: {new['active_modal'][:100]}")
        elif old.get("active_modal"):
            changes.append("Modal dismissed")

    if old.get("page_title") != new.get("page_title"):
        changes.append(f"Title changed: '{old.get('page_title', '')}' → '{new.get('page_title', '')}'")

    visually_same = len(changes) == 0
    return {
        "is_first_scan": False,
        "changes": changes,
        "visually_same": visually_same,
        "significant_change": len(changes) >= 2 or any("REMOVED" in c or "ADDED" in c for c in changes),
    }


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
    _export_graph_live()

    return json.dumps({
        "status": "ok",
        "is_new_page": is_new,
        "page_id": page_id,
        **meta,
        "graph_stats": graph_store.get_stats(),
    })


@tool
def scan_page(page_type: str, observations: str) -> str:
    """Scan the current page to discover all interactive elements AND take a
    structured inventory of the page layout. Compares the current page to the
    previous scan and reports WHAT CHANGED. Only takes a screenshot if the
    page is meaningfully different from the last one.

    Args:
        page_type: What type of page this is (e.g. "homepage", "product_listing", "product_detail", "cart", "checkout", "login", "search_results", "category", "settings", "error_page", "form", "kids_mode", "player")
        observations: Your detailed QA observations. IMPORTANT: Don't just say "page loaded". Describe what you SEE: how many header items, what buttons are present, what content sections exist, what changed from the previous page. Compare to what you saw before.
    """
    global _last_inventory

    elements = browser.get_interactive_elements()
    back_nav = browser.detect_back_button()

    try:
        inventory = browser.get_page_inventory()
    except Exception:
        inventory = {}

    diff = _diff_inventories(_last_inventory, inventory)

    should_screenshot = (
        diff.get("is_first_scan", True)
        or diff.get("significant_change", False)
        or not diff.get("visually_same", False)
    )

    screenshot_path = ""
    if should_screenshot:
        safe_type = page_type.replace(" ", "_")
        screenshot_path = browser.take_screenshot(label=safe_type)
    else:
        screenshot_path = "(skipped — page visually same as previous scan)"

    _last_inventory = inventory
    _inventory_history.append({
        "url": browser.url, "title": browser.title,
        "page_type": page_type, "inventory": inventory,
    })

    page_id = _page_id(browser.url)

    element_summary = []
    for el in elements:
        desc = f"[{el['index']}] <{el['tag']}> \"{el['text']}\""
        if el["href"]:
            desc += f" -> {el['href']}"
        element_summary.append(desc)

    actions_text = "\n".join(element_summary[:40])

    if screenshot_path and not screenshot_path.startswith("("):
        graph_store.update_page(
            page_id,
            screenshot_path=screenshot_path,
            element_count=len(elements),
            visited=True,
            page_type=page_type,
            observations=observations,
            available_actions=actions_text,
        )
    else:
        graph_store.update_page(
            page_id,
            element_count=len(elements),
            visited=True,
            page_type=page_type,
            observations=observations,
            available_actions=actions_text,
        )
    _export_graph_live()

    result = {
        "page_title": browser.title,
        "page_url": browser.url,
        "page_id": page_id,
        "page_type": page_type,
        "screenshot": screenshot_path,
        "interactive_elements_count": len(elements),
        "interactive_elements": element_summary[:40],
        "back_navigation": back_nav,
        "page_inventory": {
            "header_items": inventory.get("header_items", []),
            "header_count": inventory.get("header_count", 0),
            "content_sections": inventory.get("content_sections", [])[:10],
            "content_section_count": inventory.get("content_section_count", 0),
            "buttons": inventory.get("buttons", [])[:10],
            "form_fields": inventory.get("form_field_count", 0),
            "footer_links": inventory.get("footer_links", [])[:10],
            "active_modal": inventory.get("active_modal"),
        },
        "changes_from_previous": diff,
        "graph_stats": graph_store.get_stats(),
    }

    if diff.get("changes"):
        result["ATTENTION"] = (
            "PAGE STATE CHANGED! Investigate these differences:\n" +
            "\n".join(f"  • {c}" for c in diff["changes"]) +
            "\n\nAsk yourself: WHY did these changes happen? What does this tell you about the site's behavior? "
            "Is this a mode change (like Kids mode)? A filter? A different user state?"
        )

    return json.dumps(result, indent=2)


@tool
def scroll_page(direction: str, reason: str, amount: int = 600, selector: str = "") -> str:
    """Scroll the page or a specific container to reveal hidden content.
    Use this to discover content below the fold, scroll horizontal carousels,
    or explore lazy-loaded sections.

    Args:
        direction: One of "down", "up", "left", "right"
        reason: Why you are scrolling (e.g. "Reveal more content rows below the fold", "Scroll carousel to see more items")
        amount: Pixels to scroll (default 600). Use ~300 for gentle scrolls, ~800 for large jumps.
        selector: Optional CSS selector for a scrollable container (e.g. a carousel row). Leave empty to scroll the whole page.
    """
    sel = selector if selector else None
    try:
        result = browser.scroll(direction=direction, amount=amount, selector=sel)
    except Exception as e:
        return json.dumps({"error": f"Scroll failed: {e}"})

    screenshot = browser.take_screenshot(label=f"scroll_{direction}")

    output = {
        "status": "scrolled",
        "direction": direction,
        "amount": amount,
        "reason": reason,
        "screenshot": screenshot,
        "scroll_position": {
            "x": result.get("scrollX", 0),
            "y": result.get("scrollY", 0),
        },
        "page_size": {
            "total_height": result.get("scrollHeight", 0),
            "total_width": result.get("scrollWidth", 0),
            "viewport_height": result.get("viewportHeight", 0),
            "viewport_width": result.get("viewportWidth", 0),
        },
        "at_boundary": {
            "top": result.get("atTop", False),
            "bottom": result.get("atBottom", False),
            "left": result.get("atLeft", False),
            "right": result.get("atRight", False),
        },
    }
    return json.dumps(output, indent=2)


@tool
def type_text(selector_or_index: str, text: str, reason: str,
              clear: bool = True, submit: bool = False) -> str:
    """Type text into an input field, search bar, or textarea. Use this to test
    search functionality, fill out forms, enter invalid data, etc.

    Args:
        selector_or_index: Either a CSS selector (e.g. 'input[name="search"]') or
            an element index from scan_page (e.g. "5"). For form fields, use
            get_form_fields first to find selectors.
        text: The text to type
        reason: Why you are typing this (e.g. "Search for a movie", "Enter invalid email to test validation")
        clear: Whether to clear the field first (default True)
        submit: Whether to press Enter after typing (default False)
    """
    selector = selector_or_index
    if selector_or_index.isdigit():
        elements = browser.get_interactive_elements()
        idx = int(selector_or_index)
        for el in elements:
            if el["index"] == idx:
                selector = el["selector"]
                break

    try:
        result = browser.type_text(selector, text, clear=clear, submit=submit)
    except Exception as e:
        return json.dumps({"error": f"Type failed: {e}"})

    label = f"typed_{text.replace(' ', '_')[:30]}"
    screenshot = browser.take_screenshot(label=label)

    return json.dumps({
        "status": "typed",
        "text": text,
        "submitted": submit,
        "current_value": result.get("current_value", ""),
        "reason": reason,
        "screenshot": screenshot,
        "url_after": result.get("url", ""),
        "title_after": result.get("title", ""),
    }, indent=2)


@tool
def press_key(key: str, reason: str) -> str:
    """Press a keyboard key. Use for accessibility testing (Tab navigation),
    dismissing modals (Escape), submitting forms (Enter), navigating
    dropdowns (ArrowDown/ArrowUp), etc.

    Args:
        key: Key to press. Examples: "Tab", "Enter", "Escape", "ArrowDown",
             "ArrowUp", "ArrowLeft", "ArrowRight", "Space", "Backspace",
             "Shift+Tab" (reverse tab). For key combos use "+" separator.
        reason: Why you are pressing this key (e.g. "Tab to next form field for a11y test",
                "Escape to dismiss modal", "Enter to submit search")
    """
    try:
        result = browser.press_key(key)
    except Exception as e:
        return json.dumps({"error": f"Key press failed: {e}"})

    screenshot = browser.take_screenshot(label=f"key_{key.replace('+', '_')}")

    return json.dumps({
        "status": "key_pressed",
        "key": key,
        "reason": reason,
        "screenshot": screenshot,
        "url_after": result.get("url", ""),
        "title_after": result.get("title", ""),
    }, indent=2)


@tool
def get_form_fields() -> str:
    """Discover all input fields, textareas, and select dropdowns on the current
    page. Returns their selectors, types, placeholders, labels, and current values.
    Use this before type_text to find the right selector for a field.
    """
    fields = browser.get_input_fields()
    if not fields:
        return json.dumps({"fields": [], "message": "No input fields found on this page"})

    summary = []
    for f in fields:
        desc = f"[{f['index']}] <{f['tag']}>"
        if f.get("type"):
            desc += f" type={f['type']}"
        if f.get("label"):
            desc += f" label=\"{f['label']}\""
        elif f.get("placeholder"):
            desc += f" placeholder=\"{f['placeholder']}\""
        elif f.get("aria_label"):
            desc += f" aria-label=\"{f['aria_label']}\""
        if f.get("name"):
            desc += f" name={f['name']}"
        if f.get("required"):
            desc += " REQUIRED"
        if f.get("value"):
            desc += f" value=\"{f['value'][:30]}\""
        desc += f" selector=\"{f['selector']}\""
        summary.append(desc)

    return json.dumps({
        "field_count": len(fields),
        "fields": summary,
        "raw": fields,
    }, indent=2)


@tool
def check_page_health(reason: str = "General page health audit") -> str:
    """Run a health check on the current page. Detects broken images, empty links,
    missing alt text, unlabeled form inputs, and JavaScript console errors.
    Use this on every major page to catch quality issues.

    Args:
        reason: Context for why you're checking (e.g. "Audit homepage for a11y issues")
    """
    try:
        health = browser.check_page_health()
    except Exception as e:
        return json.dumps({"error": f"Health check failed: {e}"})

    issues_found = []
    if health.get("broken_images", 0) > 0:
        issues_found.append(f"{health['broken_images']} broken images")
    if health.get("missing_alt_text", 0) > 0:
        issues_found.append(f"{health['missing_alt_text']} images missing alt text")
    if health.get("empty_links", 0) > 0:
        issues_found.append(f"{health['empty_links']} empty/dead links")
    if health.get("unlabeled_inputs", 0) > 0:
        issues_found.append(f"{health['unlabeled_inputs']} unlabeled form inputs")
    if health.get("console_errors"):
        issues_found.append(f"{len(health['console_errors'])} console errors")

    return json.dumps({
        "reason": reason,
        "summary": {
            "total_images": health.get("total_images", 0),
            "broken_images": health.get("broken_images", 0),
            "missing_alt_text": health.get("missing_alt_text", 0),
            "total_links": health.get("total_links", 0),
            "empty_links": health.get("empty_links", 0),
            "total_inputs": health.get("total_inputs", 0),
            "unlabeled_inputs": health.get("unlabeled_inputs", 0),
            "focusable_elements": health.get("focusable_elements", 0),
        },
        "issues_found": issues_found,
        "is_healthy": len(issues_found) == 0,
        "console_errors": health.get("console_errors", [])[:10],
        "detailed_issues": health.get("issues", [])[:10],
    }, indent=2)


@tool
def resize_viewport(width: int, height: int, reason: str) -> str:
    """Resize the browser viewport to test responsive design at different breakpoints.
    Common sizes: mobile (375x812), tablet (768x1024), desktop (1920x1080).

    Args:
        width: Viewport width in pixels
        height: Viewport height in pixels
        reason: Why testing this size (e.g. "Test mobile responsive layout")
    """
    try:
        result = browser.resize_viewport(width, height)
    except Exception as e:
        return json.dumps({"error": f"Resize failed: {e}"})

    screenshot = browser.take_screenshot(label=f"viewport_{width}x{height}")

    return json.dumps({
        "status": "resized",
        "viewport": {"width": width, "height": height},
        "reason": reason,
        "screenshot": screenshot,
    }, indent=2)


@tool
def wait_and_observe(seconds: float, reason: str) -> str:
    """Pause and observe the page for a specified duration, then take a screenshot.
    Use for: watching loading animations finish, observing auto-playing carousels,
    checking timed notifications/toasts, verifying lazy-load behavior after scrolling.

    Args:
        seconds: How long to wait (0.5 to 10)
        reason: What you expect to observe (e.g. "Wait for carousel auto-advance", "Watch loading spinner complete")
    """
    ms = int(min(max(seconds, 0.5), 10) * 1000)
    try:
        browser.wait(ms=ms)
    except Exception as e:
        return json.dumps({"error": f"Wait failed: {e}"})

    screenshot = browser.take_screenshot(label="observe")

    return json.dumps({
        "status": "observed",
        "waited_seconds": ms / 1000,
        "reason": reason,
        "screenshot": screenshot,
    }, indent=2)


@tool
def hover_element(element_index: int, reason: str) -> str:
    """Hover over an interactive element to reveal tooltips, dropdown menus,
    preview cards, or hover states. IMPORTANT: After hovering, if new items
    appear (dropdown menu, submenu, etc.), use click_element with the
    selector returned in 'new_clickable_items' to interact with them.

    Args:
        element_index: The index number of the element to hover (from scan_page)
        reason: What you hope to discover (e.g. "Check for dropdown menu", "See tooltip text", "Preview card on hover")
    """
    elements = browser.get_interactive_elements()
    target = None
    for el in elements:
        if el["index"] == element_index:
            target = el
            break

    if not target:
        return json.dumps({"error": f"Element index {element_index} not found on page"})

    label = (target["text"] or "element").replace(" ", "_")[:40]

    try:
        hover_result = browser.hover_element(target["selector"])
    except Exception as e:
        return json.dumps({"error": f"Hover failed: {e}"})

    screenshot = browser.take_screenshot(label=f"hover_{label}")

    after_elements = browser.get_interactive_elements()
    before_selectors = {el["selector"] for el in elements}
    new_items = []
    for el in after_elements:
        if el["selector"] not in before_selectors and el["text"]:
            new_items.append({
                "text": el["text"],
                "selector": el["selector"],
                "tag": el["tag"],
                "href": el.get("href", ""),
            })

    result = {
        "status": "ok",
        "hovered": target["text"],
        "reason": reason,
        "screenshot": screenshot,
        "revealed_tooltips": hover_result.get("revealed_tooltips", []),
        "revealed_menu_items": hover_result.get("revealed_menu_items", []),
        "new_clickable_items": new_items[:20],
        "has_new_content": bool(new_items or hover_result.get("revealed_tooltips") or hover_result.get("revealed_menu_items")),
        "ACTION_REQUIRED": (
            f"Hover revealed {len(new_items)} new clickable items! "
            "Use click_element with selector= parameter to click items in the dropdown. "
            "Do NOT let the dropdown dismiss without exploring it."
        ) if new_items else "No new clickable items appeared.",
    }
    return json.dumps(result, indent=2)


@tool
def click_element(element_index: int, reason: str, expected_result: str,
                  selector: str = "") -> str:
    """Click an interactive element on the current page. You can click by index
    (from scan_page) OR by CSS selector (from hover_element's new_clickable_items).

    Args:
        element_index: The index number of the element to click (from scan_page). Use -1 if using selector instead.
        reason: Why you chose to click this element (for the exploration log)
        expected_result: What you expect to happen after clicking (e.g. "Should navigate to product detail page", "Should open a modal", "Should play the video")
        selector: Optional CSS selector to click directly (use for dropdown items revealed by hover_element, or specific elements). When provided, element_index is ignored.
    """
    global _current_depth

    elements = browser.get_interactive_elements()
    target = None

    if selector:
        target = {"selector": selector, "text": selector.split('"')[-2] if '"' in selector else selector[:40],
                  "tag": "element", "href": "", "index": -1}
    else:
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

    safe_text = (target["text"] or "element").replace(" ", "_")[:40]
    before_screenshot = browser.take_screenshot(label=f"before_click_{safe_text}")

    old_fingerprint = browser.get_content_fingerprint()

    try:
        meta = browser.click_element(target["selector"])
    except Exception as e:
        return json.dumps({"error": f"Click failed: {e}"})

    after_screenshot = browser.take_screenshot(label=f"after_click_{safe_text}")

    new_url = meta["url"]
    new_page_id = _page_id(new_url)
    url_changed = (new_page_id != old_page_id)
    # Also check for SPA navigation (DOM/title changed without URL change)
    is_spa_nav = meta.get("is_spa_navigation", False) or meta.get("dom_changed", False) or meta.get("title_changed", False)

    new_fingerprint = browser.get_content_fingerprint()
    content_changed = (new_fingerprint != old_fingerprint)

    view_changed = url_changed or content_changed or is_spa_nav
    is_spa_view = (content_changed or is_spa_nav) and not url_changed

    if is_spa_view:
        new_page_id = f"spa_{new_fingerprint}"
        spa_label = target["text"][:40] or "SPA view"
        logger.info("SPA view change detected: %s (fingerprint %s)", spa_label, new_fingerprint)

    if view_changed:
        _current_depth += 1

        display_url = new_url
        if is_spa_view:
            display_url = f"{new_url}#spa:{target['text'][:30]}"

        page = PageNode(
            id=new_page_id,
            url=display_url,
            title=meta["title"],
            domain=meta["domain"],
            path=meta["path"],
            page_type="spa_view" if is_spa_view else "unknown",
            depth=_current_depth,
            screenshot_path=after_screenshot,
        )
        is_new = graph_store.add_page(page)

        edge = ActionEdge(
            from_id=old_page_id,
            to_id=new_page_id,
            action_type="spa_click" if is_spa_view else "click",
            element_text=target["text"],
            element_selector=target["selector"],
            observation=f"Expected: {expected_result}",
        )
        graph_store.add_edge(edge)
        _export_graph_live()
    else:
        is_new = False

    parsed = urlparse(new_url)
    same_domain = parsed.netloc == _start_domain or parsed.netloc.endswith(f".{_start_domain}")

    result = {
        "status": "ok",
        "clicked": target["text"],
        "reason": reason,
        "expected_result": expected_result,
        "screenshot_before": before_screenshot,
        "screenshot_after": after_screenshot,
        "url_changed": url_changed,
        "content_changed": content_changed,
        "is_spa_view": is_spa_view,
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
    _export_graph_live()

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
    total_pages = stats.get("total_pages", 0)
    total_edges = stats.get("total_edges", 0)

    if total_pages < 10:
        guidance = (
            f"KEEP EXPLORING — only {total_pages} pages discovered so far. "
            "Aim for at least 10-15 pages before generating test cases. "
            "Try: hover over nav items to find dropdowns, click into content "
            "detail pages, explore search, check footer links."
        )
    elif total_pages < 15:
        guidance = (
            f"Good progress ({total_pages} pages). Consider exploring a few "
            "more areas: content detail pages, search results, account pages, "
            "help/FAQ, footer links. Hover over key elements before clicking."
        )
    else:
        guidance = (
            f"Solid exploration ({total_pages} pages, {total_edges} actions). "
            "You may proceed to generate_test_cases when ready, or explore "
            "any remaining unvisited areas."
        )

    return json.dumps({
        **stats,
        "current_depth": _current_depth,
        "max_depth": MAX_DEPTH,
        "max_pages": MAX_PAGES,
        "current_url": browser.url,
        "current_title": browser.title,
        "guidance": guidance,
    }, indent=2)


@tool
def generate_test_cases() -> str:
    """Extract all discovered user flows from the exploration graph and return them
    as structured data. Call this after exploration is complete. You MUST then
    write the full test case report using write_test_report.
    """
    page_count = graph_store.page_count()
    if page_count < 5:
        return json.dumps({
            "error": f"NOT ENOUGH EXPLORATION. Only {page_count} pages discovered — need at least 5. "
            "Go back and click MORE nav items, content links, and category pages. "
            "You must visit: every nav item, at least 2 content detail pages, search results, and auth pages. "
            "Do NOT call generate_test_cases again until you have explored at least 5 distinct pages.",
            "pages_found": page_count,
            "required": 5,
        })
    flows = graph_store.get_flows()
    pages = {pid: graph_store.get_page(pid) for pid in graph_store.pages}

    flow_descriptions = []
    for i, flow in enumerate(flows):
        steps = []
        for item in flow:
            if "url" in item:
                page = pages.get(item["page_id"])
                screenshot = page.screenshot_path if page else ""
                steps.append({
                    "type": "page",
                    "url": item["url"],
                    "title": item["title"],
                    "page_type": item["page_type"],
                    "observations": item["observations"],
                    "screenshot": screenshot,
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
                "screenshot": p.screenshot_path,
            })

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
        "screenshot_dir": browser.run_dir,
        "instruction": (
            "Now write comprehensive QA test cases using write_test_report. "
            "For EACH flow, create a test case with: ID, title, preconditions, "
            "numbered steps with specific actions, and expected results for each step. "
            "IMPORTANT: For each step that has a screenshot, add a 'Screenshot' column "
            "referencing the filename (e.g. `step_001_homepage.png`). These screenshots "
            "serve as visual evidence of expected state and can be attached in TestRail. "
            "Also add edge-case and negative test cases based on the pages you observed. "
            "After write_test_report, call export_testrail_json to produce a TestRail-compatible export."
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


@tool
def export_testrail_json(test_cases_json: str) -> str:
    """Export test cases in a TestRail-compatible JSON format with screenshot attachments.
    This file can be imported into TestRail or other test management tools.

    Args:
        test_cases_json: A JSON string containing an array of test case objects. Each object must have: "id" (e.g. "TC-001"), "title", "priority" (1-4, where 1=P0/Critical), "type" (e.g. "Functional"), "preconditions", "steps" (array of {"action": str, "expected": str, "screenshot": str or null})
    """
    try:
        test_cases = json.loads(test_cases_json)
    except json.JSONDecodeError as e:
        return json.dumps({"error": f"Invalid JSON: {e}"})

    screenshot_dir = browser.run_dir

    testrail_cases = []
    for tc in test_cases:
        steps_with_attachments = []
        for step in tc.get("steps", []):
            entry = {
                "content": step.get("action", ""),
                "expected": step.get("expected", ""),
            }
            ss = step.get("screenshot")
            if ss:
                entry["attachment"] = os.path.join(screenshot_dir, os.path.basename(ss)) if not os.path.isabs(ss) else ss
            steps_with_attachments.append(entry)

        testrail_cases.append({
            "title": tc.get("title", tc.get("id", "")),
            "custom_id": tc.get("id", ""),
            "priority_id": tc.get("priority", 2),
            "type_id": _testrail_type(tc.get("type", "Functional")),
            "custom_preconds": tc.get("preconditions", ""),
            "custom_steps_separated": steps_with_attachments,
            "custom_automation_type": 0,
        })

    export = {
        "format": "testrail",
        "version": "1.0",
        "screenshot_directory": screenshot_dir,
        "test_cases": testrail_cases,
    }

    export_path = os.path.join(PROJECT_ROOT, "testrail_export.json")
    with open(export_path, "w") as f:
        json.dump(export, f, indent=2)

    return json.dumps({
        "status": "exported",
        "file": export_path,
        "test_case_count": len(testrail_cases),
        "screenshot_dir": screenshot_dir,
    })


def _testrail_type(type_str: str) -> int:
    """Map test type string to TestRail type_id."""
    mapping = {
        "smoke": 1, "functional": 2, "regression": 3,
        "navigation": 4, "e2e": 5, "edge": 6, "negative": 7,
    }
    return mapping.get(type_str.lower(), 2)


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are the Web Cartographer QA Agent — an autonomous AI QA engineer that can thoroughly test ANY website. You explore with obsessive curiosity, notice every detail, compare states, and ask "why did this change?"

## CORE MINDSET: BE A DETECTIVE, NOT A TOURIST

After EVERY action, ask yourself:
- "What changed from what I saw before?"
- "Why did it change? What caused it?"
- "What does this tell me about how the site works?"
- "Is this the same page in a different state/mode?"

When scan_page returns `changes_from_previous`, those diffs are critical intelligence. If the header item count changed, buttons appeared or disappeared, or the page title shifted — that means something happened. Investigate it. Document exactly what changed and why.

### Smart observations (GOOD):
- "Header has 7 items: [list them]. After clicking [X], header changed to 4 items — [Y, Z, W] disappeared, new 'Exit' button appeared. This is a mode change that filters the entire site experience."
- "Dropdown revealed 12 clickable items. Clicked into 'Category A' — grid of 24 items with thumbnails, titles, and tags. Clicked first item — detail page with full description, metadata, and primary CTA button."
- "Search returned 8 results for 'test query'. Searched 'xyzzzz' — got 'No results found' with a suggestion to browse instead."

### Lazy observations (BAD — never do this):
- "Homepage loaded successfully." (says nothing)
- "Clicked X, page looks similar." (what's similar? what's different?)
- "Navigation works." (how? what happened?)

## SMART SCREENSHOTS
scan_page automatically compares the current page layout to your last scan. If the page is visually identical (same header, buttons, sections), NO screenshot is taken. Screenshots are only captured when something meaningfully changed. This means every screenshot is evidence of a real transition, not a duplicate.

## PHASE 1: DISCOVERY — UNDERSTAND WHAT THE SITE IS

You don't know what this site does. Your FIRST job is to figure it out by observing:
1. **scan_page** the homepage — read the header items, content sections, buttons, CTAs
2. **Identify the site's purpose** from what you see:
   - What is the primary call-to-action? (Watch, Buy, Sign Up, Try Free, Read, Book, etc.)
   - What kind of content is displayed? (Videos, products, articles, listings, tools, etc.)
   - Is there a search bar? Login/signup? Shopping cart icon? Dashboard?
3. **Determine the P0 test** — whatever the site's primary CTA is, THAT is the #1 thing to test:
   - If CTA says "Watch" or "Play" → test the playback flow
   - If CTA says "Add to Cart" or "Buy" → test the purchase flow
   - If CTA says "Sign Up" or "Get Started" → test the onboarding flow
   - If CTA says "Search" or "Find" → test the search/results flow
   - If CTA says "Read" or "Learn" → test the content detail flow
   - Whatever the main action is — follow it through to completion

## PHASE 2: SYSTEMATIC EXPLORATION

### 1. CLICK EVERY NAV ITEM
Read the header/navigation. Whatever items are there — click EACH one, one by one.
For each destination, scan_page and document what kind of page it is.
Do NOT skip any nav item. Do NOT assume you know what it does — click it and find out.

### 2. INTERACT WITH HOVER DROPDOWNS
When hover_element reveals new items (`new_clickable_items` in the response):
- These are clickable items inside the dropdown — click 2-3 of them using click_element(element_index=-1, selector="...")
- Do NOT let the dropdown dismiss without clicking something inside it
- After exploring one dropdown item, go_back and hover again to explore another

### 3. TEST THE PRIMARY FUNCTION
Whatever you identified as the site's core purpose — test the full flow end-to-end:
- Click the primary CTA or a content item
- Follow the flow to its natural conclusion (detail page, player, cart, form completion)
- Document every step: what appeared, what controls exist, what the expected behavior is

### 4. TEST SEARCH — MANDATORY (if search exists)
This is a P0 requirement. You MUST actually use search, not just note it exists.
- Find the search input (may be behind a search icon — click the icon first)
- get_form_fields to locate the input selector
- type_text with a REAL query relevant to the site's content (based on what you've seen on the page)
- scan_page the results — how many results? What do result cards show? Any filters?
- Clear the search and type_text with gibberish like "xyzabc999" to test "no results" experience
- scan_page again — is there a "no results" message? Suggestions? Empty state design?
- press_key "Escape" or click X to exit search — does it return to previous view?

### 5. TEST SIGN IN / SIGN UP — MANDATORY (if login/register exists)
This is a P1 requirement. You MUST click into sign-in and sign-up pages.
- Click every "Sign In", "Log In", "Register", "Sign Up", "Create Account" link/button you see
- scan_page the resulting page/modal
- get_form_fields to inventory ALL inputs: email, password, confirm password, name, etc.
- Document: field types (text, password, email), placeholders, required indicators, password rules
- Note ALL sign-in methods: email/password, Google, Facebook, Apple, SSO, phone number, etc.
- Check for "Forgot Password" link — click it and document that page too
- Check for terms/privacy links on the auth pages
- press_key "Tab" to test focus order through the form fields
- Do NOT submit real credentials, but document the complete form structure and all options
- go_back to return to main navigation

### 6. DETECT AND TEST MODE/STATE CHANGES
When clicking something causes `changes_from_previous` to show header items appearing/disappearing:
- This is a mode or state change (kids mode, admin view, language switch, category filter, etc.)
- Document exactly what changed: items removed, items added, content filtering
- Find and test the way to EXIT the mode / return to default state

### 7. SCROLL TO DISCOVER HIDDEN CONTENT
- scroll_page down 2-3 times on every major page to see below-the-fold content
- scroll_page right on any horizontal content rows/carousels
- Scroll to the footer — document help links, legal links, social links, contact info

### 8. CHECK PAGE HEALTH
- check_page_health on homepage + at least 2 other key pages
- Documents: broken images, missing alt text, console errors, unlabeled form inputs

### 9. TEST RESPONSIVE DESIGN
- resize_viewport to mobile (375x812) on the homepage
- scan_page and compare: does layout change? Nav collapse? Content reflow?
- resize_viewport back to 1920x1080 when done

## PHASE 3: TEST CASE GENERATION
CRITICAL: You MUST explore at least 8-10 DISTINCT pages before generating test cases. The system will REJECT your generate_test_cases call if you haven't visited enough pages.

EXPLORATION REQUIREMENTS (do ALL of these — no shortcuts):
1. Click EVERY nav item in the header (Movies, TV Shows, Live TV, Español, Tubi Kids, etc.) — each one is a new page
2. Click into at least 2 content items (e.g., a movie → detail page, a show → detail page)
3. Test search with a real query AND gibberish
4. Click Sign In and Sign Up
5. Explore hover dropdowns and click items inside them
6. Scroll down on every page you visit
7. Check page health on 2+ pages
8. Test responsive design

After visiting 8+ distinct pages AND 40+ tool calls, THEN call generate_test_cases → write_test_report → export_testrail_json.

Generate test cases covering EVERYTHING you discovered:
1. **Primary function** (P0) — the site's core action, end-to-end
2. **Navigation** (P1) — one TC per nav destination
3. **Dropdown/menu interactions** (P1) — hover → click flows
4. **Search** (P1) — valid query, no results, edge cases
5. **Mode/state changes** (P1) — any discovered mode switches
6. **Content detail** (P1) — clicking into items, viewing details
7. **Forms/auth** (P1) — field inventory, tab order, validation cues
8. **Responsive** (P2) — layout changes at mobile breakpoint
9. **Page health/a11y** (P2) — broken assets, missing labels, console errors
10. **Edge cases** (P3) — empty states, special characters, boundary conditions

### Report format:
```
### TC-XXX: [Title]
**Priority:** P0-P3
**Type:** Smoke / Functional / Navigation / E2E / Accessibility / Responsive / Mode

| Step | Action | Expected Result | Screenshot |
|------|--------|-----------------|------------|
```

## Phase 4: TestRail Export
Call export_testrail_json with JSON array of ALL test cases.

## SPA Awareness
Many modern sites change content without changing the URL. The tools detect this automatically via DOM fingerprinting. Always scan_page after clicking to capture what changed.

## Rules
- Stay on the same domain — do not follow external links
- Visit but do not submit login/signup forms
- Skip mailto, tel, and download links
- Depth limit: {max_depth} | Page limit: {max_pages}
- Do NOT generate test cases until you've completed the exploration checklist

Begin. Observe the site. Figure out what it is. Test it like it matters.
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
            scroll_page,
            hover_element,
            click_element,
            type_text,
            press_key,
            get_form_fields,
            check_page_health,
            resize_viewport,
            wait_and_observe,
            go_back,
            get_exploration_status,
            generate_test_cases,
            write_test_report,
            export_testrail_json,
        ],
    )
    return agent
