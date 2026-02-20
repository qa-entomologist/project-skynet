"""Mobile Cartographer Agent - explores Android apps and generates QA test cases.

Same architecture as the Web Cartographer but uses Appium + Android emulator
instead of Playwright + browser.
"""

import json
import logging
import os

from strands import Agent, tool
from strands.models import BedrockModel

from src.config import AWS_REGION, MAX_DEPTH, MAX_PAGES
from src.mobile_manager import mobile
from src.graph_store import (
    PageNode,
    ActionEdge,
    MemoryGraphStore,
    create_graph_store,
)

logger = logging.getLogger(__name__)

PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))

graph_store: MemoryGraphStore = create_graph_store()
_current_depth = 0
_last_elements: list[dict] = []


# ---------------------------------------------------------------------------
# Agent tools
# ---------------------------------------------------------------------------


@tool
def scan_screen(screen_type: str, observations: str) -> str:
    """Scan the current screen to discover all interactive elements.
    Takes a screenshot and records your QA observations.

    Args:
        screen_type: Classification of this screen (e.g. "splash", "home", "login", "player", "settings", "search", "detail", "menu", "dialog", "onboarding", "profile", "error")
        observations: Detailed QA observations: what content is displayed, layout, loading states, any issues, accessibility concerns, or notable behavior.
    """
    global _last_elements

    safe_type = screen_type.replace(" ", "_")
    screenshot_path = mobile.take_screenshot(label=safe_type)
    elements = mobile.get_screen_elements()
    _last_elements = elements

    screen_id = mobile.get_screen_id()
    screen_title = mobile.get_screen_title()

    element_summary = []
    for el in elements:
        label = el["text"] or el["content_desc"] or el["resource_id"].split("/")[-1]
        desc = f"[{el['index']}] {el['type']}: \"{label}\""
        if el["scrollable"]:
            desc += " (scrollable)"
        if not el["enabled"]:
            desc += " (disabled)"
        element_summary.append(desc)

    actions_text = "\n".join(element_summary[:50])

    page = PageNode(
        id=screen_id,
        url=f"{mobile.package}/{mobile.activity}",
        title=screen_title,
        domain=mobile.package,
        path=mobile.activity,
        page_type=screen_type,
        screenshot_path=screenshot_path,
        element_count=len(elements),
        depth=_current_depth,
        visited=True,
        observations=observations,
        available_actions=actions_text,
    )
    is_new = graph_store.add_page(page)
    if not is_new:
        graph_store.update_page(
            screen_id,
            screenshot_path=screenshot_path,
            element_count=len(elements),
            visited=True,
            page_type=screen_type,
            observations=observations,
            available_actions=actions_text,
        )

    result = {
        "platform": mobile.platform,
        "screen_id": screen_id,
        "screen_title": screen_title,
        "activity": mobile.activity,
        "package": mobile.package,
        "screen_type": screen_type,
        "screenshot_saved": screenshot_path,
        "interactive_elements_count": len(elements),
        "interactive_elements": element_summary[:50],
        "is_new_screen": is_new,
        "graph_stats": graph_store.get_stats(),
    }
    return json.dumps(result, indent=2)


@tool
def tap_element(element_index: int, reason: str, expected_result: str) -> str:
    """Tap an interactive element on the current screen by its index number
    (from scan_screen results). Records the action and your expectation.

    Args:
        element_index: The index number of the element to tap (from scan_screen)
        reason: Why you chose to tap this element
        expected_result: What you expect to happen (e.g. "Should open the player", "Should navigate to settings")
    """
    global _current_depth, _last_elements

    target = next((e for e in _last_elements if e["index"] == element_index), None)
    if not target:
        return json.dumps({"error": f"Element index {element_index} not found. Call scan_screen first."})

    if graph_store.page_count() >= MAX_PAGES:
        return json.dumps({"error": "MAX_PAGES limit reached. Stop exploring and generate test cases."})

    old_screen_id = mobile.get_screen_id()
    label = (target["text"] or target["content_desc"] or "element").replace(" ", "_")[:40]
    before_screenshot = mobile.take_screenshot(label=f"before_tap_{label}")

    try:
        mobile.tap_by_index(element_index, _last_elements)
    except Exception as e:
        return json.dumps({"error": f"Tap failed: {e}"})

    after_screenshot = mobile.take_screenshot(label=f"after_tap_{label}")
    new_screen_id = mobile.get_screen_id()
    screen_changed = new_screen_id != old_screen_id

    if screen_changed:
        _current_depth += 1
        screen_title = mobile.get_screen_title()
        page = PageNode(
            id=new_screen_id,
            url=f"{mobile.package}/{mobile.activity}",
            title=screen_title,
            domain=mobile.package,
            path=mobile.activity,
            depth=_current_depth,
            screenshot_path=after_screenshot,
        )
        is_new = graph_store.add_page(page)

        edge = ActionEdge(
            from_id=old_screen_id,
            to_id=new_screen_id,
            action_type="tap",
            element_text=target["text"] or target["content_desc"],
            element_selector=target["resource_id"],
            observation=f"Expected: {expected_result}",
        )
        graph_store.add_edge(edge)
    else:
        is_new = False

    result = {
        "status": "ok",
        "tapped": target["text"] or target["content_desc"] or target["resource_id"],
        "reason": reason,
        "expected_result": expected_result,
        "screenshot_before": before_screenshot,
        "screenshot_after": after_screenshot,
        "screen_changed": screen_changed,
        "is_new_screen": is_new,
        "current_activity": mobile.activity,
        "current_depth": _current_depth,
        "at_max_depth": _current_depth >= MAX_DEPTH,
        "graph_stats": graph_store.get_stats(),
    }
    return json.dumps(result, indent=2)


@tool
def swipe_screen(direction: str, reason: str) -> str:
    """Swipe on the screen to scroll or reveal hidden content.

    Args:
        direction: Direction to swipe — "up" (scroll down), "down" (scroll up), "left" (next item), "right" (previous item)
        reason: Why you are swiping (e.g. "Scroll down to see more content", "Swipe through carousel")
    """
    old_screen_id = mobile.get_screen_id()

    try:
        mobile.swipe(direction)
    except Exception as e:
        return json.dumps({"error": f"Swipe failed: {e}"})

    screenshot = mobile.take_screenshot(label=f"after_swipe_{direction}")
    new_screen_id = mobile.get_screen_id()

    if new_screen_id != old_screen_id:
        edge = ActionEdge(
            from_id=old_screen_id,
            to_id=new_screen_id,
            action_type="swipe",
            element_text=f"swipe_{direction}",
            observation=reason,
        )
        graph_store.add_edge(edge)

    return json.dumps({
        "status": "ok",
        "direction": direction,
        "screenshot": screenshot,
        "screen_changed": new_screen_id != old_screen_id,
        "graph_stats": graph_store.get_stats(),
    })


@tool
def press_back(reason: str) -> str:
    """Go back to the previous screen. On Android this presses the system
    back button. On iOS this performs an edge-swipe (standard iOS back gesture).

    Args:
        reason: Why you are going back (e.g. "Done exploring settings, returning to home")
    """
    global _current_depth

    old_screen_id = mobile.get_screen_id()
    mobile.press_back()
    new_screen_id = mobile.get_screen_id()

    if _current_depth > 0:
        _current_depth -= 1

    edge = ActionEdge(
        from_id=old_screen_id,
        to_id=new_screen_id,
        action_type="back",
        element_text="android_back",
        observation=reason,
    )
    graph_store.add_edge(edge)

    return json.dumps({
        "status": "ok",
        "reason": reason,
        "current_activity": mobile.activity,
        "current_depth": _current_depth,
        "screen_changed": new_screen_id != old_screen_id,
        "graph_stats": graph_store.get_stats(),
    })


@tool
def type_text(text: str, field_description: str) -> str:
    """Type text into the currently focused input field.

    Args:
        text: The text to type
        field_description: Description of the field (e.g. "search box", "email input")
    """
    try:
        mobile.type_text(text)
        mobile.hide_keyboard()
        screenshot = mobile.take_screenshot(label=f"typed_{field_description.replace(' ', '_')[:30]}")
        return json.dumps({"status": "ok", "typed": text, "field": field_description, "screenshot": screenshot})
    except Exception as e:
        return json.dumps({"error": f"Type failed: {e}"})


@tool
def get_exploration_status() -> str:
    """Get the current exploration progress — screens discovered, visited,
    current depth. Use this to decide when to stop exploring.
    """
    stats = graph_store.get_stats()
    return json.dumps({
        **stats,
        "current_depth": _current_depth,
        "max_depth": MAX_DEPTH,
        "max_pages": MAX_PAGES,
        "current_activity": mobile.activity,
        "current_package": mobile.package,
    }, indent=2)


@tool
def generate_test_cases() -> str:
    """Extract all discovered user flows from the exploration graph.
    Call this after exploration is complete, then call write_test_report.
    """
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
                    "type": "screen",
                    "activity": item["url"],
                    "title": item["title"],
                    "screen_type": item["page_type"],
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

    screen_inventory = []
    for p in pages.values():
        if p:
            screen_inventory.append({
                "activity": p.url,
                "title": p.title,
                "screen_type": p.page_type,
                "observations": p.observations,
                "element_count": p.element_count,
                "screenshot": p.screenshot_path,
            })

    graph_json = graph_store.to_json()
    graph_path = os.path.join(PROJECT_ROOT, "web", "graph_data.json")
    os.makedirs(os.path.dirname(graph_path), exist_ok=True)
    with open(graph_path, "w") as f:
        f.write(graph_json)

    result = {
        "total_flows": len(flow_descriptions),
        "total_screens": len(screen_inventory),
        "flows": flow_descriptions,
        "screen_inventory": screen_inventory,
        "graph_exported": graph_path,
        "screenshot_dir": mobile.run_dir,
        "instruction": (
            "Now write comprehensive QA test cases using write_test_report. "
            "For EACH flow, create a test case with: ID, title, preconditions, "
            "numbered steps with specific actions, and expected results for each step. "
            "Reference screenshot filenames in each step. "
            "After write_test_report, call export_testrail_json."
        ),
    }
    return json.dumps(result, indent=2)


@tool
def write_test_report(markdown_content: str) -> str:
    """Write the final QA test case report as a markdown file.

    Args:
        markdown_content: Complete test case report in markdown. Must include test suite summary, individual test cases with IDs/steps/expected results, and a coverage matrix.
    """
    report_path = os.path.join(PROJECT_ROOT, "test_cases_mobile.md")
    with open(report_path, "w") as f:
        f.write(markdown_content)

    return json.dumps({
        "status": "report_written",
        "file": report_path,
        "stats": graph_store.get_stats(),
    })


@tool
def export_testrail_json(test_cases_json: str) -> str:
    """Export test cases as TestRail-compatible JSON with screenshot attachments.

    Args:
        test_cases_json: JSON array of test case objects. Each must have: "id", "title", "priority" (1-4), "type", "preconditions", "steps" (array of {"action", "expected", "screenshot"})
    """
    try:
        test_cases = json.loads(test_cases_json)
    except json.JSONDecodeError as e:
        return json.dumps({"error": f"Invalid JSON: {e}"})

    screenshot_dir = mobile.run_dir
    type_map = {
        "smoke": 1, "functional": 2, "regression": 3,
        "navigation": 4, "e2e": 5, "edge": 6, "negative": 7,
    }

    testrail_cases = []
    for tc in test_cases:
        steps = []
        for step in tc.get("steps", []):
            entry = {
                "content": step.get("action", ""),
                "expected": step.get("expected", ""),
            }
            ss = step.get("screenshot")
            if ss:
                entry["attachment"] = (
                    os.path.join(screenshot_dir, os.path.basename(ss))
                    if not os.path.isabs(ss)
                    else ss
                )
            steps.append(entry)

        testrail_cases.append({
            "title": tc.get("title", tc.get("id", "")),
            "custom_id": tc.get("id", ""),
            "priority_id": tc.get("priority", 2),
            "type_id": type_map.get(tc.get("type", "functional").lower(), 2),
            "custom_preconds": tc.get("preconditions", ""),
            "custom_steps_separated": steps,
            "custom_automation_type": 0,
        })

    export = {
        "format": "testrail",
        "version": "1.0",
        "platform": "android",
        "screenshot_directory": screenshot_dir,
        "test_cases": testrail_cases,
    }

    export_path = os.path.join(PROJECT_ROOT, "testrail_export_mobile.json")
    with open(export_path, "w") as f:
        json.dump(export, f, indent=2)

    return json.dumps({
        "status": "exported",
        "file": export_path,
        "test_case_count": len(testrail_cases),
        "screenshot_dir": screenshot_dir,
    })


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

MOBILE_SYSTEM_PROMPT = """You are the Mobile Cartographer QA Agent — an autonomous AI that explores native mobile apps (Android or iOS) on an emulator/simulator, captures visual evidence at every step, and produces comprehensive QA test cases ready for TestRail.

## Your Mission
Systematically explore the app to discover all screens and user flows, capture screenshots as visual evidence, then generate a complete QA test suite.

The scan_screen output will tell you which platform you are on (android or ios). Adapt your observations accordingly.

## Phase 1: Exploration
1. Start by scanning the current screen (the app has already been launched for you)
2. At each screen:
   - Classify its type (splash, home, login, player, settings, search, detail, menu, dialog, onboarding, profile, error, tab_bar, etc.)
   - Record detailed QA observations (layout, content, states, issues)
   - A screenshot is captured automatically
3. Tap through different elements to discover new screens:
   - For each tap, state what you EXPECT to happen
   - Before/after screenshots are captured automatically
   - Scan the resulting screen and note what ACTUALLY happened
4. Use swipe_screen to:
   - Scroll down to discover content below the fold
   - Swipe through carousels, tabs, or horizontal lists
   - Pull down to check for refresh behavior
5. Use press_back to return to previous screens:
   - On Android: presses the system back button
   - On iOS: performs a swipe-from-left-edge (standard iOS back gesture)
6. Handle common mobile scenarios:
   - Permission dialogs — they auto-accept, but note them in observations
   - Splash/loading screens — wait and scan after they pass
   - Keyboard appearing — note input fields, use type_text if needed
   - Dialogs/modals/action sheets — scan and dismiss them
   - Tab bars (iOS) / Bottom navigation (Android) — explore each tab

## Platform-Specific Observations
When recording observations, note platform-specific behavior:
- **Android**: material design components, navigation drawer, FAB buttons, snackbars, back button behavior
- **iOS**: navigation bars, tab bars, swipe gestures, action sheets, haptic feedback indicators, safe area usage

## Phase 2: Test Case Generation
After exploration, call generate_test_cases, then write_test_report with a comprehensive markdown report.

### Report Structure
1. **Test Suite Summary** — platform, app package/bundle ID, screens discovered, flows mapped
2. **Test Cases** — one per discovered flow:

```
### TC-XXX: [Test Case Title]
**Priority:** P0/P1/P2/P3
**Type:** Smoke / Functional / Navigation / E2E
**Platform:** Android / iOS / Both
**Preconditions:** App installed, user logged out/in, etc.

| Step | Action | Expected Result | Screenshot |
|------|--------|-----------------|------------|
| 1    | Launch app | Splash screen appears, then home screen loads | `step_001_home.png` |
| 2    | Tap "[element]" | [expected screen/behavior] | `step_002_before_tap_X.png` |
```

3. **Mobile-Specific Test Cases** — orientation, gestures, back button behavior, deep links
4. **Edge Cases** — network errors, empty states, large content, interrupted flows
5. **Coverage Matrix** — screens to test cases

## Phase 3: TestRail Export
After writing the test report, call export_testrail_json with the structured test cases.

## Navigation Rules
- Explore systematically: don't revisit screens you've already fully explored
- Use press_back to navigate backwards
- Skip actual login/signup but note the flows exist
- Skip video playback but note the player screen elements
- Screen limit: {max_pages} | Depth limit: {max_depth}

## Workflow
1. scan_screen → tap_element (with expected result) → scan_screen → repeat
2. Use swipe_screen to discover hidden content on each screen
3. When at dead end: press_back → scan_screen → try next path
4. Periodically: get_exploration_status
5. When done: generate_test_cases → write_test_report → export_testrail_json

Start exploring now!
""".format(max_depth=MAX_DEPTH, max_pages=MAX_PAGES)


def create_mobile_agent() -> Agent:
    """Create and return the Mobile Cartographer QA agent."""
    model = BedrockModel(
        model_id="anthropic.claude-3-5-sonnet-20241022-v2:0",
        region_name=AWS_REGION,
    )

    return Agent(
        model=model,
        system_prompt=MOBILE_SYSTEM_PROMPT,
        tools=[
            scan_screen,
            tap_element,
            swipe_screen,
            press_back,
            type_text,
            get_exploration_status,
            generate_test_cases,
            write_test_report,
            export_testrail_json,
        ],
    )
