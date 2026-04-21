"""API 路由聚合."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.routes import dashboard, ml, notes, pipeline, upload

api_router = APIRouter()

# Health check
@api_router.get("/health")
async def health_check():
    return {"status": "ok"}

# 各模块路由
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["Dashboard"])
api_router.include_router(ml.router, prefix="/ml", tags=["ML Models"])
api_router.include_router(notes.router, prefix="/notes", tags=["Notes"])
api_router.include_router(pipeline.router, prefix="/pipeline", tags=["Pipeline"])
api_router.include_router(upload.router, prefix="/upload", tags=["Upload"])
