from __future__ import annotations

import argparse
import json
import re
import time
from html import unescape
from pathlib import Path
from urllib.parse import urlparse

import requests
from loguru import logger

from src.paths import HTML_PAGES_DIR, NOTE_MEDIA_DIR, REPORTS_DIR, ensure_project_dirs
from src.utils import dump_json, load_json, norm_str


ALLOWED_IMAGE_HOST_SUFFIXES = ("xiaohongshu.com", "xhscdn.com")


def load_html(html_path: Path) -> str:
    return html_path.read_text(encoding="utf-8")


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", unescape(value or "")).strip()


def normalize_image_url(url: str) -> str:
    url = clean_text(url)
    if not url:
        return ""
    if url.startswith("//"):
        return f"https:{url}"
    return url


def try_load_json(text: str) -> dict | None:
    try:
        return json.loads(text)
    except Exception:
        return None


def extract_braced_object(text: str, start_index: int) -> str | None:
    brace_depth = 0
    in_string = False
    escape = False
    object_started = False
    for index in range(start_index, len(text)):
        char = text[index]
        if in_string:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
            continue
        if char == "{":
            brace_depth += 1
            object_started = True
        elif char == "}":
            brace_depth -= 1
            if object_started and brace_depth == 0:
                return text[start_index : index + 1]
    return None


def sanitize_js_object_literal(object_text: str) -> str:
    sanitized = re.sub(r":undefined([,}])", r":null\1", object_text)
    return re.sub(r"\bundefined\b", "null", sanitized)


def extract_initial_state(html: str) -> dict | None:
    marker = "window.__INITIAL_STATE__="
    start = html.find(marker)
    if start == -1:
        return None
    object_text = extract_braced_object(html, start + len(marker))
    if not object_text:
        return None
    return try_load_json(sanitize_js_object_literal(object_text))


def dedupe_keep_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for item in items:
        if item and item not in seen:
            seen.add(item)
            deduped.append(item)
    return deduped


def is_allowed_image_url(url: str) -> bool:
    host = urlparse(url).netloc.lower()
    return any(host.endswith(suffix) for suffix in ALLOWED_IMAGE_HOST_SUFFIXES)


def decode_js_escaped_url(url: str) -> str:
    return normalize_image_url(url.replace("\\/", "/"))


def extract_urls_from_image_item(image_item: dict) -> list[str]:
    prioritized_candidates: list[str] = []
    for key in ("urlDefault", "url"):
        value = image_item.get(key)
        if isinstance(value, str):
            prioritized_candidates.append(value)
    info_list = image_item.get("infoList", [])
    if isinstance(info_list, list):
        for scene_name in ("WB_DFT", "WB_PRV"):
            for info in info_list:
                if isinstance(info, dict) and info.get("imageScene") == scene_name and isinstance(info.get("url"), str):
                    prioritized_candidates.append(info["url"])
    if isinstance(image_item.get("urlPre"), str):
        prioritized_candidates.append(image_item["urlPre"])
    for candidate in prioritized_candidates:
        normalized = decode_js_escaped_url(candidate)
        if normalized and is_allowed_image_url(normalized):
            return [normalized]
    return []


def extract_note_from_initial_state(state: dict | None) -> dict:
    if not isinstance(state, dict):
        return {}
    note_state = state.get("note")
    if not isinstance(note_state, dict):
        return {}
    current_note_id = note_state.get("currentNoteId")
    note_detail_map = note_state.get("noteDetailMap")
    if not current_note_id or not isinstance(note_detail_map, dict):
        return {}
    note_entry = note_detail_map.get(current_note_id)
    if not isinstance(note_entry, dict):
        return {}
    note_payload = note_entry.get("note")
    if not isinstance(note_payload, dict):
        return {}

    user_payload = note_payload.get("user", {}) if isinstance(note_payload.get("user"), dict) else {}
    interact_info = note_payload.get("interactInfo", {}) if isinstance(note_payload.get("interactInfo"), dict) else {}
    image_urls: list[str] = []
    for image_item in note_payload.get("imageList", []):
        if isinstance(image_item, dict):
            image_urls.extend(extract_urls_from_image_item(image_item))
    tags: list[str] = []
    for tag in note_payload.get("tagList", []):
        if isinstance(tag, dict):
            tag_name = clean_text(tag.get("name", ""))
            if tag_name:
                tags.append(tag_name)
    note_id = clean_text(str(note_payload.get("noteId", current_note_id)))
    return {
        "note_id": note_id,
        "note_url": f"https://www.xiaohongshu.com/explore/{note_id}" if note_id else "",
        "title": clean_text(note_payload.get("title", "")),
        "desc": clean_text(note_payload.get("desc", "") or note_payload.get("content", "")),
        "image_list": dedupe_keep_order(image_urls),
        "tags": dedupe_keep_order(tags),
        "user_id": clean_text(str(user_payload.get("userId", ""))),
        "nickname": clean_text(user_payload.get("nickname", "")),
        "avatar": decode_js_escaped_url(user_payload.get("avatar", "")) if user_payload.get("avatar") else "",
        "liked_count": interact_info.get("likedCount", ""),
        "collected_count": interact_info.get("collectedCount", ""),
        "comment_count": interact_info.get("commentCount", ""),
        "share_count": interact_info.get("shareCount", ""),
        "note_type": clean_text(note_payload.get("type", "")),
        "publish_time": note_payload.get("time", ""),
    }


def extract_note_id(html: str, html_path: Path) -> str:
    patterns = [r'"noteId"\s*:\s*"([^"]+)"', r'"note_id"\s*:\s*"([^"]+)"', r"/explore/([0-9a-z]+)"]
    for pattern in patterns:
        match = re.search(pattern, html, flags=re.IGNORECASE)
        if match:
            return match.group(1)
    return html_path.stem


def parse_note_from_html(html_path: Path) -> dict:
    html = load_html(html_path)
    state_note = extract_note_from_initial_state(extract_initial_state(html))
    note = {
        "source_html": str(html_path.resolve()),
        "note_id": extract_note_id(html, html_path),
        "note_url": "",
        "title": "untitled_post",
        "desc": "",
        "image_list": [],
        "tags": [],
        "user_id": "",
        "nickname": "",
        "avatar": "",
        "liked_count": "",
        "collected_count": "",
        "comment_count": "",
        "share_count": "",
        "note_type": "",
        "publish_time": "",
    }
    note.update({key: value for key, value in state_note.items() if value not in ("", [], None)})
    if not note.get("note_url") and note.get("note_id"):
        note["note_url"] = f"https://www.xiaohongshu.com/explore/{note['note_id']}"
    return note


def build_note_save_path(note: dict) -> Path:
    safe_title = norm_str(str(note["title"]))[:40] or "untitled"
    safe_id = norm_str(str(note["note_id"]))[:32] or "unknown"
    return NOTE_MEDIA_DIR / f"{safe_title}_{safe_id}"


def load_existing_import_index() -> dict[str, tuple[dict, Path]]:
    index: dict[str, tuple[dict, Path]] = {}
    for info_path in NOTE_MEDIA_DIR.glob("*/info.json"):
        try:
            info = load_json(info_path)
        except Exception:
            continue
        source_html = str(info.get("source_html") or "").strip()
        if source_html:
            index[source_html] = (info, info_path.parent)
    return index


def bundle_has_downloaded_images(note: dict, save_path: Path) -> bool:
    image_list = note.get("image_list") or []
    return all((save_path / f"image_{index}.jpg").exists() for index, _ in enumerate(image_list))


def download_image(image_url: str, output_path: Path, pause_seconds: float) -> None:
    with requests.Session() as session:
        # Ignore ambient proxy environment variables so local broken proxy config
        # does not block compliant image downloads.
        session.trust_env = False
        response = session.get(image_url, timeout=20)
    response.raise_for_status()
    output_path.write_bytes(response.content)
    time.sleep(pause_seconds)


def save_note_bundle(note: dict, download_images: bool, pause_seconds: float) -> Path:
    save_path = build_note_save_path(note)
    save_path.mkdir(parents=True, exist_ok=True)
    dump_json(save_path / "info.json", note)

    detail_lines = [
        f"note_id: {note['note_id']}",
        f"note_url: {note.get('note_url', '')}",
        f"title: {note['title']}",
        f"nickname: {note.get('nickname', '')}",
        f"user_id: {note.get('user_id', '')}",
        f"desc: {note.get('desc', '')}",
        f"tags: {note.get('tags', [])}",
        f"liked_count: {note.get('liked_count', '')}",
        f"collected_count: {note.get('collected_count', '')}",
        f"comment_count: {note.get('comment_count', '')}",
        f"share_count: {note.get('share_count', '')}",
        f"note_type: {note.get('note_type', '')}",
        f"publish_time: {note.get('publish_time', '')}",
        f"source_html: {note['source_html']}",
        "image_list:",
    ]
    detail_lines.extend(f"- {image_url}" for image_url in note.get("image_list", []))
    (save_path / "detail.txt").write_text("\n".join(detail_lines) + "\n", encoding="utf-8")

    if download_images:
        for index, image_url in enumerate(note.get("image_list", [])):
            if not is_allowed_image_url(image_url):
                logger.warning(f"Skip non-allowlisted image host: {image_url}")
                continue
            try:
                download_image(image_url, save_path / f"image_{index}.jpg", pause_seconds)
            except Exception as exc:
                logger.warning(f"Download failed for {image_url}: {exc}")
    return save_path


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Import manually saved Xiaohongshu post HTML files.")
    parser.add_argument("--html-dir", default=str(HTML_PAGES_DIR), help="Directory containing manually saved HTML files.")
    parser.add_argument("--download-images", action="store_true", default=True, help="Download allowlisted image URLs.")
    parser.add_argument("--no-download-images", action="store_false", dest="download_images", help="Skip image downloads.")
    parser.add_argument("--pause-seconds", type=float, default=1.0, help="Pause between image downloads.")
    return parser


def import_html_notes(html_dir: str | Path, download_images: bool = True, pause_seconds: float = 1.0) -> list[dict]:
    ensure_project_dirs()
    html_dir = Path(html_dir).resolve()
    if not html_dir.is_dir():
        raise FileNotFoundError(f"HTML directory not found: {html_dir}")
    html_files = sorted(path for path in html_dir.iterdir() if path.suffix.lower() in {".html", ".htm"})
    if not html_files:
        logger.warning(f"No HTML files found in {html_dir}")
        dump_json(REPORTS_DIR / "compliant_import_manifest.json", [])
        return []

    existing_index = load_existing_import_index()
    imported: list[dict] = []
    for html_file in html_files:
        try:
            html_key = str(html_file.resolve())
            existing = existing_index.get(html_key)
            if existing:
                existing_note, existing_path = existing
                if not download_images or bundle_has_downloaded_images(existing_note, existing_path):
                    imported.append(existing_note)
                    logger.info(f"Skipped already imported HTML {html_file} -> {existing_path}")
                    continue

            note = parse_note_from_html(html_file)
            save_path = save_note_bundle(note, download_images, pause_seconds)
            imported.append(note)
            existing_index[html_key] = (note, save_path)
            logger.info(f"Imported {html_file} -> {save_path}")
        except Exception as exc:
            logger.warning(f"Failed to import {html_file}: {exc}")
    dump_json(REPORTS_DIR / "compliant_import_manifest.json", imported)
    logger.info(f"Saved manifest to {REPORTS_DIR / 'compliant_import_manifest.json'}")
    return imported


def main() -> None:
    args = build_argument_parser().parse_args()
    import_html_notes(args.html_dir, download_images=args.download_images, pause_seconds=args.pause_seconds)


if __name__ == "__main__":
    main()
