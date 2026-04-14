from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from pathlib import Path

from src.paths import REPORTS_DIR, ensure_project_dirs
from src.utils import dump_json, load_json


# 图像兴趣标签中文映射
LABEL_TO_ROUTE_ZONE = {
    "architecture_overview": "主轴建筑区",
    "courtyard_garden": "园林步道区",
    "garden_plants": "庭院植物区",
    "plaque_inscription": "匾额碑刻区",
    "architectural_detail": "建筑细部观察区",
    "interior_exhibition": "室内展陈区",
    "artifact_object": "文物器物区",
    "map_ticket_guide": "入口导览区",
    "people_checkin": "热门打卡区",
    "night_view_lighting": "夜游灯光区",
}

# 标签权重（用于计算兴趣热度指数）
LABEL_WEIGHTS = {
    "architecture_overview": 1.0,
    "courtyard_garden": 0.9,
    "garden_plants": 0.8,
    "plaque_inscription": 1.2,  # 文化价值高
    "architectural_detail": 1.1,
    "interior_exhibition": 0.9,
    "artifact_object": 1.1,
    "map_ticket_guide": 0.6,
    "people_checkin": 0.7,
    "night_view_lighting": 0.85,
}

# 文化展示建议模板 - 更人性化的表达
LABEL_TO_CULTURAL_ACTION = {
    "architecture_overview": {
        "insight": "游客渴望快速建立整体认知，而非碎片化信息",
        "action": "在建筑总览点设置「1分钟看懂格局」数字导览卡，用一张图说清建筑的时代背景、功能分区与游览路线",
        "benefit": "帮助游客建立空间认知框架，减少迷路焦虑，提升游览自信",
    },
    "plaque_inscription": {
        "insight": "匾额碑刻是文化精华，但文字障碍让多数游客望而却步",
        "action": "推出「扫码识匾额」功能：逐字释义+历史典故+书法欣赏，3分钟读懂一块匾",
        "benefit": "将“看不懂”转化为“原来如此”的文化共鸣，提升文化获得感",
    },
    "architectural_detail": {
        "insight": "细节之美需要近距离观察，但物理距离限制了体验",
        "action": "在斗拱、雕刻、屋檐等细部旁设置「微观视角」二维码，扫码可看3D拆解与工艺讲解",
        "benefit": "让“看不见”的细节成为“惊艳发现”，深化建筑审美体验",
    },
    "interior_exhibition": {
        "insight": "孤立展柜难以传递文物背后的故事价值",
        "action": "设计「故事线导览」：按历史人物或事件串联展柜，像追剧一样逛展览",
        "benefit": "用叙事逻辑替代空间逻辑，让文物“活”起来，提升记忆度与传播欲",
    },
    "artifact_object": {
        "insight": "器物功能陌生化是理解障碍的主要来源",
        "action": "制作「古人怎么用」系列短视频：还原器物的使用场景与生活方式",
        "benefit": "跨越时空建立生活连接，让文物从“冷冰冰”变得“可触摸”",
    },
    "courtyard_garden": {
        "insight": "园林之美在于“景-史-人”的交融，但游客往往只见其形不见其意",
        "action": "在园林节点设置「此刻此景」语音导览：讲一段历史、一位人物、一种心境",
        "benefit": "将空间游览转化为情感体验，让园林成为可共鸣的文化场景",
    },
    "garden_plants": {
        "insight": "植物景观是拍照热点，但文化内涵常被忽视",
        "action": "推出「四季有故事」植物图鉴：每种植物的寓意、诗词、与建筑的关系",
        "benefit": "让“好看”的照片背后有“好故事”，提升分享价值与文化认同",
    },
    "night_view_lighting": {
        "insight": "夜游是差异化体验机会，但照明设计影响氛围与安全",
        "action": "优化夜游灯光层次：基础照明保安全，重点照明造氛围，互动照明增趣味",
        "benefit": "延长停留时间，创造独特记忆点，提升重游意愿",
    },
    "people_checkin": {
        "insight": "打卡需求是真实的，但排队与拥挤损害体验",
        "action": "设置「最佳拍摄点」标识与预约时段，提供拍照姿势参考与实时排队提示",
        "benefit": "尊重游客社交需求，将无序拥堵转化为有序体验",
    },
}

NEGATIVE_EXPERIENCE_KEYWORDS = {
    "拥挤": "高峰时段可能拥挤",
    "排队": "排队等待体验不佳",
    "一般": "体验一般，亮点感知不足",
    "祛魅": "预期与实际存在落差",
    "看不懂": "文化信息理解门槛较高",
    "无聊": "互动性不足，停留意愿偏弱",
}


def try_load(path: Path, default):
    if not path.exists():
        return default
    try:
        return load_json(path)
    except Exception:
        return default


def parse_int(value) -> int:
    try:
        text = str(value).strip()
        return int(text) if text else 0
    except Exception:
        return 0


def build_note_engagement() -> dict[str, dict]:
    manifest_path = REPORTS_DIR / "compliant_import_manifest.json"
    manifest = try_load(manifest_path, [])
    mapping: dict[str, dict] = {}
    for note in manifest:
        note_id = str(note.get("note_id") or "").strip()
        if not note_id:
            continue
        mapping[note_id] = {
            "liked_count": parse_int(note.get("liked_count")),
            "collected_count": parse_int(note.get("collected_count")),
            "comment_count": parse_int(note.get("comment_count")),
            "share_count": parse_int(note.get("share_count")),
            "engagement_score": parse_int(note.get("liked_count")) * 1
            + parse_int(note.get("collected_count")) * 2
            + parse_int(note.get("comment_count")) * 3
            + parse_int(note.get("share_count")) * 2,
        }
    return mapping


def summarize_visual_interest(predictions: list[dict]) -> dict:
    """高级图像兴趣分析 - 综合频次、权重、置信度"""
    label_counter: Counter[str] = Counter()
    label_confidence: defaultdict[str, list[float]] = defaultdict(list)
    note_label_counter: defaultdict[str, Counter[str]] = defaultdict(Counter)

    for row in predictions:
        label = str(row.get("predicted_top_label") or "").strip()
        note_id = str(row.get("note_id") or "").strip()
        confidence = float(row.get("confidence") or 0.0)

        if not label:
            continue

        # 加权计数（考虑标签权重）
        weight = LABEL_WEIGHTS.get(label, 1.0)
        label_counter.update([label])
        label_confidence[label].append(confidence * weight)

        if note_id:
            note_label_counter[note_id].update([label])

    # 计算热度指数 = 频次 × 平均置信度 × 标签权重
    heat_scores = {}
    for label, count in label_counter.items():
        avg_confidence = sum(label_confidence[label]) / len(label_confidence[label])
        weight = LABEL_WEIGHTS.get(label, 1.0)
        heat_scores[label] = count * avg_confidence * weight

    # 按热度排序
    sorted_labels = sorted(heat_scores.items(), key=lambda x: x[1], reverse=True)

    top_labels = [
        {
            "label": label,
            "label_zh": LABEL_TO_ROUTE_ZONE.get(label, label),
            "count": label_counter[label],
            "heat_score": round(score, 2),
            "avg_confidence": round(sum(label_confidence[label]) / len(label_confidence[label]), 3),
        }
        for label, score in sorted_labels[:5]
    ]

    # 主导标签（每篇笔记最突出的兴趣点）
    dominant_by_note = {}
    for note_id, counter in note_label_counter.items():
        dominant_by_note[note_id] = counter.most_common(1)[0][0]

    # 兴趣集中度（赫芬达尔指数）
    total = sum(label_counter.values())
    hhi = sum((count / total) ** 2 for count in label_counter.values()) if total > 0 else 0

    return {
        "top_labels": top_labels,
        "dominant_label_by_note": dominant_by_note,
        "interest_concentration": round(hhi, 3),  # 越接近1表示兴趣越集中
        "total_predictions": len(predictions),
        "unique_labels": len(label_counter),
    }


def summarize_sentiment(sentiment_rows: list[dict], sentiment_summary: dict) -> dict:
    """高级情感分析汇总 - 整合多维度指标"""
    issue_counter: Counter[str] = Counter()
    intensity_dist = Counter()
    confidence_sum = 0.0
    volatility_sum = 0.0

    for row in sentiment_rows:
        text = str(row.get("sentiment_text") or "")
        intensity_dist.update([row.get("sentiment_intensity", "平")])
        confidence_sum += row.get("confidence", 0.0)
        volatility_sum += row.get("volatility", 0.0)

        for keyword, issue_name in NEGATIVE_EXPERIENCE_KEYWORDS.items():
            if keyword in text:
                issue_counter.update([issue_name])

    total = len(sentiment_rows) or 1

    return {
        "distribution": sentiment_summary.get("sentiment_distribution", {}),
        "distribution_zh": sentiment_summary.get("sentiment_distribution_zh", {}),
        "intensity_distribution": dict(intensity_dist),
        "average_score": sentiment_summary.get("average_sentiment_score", 0.0),
        "average_confidence": round(confidence_sum / total, 3),
        "average_volatility": round(volatility_sum / total, 3),
        "positive_index": sentiment_summary.get("positive_index", 0.5),
        "top_negative_signals": [{"issue": issue, "count": count} for issue, count in issue_counter.most_common(5)],
    }


def build_route_recommendations(visual_summary: dict, sentiment_info: dict) -> list[dict]:
    """路线优化建议 - 更人性化的表达"""
    recommendations: list[dict] = []
    top_labels = visual_summary.get("top_labels", [])
    concentration = visual_summary.get("interest_concentration", 0.5)
    positive_index = sentiment_info.get("positive_index", 0.5)
    negative_signals = sentiment_info.get("top_negative_signals", [])
    avg_volatility = sentiment_info.get("average_volatility", 0.0)

    # 1. 游客真正想看的路线
    if top_labels:
        route_names = [LABEL_TO_ROUTE_ZONE.get(item["label"], item["label"]) for item in top_labels[:4]]
        route_flow = " → ".join(route_names)

        # 根据集中度给出不同建议
        if concentration > 0.3:
            insight = "游客目光高度聚焦，说明这些区域有独特的吸引力"
            suggestion = f"建议将「{route_flow}」设为主推路线，采用环形设计让游客自然回流"
            benefit = "顺应游客兴趣，减少无效走动，提升核心区域体验深度"
        else:
            insight = "游客兴趣分散多元，说明不同人群有不同偏好"
            suggestion = f"设计多条主题支线：建筑线、园林线、文化线，让「{route_names[0]}」作为交汇枢纽"
            benefit = "满足多元需求，分散客流压力，提升整体满意度"

        recommendations.append({
            "theme": "🎯 游客真正想看的路线",
            "priority": "高",
            "insight": insight,
            "suggestion": suggestion,
            "benefit": benefit,
            "data": f"热度Top4: {', '.join([f'{item['label_zh']}({item['heat_score']})' for item in top_labels[:4]])}",
        })

    # 2. 让"堵点"变"亮点"
    if negative_signals:
        issue = negative_signals[0]["issue"]
        count = negative_signals[0]["count"]

        if avg_volatility > 2.0 or count >= 5:
            recommendations.append({
                "theme": "⚠️ 紧急：体验危机预警",
                "priority": "紧急",
                "insight": f"「{issue}」被频繁提及，已成为影响口碑的关键因素",
                "suggestion": "立即启动三级响应：①增派现场引导员 ②开启备用通道 ③推送「错峰攻略」给后续游客",
                "benefit": "将负面体验控制在最小范围，防止口碑扩散",
                "data": f"提及次数: {count}, 情感波动: {avg_volatility:.2f}",
            })
        else:
            recommendations.append({
                "theme": "🔄 让“堵点”变“亮点”",
                "priority": "高",
                "insight": f"「{issue}」是游客的主要痛点，但痛点往往藏着机会",
                "suggestion": "将等待区改造成「预热体验区」：排队时扫码听建筑故事、看最佳拍摄攻略、预约专属讲解",
                "benefit": "把无奈的等待转化为有价值的文化预习，变负面为惊喜",
                "data": f"提及次数: {count}",
            })

    # 3. 创造"哇"时刻
    if positive_index < 0.6:
        recommendations.append({
            "theme": "✨ 创造“哇”时刻",
            "priority": "中",
            "insight": "整体情感偏平淡，缺少让人眼前一亮的记忆点",
            "suggestion": "在3个关键节点设置「隐藏彩蛋」：①特定角度的绝美框景 ②定时出现的文化表演 ③扫码解锁的专属故事",
            "benefit": "用意外惊喜打破平淡，创造值得分享的社交货币",
            "data": f"正向情感指数: {positive_index:.2f}（低于0.6建议强化）",
        })

    # 4. 给游客"选择权"
    recommendations.append({
        "theme": "🎫 给游客“选择权”",
        "priority": "中",
        "insight": "不同游客有不同需求，一刀切的服务难以满足所有人",
        "suggestion": "入口提供三种「身份卡」：①「打卡族」- 最佳拍照路线 ②「文化控」- 深度讲解路线 ③「亲子团」- 互动体验路线",
        "benefit": "让游客感到被理解、被尊重，提升归属感和满意度",
        "data": "基于游客画像的个性化服务设计",
    })

    return recommendations


def build_culture_recommendations(visual_summary: dict, sentiment_info: dict) -> list[dict]:
    """文化展示建议 - 更人性化的表达"""
    recs: list[dict] = []
    top_labels = visual_summary.get("top_labels", [])
    concentration = visual_summary.get("interest_concentration", 0.5)
    distribution_zh = sentiment_info.get("distribution_zh", {})
    intensity_dist = sentiment_info.get("intensity_distribution", {})
    negative_count = distribution_zh.get("负向", 0)
    total = sum(distribution_zh.values()) if distribution_zh else 1
    negative_ratio = negative_count / total
    strong_negative = intensity_dist.get("强", 0)

    # 1. 热点区域的文化深化
    for item in top_labels[:3]:
        label = item["label"]
        label_zh = item.get("label_zh", label)
        action_template = LABEL_TO_CULTURAL_ACTION.get(label)
        heat_score = item.get("heat_score", 0)

        if not action_template:
            continue

        # 根据热度确定优先级标签
        if heat_score >= 10 or strong_negative > 0:
            priority = "🔴 立即行动"
        elif heat_score >= 5:
            priority = "🟡 近期优化"
        else:
            priority = "🟢 持续改进"

        recs.append({
            "focus_label": label,
            "focus_label_zh": label_zh,
            "priority": priority,
            "heat_score": heat_score,
            "insight": action_template["insight"],
            "suggestion": action_template["action"],
            "benefit": action_template["benefit"],
            "data": f"热度指数 {heat_score} | 出现 {item['count']} 次 | 游客关注度 {item['avg_confidence']:.0%}",
        })

    # 2. 情感危机预警与修复
    if strong_negative > 0:
        recs.append({
            "focus_label": "emergency_response",
            "focus_label_zh": "⚠️ 情感危机预警",
            "priority": "🔴 立即行动",
            "insight": "有游客表达了强烈不满，这可能是个例，也可能是系统性问题的信号",
            "suggestion": "①24小时内联系当事人了解详情并致歉补偿 ②排查同类问题是否存在 ③在官方渠道发布改进说明",
            "benefit": "将危机转化为展示服务诚意的机会，挽回口碑",
            "data": f"强负向情感: {strong_negative} 条",
        })

    # 3. 弥合"看不懂"的鸿沟
    if negative_ratio >= 0.15:
        recs.append({
            "focus_label": "narrative_gap",
            "focus_label_zh": "📖 弥合“看不懂”的鸿沟",
            "priority": "🟡 近期优化",
            "insight": "近五分之一的游客感到困惑或失望，说明文化传递存在断层",
            "suggestion": "设计「三层解读」体系：①30秒速览（是什么）②3分钟故事（为什么重要）③深度专题（背后的故事）",
            "benefit": "让不同需求的游客都能找到适合自己的理解深度，从“路过”变“懂得”",
            "data": f"负向情感占比: {negative_ratio:.1%}",
        })

    # 4. 多元兴趣的平衡艺术
    if concentration < 0.2:
        recs.append({
            "focus_label": "diverse_interests",
            "focus_label_zh": "🎨 多元兴趣的平衡艺术",
            "priority": "🟢 持续改进",
            "insight": "游客兴趣像彩虹一样多元，这是宝藏也是挑战",
            "suggestion": "不追求“一网打尽”，而是设计「主题入口」：建筑爱好者走东门、摄影爱好者走南门、亲子家庭走西门",
            "benefit": "让不同游客从进门那一刻就感到“这是为我设计的”，提升专属感",
            "data": f"兴趣集中度: {concentration:.2f}（分散度较高）",
        })

    return recs


def build_priority_notes(
    engagement_by_note: dict[str, dict],
    dominant_label_by_note: dict[str, str],
    sentiment_rows: list[dict],
) -> list[dict]:
    sentiment_map = {str(row.get("note_id") or "").strip(): row for row in sentiment_rows}
    ranked = sorted(engagement_by_note.items(), key=lambda item: item[1]["engagement_score"], reverse=True)
    output: list[dict] = []
    for note_id, engagement in ranked[:5]:
        sentiment = sentiment_map.get(note_id, {})
        output.append(
            {
                "note_id": note_id,
                "engagement_score": engagement["engagement_score"],
                "dominant_interest_label": dominant_label_by_note.get(note_id, "unknown"),
                "sentiment_label": sentiment.get("sentiment_label", "unknown"),
                "sentiment_score": sentiment.get("sentiment_score", 0.0),
            }
        )
    return output


def save_markdown_report(payload: dict) -> Path:
    """生成人性化的中文Markdown报告"""
    sentiment = payload['sentiment_summary']
    visual = payload['visual_interest']

    lines = [
        "# 🏛️ 游客体验洞察与优化建议",
        "",
        "> 💡 **报告核心观点**：数据背后是一个个真实的游客，我们的目标是让每一次游览都成为值得回忆的体验。",
        "",
        "---",
        "",
        "## 📊 数据洞察",
        "",
        "### 游客情感画像",
        f"- **整体氛围**：{sentiment.get('distribution_zh', {})}",
        f"- **情感基调**：平均得分 {sentiment.get('average_score', 0):.2f}，正向指数 {sentiment.get('positive_index', 0):.1%}",
        f"- **情感稳定性**：{sentiment.get('average_volatility', 0):.2f}（{'波动较大，需关注体验一致性' if sentiment.get('average_volatility', 0) > 1.5 else '相对稳定'}）",
        "",
        "### 游客兴趣热点",
        f"- **兴趣集中度**：{visual.get('interest_concentration', 0):.2f}（{'兴趣多元，需差异化服务' if visual.get('interest_concentration', 0) < 0.2 else '兴趣聚焦，可重点打造'}）",
        f"- **分析样本**：{visual.get('total_predictions', 0)} 张游客照片",
        "",
        "**热度排行榜**：",
    ]

    for i, item in enumerate(visual.get('top_labels', []), 1):
        lines.append(f"{i}. **{item['label_zh']}** — 热度 {item['heat_score']:.1f} | {item['count']} 次关注 | 置信度 {item['avg_confidence']:.0%}")

    lines.extend([
        "",
        "---",
        "",
        "## 🎯 路线优化建议",
        "",
        "> 让动线设计顺应游客本能，而非挑战人性",
        "",
    ])

    for item in payload["route_recommendations"]:
        lines.append(f"### {item['theme']}")
        lines.append(f"**优先级**：{item['priority']}")
        lines.append(f"")
        lines.append(f"**🔍 洞察**：{item['insight']}")
        lines.append(f"")
        lines.append(f"**💡 建议**：{item['suggestion']}")
        lines.append(f"")
        lines.append(f"**✅ 价值**：{item['benefit']}")
        if 'data' in item:
            lines.append(f"")
            lines.append(f"**📈 数据**：{item['data']}")
        lines.append(["", "---", ""])

    lines.extend([
        "",
        "## 🏺 文化展示建议",
        "",
        "> 让文物会说话，让历史有温度",
        "",
    ])

    for item in payload["culture_recommendations"]:
        lines.append(f"### {item['focus_label_zh']}")
        lines.append(f"**优先级**：{item['priority']}")
        lines.append(f"")
        lines.append(f"**🔍 洞察**：{item['insight']}")
        lines.append(f"")
        lines.append(f"**💡 建议**：{item['suggestion']}")
        lines.append(f"")
        lines.append(f"**✅ 价值**：{item['benefit']}")
        lines.append(f"")
        lines.append(f"**📈 数据**：{item['data']}")
        lines.append(["", "---", ""])

    lines.extend([
        "",
        "## ⭐ 重点关注样本",
        "",
        "> 这些笔记互动量高，代表了游客的典型声音",
        "",
    ])

    for item in payload["priority_notes"]:
        sentiment_label_zh = {"positive": "😊 正向", "negative": "😞 负向", "neutral": "😐 中性"}.get(
            item['sentiment_label'], item['sentiment_label']
        )
        lines.append(
            f"- **笔记 {item['note_id']}** | 互动得分 {item['engagement_score']} | "
            f"关注「{item['dominant_interest_label']}」| 情感 {sentiment_label_zh}"
        )

    lines.extend([
        "",
        "---",
        "",
        "*报告生成时间：自动生成于数据分析完成后*",
        "",
        "*💬 反馈与建议：如需调整分析维度或建议方向，请联系产品团队*",
    ])

    output_path = REPORTS_DIR / "management_recommendations.md"
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return output_path


def generate_management_recommendations() -> dict:
    ensure_project_dirs()
    sentiment_rows = try_load(REPORTS_DIR / "note_text_sentiment.json", [])
    sentiment_summary = try_load(REPORTS_DIR / "note_text_sentiment_summary.json", {})
    predictions = try_load(REPORTS_DIR / "vlm_interest_predictions.json", [])
    engagement_by_note = build_note_engagement()

    visual_interest = summarize_visual_interest(predictions)
    sentiment_info = summarize_sentiment(sentiment_rows, sentiment_summary)
    route_recommendations = build_route_recommendations(visual_interest, sentiment_info)
    culture_recommendations = build_culture_recommendations(visual_interest, sentiment_info)
    priority_notes = build_priority_notes(
        engagement_by_note,
        visual_interest.get("dominant_label_by_note", {}),
        sentiment_rows,
    )

    payload = {
        "sentiment_summary": sentiment_info,
        "visual_interest": visual_interest,
        "route_recommendations": route_recommendations,
        "culture_recommendations": culture_recommendations,
        "priority_notes": priority_notes,
        "data_quality": {
            "sentiment_note_count": len(sentiment_rows),
            "vlm_prediction_count": len(predictions),
            "note_engagement_count": len(engagement_by_note),
        },
    }
    dump_json(REPORTS_DIR / "management_recommendations.json", payload)
    markdown_path = save_markdown_report(payload)
    payload["markdown_report_path"] = str(markdown_path)
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate digital recommendations for route optimization and cultural interpretation."
    )
    return parser.parse_args()


def main() -> None:
    parse_args()
    payload = generate_management_recommendations()
    print(
        "saved management recommendations -> "
        f"{REPORTS_DIR / 'management_recommendations.json'} and {payload['markdown_report_path']}"
    )


if __name__ == "__main__":
    main()
