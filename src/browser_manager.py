"""Manages a Playwright browser instance for web exploration.

Uses subprocess-based Playwright to avoid threading issues with Strands Agent,
which runs tools in worker threads.
"""

import json
import os
import subprocess
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

    def start(self):
        self._proc = subprocess.Popen(
            ["python3", _HELPER_SCRIPT, str(HEADLESS).lower()],
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

    def take_screenshot(self) -> str:
        """Capture a screenshot and return the file path."""
        url_hash = hashlib.md5(self._current_url.encode()).hexdigest()[:10]
        ts = int(time.time())
        filename = f"{url_hash}_{ts}.png"
        filepath = os.path.join(SCREENSHOT_DIR, filename)
        resp = self._send({"action": "screenshot", "path": filepath})
        return resp.get("path", filepath)

    def get_interactive_elements(self) -> list[dict]:
        """Extract all clickable/interactive elements from the page."""
        resp = self._send({"action": "get_elements"})
        return resp.get("elements", [])

    def click_element(self, selector: str) -> dict:
        """Click an element by selector and return new page metadata."""
        resp = self._send({"action": "click", "selector": selector})
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


# Global instance
browser = BrowserManager()
