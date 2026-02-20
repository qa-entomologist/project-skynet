#!/usr/bin/env python3
"""Playwright browser helper - runs as a subprocess to avoid threading issues.

Reads JSON commands from stdin, writes JSON responses to stdout.
"""

import json
import sys
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright


def get_page_meta(page):
    url = page.url
    parsed = urlparse(url)
    return {
        "url": url,
        "title": page.title(),
        "domain": parsed.netloc,
        "path": parsed.path,
    }


GET_ELEMENTS_JS = """() => {
    const interactiveSelectors = 'a[href], button, input[type="submit"], [role="button"], [role="link"], [role="tab"], [role="menuitem"], [onclick], details > summary';
    const els = document.querySelectorAll(interactiveSelectors);
    const results = [];
    let idx = 0;

    for (const el of els) {
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

        let selector;
        if (el.id) {
            selector = '#' + CSS.escape(el.id);
        } else if (el.getAttribute('data-testid')) {
            selector = '[data-testid="' + el.getAttribute('data-testid') + '"]';
        } else {
            const siblings = el.parentElement ? Array.from(el.parentElement.children).filter(s => s.tagName === el.tagName) : [];
            const nthIdx = siblings.indexOf(el) + 1;
            const parentSelector = el.parentElement && el.parentElement.id
                ? '#' + CSS.escape(el.parentElement.id)
                : '';
            selector = parentSelector
                ? parentSelector + ' > ' + tag + ':nth-of-type(' + nthIdx + ')'
                : tag + ':nth-of-type(' + nthIdx + ')';
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
}"""

DETECT_BACK_JS = """() => {
    const backPatterns = [
        'a[aria-label*="back" i]',
        'button[aria-label*="back" i]',
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
}"""


def respond(data):
    sys.stdout.write(json.dumps(data) + "\n")
    sys.stdout.flush()


def main():
    headless = sys.argv[1] == "true" if len(sys.argv) > 1 else True

    pw = sync_playwright().start()
    br = pw.chromium.launch(headless=headless)
    ctx = br.new_context(
        viewport={"width": 1280, "height": 900},
        user_agent=(
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
    )
    page = ctx.new_page()

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue

        try:
            cmd = json.loads(line)
        except json.JSONDecodeError:
            respond({"error": "invalid json"})
            continue

        action = cmd.get("action")

        try:
            if action == "ping":
                respond({"status": "ok"})

            elif action == "navigate":
                url = cmd["url"]
                page.goto(url, wait_until="domcontentloaded", timeout=15000)
                page.wait_for_timeout(2000)
                respond(get_page_meta(page))

            elif action == "screenshot":
                path = cmd["path"]
                page.screenshot(path=path, full_page=False)
                respond({"path": path})

            elif action == "get_elements":
                elements = page.evaluate(GET_ELEMENTS_JS)
                respond({"elements": elements})

            elif action == "click":
                selector = cmd["selector"]
                # Capture DOM state before click for SPA detection
                dom_before = page.evaluate("() => document.body.innerHTML.length")
                title_before = page.title()
                
                try:
                    page.click(selector, timeout=5000)
                    page.wait_for_timeout(2000)
                except Exception:
                    try:
                        page.evaluate(f"document.querySelector('{selector}')?.click()")
                        page.wait_for_timeout(2000)
                    except Exception:
                        pass
                
                # Check for DOM changes (SPA navigation)
                dom_after = page.evaluate("() => document.body.innerHTML.length")
                title_after = page.title()
                dom_changed = abs(dom_after - dom_before) > 100  # Significant DOM change
                title_changed = title_before != title_after
                
                meta = get_page_meta(page)
                meta["dom_changed"] = dom_changed
                meta["title_changed"] = title_changed
                meta["is_spa_navigation"] = not meta["url"].startswith(cmd.get("previous_url", "")) and (dom_changed or title_changed)
                respond(meta)

            elif action == "go_back":
                try:
                    page.go_back(wait_until="domcontentloaded", timeout=10000)
                    page.wait_for_timeout(1500)
                except Exception:
                    pass
                respond(get_page_meta(page))

            elif action == "detect_back":
                result = page.evaluate(DETECT_BACK_JS)
                respond({"result": result})

            elif action == "quit":
                respond({"status": "bye"})
                break

            else:
                respond({"error": f"unknown action: {action}"})

        except Exception as e:
            respond({"error": str(e)})

    br.close()
    pw.stop()


if __name__ == "__main__":
    main()
