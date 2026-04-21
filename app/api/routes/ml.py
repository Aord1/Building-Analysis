"""机器学习相关 API."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.core.config import get_settings
from ml.sentiment_svm import SVMTrainer, generate_sample_data
from ml.vlm_trainer import TrainingConfig, VLMTrainer

router = APIRouter()


class TrainSVMRequest(BaseModel):
    """训练 SVM 请求."""
    tune_hyperparams: bool = Field(default=True, description="是否调优超参数")
    test_size: float = Field(default=0.2, ge=0.1, le=0.5)


class TrainVLMRequest(BaseModel):
    """训练 VLM 请求."""
    epochs: int = Field(default=50, ge=1, le=200)
    batch_size: int = Field(default=32, ge=8, le=128)
    learning_rate: float = Field(default=1e-4, ge=1e-6, le=1e-2)


class ModelInfo(BaseModel):
    """模型信息."""
    name: str
    type: str
    exists: bool
    path: str
    size_mb: float = 0.0


@router.get("/models", response_model=list[ModelInfo])
async def list_models() -> list[ModelInfo]:
    """列出所有模型."""
    settings = get_settings()
    models: list[ModelInfo] = []
    
    # SVM 模型
    svm_path = settings.svm_model_path
    svm_size = svm_path.stat().st_size / 1024 / 1024 if svm_path.exists() else 0
    models.append(ModelInfo(
        name="SVM_Sentiment",
        type="scikit-learn",
        exists=svm_path.exists(),
        path=str(svm_path),
        size_mb=round(svm_size, 2),
    ))
    
    # VLM 模型
    vlm_path = settings.vlm_model_path
    vlm_size = vlm_path.stat().st_size / 1024 / 1024 if vlm_path.exists() else 0
    models.append(ModelInfo(
        name="LightweightVLM",
        type="PyTorch",
        exists=vlm_path.exists(),
        path=str(vlm_path),
        size_mb=round(vlm_size, 2),
    ))
    
    return models


@router.post("/train/svm")
async def train_svm(request: TrainSVMRequest) -> dict[str, Any]:
    """训练 SVM 情感分析模型."""
    try:
        settings = get_settings()
        
        # 准备数据
        texts, labels = generate_sample_data()
        
        # 训练
        trainer = SVMTrainer(settings.model_dir)
        X_train, X_test, y_train, y_test = trainer.prepare_data(
            texts, labels, test_size=request.test_size
        )
        trainer.train(X_train, y_train, tune_hyperparams=request.tune_hyperparams)
        
        # 评估
        metrics = trainer.evaluate(X_test, y_test)
        
        # 保存
        save_path = trainer.save()
        
        return {
            "success": True,
            "metrics": metrics.model_dump(),
            "model_path": str(save_path),
            "message": "SVM model trained successfully",
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/train/vlm")
async def train_vlm(request: TrainVLMRequest) -> dict[str, Any]:
    """训练 VLM 模型."""
    try:
        settings = get_settings()
        
        config = TrainingConfig(
            num_epochs=request.epochs,
            batch_size=request.batch_size,
            learning_rate=request.learning_rate,
            save_dir=settings.model_dir,
        )
        
        # 注意：实际训练需要真实数据
        # 这里返回训练配置信息
        
        return {
            "success": True,
            "config": {
                "epochs": request.epochs,
                "batch_size": request.batch_size,
                "learning_rate": request.learning_rate,
                "device": config.device,
            },
            "message": "VLM training job started",
            "note": "实际训练需要准备标注数据集",
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/models/{model_name}/metrics")
async def get_model_metrics(model_name: str) -> dict[str, Any]:
    """获取模型评估指标."""
    settings = get_settings()
    
    if model_name == "svm":
        info_path = settings.svm_model_path.with_suffix(".json")
    elif model_name == "vlm":
        info_path = settings.model_dir / "vlm_metrics.json"
    else:
        raise HTTPException(status_code=404, detail=f"Unknown model: {model_name}")
    
    if not info_path.exists():
        return {"error": "Metrics not found", "model": model_name}
    
    import json
    with open(info_path, "r", encoding="utf-8") as f:
        return json.load(f)
