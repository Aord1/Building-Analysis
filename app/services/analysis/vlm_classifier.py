"""VLM 图片分类服务 - 支持自训练模型."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import torch
from loguru import logger

from app.core.config import Settings, get_settings
from app.models.schemas import InterestCategory, VLMPrediction
from ml.vlm_model import ImagePreprocessor, LightweightVLM


class VLMService:
    """VLM 分类服务."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.reports_dir = self.settings.reports_dir
        
        self.model: LightweightVLM | None = None
        self.preprocessor = ImagePreprocessor()
        self.device = torch.device(
            "cuda" if torch.cuda.is_available() else "cpu"
        )
        
        self._load_model()

    def _load_model(self) -> None:
        """加载模型."""
        model_path = self.settings.vlm_model_path

        if model_path.exists():
            try:
                self.model = LightweightVLM.load(model_path, str(self.device))
                self.model.to(self.device)
                logger.info(f"Loaded local VLM from {model_path}")
            except Exception as e:
                logger.error(f"Failed to load local model: {e}")
                self.model = None
        else:
            logger.warning(f"Local model not found at {model_path}")
            self.model = None

    @property
    def is_loaded(self) -> bool:
        """检查模型是否已加载."""
        return self.model is not None

    def predict(self, image_path: str) -> dict[str, Any]:
        """预测单张图片.

        Args:
            image_path: 图片路径

        Returns:
            预测结果字典
        """
        from pathlib import Path

        result = self.classify_image(Path(image_path))
        if result is None:
            return {"labels": [], "confidence": 0.0}

        return {
            "labels": [result.predicted_category.value],
            "confidence": result.confidence,
        }

    def classify_image(
        self,
        image_path: Path,
        note_id: str = "",
        image_name: str = "",
    ) -> VLMPrediction | None:
        """分类单张图片."""
        if self.model is None:
            logger.error("Model not loaded")
            return None
        
        if not image_path.exists():
            logger.warning(f"Image not found: {image_path}")
            return None
        
        try:
            # 预处理
            image_tensor = self.preprocessor(image_path).unsqueeze(0)
            image_tensor = image_tensor.to(self.device)
            
            # 预测
            self.model.eval()
            with torch.no_grad():
                output = self.model(image_tensor)
                logits = output["logits"]
                probabilities = torch.softmax(logits, dim=1)[0]
            
            # 获取预测结果
            conf, pred_id = torch.max(probabilities, dim=0)
            pred_id = pred_id.item()
            conf = conf.item()
            
            # 所有类别的概率
            all_probs = {
                self.model.CATEGORIES[i]: probabilities[i].item()
                for i in range(len(self.model.CATEGORIES))
            }
            
            return VLMPrediction(
                note_id=note_id,
                image_name=image_name or image_path.name,
                image_path=str(image_path.relative_to(self.settings.project_root)),
                predicted_category=InterestCategory(self.model.CATEGORIES[pred_id]),
                predicted_category_zh=self.model.get_category_name_zh(pred_id),
                confidence=round(conf, 4),
                all_probabilities=all_probs,
                is_local_model=True,
            )
            
        except Exception as e:
            logger.error(f"Failed to classify {image_path}: {e}")
            return None

    def classify_batch(
        self,
        records: list[dict[str, Any]],
        limit: int = 0,
    ) -> list[VLMPrediction]:
        """批量分类."""
        if limit > 0:
            records = records[:limit]
        
        predictions: list[VLMPrediction] = []
        
        for i, record in enumerate(records, 1):
            image_path = self.settings.project_root / record["image_path"]
            
            logger.info(f"[{i}/{len(records)}] Classifying {image_path.name}")
            
            pred = self.classify_image(
                image_path=image_path,
                note_id=record.get("note_id", ""),
                image_name=record.get("image_name", ""),
            )
            
            if pred:
                predictions.append(pred)
        
        # 保存结果
        self._save_predictions(predictions)
        
        logger.info(f"Classified {len(predictions)} images")
        return predictions

    def _save_predictions(self, predictions: list[VLMPrediction]) -> Path:
        """保存预测结果."""
        self.settings.ensure_dirs()
        
        output_path = self.reports_dir / "vlm_predictions.json"
        data = [p.model_dump() for p in predictions]
        
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"Saved predictions to {output_path}")
        return output_path

    def run(
        self,
        records: list[dict[str, Any]] | None = None,
        limit: int = 0,
    ) -> list[VLMPrediction]:
        """运行分类流程."""
        if records is None:
            # 从清单加载
            manifest_path = self.reports_dir / "image_manifest.json"
            if not manifest_path.exists():
                logger.warning(f"Image manifest not found: {manifest_path}")
                return []
            
            with open(manifest_path, "r", encoding="utf-8") as f:
                records = json.load(f)
        
        return self.classify_batch(records, limit)


class VLMTrainerService:
    """VLM 训练服务."""
    
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
    
    def train(
        self,
        image_dir: Path | None = None,
        labels_file: Path | None = None,
        epochs: int = 50,
    ) -> dict[str, Any]:
        """训练模型.
        
        实际项目中需要准备标注数据.
        """
        from ml.vlm_trainer import TrainingConfig, VLMTrainer
        
        config = TrainingConfig(
            num_epochs=epochs,
            save_dir=self.settings.model_dir,
            device="cuda" if torch.cuda.is_available() else "cpu",
        )
        
        trainer = VLMTrainer(config)
        # ... 训练逻辑
        
        return {"status": "training_started"}
