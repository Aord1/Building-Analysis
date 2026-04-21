"""仪表盘数据 API."""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.core.config import get_settings
from app.services.analysis.sentiment import SentimentService
from app.services.analysis.vlm_classifier import VLMService

router = APIRouter()


class DashboardStats(BaseModel):
    """仪表盘统计数据."""
    total_notes: int
    total_images: int
    avg_sentiment: float
    sentiment_distribution: dict[str, int]
    interest_distribution: dict[str, int]
    model_status: dict[str, bool]


class InterestPoint(BaseModel):
    """兴趣点数据."""
    name: str
    count: int
    avg_sentiment: float
    images: list[str]


@router.get("/stats", response_model=DashboardStats)
async def get_stats() -> DashboardStats:
    """获取仪表盘统计数据."""
    settings = get_settings()
    
    # 加载笔记数据
    notes = []
    notes_file = settings.data_dir / "notes.json"
    if notes_file.exists():
        with open(notes_file, "r", encoding="utf-8") as f:
            notes = json.load(f)
    
    # 加载图片清单
    manifest = []
    manifest_file = settings.data_dir / "image_manifest.json"
    if manifest_file.exists():
        with open(manifest_file, "r", encoding="utf-8") as f:
            manifest = json.load(f)
    
    # 情感分布
    sentiments = [n.get("sentiment_score", 0) for n in notes if "sentiment_score" in n]
    avg_sentiment = sum(sentiments) / len(sentiments) if sentiments else 0
    
    sentiment_dist = {"positive": 0, "neutral": 0, "negative": 0}
    for s in sentiments:
        if s > 0.2:
            sentiment_dist["positive"] += 1
        elif s < -0.2:
            sentiment_dist["negative"] += 1
        else:
            sentiment_dist["neutral"] += 1
    
    # 兴趣点分布
    interest_dist: dict[str, int] = {}
    for item in manifest:
        for label in item.get("labels", []):
            interest_dist[label] = interest_dist.get(label, 0) + 1
    
    # 模型状态
    svm = SentimentService()
    vlm = VLMService()
    
    return DashboardStats(
        total_notes=len(notes),
        total_images=len(manifest),
        avg_sentiment=round(avg_sentiment, 2),
        sentiment_distribution=sentiment_dist,
        interest_distribution=interest_dist,
        model_status={
            "svm": svm.is_loaded,
            "vlm": vlm.is_loaded,
        },
    )


@router.get("/interest-points", response_model=list[InterestPoint])
async def get_interest_points() -> list[InterestPoint]:
    """获取兴趣点分析数据."""
    settings = get_settings()
    
    # 加载数据
    notes = []
    notes_file = settings.data_dir / "notes.json"
    if notes_file.exists():
        with open(notes_file, "r", encoding="utf-8") as f:
            notes = json.load(f)
    
    manifest = []
    manifest_file = settings.data_dir / "image_manifest.json"
    if manifest_file.exists():
        with open(manifest_file, "r", encoding="utf-8") as f:
            manifest = json.load(f)
    
    # 按兴趣点聚合
    points: dict[str, dict[str, Any]] = {}
    
    for item in manifest:
        labels = item.get("labels", [])
        sentiment = item.get("sentiment", 0)
        image_path = item.get("image_path", "")
        
        for label in labels:
            if label not in points:
                points[label] = {
                    "count": 0,
                    "sentiments": [],
                    "images": [],
                }
            points[label]["count"] += 1
            points[label]["sentiments"].append(sentiment)
            if len(points[label]["images"]) < 5:
                points[label]["images"].append(image_path)
    
    # 转换为响应格式
    result = []
    for name, data in sorted(points.items(), key=lambda x: x[1]["count"], reverse=True):
        avg_sent = sum(data["sentiments"]) / len(data["sentiments"]) if data["sentiments"] else 0
        result.append(InterestPoint(
            name=name,
            count=data["count"],
            avg_sentiment=round(avg_sent, 2),
            images=data["images"],
        ))
    
    return result


@router.get("/recommendations")
async def get_recommendations() -> dict[str, Any]:
    """获取优化建议."""
    settings = get_settings()
    
    # 加载数据
    manifest = []
    manifest_file = settings.data_dir / "image_manifest.json"
    if manifest_file.exists():
        with open(manifest_file, "r", encoding="utf-8") as f:
            manifest = json.load(f)
    
    # 统计兴趣点
    interest_counts: dict[str, int] = {}
    for item in manifest:
        for label in item.get("labels", []):
            interest_counts[label] = interest_counts.get(label, 0) + 1
    
    # 生成建议
    recommendations = []
    
    if not interest_counts:
        recommendations.append({
            "type": "info",
            "title": "数据不足",
            "content": "请先导入笔记数据并运行分析流程",
        })
    else:
        # 热门兴趣点
        top_interests = sorted(interest_counts.items(), key=lambda x: x[1], reverse=True)[:3]
        recommendations.append({
            "type": "success",
            "title": "热门兴趣点",
            "content": f"游客最关注: {', '.join([f'{k}({v}次)' for k, v in top_interests])}",
        })
        
        # 长尾兴趣点
        if len(interest_counts) > 5:
            low_interests = [k for k, v in interest_counts.items() if v <= 2]
            if low_interests:
                recommendations.append({
                    "type": "warning",
                    "title": "待提升区域",
                    "content": f"以下兴趣点关注度较低，可考虑优化: {', '.join(low_interests[:5])}",
                })
    
    return {
        "recommendations": recommendations,
        "total": len(recommendations),
    }
