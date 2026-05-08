"""
Sentiment Analyzer — analisis sentimen teks.

Menggunakan dua pendekatan untuk hasil yang lebih robust:

1. VADER (Valence Aware Dictionary and sEntiment Reasoner)
   - Rule-based, dioptimasi untuk teks sosmed / pendek
   - Output: compound score (-1 sampai +1)

2. TextBlob
   - ML-based, bagus untuk teks lebih panjang
   - Output: polarity (-1 sampai +1) + subjectivity

Combined: rata-rata dari compound VADER + polarity TextBlob.
"""

from typing import Tuple

from textblob import TextBlob
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer


class SentimentAnalyzer:
    """
    Analisis sentimen teks menggunakan VADER + TextBlob.

    Penggunaan:
        analyzer = SentimentAnalyzer()
        label, score = analyzer.analyze("Lansia perlu perawatan khusus")
        # label = "positive", score = 0.45
    """

    def __init__(self):
        """Inisialisasi kedua sentiment engine."""
        self.vader = SentimentIntensityAnalyzer()

    def analyze(self, text: str) -> Tuple[str, float]:
        """
        Analisis sentimen teks.

        Args:
            text: Teks yang akan dianalisis

        Returns:
            Tuple[str, float]: (label, score)
            label: "positive", "negative", atau "neutral"
            score: float dari -1 (negatif) sampai +1 (positif)
        """
        if not text or not text.strip():
            return "neutral", 0.0

        # VADER — compound score
        vader_scores = self.vader.polarity_scores(str(text))
        vader_compound = vader_scores["compound"]

        # TextBlob — polarity
        try:
            blob = TextBlob(str(text))
            blob_polarity = blob.sentiment.polarity
        except Exception:
            blob_polarity = 0.0

        # Combined score: rata-rata
        combined = (vader_compound + blob_polarity) / 2.0

        # Label
        if combined > 0.05:
            label = "positive"
        elif combined < -0.05:
            label = "negative"
        else:
            label = "neutral"

        return label, round(combined, 4)
