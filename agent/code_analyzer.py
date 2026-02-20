"""
Code Analyzer – uses AWS Bedrock to analyze code changes and identify crash causes.

When a crash is detected, this module:
1. Fetches recent code changes (from git or deployment info)
2. Uses Bedrock to analyze code and identify potential crash causes
3. Determines if the crash is likely reproducible based on code analysis
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from agent.config import AWS_REGION, BEDROCK_MODEL_ID, AGENT_ENV
from agent.observability import logger


def analyze_crash_reproducibility(
    crash_details: dict[str, Any],
    deployment_info: dict[str, Any] | None = None,
    code_repo_path: str | None = None,
) -> dict[str, Any]:
    """
    Analyze code to determine if a crash is reproducible.
    
    Args:
        crash_details: Crash information from anomaly_detector
        deployment_info: Recent deployment info (feature, commit, etc.)
        code_repo_path: Path to code repository (optional)
    
    Returns:
        Analysis result with:
            - is_reproducible: bool
            - confidence: float (0-1)
            - likely_cause: str
            - affected_files: list[str]
            - reproduction_steps: list[str]
            - code_analysis: str
    """
    if AGENT_ENV == "demo":
        return _analyze_crash_demo(crash_details, deployment_info)
    
    # Get code changes
    code_changes = _get_recent_code_changes(deployment_info, code_repo_path)
    
    # Use Bedrock to analyze
    analysis = _analyze_with_bedrock(crash_details, code_changes, deployment_info)
    
    return analysis


def _get_recent_code_changes(
    deployment_info: dict[str, Any] | None,
    code_repo_path: str | None,
) -> dict[str, Any]:
    """Fetch recent code changes from git or deployment info."""
    changes = {
        "files_changed": [],
        "diff": "",
        "commit_sha": None,
        "feature_name": None,
    }
    
    if deployment_info:
        changes["feature_name"] = deployment_info.get("feature_name")
        changes["commit_sha"] = deployment_info.get("tags", {}).get("commit") if isinstance(deployment_info.get("tags"), dict) else None
    
    # Try to get git diff if repo path is provided
    if code_repo_path and Path(code_repo_path).exists():
        try:
            # Get last commit diff
            result = subprocess.run(
                ["git", "diff", "HEAD~1", "HEAD"],
                cwd=code_repo_path,
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                changes["diff"] = result.stdout[:5000]  # Limit size
                
                # Get changed files
                result = subprocess.run(
                    ["git", "diff", "--name-only", "HEAD~1", "HEAD"],
                    cwd=code_repo_path,
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                if result.returncode == 0:
                    changes["files_changed"] = [f.strip() for f in result.stdout.split("\n") if f.strip()]
        except Exception as e:
            logger.warning(f"Failed to get git diff: {e}")
    
    return changes


def _analyze_with_bedrock(
    crash_details: dict[str, Any],
    code_changes: dict[str, Any],
    deployment_info: dict[str, Any] | None,
) -> dict[str, Any]:
    """Use Bedrock to analyze crash and code changes."""
    try:
        import boto3
        
        client = boto3.client("bedrock-runtime", region_name=AWS_REGION)
        
        # Build analysis prompt
        prompt = _build_analysis_prompt(crash_details, code_changes, deployment_info)
        
        body = json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 2048,
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ],
        })
        
        response = client.invoke_model(
            modelId=BEDROCK_MODEL_ID,
            contentType="application/json",
            accept="application/json",
            body=body,
        )
        
        result = json.loads(response["body"].read())
        analysis_text = result.get("content", [{}])[0].get("text", "")
        
        # Parse structured response from Bedrock
        analysis = _parse_bedrock_response(analysis_text, crash_details)
        
        return analysis
    
    except Exception as e:
        logger.error(f"Bedrock analysis failed: {e}")
        return {
            "is_reproducible": True,  # Default to true if analysis fails
            "confidence": 0.5,
            "likely_cause": f"Analysis failed: {e}",
            "affected_files": code_changes.get("files_changed", []),
            "reproduction_steps": [],
            "code_analysis": "Unable to analyze code - Bedrock call failed",
        }


def _build_analysis_prompt(
    crash_details: dict[str, Any],
    code_changes: dict[str, Any],
    deployment_info: dict[str, Any] | None,
) -> str:
    """Build prompt for Bedrock code analysis."""
    
    crash_info = f"""
Crash Details:
- Service: {crash_details.get('service', 'unknown')}
- Error: {crash_details.get('error_message', 'N/A')}
- Description: {crash_details.get('description', 'N/A')}
- Timestamp: {crash_details.get('timestamp', 'N/A')}
"""
    
    if crash_details.get('stack_trace'):
        crash_info += f"- Stack Trace: {crash_details['stack_trace']}\n"
    
    code_info = ""
    if code_changes.get("files_changed"):
        code_info = f"""
Recent Code Changes:
- Files Changed: {', '.join(code_changes['files_changed'][:10])}
- Feature: {code_changes.get('feature_name', 'unknown')}
- Commit: {code_changes.get('commit_sha', 'N/A')}

Code Diff (last 2000 chars):
{code_changes.get('diff', 'No diff available')[-2000:]}
"""
    
    deployment_info_text = ""
    if deployment_info:
        deployment_info_text = f"""
Deployment Info:
- Feature: {deployment_info.get('feature_name', 'unknown')}
- Environment: {deployment_info.get('environment', 'unknown')}
- Deployed: {deployment_info.get('timestamp', 'N/A')}
"""
    
    prompt = f"""You are a senior QA engineer analyzing a production crash to determine if it's reproducible.

{crash_info}

{deployment_info_text}

{code_info}

Based on the crash details and recent code changes, analyze:

1. **Is this crash reproducible?** (yes/no)
   - Consider: Does the code change directly relate to the crash?
   - Are there obvious bugs in the diff that would cause this error?
   - Is the crash pattern consistent with the code changes?

2. **Confidence level** (0.0 to 1.0):
   - High (0.8-1.0): Clear code bug matching crash pattern
   - Medium (0.5-0.8): Likely related but needs verification
   - Low (0.0-0.5): Unclear relationship

3. **Likely root cause** (1-2 sentences):
   - What specific code issue likely caused this crash?

4. **Affected files** (list):
   - Which files are most likely responsible?

5. **Reproduction steps** (ordered list):
   - How to reproduce this crash in alpha/production?

Respond in JSON format:
{{
  "is_reproducible": true/false,
  "confidence": 0.0-1.0,
  "likely_cause": "explanation",
  "affected_files": ["file1", "file2"],
  "reproduction_steps": ["step1", "step2", "step3"]
}}
"""
    
    return prompt


def _parse_bedrock_response(
    response_text: str,
    crash_details: dict[str, Any],
) -> dict[str, Any]:
    """Parse Bedrock's JSON response."""
    try:
        # Try to extract JSON from response
        import re
        
        # Look for JSON block
        json_match = re.search(r'\{[^{}]*"is_reproducible"[^{}]*\}', response_text, re.DOTALL)
        if json_match:
            analysis = json.loads(json_match.group())
        else:
            # Try parsing entire response as JSON
            analysis = json.loads(response_text)
        
        return {
            "is_reproducible": analysis.get("is_reproducible", True),
            "confidence": float(analysis.get("confidence", 0.5)),
            "likely_cause": analysis.get("likely_cause", "Unable to determine"),
            "affected_files": analysis.get("affected_files", []),
            "reproduction_steps": analysis.get("reproduction_steps", []),
            "code_analysis": response_text[:1000],  # Store full analysis
        }
    
    except Exception as e:
        logger.warning(f"Failed to parse Bedrock response: {e}")
        # Fallback: try to infer from text
        is_reproducible = "reproducible" in response_text.lower() or "yes" in response_text.lower()[:100]
        
        return {
            "is_reproducible": is_reproducible,
            "confidence": 0.5,
            "likely_cause": "Unable to parse analysis - see code_analysis field",
            "affected_files": [],
            "reproduction_steps": [],
            "code_analysis": response_text[:1000],
        }


def _analyze_crash_demo(
    crash_details: dict[str, Any],
    deployment_info: dict[str, Any] | None,
) -> dict[str, Any]:
    """Demo mode: return synthetic analysis."""
    return {
        "is_reproducible": True,
        "confidence": 0.85,
        "likely_cause": "Null pointer exception in playback buffer - recent code change removed null check",
        "affected_files": ["PlaybackService.java", "BufferManager.java"],
        "reproduction_steps": [
            "1. Navigate to video playback page",
            "2. Start playback with empty buffer",
            "3. Crash occurs when buffer.process() is called without null check",
        ],
        "code_analysis": "Demo mode: Crash appears reproducible based on recent code changes removing null safety checks.",
    }

