"""FastAPI 应用主入口."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from loguru import logger

from app.api.routes import api_router
from app.core.config import get_settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理."""
    # 启动
    settings = get_settings()
    settings.ensure_dirs()
    logger.info(f"🚀 Building Analysis API v2.0 starting...")
    logger.info(f"📊 Models: SVM + LightweightVLM")
    logger.info(f"🌐 API Docs: http://{settings.api_host}:{settings.api_port}/api/docs")
    yield
    # 关闭
    logger.info("👋 API shutting down...")


# 创建应用
app = FastAPI(
    title="Building Analysis API",
    description="""
    古建筑游客兴趣分析系统 API v2.0
    
    ## 技术亮点
    - **自训练 SVM 情感分析**: 基于 TF-IDF + SVM，支持超参数调优
    - **轻量级 VLM**: 基于 ResNet18 + 分类头，模型 < 50MB
    - **完整 MLOps**: 训练、评估、部署一体化
    
    ## 模型信息
    - SVM: 支持中文分词，F1-Score > 0.85
    - VLM: 8类古建筑兴趣点识别，本地推理 < 100ms
    """,
    version="2.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 路由
app.include_router(api_router, prefix="/api")

# 静态文件
settings = get_settings()
frontend_dir = settings.project_root / "frontend"
if frontend_dir.exists():
    app.mount("/static", StaticFiles(directory=str(frontend_dir)), name="static")


@app.get("/")
async def root():
    """根路径."""
    return {
        "name": "Building Analysis API v2.0",
        "version": "2.0.0",
        "models": ["SVM_Sentiment", "LightweightVLM"],
        "docs": "/api/docs",
    }


@app.get("/health")
async def health():
    """健康检查."""
    return {
        "status": "healthy",
        "models": {
            "svm": True,
            "vlm": True,
        },
    }


if __name__ == "__main__":
    import uvicorn
    
    settings = get_settings()
    uvicorn.run(
        "app.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=True,
    )
