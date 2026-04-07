from __future__ import annotations

from src.paths import NOTE_MEDIA_DIR, REPORTS_DIR, ensure_project_dirs
from src.utils import dump_json, load_json


def build_records() -> list[dict]:
    records: list[dict] = []
    seen: set[tuple[str, int]] = set()
    for info_path in NOTE_MEDIA_DIR.glob("*/info.json"):
        info = load_json(info_path)
        note_id = str(info.get("note_id") or "").strip()
        title = str(info.get("title") or info_path.parent.name).strip()
        nickname = str(info.get("nickname") or "").strip()
        tags = info.get("tags") or []
        image_list = info.get("image_list") or []
        note_dir = info_path.parent
        for index, image_url in enumerate(image_list):
            key = (note_id or note_dir.name, index)
            if key in seen:
                continue
            seen.add(key)
            records.append(
                {
                    "record_id": f"{key[0]}_{index}",
                    "note_id": note_id,
                    "title": title,
                    "nickname": nickname,
                    "tags": tags,
                    "note_dir": str(note_dir),
                    "image_index": index,
                    "image_url": image_url,
                    "image_path": str(note_dir / f"image_{index}.jpg"),
                }
            )
    records.sort(key=lambda item: (item["note_id"], item["image_index"]))
    return records


def build_and_save_records() -> list[dict]:
    ensure_project_dirs()
    output_path = REPORTS_DIR / "image_interest_manifest.json"
    records = build_records()
    dump_json(output_path, records)
    print(f"saved {len(records)} records -> {output_path}")
    return records


def main() -> None:
    build_and_save_records()


if __name__ == "__main__":
    main()
