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


CONTENT_FINGERPRINT_JS = """() => {
    const title = document.title || '';
    const h1s = Array.from(document.querySelectorAll('h1'))
        .map(h => h.innerText.trim()).filter(Boolean).join('|');
    const h2s = Array.from(document.querySelectorAll('h2'))
        .map(h => h.innerText.trim()).filter(Boolean).join('|');

    const mainEl = document.querySelector(
        'main, [role="main"], #content, #root > div, .main-content, article'
    );
    const source = mainEl || document.body;
    const mainText = source.innerText.trim().substring(0, 500);

    const navItems = Array.from(document.querySelectorAll(
        'nav a[aria-current], .active, [class*="selected"], [class*="active"]'
    )).map(el => el.innerText.trim()).filter(Boolean).join('|');

    return { title, h1s, h2s, mainText, navItems };
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

    page.evaluate("""() => {
        window.__console_errors = [];
        const orig = console.error;
        console.error = function() {
            window.__console_errors.push(Array.from(arguments).map(String).join(' ').substring(0, 200));
            if (window.__console_errors.length > 50) window.__console_errors.shift();
            orig.apply(console, arguments);
        };
        window.addEventListener('error', (e) => {
            window.__console_errors.push('JS Error: ' + (e.message || '') + ' at ' + (e.filename || '') + ':' + (e.lineno || ''));
        });
    }""")

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

            elif action == "hover":
                selector = cmd["selector"]
                try:
                    page.hover(selector, timeout=5000)
                    page.wait_for_timeout(cmd.get("wait_ms", 1500))
                except Exception:
                    try:
                        page.evaluate(f"""(() => {{
                            const el = document.querySelector('{selector}');
                            if (el) {{
                                el.dispatchEvent(new MouseEvent('mouseenter', {{bubbles: true}}));
                                el.dispatchEvent(new MouseEvent('mouseover', {{bubbles: true}}));
                            }}
                        }})()""")
                        page.wait_for_timeout(cmd.get("wait_ms", 1500))
                    except Exception:
                        pass

                tooltip_js = """() => {
                    const tooltipSelectors = [
                        '[role="tooltip"]', '.tooltip', '[class*="tooltip"]',
                        '[class*="popover"]', '[class*="dropdown-menu"]',
                        '[class*="hover-card"]', '[class*="preview"]',
                        '[data-tippy-root]', '.tippy-box',
                        '[class*="flyout"]', '[class*="submenu"]',
                        '[aria-expanded="true"] + *',
                    ];
                    const found = [];
                    for (const sel of tooltipSelectors) {
                        const els = document.querySelectorAll(sel);
                        for (const el of els) {
                            const rect = el.getBoundingClientRect();
                            if (rect.width > 0 && rect.height > 0) {
                                const text = (el.innerText || '').trim().substring(0, 200);
                                if (text) found.push({ selector: sel, text });
                            }
                        }
                    }
                    return found;
                }"""
                revealed = page.evaluate(tooltip_js)

                new_elements_js = """() => {
                    const dropdowns = document.querySelectorAll(
                        '[class*="dropdown"][class*="open"], [class*="dropdown"][class*="show"], ' +
                        '[aria-expanded="true"], [class*="menu"][class*="visible"], ' +
                        '[class*="submenu"]:not([style*="display: none"]), ' +
                        'ul[class*="dropdown-menu"][class*="show"]'
                    );
                    const items = [];
                    for (const dd of dropdowns) {
                        const links = dd.querySelectorAll('a, button, [role="menuitem"]');
                        for (const link of links) {
                            const rect = link.getBoundingClientRect();
                            if (rect.width > 0 && rect.height > 0) {
                                const text = (link.innerText || '').trim().substring(0, 80);
                                if (text) items.push(text);
                            }
                        }
                    }
                    return items;
                }"""
                menu_items = page.evaluate(new_elements_js)

                meta = get_page_meta(page)
                meta["revealed_tooltips"] = revealed
                meta["revealed_menu_items"] = menu_items
                respond(meta)

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

            elif action == "scroll":
                direction = cmd.get("direction", "down")
                amount = cmd.get("amount", 600)
                selector = cmd.get("selector")

                scroll_js = None
                if selector:
                    if direction in ("left", "right"):
                        dx = amount if direction == "right" else -amount
                        scroll_js = f"""() => {{
                            const el = document.querySelector('{selector}');
                            if (el) {{ el.scrollBy({{ left: {dx}, behavior: 'smooth' }}); return true; }}
                            return false;
                        }}"""
                    else:
                        dy = amount if direction == "down" else -amount
                        scroll_js = f"""() => {{
                            const el = document.querySelector('{selector}');
                            if (el) {{ el.scrollBy({{ top: {dy}, behavior: 'smooth' }}); return true; }}
                            return false;
                        }}"""
                else:
                    if direction in ("left", "right"):
                        dx = amount if direction == "right" else -amount
                        scroll_js = f"() => {{ window.scrollBy({{ left: {dx}, behavior: 'smooth' }}); return true; }}"
                    else:
                        dy = amount if direction == "down" else -amount
                        scroll_js = f"() => {{ window.scrollBy({{ top: {dy}, behavior: 'smooth' }}); return true; }}"

                page.evaluate(scroll_js)
                page.wait_for_timeout(cmd.get("wait_ms", 1000))

                viewport_js = """() => {
                    return {
                        scrollX: Math.round(window.scrollX),
                        scrollY: Math.round(window.scrollY),
                        scrollHeight: document.documentElement.scrollHeight,
                        scrollWidth: document.documentElement.scrollWidth,
                        viewportHeight: window.innerHeight,
                        viewportWidth: window.innerWidth,
                        atTop: window.scrollY < 10,
                        atBottom: window.scrollY + window.innerHeight >= document.documentElement.scrollHeight - 10,
                        atLeft: window.scrollX < 10,
                        atRight: window.scrollX + window.innerWidth >= document.documentElement.scrollWidth - 10,
                    };
                }"""
                position = page.evaluate(viewport_js)
                respond({"status": "ok", "direction": direction, "amount": amount, **position})

            elif action == "type_text":
                selector = cmd["selector"]
                text = cmd["text"]
                clear = cmd.get("clear", True)
                submit = cmd.get("submit", False)
                try:
                    if clear:
                        page.fill(selector, "", timeout=3000)
                    page.type(selector, text, delay=cmd.get("delay_ms", 50))
                    page.wait_for_timeout(800)
                    if submit:
                        page.press(selector, "Enter")
                        page.wait_for_timeout(2000)
                except Exception as e:
                    respond({"error": f"type_text failed: {e}"})
                    continue
                meta = get_page_meta(page)
                current_val = ""
                try:
                    current_val = page.input_value(selector, timeout=1000)
                except Exception:
                    pass
                meta["typed"] = text
                meta["current_value"] = current_val
                meta["submitted"] = submit
                respond(meta)

            elif action == "press_key":
                key = cmd["key"]
                selector = cmd.get("selector")
                try:
                    if selector:
                        page.press(selector, key, timeout=3000)
                    else:
                        page.keyboard.press(key)
                    page.wait_for_timeout(cmd.get("wait_ms", 800))
                except Exception as e:
                    respond({"error": f"press_key failed: {e}"})
                    continue
                meta = get_page_meta(page)
                meta["key_pressed"] = key
                respond(meta)

            elif action == "check_page_health":
                health_js = """() => {
                    const issues = [];
                    // Broken images
                    const imgs = document.querySelectorAll('img');
                    let brokenImgs = 0;
                    for (const img of imgs) {
                        if (img.complete && img.naturalWidth === 0 && img.src) {
                            brokenImgs++;
                            if (brokenImgs <= 5) {
                                issues.push({type: 'broken_image', src: img.src.substring(0, 200), alt: img.alt || ''});
                            }
                        }
                    }

                    // Empty links
                    const links = document.querySelectorAll('a');
                    let emptyLinks = 0;
                    for (const a of links) {
                        if (!a.href || a.href === '#' || a.href === 'javascript:void(0)') {
                            const text = (a.innerText || '').trim();
                            if (text) {
                                emptyLinks++;
                                if (emptyLinks <= 5)
                                    issues.push({type: 'empty_link', text: text.substring(0, 60)});
                            }
                        }
                    }

                    // Missing alt text
                    let missingAlt = 0;
                    for (const img of imgs) {
                        if (!img.alt && img.src && img.width > 50) {
                            missingAlt++;
                        }
                    }

                    // Missing form labels
                    let unlabeledInputs = 0;
                    const inputs = document.querySelectorAll('input:not([type="hidden"]), textarea, select');
                    for (const input of inputs) {
                        const id = input.id;
                        const hasLabel = id && document.querySelector('label[for="' + id + '"]');
                        const hasAria = input.getAttribute('aria-label') || input.getAttribute('aria-labelledby');
                        const hasPlaceholder = input.placeholder;
                        if (!hasLabel && !hasAria && !hasPlaceholder) unlabeledInputs++;
                    }

                    // Contrast issues (basic check via computed styles on text)
                    // Focus indicators
                    const focusable = document.querySelectorAll('a, button, input, select, textarea, [tabindex]');

                    return {
                        total_images: imgs.length,
                        broken_images: brokenImgs,
                        missing_alt_text: missingAlt,
                        total_links: links.length,
                        empty_links: emptyLinks,
                        total_inputs: inputs.length,
                        unlabeled_inputs: unlabeledInputs,
                        focusable_elements: focusable.length,
                        issues: issues,
                    };
                }"""
                health = page.evaluate(health_js)

                console_errors = []
                try:
                    errors_js = """() => {
                        if (window.__console_errors) return window.__console_errors;
                        return [];
                    }"""
                    console_errors = page.evaluate(errors_js)
                except Exception:
                    pass
                health["console_errors"] = console_errors
                respond(health)

            elif action == "resize_viewport":
                width = cmd["width"]
                height = cmd["height"]
                page.set_viewport_size({"width": width, "height": height})
                page.wait_for_timeout(1000)
                meta = get_page_meta(page)
                meta["viewport"] = {"width": width, "height": height}
                respond(meta)

            elif action == "wait":
                ms = cmd.get("ms", 2000)
                page.wait_for_timeout(ms)
                meta = get_page_meta(page)
                meta["waited_ms"] = ms
                respond(meta)

            elif action == "get_input_fields":
                fields_js = """() => {
                    const inputs = document.querySelectorAll(
                        'input:not([type="hidden"]):not([type="submit"]):not([type="button"]), ' +
                        'textarea, select, [contenteditable="true"]'
                    );
                    const results = [];
                    let idx = 0;
                    for (const el of inputs) {
                        const rect = el.getBoundingClientRect();
                        if (rect.width === 0 || rect.height === 0) continue;
                        const style = window.getComputedStyle(el);
                        if (style.display === 'none' || style.visibility === 'hidden') continue;

                        const tag = el.tagName.toLowerCase();
                        const type = el.type || '';
                        const name = el.name || '';
                        const placeholder = el.placeholder || '';
                        const value = el.value || '';
                        const ariaLabel = el.getAttribute('aria-label') || '';
                        const id = el.id || '';
                        const label_el = id ? document.querySelector('label[for="' + id + '"]') : null;
                        const label = label_el ? label_el.innerText.trim() : '';

                        let selector;
                        if (id) selector = '#' + CSS.escape(id);
                        else if (el.getAttribute('data-testid'))
                            selector = '[data-testid="' + el.getAttribute('data-testid') + '"]';
                        else if (name)
                            selector = tag + '[name="' + name + '"]';
                        else
                            selector = tag + ':nth-of-type(' + (idx + 1) + ')';

                        results.push({
                            index: idx,
                            tag, type, name, placeholder, value,
                            aria_label: ariaLabel,
                            label,
                            selector,
                            required: el.required || false,
                        });
                        idx++;
                        if (idx >= 30) break;
                    }
                    return results;
                }"""
                fields = page.evaluate(fields_js)
                respond({"fields": fields})

            elif action == "page_inventory":
                inventory_js = """() => {
                    const vis = (el) => {
                        if (!el) return false;
                        const r = el.getBoundingClientRect();
                        if (r.width === 0 || r.height === 0) return false;
                        const s = window.getComputedStyle(el);
                        return s.display !== 'none' && s.visibility !== 'hidden';
                    };
                    const txt = (el) => (el.innerText || el.textContent || '').trim().substring(0, 60);

                    // Header / nav items
                    const header = document.querySelector('header, [role="banner"], nav');
                    const navLinks = header ? header.querySelectorAll('a, button, [role="link"], [role="button"]') : [];
                    const headerItems = [];
                    for (const el of navLinks) {
                        if (vis(el)) {
                            const t = txt(el);
                            if (t && t.length < 50) headerItems.push(t);
                        }
                    }

                    // Main content sections / rows
                    const sections = document.querySelectorAll(
                        'section, [class*="row"], [class*="carousel"], [class*="shelf"], [class*="rail"], ' +
                        '[class*="slider"], [class*="container"] > div > div'
                    );
                    let contentSections = 0;
                    const sectionNames = [];
                    for (const sec of sections) {
                        if (vis(sec)) {
                            const heading = sec.querySelector('h1, h2, h3, h4, [class*="title"]');
                            if (heading) {
                                const t = txt(heading);
                                if (t && !sectionNames.includes(t)) {
                                    sectionNames.push(t);
                                    contentSections++;
                                }
                            }
                        }
                        if (contentSections >= 20) break;
                    }

                    // Buttons
                    const allButtons = document.querySelectorAll('button, [role="button"], input[type="submit"]');
                    const buttons = [];
                    for (const btn of allButtons) {
                        if (vis(btn)) {
                            const t = txt(btn);
                            if (t && t.length < 40 && !buttons.includes(t)) buttons.push(t);
                        }
                        if (buttons.length >= 20) break;
                    }

                    // Forms / inputs
                    const inputs = document.querySelectorAll('input:not([type="hidden"]), textarea, select');
                    const formFields = [];
                    for (const inp of inputs) {
                        if (vis(inp)) {
                            formFields.push({
                                type: inp.type || inp.tagName.toLowerCase(),
                                placeholder: inp.placeholder || '',
                                label: inp.getAttribute('aria-label') || '',
                                name: inp.name || '',
                            });
                        }
                        if (formFields.length >= 10) break;
                    }

                    // Footer
                    const footer = document.querySelector('footer, [role="contentinfo"]');
                    const footerLinks = [];
                    if (footer) {
                        const flinks = footer.querySelectorAll('a');
                        for (const a of flinks) {
                            if (vis(a)) {
                                const t = txt(a);
                                if (t && t.length < 40) footerLinks.push(t);
                            }
                            if (footerLinks.length >= 15) break;
                        }
                    }

                    // Modals / overlays
                    const modals = document.querySelectorAll(
                        '[role="dialog"], [class*="modal"], [class*="overlay"], [class*="popup"]'
                    );
                    let activeModal = null;
                    for (const m of modals) {
                        if (vis(m)) {
                            activeModal = txt(m).substring(0, 200);
                            break;
                        }
                    }

                    // Background color / theme hint
                    const bg = window.getComputedStyle(document.body).backgroundColor;

                    return {
                        header_items: headerItems,
                        header_count: headerItems.length,
                        content_sections: sectionNames,
                        content_section_count: sectionNames.length,
                        buttons: buttons,
                        button_count: buttons.length,
                        form_fields: formFields,
                        form_field_count: formFields.length,
                        footer_links: footerLinks,
                        footer_link_count: footerLinks.length,
                        active_modal: activeModal,
                        page_title: document.title,
                        bg_color: bg,
                        scroll_height: document.documentElement.scrollHeight,
                        viewport_height: window.innerHeight,
                    };
                }"""
                inventory = page.evaluate(inventory_js)
                respond(inventory)

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

            elif action == "content_fingerprint":
                result = page.evaluate(CONTENT_FINGERPRINT_JS)
                respond({"fingerprint": result})

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
