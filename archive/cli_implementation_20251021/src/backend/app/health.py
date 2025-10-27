from fastapi import APIRouter
from app.config import settings

router = APIRouter()

@router.get("/status")
async def health_status():
    return {"status": "ok"}

@router.get("/features")
async def feature_status():
    return {
        "feature_003_001": settings.feature_003_001_enabled,
        "feature_003_002": settings.feature_003_002_enabled,
        "feature_003_003": settings.feature_003_003_enabled,
        "feature_003_004": settings.feature_003_004_enabled,
        "feature_003_005": settings.feature_003_005_enabled,
        "feature_003_006": settings.feature_003_006_enabled
    }