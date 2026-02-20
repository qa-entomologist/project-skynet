"""Manages a Playwright browser instance for web exploration.

Uses subprocess-based Playwright to avoid threading issues with Strands Agent,
which runs tools in worker threads.
"""

import json
import os
import subprocess
import sys
import time
import hashlib
from urllib.parse import urlparse
from src.config import HEADLESS, SCREENSHOT_DIR

_HELPER_SCRIPT = os.path.join(os.path.dirname(__file__), "_pw_helper.py")


class BrowserManager:
    """Manages a long-running Playwright subprocess.

    Communication happens via stdin/stdout JSON messages to avoid
    greenlet/threading issues between Strands' worker threads and Playwright.
    """

    def __init__(self):
        self._proc: subprocess.Popen | None = None
        self._current_url: str = ""
        self._current_title: str = ""
        self._step_counter: int = 0
        self._run_dir: str = ""

    def start(self):
        run_id = time.strftime("%Y%m%d_%H%M%S")
        self._run_dir = os.path.join(SCREENSHOT_DIR, f"run_{run_id}")
        os.makedirs(self._run_dir, exist_ok=True)
        self._step_counter = 0

        self._proc = subprocess.Popen(
            [sys.executable, _HELPER_SCRIPT, str(HEADLESS).lower()],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        resp = self._send({"action": "ping"})
        if resp.get("status") != "ok":
            raise RuntimeError(f"Browser helper failed to start: {resp}")

    def stop(self):
        if self._proc:
            try:
                self._send({"action": "quit"})
            except Exception:
                pass
            self._proc.terminate()
            self._proc.wait(timeout=5)
            self._proc = None

    def _send(self, msg: dict) -> dict:
        if not self._proc or self._proc.poll() is not None:
            raise RuntimeError("Browser process not running")
        line = json.dumps(msg) + "\n"
        self._proc.stdin.write(line)
        self._proc.stdin.flush()
        resp_line = self._proc.stdout.readline()
        if not resp_line:
            stderr = self._proc.stderr.read()
            raise RuntimeError(f"Browser helper died: {stderr[:500]}")
        return json.loads(resp_line)

    @property
    def url(self) -> str:
        return self._current_url

    @property
    def title(self) -> str:
        return self._current_title

    def navigate(self, url: str) -> dict:
        """Navigate to a URL and return page metadata."""
        resp = self._send({"action": "navigate", "url": url})
        if "error" in resp:
            raise RuntimeError(resp["error"])
        self._current_url = resp.get("url", url)
        self._current_title = resp.get("title", "")
        return resp

    @property
    def run_dir(self) -> str:
        return self._run_dir

    def take_screenshot(self, label: str = "page") -> str:
        """Capture a screenshot with a meaningful name and return the file path.

        Args:
            label: Descriptive label (e.g. "homepage", "before_click_add_to_cart")
        """
        self._step_counter += 1
        safe_label = label.replace(" ", "_").replace("/", "_")[:60]
        filename = f"step_{self._step_counter:03d}_{safe_label}.png"
        filepath = os.path.join(self._run_dir, filename)
        resp = self._send({"action": "screenshot", "path": filepath})
        return resp.get("path", filepath)

    def get_interactive_elements(self) -> list[dict]:
        """Extract all clickable/interactive elements from the page."""
        resp = self._send({"action": "get_elements"})
        return resp.get("elements", [])

    def click_element(self, selector: str) -> dict:
        """Click an element by selector and return new page metadata."""
        resp = self._send({"action": "click", "selector": selector, "previous_url": self._current_url})
        self._current_url = resp.get("url", self._current_url)
        self._current_title = resp.get("title", self._current_title)
        return resp

    def go_back(self) -> dict:
        """Navigate back in browser history."""
        resp = self._send({"action": "go_back"})
        self._current_url = resp.get("url", self._current_url)
        self._current_title = resp.get("title", self._current_title)
        return resp

    def detect_back_button(self) -> dict | None:
        """Try to find a UI back-button or home/logo link on the page."""
        resp = self._send({"action": "detect_back"})
        result = resp.get("result")
        return result

    def get_content_fingerprint(self) -> str:
        """Get a hash of the visible page content to detect SPA view changes."""
        resp = self._send({"action": "content_fingerprint"})
        fp_data = resp.get("fingerprint", {})
        raw = json.dumps(fp_data, sort_keys=True)
        return hashlib.md5(raw.encode()).hexdigest()[:16]


# Global instance
browser = BrowserManager()
