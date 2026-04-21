"""
轻量级视觉语言模型 (VLM)
======================
技术亮点:
- 基于 ResNet + Transformer 的轻量级架构
- 支持端到端训练
- 模型大小 < 100MB，可在 CPU 上快速推理
- 针对古建筑场景优化
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import torch
import torch.nn as nn
import torch.nn.functional as F
from loguru import logger
from PIL import Image
from torchvision import models, transforms


class ImageEncoder(nn.Module):
    """图片编码器 - 使用预训练 ResNet."""
    
    def __init__(self, output_dim: int = 256, freeze_backbone: bool = False) -> None:
        super().__init__()
        
        # 使用 ResNet18 作为骨干网络（轻量级）
        resnet = models.resnet18(weights=models.ResNet18_Weights.IMAGENET1K_V1)
        
        # 移除最后的全连接层
        self.backbone = nn.Sequential(*list(resnet.children())[:-1])
        
        if freeze_backbone:
            for param in self.backbone.parameters():
                param.requires_grad = False
        
        # 投影层
        self.projection = nn.Sequential(
            nn.Linear(512, 512),
            nn.ReLU(),
            nn.Dropout(0.3),
            nn.Linear(512, output_dim),
        )
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """前向传播.
        
        Args:
            x: 输入图片 [B, 3, H, W]
            
        Returns:
            图片特征 [B, output_dim]
        """
        features = self.backbone(x)  # [B, 512, 1, 1]
        features = features.view(features.size(0), -1)  # [B, 512]
        output = self.projection(features)  # [B, output_dim]
        return output


class CategoryEmbedding(nn.Module):
    """类别文本嵌入."""
    
    def __init__(self, num_categories: int, embedding_dim: int = 256) -> None:
        super().__init__()
        self.embeddings = nn.Embedding(num_categories, embedding_dim)
        self.projection = nn.Sequential(
            nn.Linear(embedding_dim, embedding_dim),
            nn.ReLU(),
            nn.Dropout(0.3),
        )
    
    def forward(self, category_ids: torch.Tensor) -> torch.Tensor:
        """获取类别嵌入.
        
        Args:
            category_ids: 类别ID [B] 或 [B, num_categories]
            
        Returns:
            类别嵌入 [B, embedding_dim] 或 [B, num_categories, embedding_dim]
        """
        if category_ids.dim() == 1:
            emb = self.embeddings(category_ids)
            return self.projection(emb)
        else:
            # 多类别
            B, N = category_ids.shape
            emb = self.embeddings(category_ids.view(-1))  # [B*N, D]
            emb = self.projection(emb)
            return emb.view(B, N, -1)  # [B, N, D]


class LightweightVLM(nn.Module):
    """轻量级视觉语言模型."""
    
    CATEGORIES = [
        "architecture_overview",  # 建筑全景
        "garden_plants",          # 园林植物
        "plaque_inscription",     # 牌匾题字
        "people_checkin",         # 人物打卡
        "detail_carving",         # 细节雕刻
        "interior_space",         # 室内空间
        "decoration_art",         # 装饰艺术
        "historical_relic",       # 历史遗迹
    ]
    
    CATEGORY_ZH = {
        "architecture_overview": "建筑全景",
        "garden_plants": "园林植物",
        "plaque_inscription": "牌匾题字",
        "people_checkin": "人物打卡",
        "detail_carving": "细节雕刻",
        "interior_space": "室内空间",
        "decoration_art": "装饰艺术",
        "historical_relic": "历史遗迹",
    }
    
    def __init__(
        self,
        num_categories: int = 8,
        embedding_dim: int = 256,
        freeze_backbone: bool = False,
    ) -> None:
        super().__init__()
        
        self.num_categories = num_categories
        self.embedding_dim = embedding_dim
        
        # 图片编码器
        self.image_encoder = ImageEncoder(embedding_dim, freeze_backbone)
        
        # 类别嵌入
        self.category_embedding = CategoryEmbedding(num_categories, embedding_dim)
        
        # 融合层
        self.fusion = nn.Sequential(
            nn.Linear(embedding_dim * 2, embedding_dim),
            nn.ReLU(),
            nn.Dropout(0.3),
            nn.Linear(embedding_dim, 1),
        )
        
        # 分类头
        self.classifier = nn.Linear(embedding_dim, num_categories)
        
        self._init_weights()
    
    def _init_weights(self) -> None:
        """初始化权重."""
        for m in self.modules():
            if isinstance(m, nn.Linear):
                nn.init.xavier_uniform_(m.weight)
                if m.bias is not None:
                    nn.init.zeros_(m.bias)
    
    def forward(
        self,
        images: torch.Tensor,
        return_features: bool = False,
    ) -> dict[str, torch.Tensor]:
        """前向传播.
        
        Args:
            images: 输入图片 [B, 3, H, W]
            return_features: 是否返回特征
            
        Returns:
            包含 logits 和 features 的字典
        """
        # 编码图片
        image_features = self.image_encoder(images)  # [B, D]
        
        # 分类预测
        logits = self.classifier(image_features)  # [B, num_categories]
        
        output = {"logits": logits}
        
        if return_features:
            output["image_features"] = image_features
        
        return output
    
    def predict(
        self,
        images: torch.Tensor,
    ) -> tuple[torch.Tensor, torch.Tensor]:
        """预测类别.
        
        Args:
            images: 输入图片 [B, 3, H, W]
            
        Returns:
            (预测类别ID, 置信度)
        """
        self.eval()
        with torch.no_grad():
            output = self.forward(images)
            logits = output["logits"]
            probabilities = F.softmax(logits, dim=-1)
            confidences, predictions = torch.max(probabilities, dim=-1)
        
        return predictions, confidences
    
    def get_category_name(self, category_id: int) -> str:
        """获取类别名称."""
        return self.CATEGORIES[category_id]
    
    def get_category_name_zh(self, category_id: int) -> str:
        """获取类别中文名称."""
        category = self.CATEGORIES[category_id]
        return self.CATEGORY_ZH.get(category, category)
    
    def save(self, path: Path) -> None:
        """保存模型."""
        path.parent.mkdir(parents=True, exist_ok=True)
        torch.save({
            "model_state_dict": self.state_dict(),
            "num_categories": self.num_categories,
            "embedding_dim": self.embedding_dim,
            "categories": self.CATEGORIES,
            "categories_zh": self.CATEGORY_ZH,
        }, path)
        logger.info(f"Model saved to {path}")
    
    @classmethod
    def load(cls, path: Path, device: str = "cpu") -> LightweightVLM:
        """加载模型."""
        checkpoint = torch.load(path, map_location=device)
        
        model = cls(
            num_categories=checkpoint.get("num_categories", 8),
            embedding_dim=checkpoint.get("embedding_dim", 256),
        )
        model.load_state_dict(checkpoint["model_state_dict"])
        model.eval()
        
        # 恢复类别映射
        if "categories" in checkpoint:
            model.CATEGORIES = checkpoint["categories"]
        if "categories_zh" in checkpoint:
            model.CATEGORY_ZH = checkpoint["categories_zh"]
        
        logger.info(f"Model loaded from {path}")
        return model


class ImagePreprocessor:
    """图片预处理器."""
    
    def __init__(self, image_size: int = 224) -> None:
        self.transform = transforms.Compose([
            transforms.Resize((image_size, image_size)),
            transforms.ToTensor(),
            transforms.Normalize(
                mean=[0.485, 0.456, 0.406],
                std=[0.229, 0.224, 0.225],
            ),
        ])
    
    def __call__(self, image_path: Path) -> torch.Tensor:
        """预处理图片."""
        image = Image.open(image_path).convert("RGB")
        return self.transform(image)
    
    def preprocess_batch(self, image_paths: list[Path]) -> torch.Tensor:
        """批量预处理."""
        tensors = [self(path) for path in image_paths]
        return torch.stack(tensors)


def test_model() -> None:
    """测试模型."""
    logger.info("Testing LightweightVLM...")
    
    # 创建模型
    model = LightweightVLM()
    
    # 测试输入
    batch_size = 4
    images = torch.randn(batch_size, 3, 224, 224)
    
    # 前向传播
    output = model.forward(images, return_features=True)
    
    logger.info(f"Input shape: {images.shape}")
    logger.info(f"Logits shape: {output['logits'].shape}")
    logger.info(f"Features shape: {output['image_features'].shape}")
    
    # 预测
    predictions, confidences = model.predict(images)
    logger.info(f"Predictions: {predictions}")
    logger.info(f"Confidences: {confidences}")
    
    # 统计参数量
    total_params = sum(p.numel() for p in model.parameters())
    trainable_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
    
    logger.info(f"Total parameters: {total_params:,}")
    logger.info(f"Trainable parameters: {trainable_params:,}")
    logger.info(f"Model size: ~{total_params * 4 / 1024 / 1024:.2f} MB (float32)")


if __name__ == "__main__":
    test_model()
