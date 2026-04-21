"""
基于 SVM 的情感分析模型
===================
技术亮点:
- 使用 TF-IDF + SVM 进行文本分类
- 支持中文分词 (jieba)
- 包含完整的训练、评估、保存/加载流程
- 可解释性强，适合古建筑评论分析
"""

from __future__ import annotations

import json
import pickle
from pathlib import Path
from typing import Any

import jieba
import numpy as np
from loguru import logger
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.model_selection import GridSearchCV, train_test_split
from sklearn.svm import SVC
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
)

from app.models.schemas import ModelMetrics, SentimentLabel, SentimentResult


class TextPreprocessor:
    """文本预处理器."""
    
    @staticmethod
    def tokenize(text: str) -> str:
        """中文分词."""
        if not text:
            return ""
        # 使用 jieba 分词
        words = jieba.cut(text.strip())
        # 过滤停用词和短词
        stopwords = {"的", "了", "在", "是", "我", "有", "和", "就", "不", "人", "都", "一", "一个", "上", "也", "很", "到", "说", "要", "去", "你", "会", "着", "没有", "看", "好", "自己", "这"}
        filtered = [w for w in words if len(w) > 1 and w not in stopwords]
        return " ".join(filtered)


class SVMTrainer:
    """SVM 情感分析模型训练器."""
    
    def __init__(self, model_dir: Path = Path("models")) -> None:
        self.model_dir = model_dir
        self.model_dir.mkdir(parents=True, exist_ok=True)
        
        self.vectorizer: TfidfVectorizer | None = None
        self.model: SVC | None = None
        self.preprocessor = TextPreprocessor()
        
    def prepare_data(
        self,
        texts: list[str],
        labels: list[str],
        test_size: float = 0.2,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """准备训练数据."""
        logger.info(f"Preparing data: {len(texts)} samples")
        
        # 分词处理
        processed_texts = [self.preprocessor.tokenize(t) for t in texts]
        
        # 划分训练集和测试集
        X_train, X_test, y_train, y_test = train_test_split(
            processed_texts, labels, test_size=test_size, random_state=42, stratify=labels
        )
        
        # TF-IDF 向量化
        self.vectorizer = TfidfVectorizer(
            max_features=10000,
            ngram_range=(1, 2),
            min_df=2,
            max_df=0.95,
        )
        X_train_vec = self.vectorizer.fit_transform(X_train)
        X_test_vec = self.vectorizer.transform(X_test)
        
        logger.info(f"Train: {X_train_vec.shape}, Test: {X_test_vec.shape}")
        return X_train_vec, X_test_vec, np.array(y_train), np.array(y_test)
    
    def train(
        self,
        X_train: np.ndarray,
        y_train: np.ndarray,
        tune_hyperparams: bool = True,
    ) -> SVC:
        """训练 SVM 模型."""
        logger.info("Training SVM model...")
        
        if tune_hyperparams:
            # 超参数调优
            param_grid = {
                "C": [0.1, 1, 10],
                "kernel": ["linear", "rbf"],
                "gamma": ["scale", "auto"],
            }
            grid_search = GridSearchCV(
                SVC(probability=True, random_state=42),
                param_grid,
                cv=5,
                scoring="f1_weighted",
                n_jobs=-1,
            )
            grid_search.fit(X_train, y_train)
            self.model = grid_search.best_estimator_
            logger.info(f"Best params: {grid_search.best_params_}")
        else:
            self.model = SVC(
                kernel="linear",
                C=1.0,
                probability=True,
                random_state=42,
            )
            self.model.fit(X_train, y_train)
        
        logger.info("Training completed")
        return self.model
    
    def evaluate(
        self,
        X_test: np.ndarray,
        y_test: np.ndarray,
    ) -> ModelMetrics:
        """评估模型性能."""
        if self.model is None:
            raise ValueError("Model not trained")
        
        y_pred = self.model.predict(X_test)
        
        metrics = ModelMetrics(
            model_name="SVM_Sentiment",
            model_type="SVM",
            accuracy=accuracy_score(y_test, y_pred),
            precision=precision_score(y_test, y_pred, average="weighted", zero_division=0),
            recall=recall_score(y_test, y_pred, average="weighted", zero_division=0),
            f1_score=f1_score(y_test, y_pred, average="weighted", zero_division=0),
            training_samples=len(y_test) * 4,  # 近似
            validation_samples=len(y_test),
        )
        
        logger.info(f"\nClassification Report:\n{classification_report(y_test, y_pred)}")
        return metrics
    
    def save(self, path: Path | None = None) -> Path:
        """保存模型."""
        if self.model is None or self.vectorizer is None:
            raise ValueError("Model not trained")
        
        save_path = path or self.model_dir / "svm_sentiment.pkl"
        save_path.parent.mkdir(parents=True, exist_ok=True)
        
        model_data = {
            "model": self.model,
            "vectorizer": self.vectorizer,
            "preprocessor": self.preprocessor,
        }
        
        with open(save_path, "wb") as f:
            pickle.dump(model_data, f)
        
        # 保存模型信息
        info_path = save_path.with_suffix(".json")
        model_info = {
            "model_type": "SVM",
            "vectorizer": "TF-IDF",
            "features": self.vectorizer.get_feature_names_out().tolist()[:100],
            "n_features": len(self.vectorizer.get_feature_names_out()),
        }
        with open(info_path, "w", encoding="utf-8") as f:
            json.dump(model_info, f, ensure_ascii=False, indent=2)
        
        logger.info(f"Model saved to {save_path}")
        return save_path
    
    def load(self, path: Path) -> None:
        """加载模型."""
        with open(path, "rb") as f:
            model_data = pickle.load(f)
        
        self.model = model_data["model"]
        self.vectorizer = model_data["vectorizer"]
        self.preprocessor = model_data.get("preprocessor", TextPreprocessor())
        
        logger.info(f"Model loaded from {path}")


class SVMSentimentAnalyzer:
    """SVM 情感分析器 - 用于生产环境."""
    
    def __init__(self, model_path: Path | None = None) -> None:
        self.model_path = model_path or Path("models/svm_sentiment.pkl")
        self.trainer = SVMTrainer()
        self._load_model()
    
    def _load_model(self) -> None:
        """加载预训练模型."""
        if self.model_path.exists():
            self.trainer.load(self.model_path)
            logger.info("SVM model loaded")
        else:
            logger.warning(f"Model not found at {self.model_path}, using fallback")
            self.trainer.model = None
    
    def analyze(self, text: str) -> SentimentResult:
        """分析文本情感."""
        if self.trainer.model is None or self.trainer.vectorizer is None:
            # 回退到简单规则
            return self._fallback_analyze(text)
        
        # 预处理
        processed = self.trainer.preprocessor.tokenize(text)
        X = self.trainer.vectorizer.transform([processed])
        
        # 预测
        prediction = self.trainer.model.predict(X)[0]
        probabilities = self.trainer.model.predict_proba(X)[0]
        confidence = max(probabilities)
        
        # 计算情感分数 (-1 到 1)
        label_to_score = {
            "positive": 0.7,
            "neutral": 0.0,
            "negative": -0.7,
        }
        sentiment_score = label_to_score.get(prediction, 0.0)
        
        # 根据置信度调整
        sentiment_score *= confidence
        
        return SentimentResult(
            note_id="",
            sentiment_label=SentimentLabel(prediction),
            sentiment_score=round(sentiment_score, 3),
            confidence=round(confidence, 3),
            features={"tfidf_sum": float(X.sum())},
        )
    
    def _fallback_analyze(self, text: str) -> SentimentResult:
        """简单的规则回退."""
        positive_words = ["好", "美", "棒", "喜欢", "推荐", "值得", "精彩", "漂亮"]
        negative_words = ["差", "烂", "失望", "不好", "坑", "贵", "挤", "脏"]
        
        pos_count = sum(1 for w in positive_words if w in text)
        neg_count = sum(1 for w in negative_words if w in text)
        
        if pos_count > neg_count:
            label = SentimentLabel.POSITIVE
            score = 0.5
        elif neg_count > pos_count:
            label = SentimentLabel.NEGATIVE
            score = -0.5
        else:
            label = SentimentLabel.NEUTRAL
            score = 0.0
        
        return SentimentResult(
            note_id="",
            sentiment_label=label,
            sentiment_score=score,
            confidence=0.5,
            features={"fallback": True},
        )
    
    def batch_analyze(self, texts: list[tuple[str, str]]) -> list[SentimentResult]:
        """批量分析."""
        results = []
        for note_id, text in texts:
            result = self.analyze(text)
            result.note_id = note_id
            results.append(result)
        return results


def load_data_from_json(data_path: Path | None = None) -> tuple[list[str], list[str]]:
    """从 data/ 目录加载训练数据.
    
    优先加载 training_sentiment.json，如果不存在则加载 notes.json
    """
    data_dir = data_path or Path("data")
    
    # 优先使用专门的训练数据
    train_file = data_dir / "training_sentiment.json"
    if train_file.exists():
        logger.info(f"Loading training data from {train_file}")
        with open(train_file, "r", encoding="utf-8") as f:
            notes = json.load(f)
    else:
        # 回退到 notes.json
        notes_file = data_dir / "notes.json"
        if notes_file.exists():
            logger.info(f"Loading data from {notes_file}")
            with open(notes_file, "r", encoding="utf-8") as f:
                notes = json.load(f)
        else:
            logger.warning("No data file found, using sample data")
            return generate_sample_data()
    
    texts = []
    labels = []
    
    for note in notes:
        content = note.get("content", "")
        label = note.get("sentiment_label", "neutral")
        
        if content and label:
            texts.append(content)
            labels.append(label)
    
    logger.info(f"Loaded {len(texts)} samples from data files")
    logger.info(f"  Positive: {labels.count('positive')}")
    logger.info(f"  Neutral: {labels.count('neutral')}")
    logger.info(f"  Negative: {labels.count('negative')}")
    
    return texts, labels


def generate_sample_data() -> tuple[list[str], list[str]]:
    """生成示例训练数据（当没有数据文件时使用）."""
    logger.info("Using sample data for training")
    
    # 正面评价
    positive_samples = [
        "这座古建筑真是太美了，雕梁画栋，气势恢宏！",
        "强烈推荐来这里，历史文化底蕴深厚",
        "园林景观设计精巧，植物配置很有讲究",
        "牌匾书法苍劲有力，值得细细品味",
        "建筑细节处理得非常精致，古人的智慧令人叹服",
        "这里拍照特别出片，每个角落都是风景",
        "导游讲解很专业，学到了很多历史知识",
        "保护得很好，能感受到浓厚的历史氛围",
        "庭院深深，一步一景，美不胜收",
        "古香古色，仿佛穿越回了古代",
    ]
    
    # 中性评价
    neutral_samples = [
        "建筑规模中等，适合半天游览",
        "这里是一个普通的古建筑景点",
        "游客数量适中，不算太拥挤",
        "门票价格一般，性价比还可以",
        "交通还算方便，有公交车直达",
        "建筑年代比较久远，保存状况一般",
        "是一个了解当地历史的地方",
        "景色还可以，没有特别惊艳",
        "适合带老人孩子来散步",
        "周末人比较多，平时还可以",
    ]
    
    # 负面评价
    negative_samples = [
        "人太多了，完全没法好好看",
        "门票太贵，不值得这个价",
        "商业化太严重，失去了古韵",
        "管理混乱，到处都在施工",
        "讲解服务太差，导游态度不好",
        "建筑维护不到位，有些破败",
        "停车非常困难，周边交通拥堵",
        "卫生条件差，厕所很脏",
        "被坑了，实物和宣传差距很大",
        "排队时间太长，体验很差",
    ]
    
    texts = positive_samples + neutral_samples + negative_samples
    labels = (
        ["positive"] * len(positive_samples) +
        ["neutral"] * len(neutral_samples) +
        ["negative"] * len(negative_samples)
    )
    
    return texts, labels


def main() -> None:
    """训练模型（使用 data/ 目录数据）."""
    logger.info("Starting SVM model training...")
    
    # 从 data/ 目录加载数据
    texts, labels = load_data_from_json()
    
    # 训练
    trainer = SVMTrainer()
    X_train, X_test, y_train, y_test = trainer.prepare_data(texts, labels)
    trainer.train(X_train, y_train, tune_hyperparams=True)
    
    # 评估
    metrics = trainer.evaluate(X_test, y_test)
    logger.info(f"Model metrics: {metrics.model_dump()}")
    
    # 保存
    trainer.save()
    
    # 测试
    analyzer = SVMSentimentAnalyzer()
    test_text = "这座古建筑真是太美了，强烈推荐！"
    result = analyzer.analyze(test_text)
    logger.info(f"Test: '{test_text}' -> {result.sentiment_label.value} ({result.confidence:.2f})")


if __name__ == "__main__":
    main()
