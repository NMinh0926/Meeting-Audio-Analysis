"""Sentiment classification service."""
from typing import Any
import logging

from app.core.config import get_settings
from app.models.schemas import SentimentResult

logger = logging.getLogger(__name__)

# Global model instance
_sentiment_pipeline: Any = None

def get_sentiment_pipeline() -> Any:
    global _sentiment_pipeline
    if _sentiment_pipeline is None:
        settings = get_settings()
        try:
            from transformers import pipeline
            _sentiment_pipeline = pipeline(
                "text-classification",
                model=settings.SENTIMENT_MODEL,
                device=-1
            )
        except Exception as e:
            logger.error(f"Failed to load sentiment model: {e}")
            raise
    return _sentiment_pipeline

# Explicit mapping
LABEL_MAPPING = {
    "positive": "happy",
    "negative": "angry",
    "neutral": "neutral"
}

def predict_sentiment(text: str) -> SentimentResult:
    """Predicts sentiment for a given text.
    
    Maps model output to target labels: happy, angry, neutral.
    """
    text = text.strip()
    if not text:
        return SentimentResult(sentiment="neutral", confidence=1.0)
        
    try:
        classifier = get_sentiment_pipeline()
        
        # Max length for distilbert is usually 512 tokens. 
        # We can truncate string to avoid error if it's too long.
        # Just passing it to pipeline with truncation=True
        preds = classifier(text, truncation=True, max_length=512)
        
        # Output format: [{'label': 'positive', 'score': 0.9}]
        label = preds[0]['label'].lower()
        score = preds[0]['score']
        
        target_label = LABEL_MAPPING.get(label, "neutral")
        return SentimentResult(sentiment=target_label, confidence=round(score, 4))
        
    except Exception as e:
        logger.warning(f"Sentiment classification failed for text '{text}': {e}")
        return SentimentResult(sentiment="unknown", confidence=0.0)

