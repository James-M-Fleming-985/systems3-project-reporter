from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.config import settings
from app.health import router as health_router
from app.features import (
    router_001, router_002, router_003,
    router_004, router_005, router_006
)
from app.exceptions import FeatureDisabledException

app = FastAPI(title="ZnNi Line Report Generator")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.exception_handler(FeatureDisabledException)
async def feature_disabled_handler(request: Request, exc: FeatureDisabledException):
    return JSONResponse(
        status_code=403,
        content={"detail": str(exc)}
    )

app.include_router(health_router, prefix="/api/health", tags=["health"])

if settings.feature_003_001_enabled:
    app.include_router(router_001, prefix="/api/feature-001", tags=["feature-001"])
if settings.feature_003_002_enabled:
    app.include_router(router_002, prefix="/api/feature-002", tags=["feature-002"])
if settings.feature_003_003_enabled:
    app.include_router(router_003, prefix="/api/feature-003", tags=["feature-003"])
if settings.feature_003_004_enabled:
    app.include_router(router_004, prefix="/api/feature-004", tags=["feature-004"])
if settings.feature_003_005_enabled:
    app.include_router(router_005, prefix="/api/feature-005", tags=["feature-005"])
if settings.feature_003_006_enabled:
    app.include_router(router_006, prefix="/api/feature-006", tags=["feature-006"])