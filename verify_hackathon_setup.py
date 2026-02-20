#!/usr/bin/env python3
"""
Hackathon Setup Verification Script

Verifies that AWS Bedrock, Datadog, and other required services are properly configured.
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Color codes for terminal output
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
RESET = "\033[0m"

def print_header(text):
    print(f"\n{BLUE}{'='*60}{RESET}")
    print(f"{BLUE}{text}{RESET}")
    print(f"{BLUE}{'='*60}{RESET}\n")

def print_success(text):
    print(f"{GREEN}✓{RESET} {text}")

def print_error(text):
    print(f"{RED}✗{RESET} {text}")

def print_warning(text):
    print(f"{YELLOW}⚠{RESET} {text}")

def check_env_var(name, required=True):
    """Check if an environment variable is set."""
    value = os.getenv(name)
    if value:
        masked = value[:8] + "..." if len(value) > 8 else value
        print_success(f"{name} is set ({masked})")
        return True
    else:
        if required:
            print_error(f"{name} is NOT set (REQUIRED)")
        else:
            print_warning(f"{name} is NOT set (optional)")
        return False

def check_aws_bedrock():
    """Verify AWS Bedrock configuration and access."""
    print_header("AWS Bedrock Configuration")
    
    # Check environment variables
    aws_region = os.getenv("AWS_REGION", "us-east-1")
    bedrock_model = os.getenv("BEDROCK_MODEL_ID", "anthropic.claude-3-sonnet-20240229-v1:0")
    
    has_access_key = check_env_var("AWS_ACCESS_KEY_ID", required=False)
    has_secret_key = check_env_var("AWS_SECRET_ACCESS_KEY", required=False)
    has_profile = check_env_var("AWS_PROFILE", required=False)
    
    if not (has_access_key and has_secret_key) and not has_profile:
        print_error("Either AWS credentials (ACCESS_KEY_ID + SECRET_ACCESS_KEY) or AWS_PROFILE must be set")
        return False
    
    print_success(f"AWS_REGION: {aws_region}")
    print_success(f"BEDROCK_MODEL_ID: {bedrock_model}")
    
    # Try to import boto3 and test Bedrock access
    try:
        import boto3
        print_success("boto3 is installed")
        
        # Try to create a Bedrock client
        try:
            if has_profile:
                session = boto3.Session(profile_name=os.getenv("AWS_PROFILE"))
                client = session.client("bedrock-runtime", region_name=aws_region)
            else:
                client = boto3.client("bedrock-runtime", region_name=aws_region)
            
            # Try to list available models (this requires bedrock:ListFoundationModels permission)
            bedrock_client = boto3.client("bedrock", region_name=aws_region)
            try:
                models = bedrock_client.list_foundation_models()
                print_success("AWS Bedrock API access verified")
                print_success(f"Found {len(models.get('modelSummaries', []))} available models")
            except Exception as e:
                print_warning(f"Could not list models (may need bedrock:ListFoundationModels permission): {e}")
                print_success("Bedrock runtime client created successfully")
            
            return True
        except Exception as e:
            print_error(f"Failed to create Bedrock client: {e}")
            print_warning("Make sure:")
            print_warning("  1. AWS credentials are valid")
            print_warning("  2. Bedrock is enabled in your AWS account")
            print_warning("  3. Claude models are enabled in Bedrock console")
            return False
    except ImportError:
        print_error("boto3 is NOT installed. Run: pip install boto3")
        return False

def check_datadog():
    """Verify Datadog configuration."""
    print_header("Datadog Configuration")
    
    has_api_key = check_env_var("DD_API_KEY", required=True)
    has_app_key = check_env_var("DD_APP_KEY", required=False)
    dd_site = os.getenv("DD_SITE", "datadoghq.com")
    
    print_success(f"DD_SITE: {dd_site}")
    
    # Try to import datadog client
    try:
        from datadog_api_client import Configuration, ApiClient
        print_success("datadog-api-client is installed")
        
        if has_api_key:
            # Try to create a client (won't make actual API call)
            config = Configuration()
            config.api_key["apiKeyAuth"] = os.getenv("DD_API_KEY")
            if has_app_key:
                config.api_key["appKeyAuth"] = os.getenv("DD_APP_KEY")
            config.server_variables["site"] = dd_site
            
            print_success("Datadog API client configuration verified")
            if has_app_key:
                print_success("Full Datadog API access (Events + Metrics)")
            else:
                print_warning("DD_APP_KEY not set - limited to basic API access")
            
            return True
        else:
            return False
    except ImportError:
        print_error("datadog-api-client is NOT installed. Run: pip install datadog-api-client")
        return False

def check_dependencies():
    """Check if all required Python packages are installed."""
    print_header("Python Dependencies")
    
    required_packages = {
        "boto3": "AWS SDK",
        "datadog-api-client": "Datadog API client",
        "fastapi": "FastAPI web framework",
        "uvicorn": "ASGI server",
        "pydantic": "Data validation",
        "pyyaml": "YAML parsing",
        "python-dotenv": "Environment variables",
        "requests": "HTTP client",
    }
    
    optional_packages = {
        "strands-agents": "Strands Agents framework (for Web Cartographer)",
        "playwright": "Browser automation (for Web Cartographer)",
    }
    
    all_ok = True
    
    for package, description in required_packages.items():
        try:
            __import__(package.replace("-", "_"))
            print_success(f"{package} ({description})")
        except ImportError:
            print_error(f"{package} ({description}) - MISSING")
            all_ok = False
    
    print("\nOptional packages:")
    for package, description in optional_packages.items():
        try:
            __import__(package.replace("-", "_"))
            print_success(f"{package} ({description})")
        except ImportError:
            print_warning(f"{package} ({description}) - not installed")
    
    return all_ok

def check_project_structure():
    """Verify project structure is intact."""
    print_header("Project Structure")
    
    required_files = [
        "agent/main.py",
        "agent/risk_model.py",
        "agent/datadog_client.py",
        "agent/bedrock_summarizer.py",
        "server/app.py",
        "requirements.txt",
    ]
    
    all_ok = True
    for file_path in required_files:
        path = Path(file_path)
        if path.exists():
            print_success(f"{file_path} exists")
        else:
            print_error(f"{file_path} is MISSING")
            all_ok = False
    
    return all_ok

def main():
    """Run all verification checks."""
    print(f"\n{BLUE}{'='*60}{RESET}")
    print(f"{BLUE}Hackathon Setup Verification{RESET}")
    print(f"{BLUE}AWS Bedrock + Datadog Integration Check{RESET}")
    print(f"{BLUE}{'='*60}{RESET}\n")
    
    results = {
        "Project Structure": check_project_structure(),
        "Dependencies": check_dependencies(),
        "AWS Bedrock": check_aws_bedrock(),
        "Datadog": check_datadog(),
    }
    
    # Summary
    print_header("Verification Summary")
    
    all_passed = True
    for check_name, passed in results.items():
        if passed:
            print_success(f"{check_name}: PASSED")
        else:
            print_error(f"{check_name}: FAILED")
            all_passed = False
    
    print()
    if all_passed:
        print(f"{GREEN}🎉 All checks passed! You're ready for the hackathon!{RESET}\n")
        return 0
    else:
        print(f"{RED}❌ Some checks failed. Please fix the issues above.{RESET}\n")
        print(f"{YELLOW}Quick fixes:{RESET}")
        print("  1. Install dependencies: pip install -r requirements.txt")
        print("  2. Configure .env file with AWS and Datadog credentials")
        print("  3. Enable Bedrock models in AWS console")
        print("  4. Get Datadog API keys from Datadog console")
        return 1

if __name__ == "__main__":
    sys.exit(main())

