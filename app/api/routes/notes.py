"""笔记数据 API."""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.core.config import get_settings
from app.services.analysis.sentiment import SentimentService

router = APIRouter()


class Note(BaseModel):
    """笔记模型."""
    id: str
    title: str
    content: str
    images: list[str]
    sentiment_score: float = 0
    sentiment_label: str = "neutral"


class NoteListResponse(BaseModel):
    """笔记列表响应."""
    total: int
    items: list[Note]
    page: int
    page_size: int


@router.get("", response_model=NoteListResponse)
async def list_notes(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    sentiment: str | None = Query(None, regex="^(positive|neutral|negative)$"),
) -> NoteListResponse:
    """获取笔记列表."""
    settings = get_settings()
    
    # 加载数据
    notes = []
    notes_file = settings.data_dir / "notes.json"
    if notes_file.exists():
        with open(notes_file, "r", encoding="utf-8") as f:
            notes = json.load(f)
    
    # 筛选
    if sentiment:
        notes = [n for n in notes if n.get("sentiment_label") == sentiment]
    
    # 分页
    total = len(notes)
    start = (page - 1) * page_size
    end = start + page_size
    page_notes = notes[start:end]
    
    # 转换为模型
    items = []
    for n in page_notes:
        items.append(Note(
            id=n.get("id", ""),
            title=n.get("title", "")[:50],
            content=n.get("content", "")[:200],
            images=n.get("images", [])[:3],
            sentiment_score=n.get("sentiment_score", 0),
            sentiment_label=n.get("sentiment_label", "neutral"),
        ))
    
    return NoteListResponse(
        total=total,
        items=items,
        page=page,
        page_size=page_size,
    )


@router.get("/{note_id}")
async def get_note(note_id: str) -> dict[str, Any]:
    """获取单条笔记详情."""
    settings = get_settings()
    
    notes_file = settings.data_dir / "notes.json"
    if not notes_file.exists():
        raise HTTPException(status_code=404, detail="Notes not found")
    
    with open(notes_file, "r", encoding="utf-8") as f:
        notes = json.load(f)
    
    for note in notes:
        if note.get("id") == note_id:
            return note
    
    raise HTTPException(status_code=404, detail=f"Note {note_id} not found")


@router.post("/{note_id}/analyze")
async def analyze_note(note_id: str) -> dict[str, Any]:
    """分析单条笔记情感."""
    settings = get_settings()
    
    # 加载笔记
    notes_file = settings.data_dir / "notes.json"
    if not notes_file.exists():
        raise HTTPException(status_code=404, detail="Notes not found")
    
    with open(notes_file, "r", encoding="utf-8") as f:
        notes = json.load(f)
    
    note = None
    for n in notes:
        if n.get("id") == note_id:
            note = n
            break
    
    if not note:
        raise HTTPException(status_code=404, detail=f"Note {note_id} not found")
    
    # 情感分析
    analyzer = SentimentService()
    content = note.get("content", "")
    
    if not analyzer.is_loaded:
        return {
            "success": False,
            "message": "SVM model not trained yet",
        }
    
    result = analyzer.predict(content)
    
    # 更新笔记
    note["sentiment_score"] = result["score"]
    note["sentiment_label"] = result["label"]
    
    # 保存
    with open(notes_file, "w", encoding="utf-8") as f:
        json.dump(notes, f, ensure_ascii=False, indent=2)
    
    return {
        "success": True,
        "note_id": note_id,
        "sentiment": result,
    }
