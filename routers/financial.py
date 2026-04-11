"""
Financial Governance & Strategic Intelligence Router
CRUD endpoints for targets, actuals, resource costs, profiles, attribution,
forecasts, risks, levers, and bulk import.
"""
import csv
import io
import logging
import uuid
from datetime import datetime
from typing import Optional, List

import yaml
from fastapi import APIRouter, HTTPException, Request, UploadFile, File, Query
from fastapi.responses import JSONResponse

from models.financial_models import (
    FinancialTargetRequest, FinancialActualRequest, ResourceCostRequest,
    ProgramProfileRequest, AttributionRequest,
    VALID_PERIODS, VALID_COST_TYPES, VALID_CONTRIBUTION_TYPES,
)
from repositories.financial_repository import FinancialRepository

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/financial", tags=["financial"])

# Module-level repository — initialised per-user in helper
_repos: dict = {}


def _get_repo(user_id: str = "default") -> FinancialRepository:
    """Get or create a FinancialRepository for the given user."""
    if user_id not in _repos:
        import os
        from pathlib import Path
        base = os.getenv("DATA_STORAGE_PATH")
        if base is None:
            base = str(Path(__file__).resolve().parent.parent / "data")
        storage_dir = os.path.join(base, "users", user_id, "financial")
        _repos[user_id] = FinancialRepository(storage_dir=storage_dir)
    return _repos[user_id]


def _user_id_from_request(request: Request) -> str:
    """Extract user_id from JWT cookie or default."""
    try:
        from services.auth_service import get_current_user_optional
        user = get_current_user_optional(request)
        if user and hasattr(user, "user_id"):
            return user.user_id
    except Exception:
        pass
    return "default"


# ======================================================================
# Financial Targets
# ======================================================================

@router.post("/targets")
async def create_target(payload: FinancialTargetRequest, request: Request):
    if payload.period not in VALID_PERIODS:
        raise HTTPException(400, f"Invalid period. Must be one of: {', '.join(VALID_PERIODS)}")
    if payload.revenue_target < 0 or payload.cost_budget < 0:
        raise HTTPException(400, "Revenue target and cost budget must be non-negative")

    repo = _get_repo(_user_id_from_request(request))
    target = payload.model_dump()
    saved = repo.save_target(target)
    return JSONResponse(content={"status": "success", "data": saved})


@router.get("/targets")
async def list_targets(
    request: Request,
    program_id: Optional[str] = Query(None),
    period: Optional[str] = Query(None),
):
    repo = _get_repo(_user_id_from_request(request))
    targets = repo.list_targets(program_id=program_id, period=period)
    return JSONResponse(content={"status": "success", "data": targets})


@router.get("/targets/{target_id}")
async def get_target(target_id: str, request: Request):
    repo = _get_repo(_user_id_from_request(request))
    target = repo.get_target(target_id)
    if target is None:
        raise HTTPException(404, "Target not found")
    return JSONResponse(content={"status": "success", "data": target})


@router.delete("/targets/{target_id}")
async def delete_target(target_id: str, request: Request):
    repo = _get_repo(_user_id_from_request(request))
    deleted = repo.delete_target(target_id)
    if not deleted:
        raise HTTPException(404, "Target not found")
    return JSONResponse(content={"status": "success", "message": "Target deleted"})


# ======================================================================
# Financial Actuals
# ======================================================================

@router.post("/actuals")
async def create_actual(payload: FinancialActualRequest, request: Request):
    if payload.period not in VALID_PERIODS:
        raise HTTPException(400, f"Invalid period. Must be one of: {', '.join(VALID_PERIODS)}")

    repo = _get_repo(_user_id_from_request(request))
    actual = payload.model_dump()
    saved = repo.save_actual(actual)

    # Calculate variance against matching target
    variance = _calculate_variance(repo, saved)

    # Trigger forecast refresh (best-effort)
    _trigger_forecast_refresh(repo, saved.get("program_id"))

    # Trigger risk check (best-effort)
    _trigger_risk_check(repo, saved.get("program_id"))

    return JSONResponse(content={
        "status": "success",
        "data": saved,
        "variance": variance,
    })


@router.get("/actuals")
async def list_actuals(
    request: Request,
    program_id: Optional[str] = Query(None),
    period: Optional[str] = Query(None),
):
    repo = _get_repo(_user_id_from_request(request))
    actuals = repo.list_actuals(program_id=program_id, period=period)
    return JSONResponse(content={"status": "success", "data": actuals})


@router.get("/actuals/{actual_id}")
async def get_actual(actual_id: str, request: Request):
    repo = _get_repo(_user_id_from_request(request))
    actual = repo.get_actual(actual_id)
    if actual is None:
        raise HTTPException(404, "Actual not found")
    return JSONResponse(content={"status": "success", "data": actual})


# ======================================================================
# Resource Costs
# ======================================================================

@router.post("/resource-costs")
async def create_resource_cost(payload: ResourceCostRequest, request: Request):
    if payload.period not in VALID_PERIODS:
        raise HTTPException(400, f"Invalid period. Must be one of: {', '.join(VALID_PERIODS)}")
    if payload.cost_type not in VALID_COST_TYPES:
        raise HTTPException(400, f"Invalid cost_type. Must be one of: {', '.join(VALID_COST_TYPES)}")
    if payload.cost_amount < 0:
        raise HTTPException(400, "Cost amount must be non-negative")

    repo = _get_repo(_user_id_from_request(request))
    cost = payload.model_dump()
    saved = repo.save_resource_cost(cost)
    return JSONResponse(content={"status": "success", "data": saved})


@router.get("/resource-costs")
async def list_resource_costs(
    request: Request,
    program_id: Optional[str] = Query(None),
    period: Optional[str] = Query(None),
    cost_type: Optional[str] = Query(None),
):
    repo = _get_repo(_user_id_from_request(request))
    costs = repo.list_resource_costs(program_id=program_id, period=period, cost_type=cost_type)
    return JSONResponse(content={"status": "success", "data": costs})


@router.get("/resource-costs/summary")
async def resource_cost_summary(
    request: Request,
    program_id: Optional[str] = Query(None),
):
    repo = _get_repo(_user_id_from_request(request))
    summary = repo.get_resource_cost_summary(program_id=program_id)
    return JSONResponse(content={"status": "success", "data": summary})


# ======================================================================
# Program Financial Profiles
# ======================================================================

@router.post("/profiles")
async def save_profile(payload: ProgramProfileRequest, request: Request):
    if payload.contribution_type not in VALID_CONTRIBUTION_TYPES:
        raise HTTPException(400, f"Invalid contribution_type. Must be one of: {', '.join(VALID_CONTRIBUTION_TYPES)}")

    repo = _get_repo(_user_id_from_request(request))
    profile = payload.model_dump()
    saved = repo.save_profile(profile)
    return JSONResponse(content={"status": "success", "data": saved})


@router.get("/profiles")
async def list_profiles(request: Request):
    repo = _get_repo(_user_id_from_request(request))
    profiles = repo.list_profiles()
    return JSONResponse(content={"status": "success", "data": profiles})


@router.get("/profiles/{program_id}")
async def get_profile(program_id: str, request: Request):
    repo = _get_repo(_user_id_from_request(request))
    profile = repo.get_profile(program_id)
    if profile is None:
        raise HTTPException(404, "Profile not found")
    return JSONResponse(content={"status": "success", "data": profile})


# ======================================================================
# Impact Attribution
# ======================================================================

@router.post("/attribution")
async def save_attribution(payload: AttributionRequest, request: Request):
    if not (0 <= payload.attribution_pct <= 100):
        raise HTTPException(400, "attribution_pct must be between 0 and 100")

    repo = _get_repo(_user_id_from_request(request))
    attr = payload.model_dump()
    attr["set_by"] = "manual"
    saved = repo.save_attribution(attr)
    return JSONResponse(content={"status": "success", "data": saved})


@router.get("/attribution")
async def list_attributions(request: Request):
    repo = _get_repo(_user_id_from_request(request))
    attributions = repo.list_attributions()
    return JSONResponse(content={"status": "success", "data": attributions})


@router.get("/attribution/{program_id}")
async def get_attribution(program_id: str, request: Request):
    repo = _get_repo(_user_id_from_request(request))
    attribution = repo.get_attribution(program_id)
    if attribution is None:
        raise HTTPException(404, "Attribution not found")
    return JSONResponse(content={"status": "success", "data": attribution})


# ======================================================================
# Forecasts
# ======================================================================

@router.get("/forecast")
async def list_forecasts(
    request: Request,
    program_id: Optional[str] = Query(None),
):
    repo = _get_repo(_user_id_from_request(request))
    forecasts = repo.list_forecasts(program_id=program_id)
    return JSONResponse(content={"status": "success", "data": forecasts})


@router.post("/forecast/refresh")
async def refresh_forecast(request: Request, program_id: Optional[str] = Query(None)):
    repo = _get_repo(_user_id_from_request(request))
    results = _trigger_forecast_refresh(repo, program_id, force=True)
    return JSONResponse(content={"status": "success", "data": results})


# ======================================================================
# Financial Risks
# ======================================================================

@router.get("/risks")
async def list_financial_risks(
    request: Request,
    program_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
):
    repo = _get_repo(_user_id_from_request(request))
    risks = repo.list_financial_risks(program_id=program_id, status=status)
    return JSONResponse(content={"status": "success", "data": risks})


@router.post("/risks/refresh")
async def refresh_risks(request: Request, program_id: Optional[str] = Query(None)):
    repo = _get_repo(_user_id_from_request(request))
    results = _trigger_risk_check(repo, program_id, force=True)
    return JSONResponse(content={"status": "success", "data": results})


# ======================================================================
# Strategic Levers
# ======================================================================

@router.get("/levers")
async def list_levers(
    request: Request,
    program_id: Optional[str] = Query(None),
):
    repo = _get_repo(_user_id_from_request(request))
    try:
        from services.strategic_lever_engine import StrategicLeverEngine
        engine = StrategicLeverEngine(repo)
        levers = engine.generate_levers(program_id=program_id)
        return JSONResponse(content={"status": "success", "data": levers})
    except ImportError:
        return JSONResponse(content={"status": "success", "data": [], "message": "Strategic lever engine not available"})
    except Exception as exc:
        logger.error(f"Lever generation error: {exc}")
        return JSONResponse(content={"status": "success", "data": [], "message": str(exc)})


# ======================================================================
# Financial Summary (Dashboard KPIs)
# ======================================================================

@router.get("/summary")
async def financial_summary(
    request: Request,
    program_id: Optional[str] = Query(None),
):
    repo = _get_repo(_user_id_from_request(request))
    summary = repo.get_financial_summary(program_id=program_id)
    return JSONResponse(content={"status": "success", "data": summary})


# ======================================================================
# Bulk Import (CSV / YAML)
# ======================================================================

@router.post("/import")
async def import_financial_data(
    request: Request,
    file: UploadFile = File(...),
    data_type: str = Query(..., description="Type of data: targets, actuals, resource_costs"),
):
    if data_type not in ("targets", "actuals", "resource_costs"):
        raise HTTPException(400, "data_type must be one of: targets, actuals, resource_costs")

    repo = _get_repo(_user_id_from_request(request))

    content = await file.read()
    filename = file.filename or ""

    try:
        if filename.endswith(".yaml") or filename.endswith(".yml"):
            rows = _parse_yaml_import(content)
        elif filename.endswith(".csv"):
            rows = _parse_csv_import(content)
        else:
            raise HTTPException(400, "Unsupported file format. Use .csv or .yaml/.yml")
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(400, f"Failed to parse file: {exc}")

    imported = 0
    errors: List[dict] = []

    for i, row in enumerate(rows):
        try:
            _validate_import_row(row, data_type)
            if data_type == "targets":
                repo.save_target(row)
            elif data_type == "actuals":
                repo.save_actual(row)
            elif data_type == "resource_costs":
                repo.save_resource_cost(row)
            imported += 1
        except Exception as exc:
            errors.append({"row": i + 1, "error": str(exc), "data": row})

    return JSONResponse(content={
        "status": "success",
        "data": {
            "total_rows": len(rows),
            "imported": imported,
            "errors": errors,
        },
    })


# ======================================================================
# Helpers
# ======================================================================

def _calculate_variance(repo: FinancialRepository, actual: dict) -> dict:
    """Calculate variance of an actual against matching target."""
    targets = repo.list_targets(
        program_id=actual.get("program_id"),
        period=actual.get("period"),
    )
    if not targets:
        return {"revenue_variance_pct": None, "cost_variance_pct": None, "message": "No matching target found"}

    # Find target for matching period_start, or use closest
    matching = None
    for t in targets:
        if t.get("period_start") == actual.get("period_start"):
            matching = t
            break
    if matching is None:
        matching = targets[0]

    rev_target = matching.get("revenue_target", 0)
    cost_budget = matching.get("cost_budget", 0)
    rev_actual = actual.get("actual_revenue", 0)
    cost_actual = actual.get("actual_cost", 0)

    rev_var = ((rev_actual - rev_target) / rev_target * 100) if rev_target else 0
    cost_var = ((cost_actual - cost_budget) / cost_budget * 100) if cost_budget else 0

    return {
        "revenue_variance_pct": round(rev_var, 2),
        "revenue_variance_abs": round(rev_actual - rev_target, 2),
        "cost_variance_pct": round(cost_var, 2),
        "cost_variance_abs": round(cost_actual - cost_budget, 2),
    }


def _trigger_forecast_refresh(repo: FinancialRepository, program_id: Optional[str] = None, force: bool = False) -> list:
    """Run forecast engine if available."""
    try:
        from services.forecast_engine import ForecastEngine
        engine = ForecastEngine(repo)
        results = engine.generate_forecasts(program_id=program_id)
        return results
    except ImportError:
        logger.debug("Forecast engine not available")
        return []
    except Exception as exc:
        logger.warning(f"Forecast refresh error: {exc}")
        return []


def _trigger_risk_check(repo: FinancialRepository, program_id: Optional[str] = None, force: bool = False) -> list:
    """Run financial risk engine if available."""
    try:
        from services.financial_risk_engine import FinancialRiskEngine
        engine = FinancialRiskEngine(repo)
        risks = engine.evaluate_risks(program_id=program_id)
        return risks
    except ImportError:
        logger.debug("Financial risk engine not available")
        return []
    except Exception as exc:
        logger.warning(f"Risk check error: {exc}")
        return []


def _parse_csv_import(content: bytes) -> List[dict]:
    """Parse CSV content into list of dicts."""
    text = content.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    rows = []
    for row in reader:
        cleaned = {}
        for k, v in row.items():
            k = k.strip().lower().replace(" ", "_")
            if v is not None:
                v = v.strip()
            cleaned[k] = v
        # Convert numeric fields
        for field in ("revenue_target", "cost_budget", "margin_target",
                       "actual_revenue", "actual_cost", "actual_margin",
                       "cost_amount", "billable_hours", "attribution_pct"):
            if field in cleaned and cleaned[field]:
                try:
                    cleaned[field] = float(cleaned[field])
                except (ValueError, TypeError):
                    pass
        rows.append(cleaned)
    return rows


def _parse_yaml_import(content: bytes) -> List[dict]:
    """Parse YAML content into list of dicts."""
    data = yaml.safe_load(content.decode("utf-8"))
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and "records" in data:
        return data["records"]
    if isinstance(data, dict):
        return [data]
    raise ValueError("YAML must be a list of records or a dict with a 'records' key")


def _validate_import_row(row: dict, data_type: str):
    """Basic validation for import rows."""
    if data_type == "targets":
        required = ["revenue_target", "cost_budget", "period", "period_start"]
    elif data_type == "actuals":
        required = ["actual_revenue", "actual_cost", "period", "period_start"]
    elif data_type == "resource_costs":
        required = ["resource_name", "cost_amount", "cost_type", "program_id", "period", "period_start"]
    else:
        required = []

    missing = [f for f in required if not row.get(f)]
    if missing:
        raise ValueError(f"Missing required fields: {', '.join(missing)}")

    period = row.get("period")
    if period and period not in VALID_PERIODS:
        raise ValueError(f"Invalid period '{period}'. Must be one of: {', '.join(VALID_PERIODS)}")

    cost_type = row.get("cost_type")
    if cost_type and cost_type not in VALID_COST_TYPES:
        raise ValueError(f"Invalid cost_type '{cost_type}'. Must be one of: {', '.join(VALID_COST_TYPES)}")
