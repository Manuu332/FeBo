"""Financial sentiment analysis using FinBERT."""

from typing import Dict, List
try:
    from transformers import AutoTokenizer, AutoModelForSequenceClassification
    import torch
except ImportError:
    torch = None
    AutoTokenizer = None

from core.logging_config import get_logger

logger = get_logger("finance.sentiment")


class FinSentiment:
    """Financial sentiment analyzer using FinBERT model."""

    def __init__(self) -> None:
        """Initialize sentiment analyzer."""
        try:
            if not torch or not AutoTokenizer:
                logger.warning("Transformers not available, sentiment analysis disabled")
                self.model = None
                self.tokenizer = None
                return

            self.model_name = "ProsusAI/finbert"
            self.tokenizer = AutoTokenizer.from_pretrained(self.model_name)
            self.model = AutoModelForSequenceClassification.from_pretrained(self.model_name)
            self.labels = ["positive", "negative", "neutral"]
            logger.info("FinSentiment initialized")
        except Exception as e:
            logger.warning(f"Failed to initialize FinSentiment: {e}. Sentiment analysis disabled.")
            self.model = None
            self.tokenizer = None

    def analyze(self, text: str) -> Dict[str, float]:
        """
        Analyze financial sentiment of text.

        Args:
            text: Text to analyze

        Returns:
            Dictionary with sentiment scores
        """
        try:
            if not self.model or not self.tokenizer:
                logger.debug("Sentiment analysis not available")
                return {"positive": 0.33, "negative": 0.33, "neutral": 0.34}

            inputs = self.tokenizer(text, return_tensors="pt", truncation=True, max_length=512)
            with torch.no_grad():
                outputs = self.model(**inputs)
                probs = torch.nn.functional.softmax(outputs.logits, dim=-1)

            scores = {self.labels[i]: probs[0][i].item() for i in range(3)}
            logger.debug(f"Sentiment analyzed: {scores}")
            return scores
        except Exception as e:
            logger.error(f"Error in sentiment analysis: {e}")
            return {"positive": 0.33, "negative": 0.33, "neutral": 0.34}


# Global sentiment analyzer
try:
    fin_sentiment = FinSentiment()
except Exception as e:
    logger.warning(f"Failed to initialize global fin_sentiment: {e}")
    fin_sentiment = None

