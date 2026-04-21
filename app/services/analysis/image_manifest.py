"""图片清单构建服务."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.core.config import get_settings


class ImageManifestBuilder:
    """图片清单构建器."""
    
    def __init__(self, data_dir: Path | None = None):
        settings = get_settings()
        self.data_dir = data_dir or settings.data_dir
        self.manifest: list[dict[str, Any]] = []
    
    def build(self, image_dir: Path | None = None) -> list[dict[str, Any]]:
        """扫描图片目录构建清单."""
        settings = get_settings()
        image_dir = image_dir or settings.image_dir
        
        self.manifest = []
        
        if not image_dir.exists():
            return self.manifest
        
        # 支持的图片格式
        extensions = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"}
        
        for ext in extensions:
            for filepath in image_dir.rglob(f"*{ext}"):
                # 跳过 README 目录
                if "README" in filepath.parts:
                    continue
                
                # 计算相对路径
                rel_path = filepath.relative_to(settings.project_root)
                
                self.manifest.append({
                    "image_path": str(rel_path).replace("\\", "/"),
                    "filename": filepath.name,
                    "size": filepath.stat().st_size,
                    "labels": [],
                    "confidence": 0.0,
                    "sentiment": 0.0,
                })
        
        return self.manifest
    
    def save(self) -> Path:
        """保存清单到文件."""
        manifest_file = self.data_dir / "image_manifest.json"
        with open(manifest_file, "w", encoding="utf-8") as f:
            json.dump(self.manifest, f, ensure_ascii=False, indent=2)
        return manifest_file
    
    def load(self) -> list[dict[str, Any]]:
        """从文件加载清单."""
        manifest_file = self.data_dir / "image_manifest.json"
        if manifest_file.exists():
            with open(manifest_file, "r", encoding="utf-8") as f:
                self.manifest = json.load(f)
        return self.manifest
