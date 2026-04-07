from __future__ import annotations

import argparse
import base64
import json
import os
import re
import time
from pathlib import Path
from openai import OpenAI

import requests

from src.paths import CONFIGS_DIR, REPORTS_DIR, ensure_project_dirs
from src.utils import dump_json, load_json


DEFAULT_BASE_URL = "https://api.siliconflow.cn/v1"
DEFAULT_MODEL = "Qwen/Qwen3-VL-8B-Instruct"


def build_http_error(response: requests.Response) -> RuntimeError:
    body = response.text.strip()
    if len(body) > 1000:
        body = body[:1000] + "...<truncated>"
    return RuntimeError(
        f"VLM API request failed: status={response.status_code}, "
        f"reason={response.reason}, body={body or '<empty>'}"
    )


def image_to_data_url(image_path: Path) -> str:
    suffix = image_path.suffix.lower()
    mime = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
    }.get(suffix, "application/octet-stream")
    encoded = base64.b64encode(image_path.read_bytes()).decode("utf-8")
    return f"data:{mime};base64,{encoded}"


def load_taxonomy(path: Path) -> list[dict]:
    raw = load_json(path)
    categories = raw.get("categories") if isinstance(raw, dict) else raw
    if not categories:
        raise ValueError(f"No categories found in {path}")
    return categories


def build_label_lookup(categories: list[dict]) -> dict[str, str]:
    return {item["label"]: item["label_zh"] for item in categories}


def build_prompt(categories: list[dict], top_k: int) -> str:
    lines = [
        "你在做古建筑游客拍照兴趣点识别。",
        "请只根据图片内容判断游客拍照的主要兴趣点，不要参考文件名，不要猜测拍摄地点。",
        "请从给定标签中选择，不要自造标签。",
        "可选类别如下：",
    ]
    for item in categories:
        lines.append(f"- {item['label']}: {item['label_zh']}")
    lines.extend(
        [
            "",
            "请返回严格 JSON，不要输出任何额外解释，格式如下：",
            "{",
            '  "predicted_top_label": "类别英文id",',
            '  "predicted_labels": ["类别英文id1", "类别英文id2"],',
            '  "reason": "一句中文理由",',
            '  "confidence": 0.0',
            "}",
            "",
            f"`predicted_labels` 最多返回 {top_k} 个，按置信度从高到低排序。",
            "如果主体是建筑整体，优先选 architecture_overview。",
            "如果主体是植物或树木，优先选 garden_plants。",
            "如果主体是牌匾、文字、题字，优先选 plaque_inscription。",
            "如果主体是人物摆拍或游客打卡，优先选 people_checkin。",
        ]
    )
    return "\n".join(lines)


def extract_json(text: str) -> dict:
    match = re.search(r"\{.*\}", text, flags=re.S)
    if not match:
        raise ValueError(f"Model response does not contain JSON: {text[:200]}")
    return json.loads(match.group(0))


def parse_response(payload: dict) -> dict:
    choices = payload.get("choices") or []
    if not choices:
        raise ValueError(f"Unexpected API response format: {payload}")
    message = choices[0].get("message") or {}
    content = message.get("content")
    if isinstance(content, str) and content.strip():
        return extract_json(content)
    if isinstance(content, list):
        texts: list[str] = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text" and item.get("text"):
                texts.append(item["text"])
        if texts:
            return extract_json("\n".join(texts))
    raise ValueError(f"Unexpected API response content: {payload}")


def call_vlm_api(
    *,
    api_key: str,
    base_url: str,
    model: str,
    image_path: Path,
    prompt: str,
    timeout: int,
) -> dict:
    with requests.Session() as session:
        # Ignore ambient proxy environment variables so local broken proxy config
        # does not block VLM API requests.
        session.trust_env = False
        response = session.post(
            f"{base_url.rstrip('/')}/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {"type": "image_url", "image_url": {"url": image_to_data_url(image_path)}},
                        ],
                    }
                ],
                "temperature": 0.2,
            },
            timeout=timeout,
        )
    if not response.ok:
        raise build_http_error(response)
    return parse_response(response.json())


def normalize_prediction(result: dict, label_lookup: dict[str, str], top_k: int) -> dict:
    predicted_labels: list[str] = []
    top_label = result.get("predicted_top_label")
    if top_label in label_lookup:
        predicted_labels.append(top_label)
    for label in result.get("predicted_labels") or []:
        if label in label_lookup and label not in predicted_labels:
            predicted_labels.append(label)
        if len(predicted_labels) >= top_k:
            break
    if not predicted_labels:
        raise ValueError(f"No valid labels returned by model: {result}")
    predicted_labels = predicted_labels[:top_k]
    top_label = predicted_labels[0]
    confidence = result.get("confidence", 0.0)
    try:
        confidence = float(confidence)
    except (TypeError, ValueError):
        confidence = 0.0
    return {
        "predicted_top_label": top_label,
        "predicted_top_label_zh": label_lookup[top_label],
        "predicted_labels": predicted_labels,
        "predicted_labels_zh": [label_lookup[label] for label in predicted_labels],
        "reason": str(result.get("reason") or "").strip(),
        "confidence": confidence,
    }


def run_classification(
    *,
    model_name: str = DEFAULT_MODEL,
    base_url: str = DEFAULT_BASE_URL,
    api_key: str = "",
    top_k: int = 3,
    limit: int = 0,
    pause_seconds: float = 1.0,
    timeout: int = 120,
) -> list[dict]:
    ensure_project_dirs()
    if not api_key:
        raise SystemExit("Missing OPENAI_API_KEY, or pass the multimodal model API key with --api-key.")

    records = load_json(REPORTS_DIR / "image_interest_manifest.json")
    if limit > 0:
        records = records[:limit]

    categories = load_taxonomy(CONFIGS_DIR / "interest_taxonomy.json")
    label_lookup = build_label_lookup(categories)
    prompt = build_prompt(categories, top_k)
    predictions: list[dict] = []
    skipped = 0

    for index, record in enumerate(records, start=1):
        image_path = Path(record["image_path"])
        if not image_path.exists():
            skipped += 1
            continue

        print(f"[{index}/{len(records)}] classifying {image_path.name}")
        raw_result = call_vlm_api(
            api_key=api_key,
            base_url=base_url,
            model=model_name,
            image_path=image_path,
            prompt=prompt,
            timeout=timeout,
        )
        predictions.append(
            {
                **record,
                **normalize_prediction(raw_result, label_lookup, top_k),
                "model_name": model_name,
                "raw_model_result": raw_result,
            }
        )
        if pause_seconds > 0:
            time.sleep(pause_seconds)

    output_path = REPORTS_DIR / "vlm_interest_predictions.json"
    dump_json(output_path, predictions)
    print(f"saved {len(predictions)} predictions -> {output_path}")
    if skipped:
        print(f"skipped {skipped} records because local images were missing")
    return predictions


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Classify tourist images with a multimodal large model.")
    parser.add_argument("--model-name", default=os.getenv("OPENAI_MODEL", DEFAULT_MODEL))
    parser.add_argument("--base-url", default=os.getenv("OPENAI_BASE_URL", DEFAULT_BASE_URL))
    parser.add_argument("--api-key", default=os.getenv("OPENAI_API_KEY", ""))
    parser.add_argument("--top-k", type=int, default=3)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--pause-seconds", type=float, default=1.0)
    parser.add_argument("--timeout", type=int, default=120)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    run_classification(
        model_name=args.model_name,
        base_url=args.base_url,
        api_key=args.api_key,
        top_k=args.top_k,
        limit=args.limit,
        pause_seconds=args.pause_seconds,
        timeout=args.timeout,
    )


if __name__ == "__main__":
    main()
