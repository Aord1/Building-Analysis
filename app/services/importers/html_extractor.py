"""通用 HTML 数据提取服务."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

from bs4 import BeautifulSoup
from loguru import logger


class HTMLDataExtractor:
    """从 HTML 文件提取文本和图像数据."""

    # 预编译噪声文本匹配正则（类常量，避免重复编译）
    _NOISE_PATTERNS = [
        re.compile(r"^\d+$"),           # 纯数字
        re.compile(r"^\W+$"),           # 纯符号
        re.compile(r"登录|注册|关注|点赞|评论|分享"),  # 常见按钮文本
        re.compile(r"^\s*$"),           # 空白
    ]

    def __init__(self, output_dir: Path | None = None) -> None:
        self.output_dir = output_dir or Path("data/processed")
        self.text_output_dir = self.output_dir / "texts"
        self.image_output_dir = self.output_dir / "images"
        self.metadata_file = self.output_dir / "extraction_metadata.json"

        # 确保目录存在
        self.text_output_dir.mkdir(parents=True, exist_ok=True)
        self.image_output_dir.mkdir(parents=True, exist_ok=True)

    def extract_from_html(
        self,
        html_path: str | Path,
        download_images: bool = True,
    ) -> dict[str, Any]:
        """从 HTML 文件提取文本和图像.

        Args:
            html_path: HTML 文件路径
            download_images: 是否下载/复制图片到本地

        Returns:
            提取结果，包含文本列表和图片列表
        """
        html_path = Path(html_path)
        if not html_path.exists():
            raise FileNotFoundError(f"HTML file not found: {html_path}")

        logger.info(f"Extracting data from {html_path}")

        with open(html_path, "r", encoding="utf-8") as f:
            soup = BeautifulSoup(f.read(), "html.parser")

        # 提取文本内容
        texts = self._extract_texts(soup, html_path)

        # 提取图片
        images = self._extract_images(soup, html_path, download_images)

        result = {
            "source_file": str(html_path),
            "texts": texts,
            "images": images,
            "stats": {
                "text_count": len(texts),
                "image_count": len(images),
            },
        }

        # 保存元数据
        self._save_metadata(result)

        logger.info(
            f"Extraction complete: {len(texts)} texts, {len(images)} images"
        )
        return result

    def extract_from_folder(
        self,
        folder_path: str | Path,
        pattern: str = "*.html",
        download_images: bool = True,
    ) -> dict[str, Any]:
        """从文件夹批量提取 HTML 数据.

        Args:
            folder_path: 文件夹路径
            pattern: HTML 文件匹配模式
            download_images: 是否下载图片

        Returns:
            批量提取结果
        """
        folder_path = Path(folder_path)
        if not folder_path.exists():
            raise FileNotFoundError(f"Folder not found: {folder_path}")

        all_results = []
        html_files = list(folder_path.rglob(pattern))

        logger.info(f"Found {len(html_files)} HTML files in {folder_path}")

        for html_file in html_files:
            try:
                result = self.extract_from_html(html_file, download_images)
                all_results.append(result)
            except Exception as e:
                logger.error(f"Failed to extract {html_file}: {e}")

        # 合并结果
        merged = self._merge_results(all_results)

        # 保存合并后的元数据
        self._save_metadata(merged, suffix="_batch")

        return merged

    def _extract_texts(
        self, soup: BeautifulSoup, source_path: Path
    ) -> list[dict[str, Any]]:
        """提取文本内容."""
        texts = []

        # 尝试多种内容选择器
        content_selectors = [
            "article",
            "[data-type='note']",
            ".note-content",
            ".content",
            ".post-content",
            ".article-content",
            "main",
        ]

        content_elements = []
        for selector in content_selectors:
            elements = soup.select(selector)
            if elements:
                content_elements = elements
                break

        # 如果没有找到特定容器，使用 body
        if not content_elements:
            content_elements = [soup.body] if soup.body else [soup]

        for idx, element in enumerate(content_elements):
            # 提取段落文本
            paragraphs = []
            for p in element.find_all(["p", "div", "span", "h1", "h2", "h3"]):
                text = p.get_text(strip=True)
                # 过滤短文本和噪声
                if len(text) > 10 and not self._is_noise_text(text):
                    paragraphs.append(text)

            # 合并段落为完整内容
            full_content = "\n".join(paragraphs)

            if full_content:
                # 生成唯一 ID
                content_hash = hashlib.md5(
                    full_content[:100].encode()
                ).hexdigest()[:8]
                text_id = f"{source_path.stem}_{idx}_{content_hash}"

                text_data = {
                    "id": text_id,
                    "source": str(source_path),
                    "title": self._extract_title(soup, element),
                    "content": full_content,
                    "paragraphs": paragraphs,
                    "word_count": len(full_content),
                }

                # 保存到文件
                self._save_text_file(text_data)
                texts.append(text_data)

        return texts

    def _extract_images(
        self,
        soup: BeautifulSoup,
        source_path: Path,
        download: bool,
    ) -> list[dict[str, Any]]:
        """提取图片."""
        images = []
        seen_urls = set()

        # 查找所有图片
        for img in soup.find_all("img"):
            src = img.get("src") or img.get("data-src") or img.get("data-original")
            if not src:
                continue

            # 去重
            if src in seen_urls:
                continue
            seen_urls.add(src)

            # 解析 URL
            img_url = self._resolve_url(src, source_path)
            if not img_url:
                continue

            # 生成图片 ID
            img_hash = hashlib.md5(src.encode()).hexdigest()[:8]
            img_id = f"{source_path.stem}_{img_hash}"

            img_data = {
                "id": img_id,
                "source": str(source_path),
                "original_url": src,
                "alt": img.get("alt", ""),
                "title": img.get("title", ""),
            }

            # 下载/复制图片
            if download:
                local_path = self._save_image(img_url, img_id, source_path)
                if local_path:
                    img_data["local_path"] = str(local_path)

            images.append(img_data)

        return images

    def _extract_title(
        self, soup: BeautifulSoup, element: Any
    ) -> str:
        """提取标题."""
        # 尝试页面标题
        if soup.title:
            return soup.title.get_text(strip=True)

        # 尝试元素内的标题
        for tag in ["h1", "h2", "h3"]:
            h = element.find(tag)
            if h:
                return h.get_text(strip=True)

        return ""

    def _is_noise_text(self, text: str) -> bool:
        """判断是否为噪声文本."""
        for pattern in self._NOISE_PATTERNS:
            if pattern.match(text):
                return True
        return False

    def _resolve_url(self, url: str, base_path: Path) -> str | None:
        """解析相对 URL."""
        if url.startswith(("http://", "https://")):
            return url
        elif url.startswith("//"):
            return "https:" + url
        elif url.startswith("/"):
            # 相对根目录，无法解析，返回原值
            return url
        elif url.startswith("data:image"):
            # Base64 图片，暂不支持
            return None
        else:
            # 相对路径，尝试本地文件
            local_path = base_path.parent / url
            if local_path.exists():
                return str(local_path)
            return url

    def _save_image(
        self,
        img_url: str,
        img_id: str,
        source_path: Path,
    ) -> Path | None:
        """保存图片到本地."""
        try:
            # 确定文件扩展名
            ext = self._get_image_extension(img_url)
            filename = f"{img_id}{ext}"
            output_path = self.image_output_dir / filename

            if output_path.exists():
                return output_path

            if img_url.startswith(("http://", "https://")):
                # 网络图片，下载
                import requests

                response = requests.get(img_url, timeout=30, stream=True)
                response.raise_for_status()

                with open(output_path, "wb") as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)

            elif Path(img_url).exists():
                # 本地图片，复制
                shutil.copy2(img_url, output_path)
            else:
                return None

            logger.debug(f"Saved image: {output_path}")
            return output_path

        except Exception as e:
            logger.warning(f"Failed to save image {img_url}: {e}")
            return None

    def _save_text_file(self, text_data: dict[str, Any]) -> Path:
        """保存文本到文件."""
        filename = f"{text_data['id']}.json"
        output_path = self.text_output_dir / filename

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(text_data, f, ensure_ascii=False, indent=2)

        return output_path

    def _get_image_extension(self, url: str) -> str:
        """获取图片扩展名."""
        # 从 URL 解析
        parsed = urlparse(url)
        path = unquote(parsed.path)
        ext = Path(path).suffix.lower()

        if ext in [".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"]:
            return ext

        return ".jpg"  # 默认

    def _merge_results(
        self, results: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """合并多个提取结果."""
        all_texts = []
        all_images = []
        sources = []

        for r in results:
            all_texts.extend(r.get("texts", []))
            all_images.extend(r.get("images", []))
            sources.append(r.get("source_file"))

        return {
            "source_files": sources,
            "texts": all_texts,
            "images": all_images,
            "stats": {
                "file_count": len(results),
                "total_texts": len(all_texts),
                "total_images": len(all_images),
            },
        }

    def _save_metadata(
        self, data: dict[str, Any], suffix: str = ""
    ) -> None:
        """保存元数据."""
        filename = f"extraction_metadata{suffix}.json"
        output_path = self.output_dir / filename

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        logger.info(f"Saved metadata to {output_path}")
