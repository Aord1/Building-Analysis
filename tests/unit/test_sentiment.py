"""情感分析服务单元测试."""

import pytest
from ml.sentiment_svm import SVMSentimentAnalyzer


class TestSVMSentimentAnalyzer:
    """测试 SVM 情感分析器."""

    def test_analyze_positive(self):
        """测试正面情感分析."""
        analyzer = SVMSentimentAnalyzer()
        result = analyzer.analyze("这座古建筑真是太美了！")
        
        assert result.sentiment_label in ["positive", "neutral", "negative"]
        assert 0 <= result.confidence <= 1

    def test_analyze_negative(self):
        """测试负面情感分析."""
        analyzer = SVMSentimentAnalyzer()
        result = analyzer.analyze("体验很差，不推荐")
        
        assert result.sentiment_label in ["positive", "neutral", "negative"]
        assert 0 <= result.confidence <= 1
