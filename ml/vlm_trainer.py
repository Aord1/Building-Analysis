"""
VLM 模型训练器
=============
支持:
- 监督学习训练
- 数据增强
- 学习率调度
- 早停机制
- 模型检查点保存
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from loguru import logger
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    f1_score,
    precision_score,
    recall_score,
)
from torch.utils.data import DataLoader, Dataset
from tqdm import tqdm

from app.models.schemas import ModelMetrics
from ml.vlm_model import ImagePreprocessor, LightweightVLM


@dataclass
class TrainingConfig:
    """训练配置."""
    batch_size: int = 32
    num_epochs: int = 50
    learning_rate: float = 1e-4
    weight_decay: float = 1e-5
    early_stopping_patience: int = 10
    device: str = "auto"
    save_dir: Path = Path("models")
    
    def __post_init__(self) -> None:
        if self.device == "auto":
            self.device = "cuda" if torch.cuda.is_available() else "cpu"


class BuildingImageDataset(Dataset):
    """古建筑图片数据集."""
    
    def __init__(
        self,
        image_paths: list[Path],
        labels: list[int],
        preprocessor: ImagePreprocessor | None = None,
        augment: bool = False,
    ) -> None:
        self.image_paths = image_paths
        self.labels = labels
        self.preprocessor = preprocessor or ImagePreprocessor()
        self.augment = augment
        
        assert len(image_paths) == len(labels), "Paths and labels must match"
    
    def __len__(self) -> int:
        return len(self.image_paths)
    
    def __getitem__(self, idx: int) -> tuple[torch.Tensor, int]:
        image_path = self.image_paths[idx]
        label = self.labels[idx]
        
        try:
            image = self.preprocessor(image_path)
        except Exception as e:
            logger.warning(f"Failed to load {image_path}: {e}")
            # 返回空白图片
            image = torch.zeros(3, 224, 224)
        
        return image, label


class VLMTrainer:
    """VLM 模型训练器."""
    
    def __init__(self, config: TrainingConfig | None = None) -> None:
        self.config = config or TrainingConfig()
        self.device = torch.device(self.config.device)
        
        self.model: LightweightVLM | None = None
        self.optimizer: optim.Optimizer | None = None
        self.scheduler: Any = None
        self.criterion = nn.CrossEntropyLoss()
        
        self.best_val_acc = 0.0
        self.patience_counter = 0
        self.history: dict[str, list[float]] = {
            "train_loss": [],
            "train_acc": [],
            "val_loss": [],
            "val_acc": [],
        }
        
        self.config.save_dir.mkdir(parents=True, exist_ok=True)
    
    def create_model(self, num_categories: int = 8) -> LightweightVLM:
        """创建模型."""
        self.model = LightweightVLM(
            num_categories=num_categories,
            embedding_dim=256,
            freeze_backbone=True,  # 初始冻结骨干网络
        )
        self.model.to(self.device)
        
        # 优化器 - 分层学习率
        backbone_params = []
        other_params = []
        
        for name, param in self.model.named_parameters():
            if "backbone" in name:
                backbone_params.append(param)
            else:
                other_params.append(param)
        
        self.optimizer = optim.AdamW([
            {"params": backbone_params, "lr": self.config.learning_rate * 0.1},
            {"params": other_params, "lr": self.config.learning_rate},
        ], weight_decay=self.config.weight_decay)
        
        # 学习率调度器
        self.scheduler = optim.lr_scheduler.ReduceLROnPlateau(
            self.optimizer, mode="max", factor=0.5, patience=5, verbose=True
        )
        
        return self.model
    
    def train_epoch(self, dataloader: DataLoader) -> tuple[float, float]:
        """训练一个 epoch.
        
        Returns:
            (平均损失, 准确率)
        """
        if self.model is None or self.optimizer is None:
            raise ValueError("Model not initialized")
        
        self.model.train()
        total_loss = 0.0
        all_preds = []
        all_labels = []
        
        pbar = tqdm(dataloader, desc="Training")
        for images, labels in pbar:
            images = images.to(self.device)
            labels = labels.to(self.device)
            
            # 前向传播
            self.optimizer.zero_grad()
            output = self.model(images)
            logits = output["logits"]
            
            loss = self.criterion(logits, labels)
            
            # 反向传播
            loss.backward()
            torch.nn.utils.clip_grad_norm_(self.model.parameters(), max_norm=1.0)
            self.optimizer.step()
            
            # 统计
            total_loss += loss.item()
            preds = torch.argmax(logits, dim=1)
            all_preds.extend(preds.cpu().numpy())
            all_labels.extend(labels.cpu().numpy())
            
            pbar.set_postfix({"loss": loss.item()})
        
        avg_loss = total_loss / len(dataloader)
        accuracy = accuracy_score(all_labels, all_preds)
        
        return avg_loss, accuracy
    
    def validate(self, dataloader: DataLoader) -> tuple[float, float]:
        """验证.
        
        Returns:
            (平均损失, 准确率)
        """
        if self.model is None:
            raise ValueError("Model not initialized")
        
        self.model.eval()
        total_loss = 0.0
        all_preds = []
        all_labels = []
        
        with torch.no_grad():
            for images, labels in tqdm(dataloader, desc="Validation"):
                images = images.to(self.device)
                labels = labels.to(self.device)
                
                output = self.model(images)
                logits = output["logits"]
                
                loss = self.criterion(logits, labels)
                total_loss += loss.item()
                
                preds = torch.argmax(logits, dim=1)
                all_preds.extend(preds.cpu().numpy())
                all_labels.extend(labels.cpu().numpy())
        
        avg_loss = total_loss / len(dataloader)
        accuracy = accuracy_score(all_labels, all_preds)
        
        return avg_loss, accuracy
    
    def train(
        self,
        train_loader: DataLoader,
        val_loader: DataLoader,
    ) -> dict[str, list[float]]:
        """完整训练流程."""
        if self.model is None:
            raise ValueError("Model not initialized")
        
        logger.info(f"Starting training on {self.device}")
        logger.info(f"Train batches: {len(train_loader)}, Val batches: {len(val_loader)}")
        
        for epoch in range(self.config.num_epochs):
            logger.info(f"\nEpoch {epoch + 1}/{self.config.num_epochs}")
            
            # 训练
            train_loss, train_acc = self.train_epoch(train_loader)
            
            # 验证
            val_loss, val_acc = self.validate(val_loader)
            
            # 记录
            self.history["train_loss"].append(train_loss)
            self.history["train_acc"].append(train_acc)
            self.history["val_loss"].append(val_loss)
            self.history["val_acc"].append(val_acc)
            
            logger.info(
                f"Train Loss: {train_loss:.4f}, Acc: {train_acc:.4f} | "
                f"Val Loss: {val_loss:.4f}, Acc: {val_acc:.4f}"
            )
            
            # 学习率调度
            if self.scheduler:
                self.scheduler.step(val_acc)
            
            # 保存最佳模型
            if val_acc > self.best_val_acc:
                self.best_val_acc = val_acc
                self.patience_counter = 0
                self.save_checkpoint("best_model.pt")
                logger.info(f"New best model saved! Val Acc: {val_acc:.4f}")
            else:
                self.patience_counter += 1
            
            # 早停
            if self.patience_counter >= self.config.early_stopping_patience:
                logger.info(f"Early stopping triggered after {epoch + 1} epochs")
                break
            
            # 定期保存
            if (epoch + 1) % 10 == 0:
                self.save_checkpoint(f"checkpoint_epoch_{epoch + 1}.pt")
        
        # 保存最终模型
        self.save_checkpoint("final_model.pt")
        
        # 保存训练历史
        self.save_history()
        
        return self.history
    
    def save_checkpoint(self, filename: str) -> None:
        """保存检查点."""
        if self.model is None:
            return
        
        path = self.config.save_dir / filename
        self.model.save(path)
    
    def save_history(self) -> None:
        """保存训练历史."""
        history_path = self.config.save_dir / "training_history.json"
        with open(history_path, "w", encoding="utf-8") as f:
            json.dump(self.history, f, indent=2)
        logger.info(f"Training history saved to {history_path}")
    
    def evaluate(self, test_loader: DataLoader) -> ModelMetrics:
        """评估模型."""
        if self.model is None:
            raise ValueError("Model not initialized")
        
        self.model.eval()
        all_preds = []
        all_labels = []
        
        with torch.no_grad():
            for images, labels in tqdm(test_loader, desc="Evaluating"):
                images = images.to(self.device)
                output = self.model(images)
                logits = output["logits"]
                preds = torch.argmax(logits, dim=1)
                
                all_preds.extend(preds.cpu().numpy())
                all_labels.extend(labels.cpu().numpy())
        
        metrics = ModelMetrics(
            model_name="LightweightVLM",
            model_type="CNN+Classifier",
            accuracy=accuracy_score(all_labels, all_preds),
            precision=precision_score(all_labels, all_preds, average="weighted", zero_division=0),
            recall=recall_score(all_labels, all_preds, average="weighted", zero_division=0),
            f1_score=f1_score(all_labels, all_preds, average="weighted", zero_division=0),
            training_samples=len(all_labels),
            validation_samples=len(all_labels),
        )
        
        logger.info(f"\nEvaluation Results:\n{classification_report(all_labels, all_preds)}")
        
        return metrics


def generate_synthetic_data(
    num_samples: int = 1000,
    num_categories: int = 8,
) -> tuple[list[Path], list[int]]:
    """生成合成数据用于演示."""
    logger.info(f"Generating {num_samples} synthetic samples...")
    
    # 在实际项目中，这里应该是真实的图片路径
    # 这里用随机数据模拟
    image_paths = [Path(f"synthetic/image_{i}.jpg") for i in range(num_samples)]
    labels = np.random.randint(0, num_categories, num_samples).tolist()
    
    return image_paths, labels


def main() -> None:
    """训练示例."""
    from sklearn.model_selection import train_test_split
    
    logger.info("Starting VLM training...")
    
    # 配置
    config = TrainingConfig(
        batch_size=16,
        num_epochs=5,  # 演示用，实际可以更多
        learning_rate=1e-3,
        device="cpu",  # 演示用 CPU
    )
    
    # 数据（实际项目中替换为真实数据）
    image_paths, labels = generate_synthetic_data(num_samples=200)
    
    # 划分数据集
    train_paths, temp_paths, train_labels, temp_labels = train_test_split(
        image_paths, labels, test_size=0.3, random_state=42, stratify=labels
    )
    val_paths, test_paths, val_labels, test_labels = train_test_split(
        temp_paths, temp_labels, test_size=0.5, random_state=42, stratify=temp_labels
    )
    
    logger.info(
        f"Data split: Train={len(train_paths)}, Val={len(val_paths)}, Test={len(test_paths)}"
    )
    
    # 创建数据集（使用合成数据，实际中需要真实图片）
    # 这里为了演示，创建虚拟数据集
    class DummyDataset(Dataset):
        def __init__(self, size: int, num_classes: int = 8) -> None:
            self.size = size
            self.num_classes = num_classes
        
        def __len__(self) -> int:
            return self.size
        
        def __getitem__(self, idx: int) -> tuple[torch.Tensor, int]:
            # 返回随机张量
            image = torch.randn(3, 224, 224)
            label = idx % self.num_classes
            return image, label
    
    train_dataset = DummyDataset(len(train_paths))
    val_dataset = DummyDataset(len(val_paths))
    test_dataset = DummyDataset(len(test_paths))
    
    train_loader = DataLoader(
        train_dataset, batch_size=config.batch_size, shuffle=True, num_workers=0
    )
    val_loader = DataLoader(
        val_dataset, batch_size=config.batch_size, shuffle=False, num_workers=0
    )
    test_loader = DataLoader(
        test_dataset, batch_size=config.batch_size, shuffle=False, num_workers=0
    )
    
    # 训练
    trainer = VLMTrainer(config)
    trainer.create_model(num_categories=8)
    trainer.train(train_loader, val_loader)
    
    # 评估
    metrics = trainer.evaluate(test_loader)
    logger.info(f"Final metrics: {metrics.model_dump()}")


if __name__ == "__main__":
    main()
