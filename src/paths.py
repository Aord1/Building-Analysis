from __future__ import annotations

from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = PACKAGE_ROOT.parent

DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
INTERIM_DIR = DATA_DIR / "interim"
PROCESSED_DIR = DATA_DIR / "processed"

HTML_PAGES_DIR = RAW_DIR / "html_pages"
NOTE_MEDIA_DIR = INTERIM_DIR / "note_media"
REPORTS_DIR = PROCESSED_DIR / "reports"

CONFIGS_DIR = PROJECT_ROOT / "configs"
DOCS_DIR = PROJECT_ROOT / "docs"


def ensure_project_dirs() -> None:
    for path in (
        DATA_DIR,
        RAW_DIR,
        INTERIM_DIR,
        PROCESSED_DIR,
        HTML_PAGES_DIR,
        NOTE_MEDIA_DIR,
        REPORTS_DIR,
        CONFIGS_DIR,
        DOCS_DIR,
    ):
        path.mkdir(parents=True, exist_ok=True)
