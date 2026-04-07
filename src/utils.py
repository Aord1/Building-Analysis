from __future__ import annotations

import json
import re
from pathlib import Path


def load_json(path: Path):
    # Accept UTF-8 files with or without BOM to avoid editor/shell encoding surprises.
    with path.open("r", encoding="utf-8-sig") as handle:
        return json.load(handle)


def dump_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)


def norm_str(text: str) -> str:
    return re.sub(r'[\\/:*?"<>| \r\n]+', "", text or "")
