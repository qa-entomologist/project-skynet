"""Manages a Playwright browser instance for web exploration."""

import os
import time
import hashlib
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright, Browser, Page, BrowserContext
from src.config import HEADLESS, SCREENSHOT_DIR


class BrowserManager:
    """Singleton-style browser manager wrapping Playwright sync API."""

    def __init__(self):
        self._playwright = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None

    def start(self):
        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(headless=HEADLESS)
        self._context = self._browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        )
        self._page = self._context.new_page()

    def stop(self):
        if self._browser:
            self._browser.close()
        if self._playwright:
            self._playwright.stop()
        self._browser = None
        self._playwright = None
        self._page = None

    @property
    def page(self) -> Page:
        if not self._page:
            raise RuntimeError("Browser not started. Call start() first.")
        return self._page

    def navigate(self, url: str, timeout: int = 15000) -> dict:
        """Navigate to a URL and return page metadata."""
        self.page.goto(url, wait_until="domcontentloaded", timeout=timeout)
        self.page.wait_for_timeout(2000)
        return self._get_page_meta()

    def take_screenshot(self) -> str:
        """Capture a screenshot and return the file path."""
        url_hash = hashlib.md5(self.page.url.encode()).hexdigest()[:10]
        ts = int(time.time())
        filename = f"{url_hash}_{ts}.png"
        filepath = os.path.join(SCREENSHOT_DIR, filename)
        self.page.screenshot(path=filepath, full_page=False)
        return filepath

    def get_interactive_elements(self) -> list[dict]:
        """Extract all clickable/interactive elements from the page.

        Returns a list of dicts with keys: index, tag, text, role, href, selector.
        """
        elements = self.page.evaluate("""() => {
            const interactiveSelectors = 'a[href], button, input[type="submit"], [role="button"], [role="link"], [role="tab"], [role="menuitem"], [onclick], details > summary';
            const els = document.querySelectorAll(interactiveSelectors);
            const results = [];
            let idx = 0;

            for (const el of els) {
                // Skip hidden elements
                const rect = el.getBoundingClientRect();
                if (rect.width === 0 || rect.height === 0) continue;
                const style = window.getComputedStyle(el);
                if (style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0') continue;

                const text = (el.innerText || el.textContent || '').trim().substring(0, 100);
                if (!text && !el.getAttribute('aria-label') && !el.getAttribute('title')) continue;

                const tag = el.tagName.toLowerCase();
                const href = el.getAttribute('href') || '';
                const role = el.getAttribute('role') || '';
                const ariaLabel = el.getAttribute('aria-label') || el.getAttribute('title') || '';
                const displayText = text || ariaLabel;

                // Build a robust selector
                let selector;
                if (el.id) {
                    selector = '#' + CSS.escape(el.id);
                } else if (el.getAttribute('data-testid')) {
                    selector = `[data-testid="${el.getAttribute('data-testid')}"]`;
                } else {
                    // Use nth-of-type approach
                    const siblings = el.parentElement ? Array.from(el.parentElement.children).filter(s => s.tagName === el.tagName) : [];
                    const nthIdx = siblings.indexOf(el) + 1;
                    const parentSelector = el.parentElement && el.parentElement.id
                        ? '#' + CSS.escape(el.parentElement.id)
                        : '';
                    selector = parentSelector
                        ? `${parentSelector} > ${tag}:nth-of-type(${nthIdx})`
                        : `${tag}:nth-of-type(${nthIdx})`;
                }

                results.push({
                    index: idx,
                    tag: tag,
                    text: displayText.substring(0, 80),
                    role: role,
                    href: href.substring(0, 200),
                    selector: selector,
                });
                idx++;

                if (idx >= 60) break;
            }
            return results;
        }""")
        return elements

    def click_element(self, selector: str, timeout: int = 5000) -> dict:
        """Click an element by selector and return new page metadata."""
        try:
            self.page.click(selector, timeout=timeout)
            self.page.wait_for_timeout(2000)
        except Exception:
            # Try JavaScript click as fallback
            try:
                self.page.evaluate(f"document.querySelector('{selector}')?.click()")
                self.page.wait_for_timeout(2000)
            except Exception:
                pass
        return self._get_page_meta()

    def go_back(self) -> dict:
        """Navigate back in browser history."""
        self.page.go_back(wait_until="domcontentloaded", timeout=10000)
        self.page.wait_for_timeout(1500)
        return self._get_page_meta()

    def _get_page_meta(self) -> dict:
        """Collect current page metadata."""
        title = self.page.title()
        url = self.page.url
        parsed = urlparse(url)
        return {
            "url": url,
            "title": title,
            "domain": parsed.netloc,
            "path": parsed.path,
        }

    def detect_back_button(self) -> dict | None:
        """Try to find a UI back-button or home/logo link on the page."""
        result = self.page.evaluate("""() => {
            // Look for back buttons
            const backPatterns = [
                'a[aria-label*="back" i]',
                'button[aria-label*="back" i]',
                'a:has(> svg[data-icon="arrow-left"])',
                '[class*="back-button" i]',
                '[class*="btn-back" i]',
            ];
            for (const pat of backPatterns) {
                const el = document.querySelector(pat);
                if (el) {
                    const rect = el.getBoundingClientRect();
                    if (rect.width > 0 && rect.height > 0) {
                        return {
                            type: 'back_button',
                            selector: pat,
                            text: (el.innerText || el.getAttribute('aria-label') || '').substring(0, 60),
                        };
                    }
                }
            }

            // Look for logo / home link
            const logoPatterns = [
                'a[href="/"] img',
                'a[href="/"] svg',
                'a[href="/"]',
                '[class*="logo" i] a',
                'a[class*="logo" i]',
                'header a:first-of-type',
            ];
            for (const pat of logoPatterns) {
                const el = document.querySelector(pat);
                if (el) {
                    const link = el.closest('a') || el;
                    const rect = link.getBoundingClientRect();
                    if (rect.width > 0 && rect.height > 0) {
                        let selector = pat;
                        if (link.id) selector = '#' + CSS.escape(link.id);
                        return {
                            type: 'logo_home',
                            selector: selector,
                            text: (link.getAttribute('aria-label') || link.getAttribute('title') || 'Home').substring(0, 60),
                        };
                    }
                }
            }

            return null;
        }""")
        return result


# Global instance
browser = BrowserManager()
