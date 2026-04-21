"""将 CSV 数据集转换为项目格式."""

import json
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def convert_csv_to_json():
    """转换 ChnSentiCorp CSV 到 notes.json."""
    data_dir = project_root / "data"
    csv_file = data_dir / "ChnSentiCorp_htl_all.csv"
    
    if not csv_file.exists():
        print(f"❌ 找不到文件: {csv_file}")
        print("请确保 data/ChnSentiCorp_htl_all.csv 存在")
        return
    
    print(f"📖 读取 {csv_file}...")
    
    try:
        import pandas as pd
        df = pd.read_csv(csv_file, encoding='utf-8')
    except Exception as e:
        print(f"❌ 读取失败: {e}")
        return
    
    print(f"   共 {len(df)} 条数据")
    
    # 转换为项目格式
    notes = []
    label_map = {0: "negative", 1: "positive"}
    
    for idx, row in df.iterrows():
        text = str(row.get('review', row.get('text', '')))
        label = int(row.get('label', 0))
        
        if text:
            notes.append({
                "id": f"chn_{idx}",
                "title": text[:50] + ("..." if len(text) > 50 else ""),
                "content": text,
                "sentiment_label": label_map.get(label, "neutral"),
                "sentiment_score": 0.0,
                "images": [],
                "source": "ChnSentiCorp",
                "split": "train" if idx < len(df) * 0.8 else "test"
            })
    
    # 保存 notes.json
    output_path = data_dir / "notes.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(notes, f, ensure_ascii=False, indent=2)
    
    print(f"\n✅ 已保存到: {output_path}")
    print(f"   总计: {len(notes)} 条")
    print(f"   正面: {sum(1 for n in notes if n['sentiment_label'] == 'positive')} 条")
    print(f"   负面: {sum(1 for n in notes if n['sentiment_label'] == 'negative')} 条")
    
    # 保存训练集
    train_notes = [n for n in notes if n.get("split") == "train"]
    if train_notes:
        train_path = data_dir / "training_sentiment.json"
        with open(train_path, "w", encoding="utf-8") as f:
            json.dump(train_notes, f, ensure_ascii=False, indent=2)
        print(f"\n💾 训练集已保存到: {train_path}")
    
    print("\n🎉 完成! 现在可以运行:")
    print("   python -m ml.sentiment_svm  # 训练模型")


if __name__ == "__main__":
    convert_csv_to_json()
