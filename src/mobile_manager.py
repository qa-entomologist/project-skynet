"""Manages an Appium connection to an Android emulator or iOS simulator.

Supports both platforms through a unified API:
- Android: UiAutomator2 driver, parses Android UI hierarchy XML
- iOS: XCUITest driver, parses iOS accessibility tree XML

Uses Appium's HTTP-based WebDriver protocol, which is thread-safe
for use with Strands Agent's worker threads.
"""

import hashlib
import os
import re
import time
import logging
from xml.etree import ElementTree as ET

from appium import webdriver
from appium.webdriver.common.appiumby import AppiumBy

from src.config import SCREENSHOT_DIR

logger = logging.getLogger(__name__)

INTERACTIVE_IOS_TYPES = frozenset({
    "Button", "Link", "Switch", "Slider", "Toggle", "MenuItem",
    "Cell", "TextField", "SecureTextField", "SearchField", "TextArea",
    "Image", "StaticText", "Tab", "SegmentedControl",
})


def _detect_platform(apk_path: str | None, app_path: str | None) -> str:
    """Infer platform from file extension."""
    path = apk_path or app_path or ""
    if path.endswith(".apk"):
        return "android"
    if path.endswith((".app", ".ipa")):
        return "ios"
    return "android"


class MobileManager:
    """Wraps Appium WebDriver for Android or iOS device interaction."""

    def __init__(self):
        self._driver = None
        self._platform: str = ""
        self._step_counter: int = 0
        self._run_dir: str = ""
        self._current_activity: str = ""
        self._current_package: str = ""

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(
        self,
        platform: str | None = None,
        apk_path: str | None = None,
        app_path: str | None = None,
        app_package: str | None = None,
        app_activity: str | None = None,
        bundle_id: str | None = None,
    ):
        """Connect to the Appium server and launch the app.

        Args:
            platform: "android" or "ios". Auto-detected from file extension if omitted.
            apk_path: Path to an Android APK.
            app_path: Path to an iOS .app (simulator) or .ipa (device).
            app_package: Android package name for an already-installed app.
            app_activity: Android launch activity (auto-detected if omitted).
            bundle_id: iOS bundle identifier for an already-installed app.
        """
        self._platform = platform or _detect_platform(apk_path, app_path)

        run_id = time.strftime("%Y%m%d_%H%M%S")
        self._run_dir = os.path.join(
            SCREENSHOT_DIR, f"mobile_{self._platform}_run_{run_id}"
        )
        os.makedirs(self._run_dir, exist_ok=True)
        self._step_counter = 0

        if self._platform == "ios":
            options = self._ios_options(app_path, bundle_id)
        else:
            options = self._android_options(apk_path, app_package, app_activity)

        appium_url = os.getenv("APPIUM_URL", "http://127.0.0.1:4723")
        logger.info("Connecting to Appium (%s) at %s", self._platform, appium_url)
        self._driver = webdriver.Remote(appium_url, options=options)
        self._refresh_screen_info()
        logger.info(
            "Connected — platform=%s package=%s activity=%s",
            self._platform,
            self._current_package,
            self._current_activity,
        )

    def stop(self):
        if self._driver:
            try:
                self._driver.quit()
            except Exception:
                pass
            self._driver = None

    # ------------------------------------------------------------------
    # Options builders
    # ------------------------------------------------------------------

    @staticmethod
    def _android_options(apk_path, app_package, app_activity):
        from appium.options.android import UiAutomator2Options

        opts = UiAutomator2Options()
        opts.platform_name = "Android"
        if apk_path:
            opts.app = os.path.abspath(apk_path)
        elif app_package:
            opts.app_package = app_package
            if app_activity:
                opts.app_activity = app_activity
        opts.no_reset = True
        opts.new_command_timeout = 300
        opts.auto_grant_permissions = True
        return opts

    @staticmethod
    def _ios_options(app_path, bundle_id):
        from appium.options.ios import XCUITestOptions
        import subprocess

        opts = XCUITestOptions()
        opts.platform_name = "iOS"
        if app_path:
            opts.app = os.path.abspath(app_path)
        elif bundle_id:
            opts.bundle_id = bundle_id
        opts.no_reset = True
        opts.new_command_timeout = 300
        opts.auto_accept_alerts = True

        device_name = os.getenv("IOS_DEVICE_NAME", "")
        platform_version = os.getenv("IOS_PLATFORM_VERSION", "")

        if not device_name:
            try:
                result = subprocess.run(
                    ["xcrun", "simctl", "list", "devices", "booted", "--json"],
                    capture_output=True, text=True, timeout=5,
                )
                import json as _json
                data = _json.loads(result.stdout)
                for runtime, devices in data.get("devices", {}).items():
                    for dev in devices:
                        if dev.get("state") == "Booted":
                            device_name = dev["name"]
                            version_match = re.search(r"(\d+\.\d+)", runtime)
                            if version_match:
                                platform_version = version_match.group(1)
                            break
                    if device_name:
                        break
            except Exception:
                pass

        if not device_name:
            device_name = "iPhone 16"
        if not platform_version:
            platform_version = "18.0"

        opts.device_name = device_name
        opts.platform_version = platform_version

        logger.info("iOS options: device=%s, version=%s", device_name, platform_version)
        return opts

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def platform(self) -> str:
        return self._platform

    @property
    def activity(self) -> str:
        return self._current_activity

    @property
    def package(self) -> str:
        return self._current_package

    @property
    def run_dir(self) -> str:
        return self._run_dir

    # ------------------------------------------------------------------
    # Screenshots
    # ------------------------------------------------------------------

    def take_screenshot(self, label: str = "screen") -> str:
        """Capture a screenshot with a sequential, descriptive filename."""
        self._step_counter += 1
        safe_label = re.sub(r"[^a-zA-Z0-9_-]", "_", label)[:60]
        filename = f"step_{self._step_counter:03d}_{safe_label}.png"
        filepath = os.path.join(self._run_dir, filename)
        self._driver.save_screenshot(filepath)
        return filepath

    # ------------------------------------------------------------------
    # Screen analysis
    # ------------------------------------------------------------------

    def get_screen_elements(self) -> list[dict]:
        """Parse the UI hierarchy and return interactive elements.

        Returns a unified format regardless of platform.
        """
        source = self._driver.page_source
        if self._platform == "ios":
            elements = self._parse_ios_elements(source)
        else:
            elements = self._parse_android_elements(source)
        self._refresh_screen_info()
        return elements

    def get_screen_id(self) -> str:
        """Deterministic ID for the current screen layout."""
        source = self._driver.page_source
        tree = ET.fromstring(source)

        parts: list[str] = []
        for node in tree.iter():
            if self._platform == "ios":
                tag = node.tag.replace("XCUIElementType", "")
                name = node.get("name", "")
                parts.append(f"{tag}:{name}")
            else:
                cls = node.get("class", "")
                rid = node.get("resource-id", "")
                if cls or rid:
                    parts.append(f"{cls}:{rid}")

        content_hash = hashlib.md5("|".join(parts).encode()).hexdigest()[:8]
        prefix = self._current_package or self._platform
        activity = self._current_activity or "main"
        return hashlib.md5(
            f"{prefix}:{activity}:{content_hash}".encode()
        ).hexdigest()[:12]

    def get_screen_title(self) -> str:
        """Best-effort title extraction from the current screen."""
        try:
            source = self._driver.page_source
            tree = ET.fromstring(source)

            if self._platform == "ios":
                return self._ios_screen_title(tree)
            return self._android_screen_title(tree)
        except Exception:
            pass
        return self._current_activity or "Unknown Screen"

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def tap_by_index(self, index: int, elements: list[dict]):
        """Tap an element identified by its index in the elements list."""
        target = next((e for e in elements if e["index"] == index), None)
        if not target:
            raise ValueError(f"Element index {index} not found")

        found = self._find_element(target)

        if found:
            found.click()
        elif target["bounds"]:
            cx, cy = self._parse_bounds(target["bounds"])
            if cx is not None:
                self._driver.tap([(cx, cy)], 100)
            else:
                raise ValueError(f"Cannot locate element: {target}")
        else:
            raise ValueError(f"Cannot locate element: {target}")

        time.sleep(1)
        self._refresh_screen_info()

    def swipe(self, direction: str, distance: float = 0.5):
        """Swipe in a cardinal direction. *distance* is a fraction of the screen."""
        size = self._driver.get_window_size()
        w, h = size["width"], size["height"]
        cx, cy = w // 2, h // 2
        d = int(min(w, h) * distance)

        vectors = {
            "up": (cx, cy + d // 2, cx, cy - d // 2),
            "down": (cx, cy - d // 2, cx, cy + d // 2),
            "left": (cx + d // 2, cy, cx - d // 2, cy),
            "right": (cx - d // 2, cy, cx + d // 2, cy),
        }
        if direction not in vectors:
            raise ValueError(f"Invalid direction: {direction}")

        sx, sy, ex, ey = vectors[direction]
        self._driver.swipe(sx, sy, ex, ey, 800)
        time.sleep(0.5)
        self._refresh_screen_info()

    def press_back(self):
        """Go back. Android: system back button. iOS: swipe from left edge."""
        if self._platform == "ios":
            size = self._driver.get_window_size()
            w, h = size["width"], size["height"]
            self._driver.swipe(0, h // 2, w // 2, h // 2, 300)
        else:
            self._driver.back()
        time.sleep(0.5)
        self._refresh_screen_info()

    def type_text(self, text: str):
        """Type text into the currently focused input field."""
        try:
            focused = self._driver.switch_to.active_element
            focused.send_keys(text)
        except Exception:
            if self._platform == "ios":
                self._driver.find_element(
                    AppiumBy.IOS_PREDICATE, 'value BEGINSWITH ""'
                ).send_keys(text)
            else:
                self._driver.find_element(
                    AppiumBy.XPATH, '//*[@focused="true"]'
                ).send_keys(text)

    def hide_keyboard(self):
        try:
            self._driver.hide_keyboard()
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Platform-specific element parsing
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_android_elements(source: str) -> list[dict]:
        tree = ET.fromstring(source)
        elements: list[dict] = []
        idx = 0

        for node in tree.iter():
            clickable = node.get("clickable") == "true"
            checkable = node.get("checkable") == "true"
            if not (clickable or checkable):
                continue

            text = node.get("text", "")
            content_desc = node.get("content-desc", "")
            resource_id = node.get("resource-id", "")
            class_name = node.get("class", "")
            bounds = node.get("bounds", "")
            enabled = node.get("enabled") == "true"
            scrollable = node.get("scrollable") == "true"
            long_clickable = node.get("long-clickable") == "true"

            if not text and not content_desc and not resource_id:
                continue

            elements.append({
                "index": idx,
                "type": class_name.rsplit(".", 1)[-1] if class_name else "unknown",
                "text": text,
                "content_desc": content_desc,
                "resource_id": resource_id,
                "bounds": bounds,
                "clickable": clickable,
                "scrollable": scrollable,
                "long_clickable": long_clickable,
                "enabled": enabled,
            })
            idx += 1

        return elements

    @staticmethod
    def _parse_ios_elements(source: str) -> list[dict]:
        tree = ET.fromstring(source)
        elements: list[dict] = []
        idx = 0

        for node in tree.iter():
            tag = node.tag
            if not tag.startswith("XCUIElementType"):
                continue

            element_type = tag.replace("XCUIElementType", "")
            visible = node.get("visible") == "true"
            enabled = node.get("enabled") == "true"

            if element_type not in INTERACTIVE_IOS_TYPES or not visible:
                continue

            name = node.get("name", "")
            label = node.get("label", "")
            value = node.get("value", "")

            if not name and not label:
                continue

            x = int(node.get("x", 0))
            y = int(node.get("y", 0))
            w = int(node.get("width", 0))
            h = int(node.get("height", 0))
            bounds = f"[{x},{y}][{x + w},{y + h}]" if w and h else ""

            is_input = element_type in (
                "TextField", "SecureTextField", "SearchField", "TextArea",
            )

            elements.append({
                "index": idx,
                "type": element_type,
                "text": label or value,
                "content_desc": name,
                "resource_id": name,
                "bounds": bounds,
                "clickable": not is_input,
                "scrollable": element_type in ("ScrollView", "Table", "CollectionView"),
                "long_clickable": False,
                "enabled": enabled,
            })
            idx += 1

        return elements

    # ------------------------------------------------------------------
    # Platform-specific title extraction
    # ------------------------------------------------------------------

    @staticmethod
    def _android_screen_title(tree: ET.Element) -> str:
        for node in tree.iter():
            rid = node.get("resource-id", "").lower()
            if any(k in rid for k in ("title", "toolbar", "action_bar", "header")):
                text = node.get("text", "")
                if text:
                    return text
        for node in tree.iter():
            text = node.get("text", "")
            if text and 3 < len(text) < 60:
                return text
        return "Unknown Screen"

    @staticmethod
    def _ios_screen_title(tree: ET.Element) -> str:
        for node in tree.iter():
            tag = node.tag
            if "NavigationBar" in tag:
                label = node.get("name", "") or node.get("label", "")
                if label:
                    return label
                for child in node:
                    label = child.get("name", "") or child.get("label", "")
                    if label and len(label) < 60:
                        return label
        for node in tree.iter():
            if node.tag.endswith("StaticText"):
                label = node.get("label", "") or node.get("name", "")
                if label and 3 < len(label) < 60:
                    return label
        return "Unknown Screen"

    # ------------------------------------------------------------------
    # Element finding
    # ------------------------------------------------------------------

    def _find_element(self, target: dict):
        """Try multiple strategies to locate an element on screen."""
        found = None

        if self._platform == "ios":
            if target["resource_id"]:
                try:
                    found = self._driver.find_element(
                        AppiumBy.ACCESSIBILITY_ID, target["resource_id"]
                    )
                except Exception:
                    pass
            if not found and target["text"]:
                try:
                    found = self._driver.find_element(
                        AppiumBy.IOS_PREDICATE,
                        f'label == "{target["text"]}"',
                    )
                except Exception:
                    pass
        else:
            if target["resource_id"]:
                try:
                    found = self._driver.find_element(
                        AppiumBy.ID, target["resource_id"]
                    )
                except Exception:
                    pass
            if not found and target["text"]:
                try:
                    found = self._driver.find_element(
                        AppiumBy.XPATH, f'//*[@text="{target["text"]}"]'
                    )
                except Exception:
                    pass
            if not found and target["content_desc"]:
                try:
                    found = self._driver.find_element(
                        AppiumBy.ACCESSIBILITY_ID, target["content_desc"]
                    )
                except Exception:
                    pass

        return found

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _refresh_screen_info(self):
        try:
            if self._platform == "android":
                self._current_activity = self._driver.current_activity or ""
                self._current_package = self._driver.current_package or ""
            else:
                caps = self._driver.capabilities
                self._current_package = caps.get("bundleId", caps.get("CFBundleIdentifier", ""))
                self._current_activity = ""
        except Exception:
            pass

    @staticmethod
    def _parse_bounds(bounds_str: str) -> tuple[int | None, int | None]:
        match = re.match(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]", bounds_str)
        if match:
            x1, y1, x2, y2 = map(int, match.groups())
            return (x1 + x2) // 2, (y1 + y2) // 2
        return None, None


mobile = MobileManager()
