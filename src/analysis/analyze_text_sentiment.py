from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path

from src.paths import NOTE_MEDIA_DIR, REPORTS_DIR, ensure_project_dirs
from src.utils import dump_json, load_json


# 情感词典 - 正向情感词（权重基于情感强度）
POSITIVE_TERMS = {
    # 强正向 (3.0)
    "太美": 3.0, "绝美": 3.0, "惊艳": 3.0, "震撼": 3.0, " breathtaking": 3.0,
    "强烈推荐": 3.0, "必去": 3.0, "一生必看": 3.0,
    # 中强正向 (2.5)
    "宝藏": 2.5, "超值": 2.5, "很美": 2.5, "绝美": 2.5, " fantastic": 2.5,
    "不虚此行": 2.5, "值得一去": 2.5, "流连忘返": 2.5,
    # 中等正向 (2.0)
    "值得": 2.0, "喜欢": 2.0, "推荐": 2.0, "好看": 2.0, "舒服": 2.0,
    "惊喜": 2.0, "古色古香": 2.0, "有韵味": 2.0, "意境": 2.0,
    # 弱正向 (1.5)
    "美": 1.5, "出片": 1.5, "不错": 1.5, "爱": 1.5, "美感": 1.5,
    "有特色": 1.5, "精致": 1.5, "典雅": 1.5, "宁静": 1.5,
    # 微正向 (1.0-1.2)
    "可爱": 1.2, "好": 1.0, "棒": 1.0, "赞": 1.0, "优秀": 1.2,
}

# 负向情感词
NEGATIVE_TERMS = {
    # 强负向 (-3.0)
    "失望": -3.0, "后悔": -3.0, "踩雷": -3.0, "不推荐": -3.0,
    "浪费": -3.0, "上当": -3.0, "骗": -3.0,
    # 中强负向 (-2.5)
    "祛魅": -2.5, "不值": -2.5, "坑": -2.5, "恶劣": -2.5,
    "极差": -2.5, "糟糕": -2.5,
    # 中等负向 (-2.0)
    "无聊": -2.0, "失落": -2.0, "没意思": -2.0, "单调": -2.0,
    "破败": -2.0, "杂乱": -2.0,
    # 弱负向 (-1.5)
    "一般": -1.5, "拥挤": -1.5, "麻烦": -1.5, "可惜": -1.5,
    "差": -1.5, "遗憾": -1.5, "看不懂": -1.5, "没感觉": -1.5,
    # 微负向 (-1.0)
    "贵": -1.0, "排队": -1.0, "远": -1.0, "热": -1.0, "累": -1.0,
}

# 否定词 - 用于情感反转
NEGATIONS = ("不", "没", "无", "未", "别", "并非", "绝不", "从不")

# 程度副词 - 用于情感强度调节
INTENSIFIERS = {
    "很": 1.3, "非常": 1.6, "超": 1.5, "太": 1.6, "特别": 1.5,
    "真": 1.3, "真的": 1.4, "极其": 1.8, "十分": 1.5, "相当": 1.4,
    "格外": 1.5, "特别": 1.5, "无比": 1.8, "绝对": 1.7, "完全": 1.5,
}

# 情感标签映射（中文）
SENTIMENT_LABELS = {
    "positive": "正向",
    "neutral": "中性",
    "negative": "负向",
}


def build_text(note: dict) -> str:
    tags = note.get("tags") or []
    tag_text = " ".join(str(tag).strip() for tag in tags if str(tag).strip())
    return "\n".join(
        part for part in [str(note.get("title") or "").strip(), str(note.get("desc") or "").strip(), tag_text] if part
    )


def find_modifier(text: str, start_index: int) -> float:
    window = text[max(0, start_index - 4) : start_index]
    modifier = 1.0
    if any(token in window for token in NEGATIONS):
        modifier *= -1.0
    for token, factor in INTENSIFIERS.items():
        if token in window:
            modifier *= factor
    return modifier


def analyze_text(text: str) -> dict:
    score = 0.0
    matches: list[dict] = []
    lowered_text = text.strip()

    for term, weight in sorted(POSITIVE_TERMS.items(), key=lambda item: len(item[0]), reverse=True):
        start = 0
        while True:
            index = lowered_text.find(term, start)
            if index == -1:
                break
            applied = weight * find_modifier(lowered_text, index)
            score += applied
            matches.append(
                {
                    "term": term,
                    "score": round(applied, 3),
                    "polarity": "positive" if applied >= 0 else "negative",
                }
            )
            start = index + len(term)

    for term, weight in sorted(NEGATIVE_TERMS.items(), key=lambda item: len(item[0]), reverse=True):
        start = 0
        while True:
            index = lowered_text.find(term, start)
            if index == -1:
                break
            applied = weight * find_modifier(lowered_text, index)
            score += applied
            matches.append(
                {
                    "term": term,
                    "score": round(applied, 3),
                    "polarity": "negative" if applied < 0 else "positive",
                }
            )
            start = index + len(term)

    # 高级情感分析公式
    # 1. 基础情感分类阈值（基于情感强度分布）
    if score >= 2.0:
        label = "positive"
        intensity = "强" if score >= 5.0 else "中" if score >= 3.0 else "弱"
    elif score <= -2.0:
        label = "negative"
        intensity = "强" if score <= -5.0 else "中" if score <= -3.0 else "弱"
    else:
        label = "neutral"
        intensity = "平"

    # 2. 置信度计算（综合匹配数量、情感强度、文本长度）
    # 公式: confidence = tanh(|score| / sqrt(match_count + 1)) * length_factor
    import math
    match_count = len(matches) if matches else 1
    length_factor = min(1.0, len(lowered_text) / 100)  # 文本越长，置信度上限越高
    base_confidence = math.tanh(abs(score) / math.sqrt(match_count + 1))
    confidence = min(1.0, round(base_confidence * (0.7 + 0.3 * length_factor), 3))

    # 3. 情感极性比例（正向 vs 负向词汇占比）
    positive_matches = [m for m in matches if m["score"] > 0]
    negative_matches = [m for m in matches if m["score"] < 0]
    total_weight = sum(abs(m["score"]) for m in matches) or 1
    positive_ratio = sum(m["score"] for m in positive_matches) / total_weight if positive_matches else 0
    negative_ratio = abs(sum(m["score"] for m in negative_matches)) / total_weight if negative_matches else 0

    # 4. 情感波动性（情感词分布离散程度）
    if len(matches) >= 2:
        scores = [m["score"] for m in matches]
        mean_score = sum(scores) / len(scores)
        variance = sum((s - mean_score) ** 2 for s in scores) / len(scores)
        volatility = round(math.sqrt(variance), 3)
    else:
        volatility = 0.0

    # 5. 选取Top匹配词（按绝对权重排序）
    top_matches = sorted(matches, key=lambda item: abs(item["score"]), reverse=True)[:5]

    return {
        "sentiment_label": label,
        "sentiment_label_zh": SENTIMENT_LABELS.get(label, label),
        "sentiment_intensity": intensity,
        "sentiment_score": round(score, 3),
        "confidence": confidence,
        "polarity_ratio": {
            "positive": round(positive_ratio, 3),
            "negative": round(negative_ratio, 3),
        },
        "volatility": volatility,
        "match_count": len(matches),
        "matched_terms": top_matches,
        "text_length": len(lowered_text),
    }


def load_notes() -> list[dict]:
    notes: list[dict] = []
    for info_path in sorted(NOTE_MEDIA_DIR.glob("*/info.json")):
        notes.append(load_json(info_path))
    return notes


def analyze_and_save_sentiment() -> dict:
    ensure_project_dirs()
    notes = load_notes()
    results: list[dict] = []
    label_counter: Counter[str] = Counter()
    label_zh_counter: Counter[str] = Counter()
    intensity_counter: Counter[str] = Counter()

    for note in notes:
        text = build_text(note)
        analysis = analyze_text(text)
        label_counter.update([analysis["sentiment_label"]])
        label_zh_counter.update([analysis["sentiment_label_zh"]])
        intensity_counter.update([analysis["sentiment_intensity"]])
        results.append(
            {
                "note_id": note.get("note_id", ""),
                "note_url": note.get("note_url", ""),
                "title": note.get("title", ""),
                "nickname": note.get("nickname", ""),
                "sentiment_text": text,
                **analysis,
            }
        )

    # 高级汇总统计
    total = len(results)
    average_score = round(sum(item["sentiment_score"] for item in results) / total, 3) if results else 0.0
    avg_confidence = round(sum(item["confidence"] for item in results) / total, 3) if results else 0.0
    avg_volatility = round(sum(item["volatility"] for item in results) / total, 3) if results else 0.0

    # 计算正向情感占比（加权）
    positive_weight = sum(
        item["polarity_ratio"]["positive"] * abs(item["sentiment_score"])
        for item in results
    ) if results else 0
    total_weight = sum(abs(item["sentiment_score"]) for item in results) if results else 1
    positive_index = round(positive_weight / total_weight, 3) if total_weight > 0 else 0.5

    summary = {
        "total_notes": total,
        "average_sentiment_score": average_score,
        "average_confidence": avg_confidence,
        "average_volatility": avg_volatility,
        "sentiment_distribution": dict(label_counter),
        "sentiment_distribution_zh": dict(label_zh_counter),
        "intensity_distribution": dict(intensity_counter),
        "positive_index": positive_index,  # 0-1，越接近1表示整体越正向
    }

    dump_json(REPORTS_DIR / "note_text_sentiment.json", results)
    dump_json(REPORTS_DIR / "note_text_sentiment_summary.json", summary)
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analyze tourist sentiment tendency from note text.")
    return parser.parse_args()


def main() -> None:
    parse_args()
    summary = analyze_and_save_sentiment()
    print(f"saved text sentiment reports for {summary['total_notes']} notes -> {REPORTS_DIR}")


if __name__ == "__main__":
    main()
