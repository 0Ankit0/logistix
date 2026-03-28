from fastapi import APIRouter

from .logistics import router as logistics_router

router = APIRouter()
router.include_router(logistics_router)
