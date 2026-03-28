from fastapi import APIRouter

from src.apps.logistics.api.v1 import router as v1_router

# Primary planned API surface: /api/v1/<resource-family>
logistics_router = APIRouter()
logistics_router.include_router(v1_router)

# Backward-compatible alias while clients migrate from /api/v1/logistics/*
legacy_logistics_router = APIRouter(prefix="/logistics", tags=["logistics-legacy"])
legacy_logistics_router.include_router(v1_router)
logistics_router.include_router(legacy_logistics_router)
