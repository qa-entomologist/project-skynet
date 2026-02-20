#!/usr/bin/env python3
"""
Unified entry point for Project Skynet agents.

Usage:
    python run_all.py web-cartographer https://www.example.com
    python run_all.py risk-advisor --feature "my-feature" --service "playback-service"
    python run_all.py risk-advisor --server
"""

import sys
import subprocess
from pathlib import Path

def main():
    if len(sys.argv) < 2:
        print("""
Project Skynet - Multi-Agent AI Platform

Available agents:
  1. web-cartographer  - Autonomous website explorer
  2. risk-advisor      - Release revert risk assessment

Usage:
  python run_all.py web-cartographer <url> [options...]
  python run_all.py risk-advisor [options...]

Examples:
  python run_all.py web-cartographer https://www.ebay.com --headed
  python run_all.py risk-advisor --feature "playback-v2" --service "playback-service"
  python run_all.py risk-advisor --server
        """)
        sys.exit(1)

    agent = sys.argv[1]
    args = sys.argv[2:]

    if agent == "web-cartographer":
        # Run the original run.py with remaining args
        subprocess.run([sys.executable, "run.py"] + args)
    elif agent == "risk-advisor":
        # Run the risk advisor with remaining args
        subprocess.run([sys.executable, "run_risk_advisor.py"] + args)
    else:
        print(f"Unknown agent: {agent}")
        print("Available agents: web-cartographer, risk-advisor")
        sys.exit(1)

if __name__ == "__main__":
    main()



