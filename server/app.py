"""
FastAPI server for the Release Revert Risk Advisor.

Endpoints:
    POST /api/assess        – Run a risk assessment
    GET  /api/runs          – List past runs
    GET  /api/runs/{run_id} – Get a specific run
    GET  /api/telemetry     – Agent observability data
    GET  /api/services      – Available services (from demo data)
    GET  /api/health        – Health check
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from agent.main import run_agent
from agent.config import EVALS_DIR, REVERT_HISTORY_PATH
from agent.observability import get_telemetry

app = FastAPI(
    title="Release Revert Risk Advisor",
    description="AI agent that assesses release risk based on historical revert patterns",
    version="1.0.0",
)

# ── CORS for React dev server ──
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ──────────────────────────────────────────────────────────────────────
# Request / Response models
# ──────────────────────────────────────────────────────────────────────

class AssessRequest(BaseModel):
    feature_name: str = Field(..., description="Name of the feature/experiment")
    service: str = Field(..., description="Service tag (e.g. playback-service)")
    platform: str | None = Field(None, description="Target platform (ios/android/web/all)")
    time_window_days: int = Field(30, description="Historical lookback window in days")
    tags: list[str] | None = Field(None, description="Optional tags for matching")
    post_deploy_minutes: int = Field(60, description="Post-deploy observation window")


class AssessResponse(BaseModel):
    run_id: str
    feature_name: str
    service: str
    platform: str
    risk_score: int
    recommendation: str
    summary: str
    risk_drivers: list[str]
    monitoring_checks: list[str]
    rollback_thresholds: list[dict[str, Any]]
    rollout_guidance: str
    matched_patterns: list[dict[str, Any]]
    scoring_breakdown: dict[str, float]
    evidence: list[str]
    agent_metrics: dict[str, Any]
    timestamp: str


# ──────────────────────────────────────────────────────────────────────
# Endpoints
# ──────────────────────────────────────────────────────────────────────

@app.post("/api/assess", response_model=AssessResponse)
async def assess_risk(req: AssessRequest):
    """Run a full risk assessment for a feature release."""
    try:
        result = run_agent(
            feature_name=req.feature_name,
            service=req.service,
            platform=req.platform,
            time_window_days=req.time_window_days,
            tags=req.tags,
            post_deploy_minutes=req.post_deploy_minutes,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/runs")
async def list_runs():
    """List all past assessment runs."""
    runs = []
    if EVALS_DIR.exists():
        for path in sorted(EVALS_DIR.glob("run_*.json"), reverse=True):
            try:
                with open(path) as f:
                    data = json.load(f)
                runs.append({
                    "run_id": data.get("run_id", path.stem),
                    "feature_name": data.get("feature_name", ""),
                    "service": data.get("service", ""),
                    "risk_score": data.get("risk_score", 0),
                    "recommendation": data.get("recommendation", ""),
                    "timestamp": data.get("timestamp", ""),
                })
            except Exception:
                continue
    return {"runs": runs, "total": len(runs)}


@app.get("/api/runs/{run_id}")
async def get_run(run_id: str):
    """Get details of a specific run."""
    path = EVALS_DIR / f"run_{run_id}.json"
    if not path.exists():
        # Try finding by partial match
        candidates = list(EVALS_DIR.glob(f"run_{run_id}*.json"))
        if candidates:
            path = candidates[0]
        else:
            raise HTTPException(status_code=404, detail="Run not found")
    with open(path) as f:
        return json.load(f)


@app.get("/api/telemetry")
async def get_agent_telemetry():
    """Return agent observability telemetry."""
    telem = get_telemetry()
    return {
        "total_runs": len(telem["runs"]),
        "total_dd_queries": len(telem["dd_queries"]),
        "runs": telem["runs"][-20:],  # Last 20
        "dd_queries": telem["dd_queries"][-50:],  # Last 50
        "summary": {
            "avg_latency_ms": (
                round(sum(r["latency_ms"] for r in telem["runs"]) / len(telem["runs"]), 1)
                if telem["runs"] else 0
            ),
            "avg_risk_score": (
                round(sum(r["risk_score"] for r in telem["runs"] if r["risk_score"] and r["risk_score"] >= 0) /
                      max(len([r for r in telem["runs"] if r["risk_score"] and r["risk_score"] >= 0]), 1), 1)
                if telem["runs"] else 0
            ),
            "recommendation_distribution": _count_recommendations(telem["runs"]),
        },
    }


@app.get("/api/services")
async def list_services():
    """List available services from demo data."""
    try:
        with open(REVERT_HISTORY_PATH) as f:
            data = yaml.safe_load(f)
        baselines = data.get("baselines", {})
        services = []
        for svc, slis in baselines.items():
            services.append({
                "name": svc,
                "slis": list(slis.keys()),
            })
        # Also extract from reverts
        reverts = data.get("reverts", [])
        revert_services = set()
        for rev in reverts:
            revert_services.add(rev.get("service", ""))
        return {
            "services": services,
            "services_with_reverts": list(revert_services),
            "total_reverts": len(reverts),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/health")
async def health_check():
    return {"status": "healthy", "agent": "Release Revert Risk Advisor", "version": "1.0.0"}


def _count_recommendations(runs: list[dict]) -> dict[str, int]:
    counts = {"ship": 0, "ramp": 0, "hold": 0, "error": 0}
    for r in runs:
        rec = r.get("recommendation", "error")
        counts[rec] = counts.get(rec, 0) + 1
    return counts


# ── Serve React UI static files ──
UI_BUILD_DIR = Path(__file__).resolve().parent.parent / "ui" / "build"

if UI_BUILD_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(UI_BUILD_DIR / "static")), name="static")

    @app.get("/{full_path:path}")
    async def serve_react(full_path: str):
        """Serve React app for any non-API route."""
        file_path = UI_BUILD_DIR / full_path
        if file_path.exists() and file_path.is_file():
            return FileResponse(str(file_path))
        return FileResponse(str(UI_BUILD_DIR / "index.html"))

