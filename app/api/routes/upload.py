"""文件上传 API."""

from __future__ import annotations

import json
import shutil
import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from app.core.config import get_settings
from app.services.importers.xhs_html import XHSImporter

router = APIRouter()


class UploadResponse(BaseModel):
    """上传响应."""
    success: bool
    message: str
    files: list[dict[str, Any]]


@router.post("/images", response_model=UploadResponse)
async def upload_images(
    files: list[UploadFile] = File(...),
) -> UploadResponse:
    """上传图片文件."""
    settings = get_settings()
    uploaded = []
    
    for file in files:
        # 检查文件类型
        if not file.content_type or not file.content_type.startswith("image/"):
            continue
        
        # 生成唯一文件名
        ext = Path(file.filename or "").suffix or ".jpg"
        filename = f"{uuid.uuid4().hex}{ext}"
        filepath = settings.image_dir / filename
        
        # 保存文件
        with open(filepath, "wb") as f:
            shutil.copyfileobj(file.file, f)
        
        uploaded.append({
            "original_name": file.filename,
            "saved_name": filename,
            "path": f"image/{filename}",
            "size": filepath.stat().st_size,
        })
    
    return UploadResponse(
        success=True,
        message=f"Uploaded {len(uploaded)} images",
        files=uploaded,
    )


@router.post("/notes/html")
async def upload_html_notes(
    file: UploadFile = File(...),
) -> dict[str, Any]:
    """上传小红书 HTML 笔记文件."""
    settings = get_settings()
    
    # 检查文件类型
    if not file.filename or not file.filename.endswith(".html"):
        raise HTTPException(status_code=400, detail="Only HTML files allowed")
    
    # 保存临时文件
    temp_path = settings.data_dir / "temp" / f"{uuid.uuid4().hex}.html"
    temp_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(temp_path, "wb") as f:
        shutil.copyfileobj(file.file, f)
    
    # 导入笔记
    try:
        importer = XHSImporter()
        notes = importer.parse_html(str(temp_path))
        
        # 保存到 notes.json
        notes_file = settings.data_dir / "notes.json"
        existing = []
        if notes_file.exists():
            with open(notes_file, "r", encoding="utf-8") as f:
                existing = json.load(f)
        
        # 添加 ID
        for note in notes:
            note["id"] = str(uuid.uuid4())
        
        existing.extend(notes)
        
        with open(notes_file, "w", encoding="utf-8") as f:
            json.dump(existing, f, ensure_ascii=False, indent=2)
        
        # 清理临时文件
        temp_path.unlink()
        
        return {
            "success": True,
            "message": f"Imported {len(notes)} notes",
            "count": len(notes),
            "notes": [
                {"id": n["id"], "title": n.get("title", "")[:50]}
                for n in notes
            ],
        }
        
    except Exception as e:
        if temp_path.exists():
            temp_path.unlink()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/notes/json")
async def upload_json_notes(
    file: UploadFile = File(...),
) -> dict[str, Any]:
    """上传 JSON 格式笔记."""
    settings = get_settings()
    
    if not file.filename or not file.filename.endswith(".json"):
        raise HTTPException(status_code=400, detail="Only JSON files allowed")
    
    try:
        content = await file.read()
        notes = json.loads(content)
        
        if not isinstance(notes, list):
            raise HTTPException(status_code=400, detail="JSON must be a list")
        
        # 添加 ID
        for note in notes:
            if "id" not in note:
                note["id"] = str(uuid.uuid4())
        
        # 保存
        notes_file = settings.data_dir / "notes.json"
        existing = []
        if notes_file.exists():
            with open(notes_file, "r", encoding="utf-8") as f:
                existing = json.load(f)
        
        existing.extend(notes)
        
        with open(notes_file, "w", encoding="utf-8") as f:
            json.dump(existing, f, ensure_ascii=False, indent=2)
        
        return {
            "success": True,
            "message": f"Imported {len(notes)} notes",
            "count": len(notes),
        }
        
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON format")
