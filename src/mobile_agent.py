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

    try:
        screenshot_path = mobile.take_screenshot(label=safe_type)
    except Exception as e:
        return json.dumps({"error": f"Screenshot failed (app may have crashed): {e}", "recovery": "Try press_back or wait 3 seconds and scan_screen again. Do NOT give up."})

    try:
        elements = mobile.get_screen_elements()
    except Exception as e:
        return json.dumps({
            "error": f"Could not read screen elements: {e}",
            "screenshot_saved": screenshot_path,
            "recovery": "The app may be in a loading or crashed state. Try: 1) press_back 2) wait 3 seconds 3) scan_screen again. Do NOT stop exploring.",
        })
    _last_elements = elements

    try:
        screen_id = mobile.get_screen_id()
        screen_title = mobile.get_screen_title()
    except Exception:
        screen_id = f"unknown_{mobile._step_counter}"
        screen_title = "Unknown / Crashed Screen"

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
        return json.dumps({"error": "MAX_PAGES limit reached. Generate test cases now: generate_test_cases → write_test_report → export_testrail_json."})

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
        "hint": "At max depth! Use press_back to return and explore other branches." if _current_depth >= MAX_DEPTH else "",
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
        element_text=f"{mobile.platform}_back",
        observation=reason,
    )
    graph_store.add_edge(edge)

    screenshot = mobile.take_screenshot(label="after_back")

    return json.dumps({
        "status": "ok",
        "reason": reason,
        "current_activity": mobile.activity,
        "current_depth": _current_depth,
        "screen_changed": new_screen_id != old_screen_id,
        "screenshot": screenshot,
        "graph_stats": graph_store.get_stats(),
        "hint": "You are back at a shallower level. Explore other branches from here.",
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
        "platform": mobile.platform,
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

MOBILE_SYSTEM_PROMPT = """You are the Mobile Cartographer QA Agent — an autonomous AI detective that explores native mobile apps on an emulator/simulator. You think like a real QA tester: curious, methodical, and thorough. You capture visual evidence at every meaningful step and produce comprehensive test cases ready for TestRail.

## Detective Mindset
You are NOT a robot that clicks randomly and stops early. You are a meticulous QA engineer who:
- Self-discovers what the app does by observing its UI, content, and navigation
- Explores EVERY reachable screen before generating test cases
- Scrolls on EVERY screen to find content below the fold
- Notes exact counts, labels, and layout details in observations
- Compares screens after actions: "What changed? What's new? What disappeared?"
- Tests the primary user journey end-to-end

## Phase 1: Discovery (First 2-3 Scans)
1. Scan the launch screen — what type of app is this? What does the UI suggest?
2. Get past any onboarding/splash/permissions to reach the main screen
3. On the main screen, take inventory:
   - How many bottom nav tabs? What are their labels?
   - What content categories exist?
   - Is there a search icon? Profile/account icon? Settings gear?
   - What is the primary action this app wants users to take?

## Phase 2: Systematic Exploration
Follow this MANDATORY checklist IN ORDER. Do NOT skip items or stop early.

### A. SIGN IN / SIGN UP — DO THIS FIRST (HIGHEST PRIORITY)
This is the VERY FIRST thing you explore, BEFORE skipping onboarding.
When the app launches and you see a splash screen with "Sign In", "Skip", "Register", etc.:
1. DO NOT tap "Skip" yet
2. Tap "Sign In" FIRST → scan_screen → document EVERY field:
   - What input fields? (email, password, phone number)
   - What social sign-in buttons? (Google, Facebook, Apple, SSO)
   - Is there a "Forgot Password" link? Tap it, scan that screen, press_back
   - Are there "Create Account" or "Sign Up" links?
3. Press back from Sign In
4. Look for "Register" / "Sign Up" / "Create Account" — tap it → scan_screen
   - Document ALL registration fields, terms checkboxes, age verification
5. Press back from Sign Up
6. NOW tap "Skip" to continue past onboarding

### B. Bottom Navigation / Tab Bar
After reaching the main screen:
- Identify ALL tabs in the bottom navigation bar
- Tap EACH tab one by one, scan each resulting screen
- For each tab: scroll down at least 2-3 swipes to see full content
- After exploring all tabs, return to the first/home tab

### C. Search — MANDATORY
One of the bottom nav tabs or top icons is likely "Search" or "Explore".
- Tap the search/explore tab or search icon
- scan_screen the search page — note trending searches, suggestions, categories
- Tap the search input field
- type_text with a REAL query relevant to the app's content (e.g., a movie/show you saw)
- scan_screen the results — how many? What do result cards look like?
- Press back, tap the search field again, type_text "xyzabc999" (gibberish)
- scan_screen — is there a "no results" message? Empty state?
- Press back to exit search

### D. Content Interaction
- Tap at least 2-3 content items (cards, tiles, list items) to see detail screens
- On detail screens, note: title, metadata, action buttons, share options, back navigation
- Test the app's primary function (e.g., if it shows content, try playing/opening one)

### E. Navigation & Menus
- Tap any hamburger menu / drawer icon
- Tap profile/account icons
- Tap settings if visible
- Explore any sub-menus or nested navigation

### F. Scrolling on EVERY Screen
- On EVERY new screen, swipe up at least 2 times to discover hidden content
- Swipe left/right if carousels or horizontal lists are present
- Note what new content appears after scrolling

### G. Mode Changes & State Detection
- After each major action, compare the screen to what you saw before
- If header items changed, content categories shifted, or the theme changed — note it explicitly
- Test toggling between different modes/views if the app offers them (e.g., kids mode, dark mode, list vs grid)

### H. Edge Cases & Back Navigation
- Test the back button from every screen to verify proper navigation
- Note any screens where back doesn't work as expected
- Check for any error states, loading indicators, or empty states

### I. CRASH RECOVERY — NEVER GIVE UP
If scan_screen or tap_element returns an error about the app crashing or failing:
1. Wait 3 seconds, then try scan_screen again
2. If still failing, use press_back
3. If still failing, wait 5 more seconds and try again
4. Document the crash as a P0 bug, but KEEP EXPLORING
5. DO NOT generate test cases after a crash — recover first and continue
You are a resilient tester. Real apps crash. You work around it and keep going.

## Phase 3: Test Case Generation
ONLY after thorough exploration (you should have 30+ screenshots minimum), call generate_test_cases, then write_test_report.

STOP — before generating, verify you completed this checklist:
[ ] Explored every bottom nav tab
[ ] Tapped into Sign In AND Sign Up — documented all fields and auth methods
[ ] Used search with a real query AND a gibberish query
[ ] Tapped at least 2-3 content items to see detail screens
[ ] Scrolled down on at least 3 screens
[ ] Tested back navigation from multiple depths
[ ] Explored settings/profile/account screens
[ ] Documented any mode changes (kids mode, language, etc.)
If you skipped any of these, GO BACK AND DO THEM before generating test cases.

### Report Structure
1. **Test Suite Summary** — platform, app package/bundle ID, screens discovered, flows mapped, total screenshots
2. **Test Cases** — at LEAST 12-15 test cases covering:

### TC-XXX: [Test Case Title]
**Priority:** P0/P1/P2/P3
**Type:** Smoke / Functional / Navigation / E2E / Negative
**Platform:** Android / iOS / Both
**Preconditions:** App installed, user logged out/in, etc.

| Step | Action | Expected Result | Screenshot |
|------|--------|-----------------|------------|
| 1    | Launch app | Splash screen appears, then home screen loads | `step_001_home.png` |
| 2    | Tap "[element]" | [expected screen/behavior] | `step_002_before_tap_X.png` |

Required test case categories (EVERY one of these needs a test case):
- P0: App launch + onboarding flow
- P0: Primary user journey (whatever the app's main function is)
- P1: Sign In flow — all fields, social auth options, forgot password
- P1: Sign Up / Register flow — all fields, terms, validation
- P1: Search with valid query — results display, result card content
- P1: Search with invalid query — empty state, error handling
- P1: Each bottom nav tab navigation
- P1: Content detail view (tapping into an item)
- P2: Back navigation from every level
- P2: Scroll behavior / content loading / below-the-fold discovery
- P2: Settings / profile / account screens
- P2: Mode changes (kids mode, language, filters)
- P3: Edge cases (empty states, permissions, dialogs)
- P3: Gesture-based interactions (swipe, pull-to-refresh)

3. **Mobile-Specific Test Cases** — gestures, back button, keyboard, orientation, deep links
4. **Edge Cases & Negative Tests** — network errors, empty states, large content, interrupted flows
5. **Coverage Matrix** — screens vs test cases

## Phase 4: TestRail Export
After writing the test report, call export_testrail_json with the structured test cases.

## Platform-Specific Observations
- **Android**: material design, navigation drawer, FAB, snackbars, system back button, notification shade
- **iOS**: navigation bars, tab bars, swipe-back gesture, action sheets, safe area, haptics

## Navigation Rules
- BREADTH FIRST: explore all tabs/sections at the same level before going deep
- Use press_back to return, then explore the NEXT unexplored path
- Skip actual login/signup but note the flows exist and what fields are required
- Skip video playback but note the player screen elements and controls
- Screen limit: {max_pages} | Depth limit: {max_depth}
- DO NOT STOP just because you hit max depth — press_back and explore other branches!

## Workflow
1. scan_screen → observe → swipe to see more → tap_element → scan_screen → repeat
2. After exploring one branch, press_back to home and explore the NEXT branch
3. Periodically: get_exploration_status — do NOT stop until you've explored most elements
4. When truly done: generate_test_cases → write_test_report → export_testrail_json

YOU MUST EXPLORE AT LEAST 15 UNIQUE SCREENS BEFORE GENERATING TEST CASES.
YOU MUST HAVE AT LEAST 30 SCREENSHOTS BEFORE GENERATING TEST CASES.
DO NOT SKIP SIGN IN, SIGN UP, OR SEARCH — THESE ARE MANDATORY.

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
