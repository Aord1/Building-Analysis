"""SVM 情感分析服务."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from loguru import logger

from app.core.config import Settings, get_settings
from app.models.schemas import SentimentLabel, SentimentResult
from ml.sentiment_svm import SVMSentimentAnalyzer


class SentimentService:
    """基于 SVM 的情感分析服务."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.analyzer = SVMSentimentAnalyzer(self.settings.svm_model_path)
        self.reports_dir = self.settings.reports_dir

    @property
    def is_loaded(self) -> bool:
        """检查模型是否已加载."""
        return (
            self.analyzer.trainer.model is not None
            and self.analyzer.trainer.vectorizer is not None
        )

    def predict(self, text: str) -> dict[str, Any]:
        """预测单条文本的情感.

        Args:
            text: 输入文本

        Returns:
            预测结果字典
        """
        result = self.analyzer.analyze(text)
        return {
            "label": result.sentiment_label.value,
            "score": result.sentiment_score,
            "confidence": result.confidence,
        }

    def analyze_note(self, note_id: str, content: str) -> SentimentResult:
        """分析单条笔记."""
        result = self.analyzer.analyze(content)
        result.note_id = note_id
        return result

    def analyze_notes(
        self, notes: list[dict[str, Any]]
    ) -> list[SentimentResult]:
        """批量分析笔记."""
        results: list[SentimentResult] = []
        
        for note in notes:
            note_id = str(note.get("note_id", ""))
            content = note.get("content", "")
            
            if not note_id:
                continue
            
            result = self.analyze_note(note_id, content)
            results.append(result)
        
        logger.info(f"Analyzed {len(results)} notes with SVM")
        return results

    def save_results(self, results: list[SentimentResult]) -> Path:
        """保存分析结果."""
        self.settings.ensure_dirs()
        
        output_path = self.reports_dir / "sentiment_results.json"
        data = [r.model_dump() for r in results]
        
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"Saved sentiment results to {output_path}")
        return output_path

    def generate_summary(
        self, results: list[SentimentResult]
    ) -> dict[str, Any]:
        """生成摘要."""
        if not results:
            return {
                "total": 0,
                "distribution": {},
                "avg_confidence": 0.0,
            }
        
        total = len(results)
        distribution = {
            label.value: sum(1 for r in results if r.sentiment_label == label)
            for label in SentimentLabel
        }
        avg_confidence = sum(r.confidence for r in results) / total
        avg_score = sum(r.sentiment_score for r in results) / total
        
        summary = {
            "total": total,
            "distribution": distribution,
            "avg_confidence": round(avg_confidence, 3),
            "avg_score": round(avg_score, 3),
            "model_type": "SVM",
        }
        
        # 保存摘要
        summary_path = self.reports_dir / "sentiment_summary.json"
        with open(summary_path, "w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
        
        return summary

    def run(self) -> dict[str, Any]:
        """运行完整分析流程."""
        # 加载导入的笔记
        import_path = self.reports_dir / "import_manifest.json"
        if not import_path.exists():
            logger.warning(f"Import manifest not found: {import_path}")
            return {"total": 0, "distribution": {}}
        
        with open(import_path, "r", encoding="utf-8") as f:
            notes = json.load(f)
        
        # 分析
        results = self.analyze_notes(notes)
        
        # 保存
        self.save_results(results)
        
        # 摘要
        summary = self.generate_summary(results)
        
        return summary
