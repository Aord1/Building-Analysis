"""小红书 HTML 导入器."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup


class XHSImporter:
    """小红书 HTML 笔记导入器."""
    
    def parse_html(self, filepath: str) -> list[dict[str, Any]]:
        """解析小红书 HTML 文件."""
        path = Path(filepath)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {filepath}")
        
        with open(path, "r", encoding="utf-8") as f:
            soup = BeautifulSoup(f.read(), "html.parser")
        
        notes = []
        
        # 尝试多种选择器查找笔记
        note_selectors = [
            ".note-item",
            ".feed-item",
            "[data-type='note']",
            ".search-item",
        ]
        
        for selector in note_selectors:
            items = soup.select(selector)
            if items:
                for item in items:
                    note = self._extract_note(item)
                    if note:
                        notes.append(note)
                break
        
        # 如果没有找到结构化数据，尝试提取所有文本
        if not notes:
            text = soup.get_text(separator="\n", strip=True)
            if text:
                notes.append({
                    "title": text[:50] + "..." if len(text) > 50 else text,
                    "content": text,
                    "images": [],
                })
        
        return notes
    
    def _extract_note(self, element: Any) -> dict[str, Any] | None:
        """从元素提取笔记数据."""
        # 提取标题
        title_selectors = [".title", "h1", "h2", "h3", ".note-title"]
        title = ""
        for sel in title_selectors:
            el = element.select_one(sel)
            if el:
                title = el.get_text(strip=True)
                break
        
        # 提取内容
        content_selectors = [".content", ".desc", ".note-content", "p"]
        content = ""
        for sel in content_selectors:
            el = element.select_one(sel)
            if el:
                content = el.get_text(strip=True)
                break
        
        # 提取图片
        images = []
        for img in element.find_all("img"):
            src = img.get("src") or img.get("data-src")
            if src:
                images.append(src)
        
        if not title and not content:
            return None
        
        return {
            "title": title or content[:50],
            "content": content or title,
            "images": images,
        }
    
    def extract_images_from_folder(self, folder_path: str) -> list[str]:
        """从文件夹提取所有图片路径."""
        folder = Path(folder_path)
        if not folder.exists():
            return []
        
        images = []
        extensions = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
        
        for ext in extensions:
            for filepath in folder.rglob(f"*{ext}"):
                images.append(str(filepath))
        
        return images
