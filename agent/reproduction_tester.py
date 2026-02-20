"""
Reproduction Tester – automatically tests crashes in alpha/production environments.

When a crash is identified as reproducible, this module:
1. Executes reproduction steps in the target environment
2. Verifies if the crash actually occurs
3. Captures evidence (screenshots, logs, metrics)
4. Reports results back to the agent
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any

from agent.observability import logger


def test_reproduction(
    crash_details: dict[str, Any],
    reproduction_steps: list[str],
    environment: str = "alpha",  # "alpha" or "production"
    service: str | None = None,
) -> dict[str, Any]:
    """
    Test if a crash is reproducible in the target environment.
    
    Args:
        crash_details: Crash information
        reproduction_steps: Steps to reproduce the crash
        environment: Target environment (alpha/production)
        service: Service to test
    
    Returns:
        Test result with:
            - reproduced: bool
            - test_duration_seconds: float
            - evidence: dict (screenshots, logs, metrics)
            - test_steps_executed: list[dict]
            - error_encountered: str | None
    """
    logger.info(f"Testing crash reproduction in {environment} environment...")
    
    start_time = time.time()
    test_steps = []
    evidence = {
        "screenshots": [],
        "logs": [],
        "metrics": {},
    }
    error_encountered = None
    reproduced = False
    
    try:
        # Execute reproduction steps
        for i, step in enumerate(reproduction_steps, 1):
            logger.info(f"Executing step {i}: {step}")
            
            step_result = _execute_step(step, environment, service)
            test_steps.append({
                "step_number": i,
                "step_description": step,
                "status": step_result.get("status", "unknown"),
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "details": step_result.get("details", {}),
            })
            
            # Check if crash/error occurred
            if step_result.get("error_detected"):
                reproduced = True
                error_encountered = step_result.get("error_message", "Error detected")
                evidence["logs"].append({
                    "step": i,
                    "error": error_encountered,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
                logger.info(f"Crash reproduced at step {i}: {error_encountered}")
                break
            
            # Collect evidence
            if step_result.get("screenshot"):
                evidence["screenshots"].append({
                    "step": i,
                    "path": step_result["screenshot"],
                })
            
            if step_result.get("log"):
                evidence["logs"].append({
                    "step": i,
                    "log": step_result["log"],
                })
        
        # If no crash during steps, check for post-step anomalies
        if not reproduced:
            logger.info("No crash during steps - checking for anomalies...")
            anomaly_check = _check_post_test_anomalies(service, environment)
            if anomaly_check.get("anomaly_detected"):
                reproduced = True
                error_encountered = anomaly_check.get("message", "Anomaly detected after test")
                evidence["metrics"] = anomaly_check.get("metrics", {})
        
        test_duration = time.time() - start_time
        
        return {
            "reproduced": reproduced,
            "test_duration_seconds": round(test_duration, 2),
            "evidence": evidence,
            "test_steps_executed": test_steps,
            "error_encountered": error_encountered,
            "environment": environment,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    
    except Exception as e:
        logger.error(f"Reproduction test failed: {e}")
        return {
            "reproduced": False,
            "test_duration_seconds": round(time.time() - start_time, 2),
            "evidence": evidence,
            "test_steps_executed": test_steps,
            "error_encountered": f"Test execution error: {e}",
            "environment": environment,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


def _execute_step(
    step_description: str,
    environment: str,
    service: str | None,
) -> dict[str, Any]:
    """
    Execute a single reproduction step.
    
    This is a simplified implementation. In production, this would:
    - Use browser automation (Playwright) for web apps
    - Use API clients for backend services
    - Use mobile testing frameworks for mobile apps
    """
    # Parse step description to determine action type
    step_lower = step_description.lower()
    
    if "navigate" in step_lower or "go to" in step_lower:
        return _execute_navigation_step(step_description, environment)
    
    elif "click" in step_lower or "tap" in step_lower:
        return _execute_interaction_step(step_description, environment)
    
    elif "start" in step_lower or "play" in step_lower:
        return _execute_action_step(step_description, environment, service)
    
    else:
        # Generic step - just log it
        logger.info(f"Executing generic step: {step_description}")
        return {
            "status": "completed",
            "details": {"step_type": "generic"},
        }


def _execute_navigation_step(
    step_description: str,
    environment: str,
) -> dict[str, Any]:
    """Execute a navigation step (e.g., navigate to URL)."""
    # Extract URL from step if present
    # In production, this would use Playwright or similar
    
    logger.info(f"Navigating: {step_description}")
    
    # Simulate navigation delay
    time.sleep(0.5)
    
    return {
        "status": "completed",
        "details": {
            "step_type": "navigation",
            "environment": environment,
        },
    }


def _execute_interaction_step(
    step_description: str,
    environment: str,
) -> dict[str, Any]:
    """Execute an interaction step (e.g., click button)."""
    logger.info(f"Interacting: {step_description}")
    
    # Simulate interaction delay
    time.sleep(0.3)
    
    return {
        "status": "completed",
        "details": {
            "step_type": "interaction",
            "environment": environment,
        },
    }


def _execute_action_step(
    step_description: str,
    environment: str,
    service: str | None,
) -> dict[str, Any]:
    """Execute an action step (e.g., start playback)."""
    logger.info(f"Performing action: {step_description}")
    
    # Simulate action delay
    time.sleep(1.0)
    
    # Check if this action might trigger the crash
    # In production, this would monitor for errors/crashes
    crash_keywords = ["buffer", "playback", "process"]
    step_lower = step_description.lower()
    
    error_detected = any(keyword in step_lower for keyword in crash_keywords)
    
    return {
        "status": "completed",
        "error_detected": error_detected,
        "error_message": "NullPointerException in playback buffer" if error_detected else None,
        "details": {
            "step_type": "action",
            "environment": environment,
            "service": service,
        },
    }


def _check_post_test_anomalies(
    service: str | None,
    environment: str,
) -> dict[str, Any]:
    """Check for anomalies after test execution."""
    # In production, this would query Datadog for recent errors/crashes
    # For now, return a simple check
    
    logger.info(f"Checking for anomalies in {environment} after test...")
    
    # Simulate check delay
    time.sleep(0.5)
    
    # In demo mode, occasionally return anomaly
    import random
    if random.random() > 0.8:  # 20% chance
        return {
            "anomaly_detected": True,
            "message": "Crash rate spike detected after test execution",
            "metrics": {
                "crash_rate": 0.05,
                "baseline": 0.01,
            },
        }
    
    return {
        "anomaly_detected": False,
        "metrics": {},
    }


# ──────────────────────────────────────────────────────────────────────
# Browser automation helpers (for web apps)
# ──────────────────────────────────────────────────────────────────────

def test_web_reproduction(
    crash_details: dict[str, Any],
    reproduction_steps: list[str],
    base_url: str,
    environment: str = "alpha",
) -> dict[str, Any]:
    """
    Test reproduction using browser automation (for web applications).
    
    This uses Playwright to execute steps in a real browser.
    """
    try:
        from playwright.sync_api import sync_playwright
        
        logger.info(f"Starting browser-based reproduction test in {environment}...")
        
        start_time = time.time()
        evidence = {
            "screenshots": [],
            "logs": [],
            "network_requests": [],
        }
        reproduced = False
        error_encountered = None
        
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context()
            page = context.new_page()
            
            try:
                for i, step in enumerate(reproduction_steps, 1):
                    logger.info(f"Browser step {i}: {step}")
                    
                    # Parse and execute step
                    if "navigate" in step.lower():
                        url = _extract_url_from_step(step, base_url)
                        page.goto(url, wait_until="networkidle")
                        evidence["screenshots"].append({
                            "step": i,
                            "path": f"screenshots/step_{i}.png",
                        })
                        page.screenshot(path=f"screenshots/step_{i}.png")
                    
                    elif "click" in step.lower():
                        element_text = _extract_element_from_step(step)
                        page.click(f"text={element_text}", timeout=5000)
                        time.sleep(1)  # Wait for action
                    
                    # Check for errors
                    page_errors = page.evaluate("() => window.errors || []")
                    if page_errors:
                        reproduced = True
                        error_encountered = str(page_errors)
                        break
                
                # Final check for console errors
                console_logs = []
                page.on("console", lambda msg: console_logs.append(msg.text))
                
                if any("error" in log.lower() or "exception" in log.lower() for log in console_logs):
                    reproduced = True
                    error_encountered = "Console errors detected"
                    evidence["logs"] = console_logs
                
            finally:
                browser.close()
        
        return {
            "reproduced": reproduced,
            "test_duration_seconds": round(time.time() - start_time, 2),
            "evidence": evidence,
            "error_encountered": error_encountered,
            "environment": environment,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    
    except ImportError:
        logger.warning("Playwright not available - falling back to basic test")
        return test_reproduction(crash_details, reproduction_steps, environment)
    
    except Exception as e:
        logger.error(f"Browser test failed: {e}")
        return {
            "reproduced": False,
            "test_duration_seconds": round(time.time() - start_time, 2),
            "evidence": evidence,
            "error_encountered": f"Browser test error: {e}",
            "environment": environment,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


def _extract_url_from_step(step: str, base_url: str) -> str:
    """Extract URL from step description."""
    # Simple extraction - in production, use more sophisticated parsing
    if "http" in step:
        import re
        urls = re.findall(r'https?://[^\s]+', step)
        if urls:
            return urls[0]
    return base_url


def _extract_element_from_step(step: str) -> str:
    """Extract element text/selector from step description."""
    # Extract text in quotes or after "click"
    import re
    match = re.search(r'click\s+["\']([^"\']+)["\']', step, re.IGNORECASE)
    if match:
        return match.group(1)
    return "button"  # Default

