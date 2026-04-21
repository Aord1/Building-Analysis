"""统一分析服务 - 支持分别使用 VLM 和 NLP 分析."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from loguru import logger

from app.core.config import Settings, get_settings
from app.services.analysis.sentiment import SentimentService
from app.services.analysis.vlm_classifier import VLMService


class UnifiedAnalyzer:
    """统一分析服务.

    支持:
    1. 从 HTML 提取数据
    2. 分别使用 NLP/VLM 分析
    3. 一键流水线完成
    """

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.settings.ensure_dirs()

        # 初始化服务
        self.sentiment_service = SentimentService(self.settings)
        self.vlm_service = VLMService(self.settings)

        # 状态跟踪
        self.status = {
            "stage": "idle",
            "progress": 0,
            "message": "Ready",
            "results": {},
        }

    def analyze_texts(
        self,
        texts: list[dict[str, Any]] | None = None,
        text_dir: Path | None = None,
    ) -> dict[str, Any]:
        """使用 NLP 分析文本.

        Args:
            texts: 文本数据列表，每个包含 id 和 content
            text_dir: 包含文本 JSON 文件的目录

        Returns:
            分析结果摘要
        """
        self._update_status("nlp_analysis", 10, "Loading texts...")

        # 加载文本
        if texts is None:
            texts = self._load_texts_from_dir(text_dir or self.settings.processed_dir / "texts")

        if not texts:
            logger.warning("No texts to analyze")
            return {"total": 0, "message": "No texts found"}

        self._update_status("nlp_analysis", 30, f"Analyzing {len(texts)} texts...")

        # 准备笔记格式
        notes = [
            {
                "note_id": t.get("id", f"text_{i}"),
                "content": t.get("content", ""),
            }
            for i, t in enumerate(texts)
        ]

        # 过滤空内容
        notes = [n for n in notes if n["content"].strip()]

        if not self.sentiment_service.is_loaded:
            logger.warning("SVM model not loaded, skipping sentiment analysis")
            return {"total": 0, "message": "Model not loaded"}

        # 批量分析
        results = self.sentiment_service.analyze_notes(notes)

        # 保存结果
        self.sentiment_service.save_results(results)
        summary = self.sentiment_service.generate_summary(results)

        # 更新文本数据
        for text, result in zip(texts, results):
            text["sentiment"] = {
                "label": result.sentiment_label.value,
                "score": result.sentiment_score,
                "confidence": result.confidence,
            }

        self._update_status("nlp_analysis", 100, f"Analyzed {len(results)} texts")

        return {
            "total": len(results),
            "summary": summary,
            "output_path": str(self.settings.reports_dir / "sentiment_results.json"),
        }

    def analyze_images(
        self,
        images: list[dict[str, Any]] | None = None,
        image_dir: Path | None = None,
    ) -> dict[str, Any]:
        """使用 VLM 分析图片.

        Args:
            images: 图片数据列表，每个包含 id 和 local_path
            image_dir: 包含图片的目录

        Returns:
            分析结果摘要
        """
        self._update_status("vlm_analysis", 10, "Loading images...")

        # 加载图片
        if images is None:
            images = self._load_images_from_dir(image_dir or self.settings.processed_dir / "images")

        if not images:
            logger.warning("No images to analyze")
            return {"total": 0, "message": "No images found"}

        if not self.vlm_service.is_loaded:
            logger.warning("VLM model not loaded, skipping image classification")
            return {"total": 0, "message": "Model not loaded"}

        self._update_status("vlm_analysis", 30, f"Analyzing {len(images)} images...")

        # 准备记录格式
        records = []
        for img in images:
            local_path = img.get("local_path")
            if local_path and Path(local_path).exists():
                records.append({
                    "note_id": img.get("id", ""),
                    "image_name": Path(local_path).name,
                    "image_path": str(Path(local_path).relative_to(self.settings.project_root)),
                })

        # 批量分类
        predictions = self.vlm_service.classify_batch(records)

        # 更新图片数据
        for img, pred in zip(images, predictions):
            img["classification"] = {
                "category": pred.predicted_category.value,
                "category_zh": pred.predicted_category_zh,
                "confidence": pred.confidence,
                "all_probabilities": pred.all_probabilities,
            }

        self._update_status("vlm_analysis", 100, f"Classified {len(predictions)} images")

        return {
            "total": len(predictions),
            "categories": self._summarize_categories(predictions),
            "output_path": str(self.settings.reports_dir / "vlm_predictions.json"),
        }

    def run_full_pipeline(
        self,
        html_source: str | Path | None = None,
        skip_extraction: bool = False,
    ) -> dict[str, Any]:
        """运行完整分析流水线.

        Args:
            html_source: HTML 文件或文件夹路径
            skip_extraction: 是否跳过提取步骤（使用已提取的数据）

        Returns:
            完整分析结果
        """
        results = {
            "extraction": None,
            "nlp_analysis": None,
            "vlm_analysis": None,
        }

        try:
            # Step 1: 提取数据
            if not skip_extraction and html_source:
                self._update_status("extraction", 0, "Extracting data from HTML...")

                from app.services.importers.html_extractor import HTMLDataExtractor

                extractor = HTMLDataExtractor(self.settings.processed_dir)

                source_path = Path(html_source)
                if source_path.is_file():
                    extraction_result = extractor.extract_from_html(source_path)
                else:
                    extraction_result = extractor.extract_from_folder(source_path)

                results["extraction"] = extraction_result
                self._update_status("extraction", 100, "Extraction complete")

            # Step 2: NLP 分析
            self._update_status("nlp", 0, "Starting NLP analysis...")
            results["nlp_analysis"] = self.analyze_texts()

            # Step 3: VLM 分析
            self._update_status("vlm", 0, "Starting VLM analysis...")
            results["vlm_analysis"] = self.analyze_images()

            # 保存合并结果
            self._save_combined_results(results)

            self._update_status("completed", 100, "Pipeline completed successfully")

            return {
                "success": True,
                "results": results,
                "summary": self._generate_pipeline_summary(results),
            }

        except Exception as e:
            logger.error(f"Pipeline failed: {e}")
            self._update_status("failed", 0, f"Pipeline failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "results": results,
            }

    def get_status(self) -> dict[str, Any]:
        """获取当前状态."""
        return self.status.copy()

    def _load_texts_from_dir(self, text_dir: Path) -> list[dict[str, Any]]:
        """从目录加载文本."""
        texts = []

        if not text_dir.exists():
            return texts

        for json_file in text_dir.glob("*.json"):
            try:
                with open(json_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict) and "content" in data:
                        texts.append(data)
            except Exception as e:
                logger.warning(f"Failed to load {json_file}: {e}")

        return texts

    def _load_images_from_dir(self, image_dir: Path) -> list[dict[str, Any]]:
        """从目录加载图片."""
        images = []

        if not image_dir.exists():
            return images

        # 支持的图片格式
        extensions = [".jpg", ".jpeg", ".png", ".gif", ".webp"]

        for ext in extensions:
            for img_path in image_dir.rglob(f"*{ext}"):
                images.append({
                    "id": img_path.stem,
                    "local_path": str(img_path),
                })

        return images

    def _summarize_categories(
        self, predictions: list[Any]
    ) -> dict[str, int]:
        """统计类别分布."""
        from collections import Counter

        categories = [p.predicted_category.value for p in predictions]
        return dict(Counter(categories))

    def _save_combined_results(self, results: dict[str, Any]) -> None:
        """保存合并结果."""
        output_path = self.settings.reports_dir / "unified_analysis_results.json"

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)

        logger.info(f"Saved combined results to {output_path}")

    def _generate_pipeline_summary(
        self, results: dict[str, Any]
    ) -> dict[str, Any]:
        """生成流水线摘要."""
        summary = {
            "texts_analyzed": 0,
            "images_analyzed": 0,
            "sentiment_distribution": {},
            "image_categories": {},
        }

        nlp_result = results.get("nlp_analysis")
        if nlp_result:
            summary["texts_analyzed"] = nlp_result.get("total", 0)
            nlp_summary = nlp_result.get("summary", {})
            summary["sentiment_distribution"] = nlp_summary.get("distribution", {})

        vlm_result = results.get("vlm_analysis")
        if vlm_result:
            summary["images_analyzed"] = vlm_result.get("total", 0)
            summary["image_categories"] = vlm_result.get("categories", {})

        return summary

    def _update_status(
        self, stage: str, progress: int, message: str
    ) -> None:
        """更新状态."""
        self.status.update({
            "stage": stage,
            "progress": progress,
            "message": message,
        })
        logger.info(f"[{stage}] {progress}% - {message}")
