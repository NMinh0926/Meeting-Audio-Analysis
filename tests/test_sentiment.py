"""Tests for sentiment classification service."""
import pytest
from unittest.mock import MagicMock

from app.services.sentiment import predict_sentiment

@pytest.fixture
def mock_sentiment_pipeline(monkeypatch):
    def mock_classifier(text, **kwargs):
        if "tuyệt vời" in text.lower():
            return [{"label": "positive", "score": 0.95}]
        elif "tệ" in text.lower():
            return [{"label": "negative", "score": 0.88}]
        elif "thông báo" in text.lower():
            return [{"label": "neutral", "score": 0.75}]
        else:
            return [{"label": "neutral", "score": 0.50}]
            
    monkeypatch.setattr("app.services.sentiment.get_sentiment_pipeline", lambda: mock_classifier)

def test_predict_sentiment_positive(mock_sentiment_pipeline):
    res = predict_sentiment("Dự án này rất tuyệt vời")
    assert res.sentiment == "happy"
    assert res.confidence == 0.95

def test_predict_sentiment_negative(mock_sentiment_pipeline):
    res = predict_sentiment("Chất lượng quá tệ")
    assert res.sentiment == "angry"
    assert res.confidence == 0.88

def test_predict_sentiment_neutral(mock_sentiment_pipeline):
    res = predict_sentiment("Tôi xin thông báo lịch họp")
    assert res.sentiment == "neutral"
    assert res.confidence == 0.75

def test_predict_sentiment_empty(mock_sentiment_pipeline):
    res = predict_sentiment("   ")
    assert res.sentiment == "neutral"
    assert res.confidence == 1.0

def test_predict_sentiment_model_fail(monkeypatch):
    def mock_fail(*args, **kwargs):
        raise RuntimeError("Model fail")
    monkeypatch.setattr("app.services.sentiment.get_sentiment_pipeline", lambda: mock_fail)
    
    res = predict_sentiment("Test fail")
    assert res.sentiment == "unknown"
    assert res.confidence == 0.0

