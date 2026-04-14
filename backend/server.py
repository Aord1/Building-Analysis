from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

# Make project imports work when running `python backend/server.py`.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.analysis.analyze_text_sentiment import analyze_and_save_sentiment
from src.analysis.build_image_manifest import build_and_save_records
from src.analysis.generate_management_recommendations import (
    build_culture_recommendations,
    build_note_engagement,
    build_priority_notes,
    build_route_recommendations,
    generate_management_recommendations,
    summarize_sentiment,
    summarize_visual_interest,
)
from src.analysis.classify_with_vlm import DEFAULT_BASE_URL, DEFAULT_MODEL, run_classification
from src.importers.xhs_html_importer import import_html_notes
from src.main import is_configured_api_key, load_dotenv
from src.paths import DATA_DIR, HTML_PAGES_DIR, INTERIM_DIR, PROCESSED_DIR, RAW_DIR, REPORTS_DIR, ensure_project_dirs
from src.utils import load_json

UPLOAD_BATCH_DIR = HTML_PAGES_DIR / "upload_batches"


def try_load(path: Path, default):
    if not path.exists():
        return default
    try:
        return load_json(path)
    except Exception:
        return default


def build_dashboard_payload() -> dict:
    sentiment_summary = try_load(REPORTS_DIR / "note_text_sentiment_summary.json", {})
    sentiment_rows = try_load(REPORTS_DIR / "note_text_sentiment.json", [])
    management = try_load(REPORTS_DIR / "management_recommendations.json", {})
    vlm_predictions = try_load(REPORTS_DIR / "vlm_interest_predictions.json", [])

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "report_dir": str(REPORTS_DIR),
        "sentiment_summary": sentiment_summary,
        "management": management,
        "sample_sentiment_rows": sentiment_rows[:10],
        "vlm_prediction_count": len(vlm_predictions),
    }


def build_vlm_answers(note_ids: set[str] | None = None, limit: int = 120) -> list[dict]:
    rows = try_load(REPORTS_DIR / "vlm_interest_predictions.json", [])
    if note_ids:
        rows = [row for row in rows if str(row.get("note_id") or "").strip() in note_ids]
    answers: list[dict] = []
    for row in rows[:limit]:
        answers.append(
            {
                "note_id": row.get("note_id"),
                "image_name": row.get("image_name"),
                "predicted_top_label": row.get("predicted_top_label"),
                "predicted_top_label_zh": row.get("predicted_top_label_zh"),
                "predicted_labels": row.get("predicted_labels", []),
                "predicted_labels_zh": row.get("predicted_labels_zh", []),
                "confidence": row.get("confidence"),
                "reason": row.get("reason"),
                "raw_model_result": row.get("raw_model_result", {}),
            }
        )
    return answers


def build_all_data_payload() -> dict:
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "dashboard": build_dashboard_payload(),
        "sentiment_rows": try_load(REPORTS_DIR / "note_text_sentiment.json", []),
        "vlm_predictions": build_vlm_answers(note_ids=None, limit=500),
        "recommendations": try_load(REPORTS_DIR / "management_recommendations.json", {}),
        "import_manifest": try_load(REPORTS_DIR / "compliant_import_manifest.json", []),
        "image_manifest": try_load(REPORTS_DIR / "image_interest_manifest.json", []),
    }


def clear_recorded_html_files() -> dict:
    ensure_project_dirs()
    deleted = 0
    deleted_paths: list[str] = []
    for ext in ("*.html", "*.htm"):
        for path in HTML_PAGES_DIR.rglob(ext):
            if not path.is_file():
                continue
            try:
                path.unlink()
                deleted += 1
                if len(deleted_paths) < 200:
                    deleted_paths.append(str(path))
            except Exception:
                continue
    return {
        "deleted_count": deleted,
        "deleted_samples": deleted_paths,
        "target_dir": str(HTML_PAGES_DIR),
        "html_pages_exists": HTML_PAGES_DIR.exists(),
    }


def _clear_dir_contents(root: Path, protected_dirs: set[Path] | None = None) -> dict:
    if not root.exists():
        return {"root": str(root), "deleted_files": 0, "deleted_dirs": 0}
    protected_dirs = protected_dirs or set()
    protected_resolved = {path.resolve() for path in protected_dirs}

    deleted_files = 0
    deleted_dirs = 0
    for file_path in root.rglob("*"):
        if not file_path.is_file():
            continue
        try:
            file_path.unlink()
            deleted_files += 1
        except Exception:
            continue

    dirs = [p for p in root.rglob("*") if p.is_dir()]
    dirs.sort(key=lambda p: len(p.parts), reverse=True)
    for dir_path in dirs:
        if dir_path.resolve() in protected_resolved:
            continue
        try:
            dir_path.rmdir()
            deleted_dirs += 1
        except Exception:
            continue
    return {"root": str(root), "deleted_files": deleted_files, "deleted_dirs": deleted_dirs}


def clear_all_data_files() -> dict:
    ensure_project_dirs()
    targets = [RAW_DIR, INTERIM_DIR, PROCESSED_DIR]
    protected = {HTML_PAGES_DIR}
    details = [_clear_dir_contents(target, protected_dirs=protected) for target in targets]
    # Recreate required project directories after cleanup.
    ensure_project_dirs()
    HTML_PAGES_DIR.mkdir(parents=True, exist_ok=True)
    return {
        "target_data_dir": str(DATA_DIR),
        "details": details,
        "deleted_file_count": sum(int(item["deleted_files"]) for item in details),
        "deleted_dir_count": sum(int(item["deleted_dirs"]) for item in details),
        "html_pages_exists": HTML_PAGES_DIR.exists(),
    }


def run_full_pipeline(payload: dict) -> dict:
    load_dotenv()
    download_images = bool(payload.get("download_images", True))
    pause_seconds = float(payload.get("pause_seconds", 0.0))
    top_k = int(payload.get("top_k", 3))
    timeout = int(payload.get("timeout", 120))
    limit = int(payload.get("limit", 0))
    run_vlm = bool(payload.get("run_vlm", True))

    html_dir = str(payload.get("html_dir") or HTML_PAGES_DIR)
    imported = import_html_notes(html_dir, download_images=download_images, pause_seconds=pause_seconds)
    imported_note_ids = sorted({str(item.get("note_id") or "").strip() for item in imported if item.get("note_id")})
    sentiment_summary = analyze_and_save_sentiment()
    records = build_and_save_records()
    management = generate_management_recommendations()

    api_key = str(payload.get("api_key") or "").strip()
    if not api_key:
        import os

        api_key = os.getenv("OPENAI_API_KEY", "")
    model_name = str(payload.get("model_name") or DEFAULT_MODEL)
    base_url = str(payload.get("base_url") or DEFAULT_BASE_URL)

    vlm_result: dict = {"ran": False, "reason": "api key missing or placeholder", "predictions_saved": 0}
    if run_vlm and records and is_configured_api_key(api_key):
        predictions = run_classification(
            model_name=model_name,
            base_url=base_url,
            api_key=api_key,
            top_k=top_k,
            limit=limit,
            pause_seconds=pause_seconds,
            timeout=timeout,
        )
        vlm_result = {"ran": True, "reason": "", "predictions_saved": len(predictions)}
        management = generate_management_recommendations()
    elif not run_vlm:
        vlm_result = {"ran": False, "reason": "disabled for this run", "predictions_saved": 0}

    return {
        "imported_notes": len(imported),
        "imported_note_ids": imported_note_ids,
        "sentiment_summary": sentiment_summary,
        "image_records": len(records),
        "vlm": vlm_result,
        "management_summary": {
            "route_count": len(management.get("route_recommendations", [])),
            "culture_count": len(management.get("culture_recommendations", [])),
        },
        "dashboard": build_dashboard_payload(),
    }


def build_scoped_recommendations(note_ids: set[str]) -> dict:
    sentiment_rows_all = try_load(REPORTS_DIR / "note_text_sentiment.json", [])
    sentiment_summary_all = try_load(REPORTS_DIR / "note_text_sentiment_summary.json", {})
    predictions_all = try_load(REPORTS_DIR / "vlm_interest_predictions.json", [])
    engagement_all = build_note_engagement()

    sentiment_rows = [row for row in sentiment_rows_all if str(row.get("note_id") or "").strip() in note_ids]
    predictions = [row for row in predictions_all if str(row.get("note_id") or "").strip() in note_ids]
    engagement = {k: v for k, v in engagement_all.items() if k in note_ids}

    if sentiment_rows:
        labels = [str(row.get("sentiment_label") or "unknown") for row in sentiment_rows]
        distribution = {label: labels.count(label) for label in sorted(set(labels))}
        average = round(sum(float(row.get("sentiment_score") or 0.0) for row in sentiment_rows) / len(sentiment_rows), 3)
        scoped_sentiment_summary = {
            "sentiment_distribution": distribution,
            "average_sentiment_score": average,
        }
    else:
        scoped_sentiment_summary = sentiment_summary_all

    visual_interest = summarize_visual_interest(predictions)
    sentiment_info = summarize_sentiment(sentiment_rows, scoped_sentiment_summary)
    route_recommendations = build_route_recommendations(visual_interest, sentiment_info)
    culture_recommendations = build_culture_recommendations(visual_interest, sentiment_info)
    priority_notes = build_priority_notes(engagement, visual_interest.get("dominant_label_by_note", {}), sentiment_rows)
    return {
        "sentiment_summary": sentiment_info,
        "visual_interest": visual_interest,
        "route_recommendations": route_recommendations,
        "culture_recommendations": culture_recommendations,
        "priority_notes": priority_notes,
        "data_quality": {
            "sentiment_note_count": len(sentiment_rows),
            "vlm_prediction_count": len(predictions),
            "note_engagement_count": len(engagement),
        },
    }


def _parse_multipart_html_files(content_type: str, body: bytes) -> list[tuple[str, bytes]]:
    marker = "boundary="
    if marker not in content_type:
        return []
    boundary = content_type.split(marker, 1)[1].strip().strip('"')
    if not boundary:
        return []

    delimiter = ("--" + boundary).encode("utf-8")
    files: list[tuple[str, bytes]] = []
    for raw_part in body.split(delimiter):
        part = raw_part.strip()
        if not part or part == b"--":
            continue
        if b"\r\n\r\n" not in part:
            continue
        header_blob, content = part.split(b"\r\n\r\n", 1)
        header_text = header_blob.decode("latin-1", errors="ignore")
        if "name=\"files\"" not in header_text or "filename=" not in header_text:
            continue

        filename = ""
        for header_line in header_text.split("\r\n"):
            if "Content-Disposition" not in header_line:
                continue
            chunks = [chunk.strip() for chunk in header_line.split(";")]
            for chunk in chunks:
                if chunk.startswith("filename="):
                    filename = chunk.split("=", 1)[1].strip().strip('"')
                    break
        if not filename:
            continue
        file_bytes = content.rstrip(b"\r\n")
        files.append((filename, file_bytes))
    return files


def _save_uploaded_html_files(file_items: list[tuple[str, bytes]]) -> tuple[Path, list[str]]:
    batch_id = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    batch_dir = UPLOAD_BATCH_DIR / batch_id
    batch_dir.mkdir(parents=True, exist_ok=True)
    saved_names: list[str] = []

    for raw_name, raw_bytes in file_items:
        src_name = Path(raw_name).name
        suffix = Path(src_name).suffix.lower()
        if suffix not in {".html", ".htm"}:
            continue
        target = batch_dir / src_name
        if target.exists():
            stem = target.stem
            ext = target.suffix
            index = 1
            while True:
                candidate = batch_dir / f"{stem}_{index}{ext}"
                if not candidate.exists():
                    target = candidate
                    break
                index += 1
        with target.open("wb") as handle:
            handle.write(raw_bytes)
        saved_names.append(target.name)
    return batch_dir, saved_names


class ApiHandler(BaseHTTPRequestHandler):
    server_version = "BuildAnalysisAPI/1.0"

    def _set_headers(self, status: int = 200) -> None:
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def _write_json(self, payload: dict, status: int = 200) -> None:
        self._set_headers(status)
        self.wfile.write(json.dumps(payload, ensure_ascii=False).encode("utf-8"))

    def do_OPTIONS(self) -> None:
        self._set_headers(204)

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/health":
            self._write_json({"status": "ok"})
            return
        if path == "/api/dashboard":
            self._write_json(build_dashboard_payload())
            return
        if path == "/api/recommendations":
            payload = try_load(REPORTS_DIR / "management_recommendations.json", {})
            self._write_json(payload)
            return
        if path == "/api/all-data":
            self._write_json(build_all_data_payload())
            return
        if path == "/api/vlm-answers":
            self._write_json({"rows": build_vlm_answers(note_ids=None, limit=500)})
            return
        if path == "/api/sentiment":
            payload = {
                "summary": try_load(REPORTS_DIR / "note_text_sentiment_summary.json", {}),
                "rows": try_load(REPORTS_DIR / "note_text_sentiment.json", []),
            }
            self._write_json(payload)
            return
        self._write_json({"error": f"Not found: {path}"}, status=404)

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        if path not in {
            "/api/recompute",
            "/api/run-pipeline",
            "/api/upload-html",
            "/api/clear-html-files",
            "/api/clear-data-files",
        }:
            self._write_json({"error": f"Not found: {path}"}, status=404)
            return

        if path == "/api/clear-html-files":
            result = clear_recorded_html_files()
            result["dashboard"] = build_dashboard_payload()
            self._write_json(result)
            return

        if path == "/api/clear-data-files":
            result = clear_all_data_files()
            result["dashboard"] = build_dashboard_payload()
            self._write_json(result)
            return

        if path == "/api/upload-html":
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length) if length > 0 else b""
            content_type = self.headers.get("Content-Type", "")
            files = _parse_multipart_html_files(content_type, body)
            batch_dir, saved_names = _save_uploaded_html_files(files)
            if not saved_names:
                self._write_json({"error": "No html files were uploaded under field name 'files'."}, status=400)
                return
            pipeline = run_full_pipeline(
                {
                    "html_dir": str(batch_dir),
                    "download_images": True,
                    "pause_seconds": 0.0,
                    "limit": 0,
                    "run_vlm": True,
                }
            )
            imported_note_ids = set(pipeline.get("imported_note_ids", []))
            scoped = build_scoped_recommendations(imported_note_ids)
            vlm_answers = build_vlm_answers(imported_note_ids, limit=200)
            total = try_load(REPORTS_DIR / "management_recommendations.json", {})
            self._write_json(
                {
                    "batch_dir": str(batch_dir),
                    "uploaded_files": saved_names,
                    "pipeline": pipeline,
                    "single_upload_vlm_answers": vlm_answers,
                    "single_upload_recommendations": scoped,
                    "total_recommendations": total,
                    "dashboard": build_dashboard_payload(),
                }
            )
            return

        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length) if length > 0 else b"{}"
        try:
            payload = json.loads(body.decode("utf-8"))
        except Exception:
            payload = {}

        if path == "/api/recompute":
            run_sentiment = bool(payload.get("run_sentiment", True))
            run_management = bool(payload.get("run_management", True))

            result: dict = {"run_sentiment": run_sentiment, "run_management": run_management}
            if run_sentiment:
                result["sentiment_summary"] = analyze_and_save_sentiment()
            if run_management:
                result["management"] = generate_management_recommendations()

            result["dashboard"] = build_dashboard_payload()
            self._write_json(result)
            return

        result = run_full_pipeline(payload)
        self._write_json(result)

    def log_message(self, format: str, *args) -> None:
        return


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backend API for Build Analysis dashboard.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    server = ThreadingHTTPServer((args.host, args.port), ApiHandler)
    print(f"Backend API started at http://{args.host}:{args.port}")
    print(
        "Available endpoints: /health, /api/dashboard, /api/sentiment, "
        "/api/recommendations, /api/recompute, /api/run-pipeline, /api/upload-html, "
        "/api/all-data, /api/vlm-answers, /api/clear-html-files, /api/clear-data-files"
    )
    server.serve_forever()


if __name__ == "__main__":
    main()
