from __future__ import annotations

import argparse
import os
from pathlib import Path

from src.analysis.build_image_manifest import build_and_save_records
from src.analysis.classify_with_vlm import DEFAULT_BASE_URL, DEFAULT_MODEL, run_classification
from src.importers.xhs_html_importer import import_html_notes
from src.paths import CONFIGS_DIR, HTML_PAGES_DIR


PLACEHOLDER_API_KEYS = {"", "your_api_key_here", "sk-your-key-here"}


def load_dotenv(dotenv_path: str | Path = ".env") -> None:
    path = Path(dotenv_path)
    if not path.is_file():
        return
    for raw_line in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            continue
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        os.environ[key] = value


def is_configured_api_key(value: str) -> bool:
    return value.strip() not in PLACEHOLDER_API_KEYS


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the pipeline: import HTML notes, build the image manifest, and optionally classify with a VLM."
    )
    parser.add_argument("--html-dir", default=str(HTML_PAGES_DIR), help="Directory containing manually saved HTML files.")
    parser.add_argument("--download-images", action="store_true", default=True, help="Download allowlisted image URLs during import.")
    parser.add_argument("--no-download-images", action="store_false", dest="download_images", help="Skip image downloads during import.")
    parser.add_argument("--pause-seconds", type=float, default=1.0, help="Pause between downloads and model calls.")
    parser.add_argument(
        "--skip-vlm",
        action="store_true",
        help="Skip multimodal classification and only run importer plus analysis manifest generation.",
    )
    parser.add_argument("--model-name", default=os.getenv("OPENAI_MODEL", DEFAULT_MODEL))
    parser.add_argument("--base-url", default=os.getenv("OPENAI_BASE_URL", DEFAULT_BASE_URL))
    parser.add_argument("--api-key", default=os.getenv("OPENAI_API_KEY", ""))
    parser.add_argument("--top-k", type=int, default=3)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--timeout", type=int, default=120)
    return parser


def main() -> None:
    load_dotenv()
    args = build_argument_parser().parse_args()

    imported = import_html_notes(
        args.html_dir,
        download_images=args.download_images,
        pause_seconds=args.pause_seconds,
    )
    print(f"imported {len(imported)} notes")

    records = build_and_save_records()
    print(f"prepared {len(records)} image records")

    if args.skip_vlm:
        print("skipped VLM classification because --skip-vlm was set")
        return
    if not records:
        print("skipped VLM classification because no image records were available")
        return

    taxonomy_path = CONFIGS_DIR / "interest_taxonomy.json"
    if not taxonomy_path.exists():
        print(f"skipped VLM classification because taxonomy config was missing: {taxonomy_path}")
        return
    if not is_configured_api_key(args.api_key):
        print("skipped VLM classification because OPENAI_API_KEY or --api-key was not provided")
        return

    predictions = run_classification(
        model_name=args.model_name,
        base_url=args.base_url,
        api_key=args.api_key,
        top_k=args.top_k,
        limit=args.limit,
        pause_seconds=args.pause_seconds,
        timeout=args.timeout,
    )
    print(f"saved {len(predictions)} VLM predictions")


if __name__ == "__main__":
    main()
