"""分析流水线 API."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, BackgroundTasks, File, HTTPException, UploadFile
from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.services.analysis.image_manifest import ImageManifestBuilder
from app.services.analysis.sentiment import SentimentService
from app.services.analysis.unified_analyzer import UnifiedAnalyzer
from app.services.analysis.vlm_classifier import VLMService
from app.services.importers.html_extractor import HTMLDataExtractor

router = APIRouter()


class PipelineStatus(BaseModel):
    """流水线状态."""
    status: str  # idle, running, completed, failed
    current_step: str
    progress: int = Field(ge=0, le=100)
    message: str


class PipelineResult(BaseModel):
    """流水线结果."""
    success: bool
    steps_completed: list[str]
    errors: list[str]
    stats: dict[str, Any]


class AnalysisRequest(BaseModel):
    """分析请求."""
    source_path: str | None = Field(None, description="HTML 文件或文件夹路径")
    skip_extraction: bool = Field(False, description="跳过提取步骤")


class AnalysisResponse(BaseModel):
    """分析响应."""
    success: bool
    message: str
    results: dict[str, Any] | None = None


# 全局状态（实际应用应使用 Redis 等）
_pipeline_state = {
    "status": "idle",
    "current_step": "",
    "progress": 0,
    "message": "Ready",
}

# 统一分析器实例
_analyzer = UnifiedAnalyzer()


def run_analysis_pipeline():
    """运行分析流水线（后台任务）."""
    global _pipeline_state
    settings = get_settings()

    try:
        _pipeline_state["status"] = "running"
        steps = []
        errors = []

        # Step 1: 构建图片清单
        _pipeline_state["current_step"] = "build_manifest"
        _pipeline_state["progress"] = 20
        _pipeline_state["message"] = "Building image manifest..."

        try:
            builder = ImageManifestBuilder(settings.data_dir)
            builder.build(settings.image_dir)
            builder.save()
            steps.append("build_manifest")
        except Exception as e:
            errors.append(f"build_manifest: {str(e)}")

        # Step 2: 情感分析
        _pipeline_state["current_step"] = "sentiment_analysis"
        _pipeline_state["progress"] = 50
        _pipeline_state["message"] = "Running sentiment analysis..."

        try:
            analyzer = SentimentService()
            if analyzer.is_loaded:
                notes_file = settings.data_dir / "notes.json"
                if notes_file.exists():
                    with open(notes_file, "r", encoding="utf-8") as f:
                        notes = json.load(f)

                    for note in notes:
                        content = note.get("content", "")
                        if content:
                            result = analyzer.predict(content)
                            note["sentiment_score"] = result["score"]
                            note["sentiment_label"] = result["label"]

                    with open(notes_file, "w", encoding="utf-8") as f:
                        json.dump(notes, f, ensure_ascii=False, indent=2)

                    steps.append("sentiment_analysis")
            else:
                errors.append("sentiment_analysis: SVM model not loaded")
        except Exception as e:
            errors.append(f"sentiment_analysis: {str(e)}")

        # Step 3: 图片分类
        _pipeline_state["current_step"] = "image_classification"
        _pipeline_state["progress"] = 80
        _pipeline_state["message"] = "Classifying images..."

        try:
            classifier = VLMService()
            if classifier.is_loaded:
                manifest_file = settings.data_dir / "image_manifest.json"
                if manifest_file.exists():
                    with open(manifest_file, "r", encoding="utf-8") as f:
                        manifest = json.load(f)

                    for item in manifest:
                        image_path = item.get("image_path", "")
                        if image_path:
                            full_path = settings.project_root / image_path
                            if full_path.exists():
                                result = classifier.predict(str(full_path))
                                item["labels"] = result["labels"]
                                item["confidence"] = result["confidence"]

                    with open(manifest_file, "w", encoding="utf-8") as f:
                        json.dump(manifest, f, ensure_ascii=False, indent=2)

                    steps.append("image_classification")
            else:
                errors.append("image_classification: VLM model not loaded")
        except Exception as e:
            errors.append(f"image_classification: {str(e)}")

        # 完成
        _pipeline_state["status"] = "completed" if not errors else "failed"
        _pipeline_state["progress"] = 100
        _pipeline_state["message"] = f"Completed {len(steps)} steps"

    except Exception as e:
        _pipeline_state["status"] = "failed"
        _pipeline_state["message"] = str(e)


@router.get("/status", response_model=PipelineStatus)
async def get_status() -> PipelineStatus:
    """获取流水线状态."""
    global _pipeline_state
    return PipelineStatus(**_pipeline_state)


@router.post("/run")
async def run_pipeline(background_tasks: BackgroundTasks) -> dict[str, Any]:
    """启动分析流水线."""
    global _pipeline_state

    if _pipeline_state["status"] == "running":
        raise HTTPException(status_code=409, detail="Pipeline already running")

    background_tasks.add_task(run_analysis_pipeline)

    return {
        "success": True,
        "message": "Pipeline started",
    }


@router.post("/reset")
async def reset_pipeline() -> dict[str, Any]:
    """重置流水线状态."""
    global _pipeline_state
    _pipeline_state = {
        "status": "idle",
        "current_step": "",
        "progress": 0,
        "message": "Ready",
    }
    return {
        "success": True,
        "message": "Pipeline reset",
    }


# ============ 新功能：HTML 提取和分析 ============

@router.post("/extract/html", response_model=AnalysisResponse)
async def extract_from_html(
    file: UploadFile = File(...),
) -> AnalysisResponse:
    """上传并提取 HTML 文件中的文本和图片.

    - **file**: HTML 文件
    """
    try:
        settings = get_settings()
        settings.ensure_dirs()

        # 保存上传的文件
        upload_dir = settings.raw_dir / "html_uploads"
        upload_dir.mkdir(parents=True, exist_ok=True)

        file_path = upload_dir / file.filename
        with open(file_path, "wb") as f:
            content = await file.read()
            f.write(content)

        # 提取数据
        extractor = HTMLDataExtractor(settings.processed_dir)
        result = extractor.extract_from_html(file_path)

        return AnalysisResponse(
            success=True,
            message=f"Extracted {result['stats']['text_count']} texts and {result['stats']['image_count']} images",
            results=result,
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/extract/html/folder", response_model=AnalysisResponse)
async def extract_from_html_folder(
    folder_path: str,
) -> AnalysisResponse:
    """从文件夹批量提取 HTML 数据.

    - **folder_path**: 包含 HTML 文件的文件夹路径
    """
    try:
        settings = get_settings()
        extractor = HTMLDataExtractor(settings.processed_dir)

        result = extractor.extract_from_folder(folder_path)

        return AnalysisResponse(
            success=True,
            message=f"Processed {result['stats']['file_count']} files, extracted {result['stats']['total_texts']} texts and {result['stats']['total_images']} images",
            results=result,
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/analyze/nlp", response_model=AnalysisResponse)
async def analyze_texts_nlp() -> AnalysisResponse:
    """使用 NLP 分析已提取的文本.

    分析 data/processed/texts/ 目录下的文本文件
    """
    try:
        analyzer = UnifiedAnalyzer()
        result = analyzer.analyze_texts()

        return AnalysisResponse(
            success=True,
            message=f"Analyzed {result['total']} texts",
            results=result,
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/analyze/vlm", response_model=AnalysisResponse)
async def analyze_images_vlm() -> AnalysisResponse:
    """使用 VLM 分析已提取的图片.

    分析 data/processed/images/ 目录下的图片文件
    """
    try:
        analyzer = UnifiedAnalyzer()
        result = analyzer.analyze_images()

        return AnalysisResponse(
            success=True,
            message=f"Classified {result['total']} images",
            results=result,
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/analyze/full", response_model=AnalysisResponse)
async def run_full_analysis(
    request: AnalysisRequest,
    background_tasks: BackgroundTasks,
) -> AnalysisResponse:
    """运行完整分析流水线.

    - **source_path**: HTML 文件或文件夹路径（可选，使用已提取的数据则留空）
    - **skip_extraction**: 是否跳过提取步骤
    """
    global _pipeline_state

    if _pipeline_state["status"] == "running":
        raise HTTPException(status_code=409, detail="Pipeline already running")

    def run_pipeline_task():
        global _pipeline_state
        analyzer = UnifiedAnalyzer()

        _pipeline_state["status"] = "running"
        _pipeline_state["current_step"] = "initialization"
        _pipeline_state["progress"] = 0

        result = analyzer.run_full_pipeline(
            html_source=request.source_path,
            skip_extraction=request.skip_extraction,
        )

        _pipeline_state["status"] = (
            "completed" if result["success"] else "failed"
        )
        _pipeline_state["progress"] = 100
        _pipeline_state["message"] = result.get("message", "Done")

    background_tasks.add_task(run_pipeline_task)

    return AnalysisResponse(
        success=True,
        message="Full analysis pipeline started",
    )


@router.get("/analyzer/status")
async def get_analyzer_status() -> dict[str, Any]:
    """获取统一分析器的当前状态."""
    analyzer = UnifiedAnalyzer()
    return analyzer.get_status()


@router.get("/results/latest")
async def get_latest_results() -> dict[str, Any]:
    """获取最新的分析结果."""
    settings = get_settings()

    results = {}

    # 尝试加载各种结果文件
    result_files = {
        "extraction": settings.processed_dir / "extraction_metadata.json",
        "nlp": settings.reports_dir / "sentiment_results.json",
        "vlm": settings.reports_dir / "vlm_predictions.json",
        "unified": settings.reports_dir / "unified_analysis_results.json",
    }

    for key, path in result_files.items():
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    results[key] = json.load(f)
            except Exception:
                pass

    return {
        "available_results": list(results.keys()),
        "results": results,
    }
