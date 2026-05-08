"""
Data normalizer — mengubah data dari berbagai format sumber
menjadi schema standar untuk output JSON.

Schema standar (v2 — Digital Media Analytics):
{
    "source": str,
    "keyword": str | None,
    "platform": str | None,
    "value": float,
    "metric": str,
    "timestamp": str | None (ISO date),
    "region": str | None,
    "sentiment": str | None (positive | negative | neutral),
    "sentiment_score": float | None,
    "metadata": {
        "fetched_at": str (ISO 8601),
        "notes": str | None,
    }
}
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


class Normalizer:
    """Normalisasi data dari berbagai sumber ke format seragam."""

    @staticmethod
    def get_timestamp() -> str:
        """Return ISO 8601 timestamp untuk metadata.fetched_at."""
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def normalize_record(
        source: str,
        value: Any,
        keyword: str = None,
        platform: str = None,
        metric: str = None,
        timestamp: str = None,
        region: str = None,
        sentiment: str = None,
        sentiment_score: float = None,
        notes: str = None,
        # Backward compat fields (masih digunakan oleh WHO collector)
        category: str = None,       # deprecated alias untuk keyword
        year: int = None,
        age_group: str = None,
        country: str = "Indonesia",
        sex: str = None,
        unit: str = None,
        indicator_code: str = None,
    ) -> Dict:
        """
        Membuat record normal sesuai schema standar v2.

        Args:
            source: Sumber data (WHO, Google Trends, YouTube, Reddit)
            value: Nilai numerik
            keyword: Keyword/topik yang dicari
            platform: Platform spesifik (web_search, youtube, reddit)
            metric: Jenis metrik (interest_score, engagement_score, percent)
            timestamp: Timestamp data (ISO date string)
            region: Region/negara
            sentiment: Label sentimen (positive, negative, neutral)
            sentiment_score: Skor sentimen numerik (-1 s.d. +1)
            notes: Catatan tambahan
            year: (backward compat) Tahun data
            age_group: (backward compat) Kelompok umur
            country: (backward compat) Negara
            sex: (backward compat) Jenis kelamin
            unit: (backward compat) Satuan nilai
            indicator_code: (backward compat) Kode indikator

        Returns:
            Dict dengan schema standar
        """
        # Build timestamp jika tidak disediakan tapi year ada
        if not timestamp and year:
            timestamp = f"{year}-01-01"

        # Backward compat: category → keyword
        if not keyword and category:
            keyword = category

        record = {
            "source": source,
            "keyword": keyword,
            "platform": platform or source.lower(),
            "value": float(value),
            "metric": metric or unit or "value",
            "timestamp": timestamp,
            "region": region or country,
            "sentiment": sentiment,
            "sentiment_score": sentiment_score,
            "metadata": {
                "fetched_at": Normalizer.get_timestamp(),
                "notes": notes,
            },
        }

        # Backward compat: simpan field tambahan jika disediakan
        if age_group:
            record["age_group"] = age_group
        if sex:
            record["sex"] = sex
        if indicator_code:
            record["metadata"]["indicator_code"] = indicator_code

        return record

    @staticmethod
    def normalize_batch(
        source: str,
        records: List[Dict],
        category_map: Dict[str, str],
    ) -> List[Dict]:
        """
        Normalisasi batch record dari response API.

        Args:
            source: Nama sumber data
            records: List dict data mentah dari API
            category_map: Mapping key API -> nama category standard

        Returns:
            List dict dengan schema standar
        """
        normalized = []
        for record in records:
            for api_key, category in category_map.items():
                if api_key in record and record[api_key] is not None:
                    normalized.append(
                        Normalizer.normalize_record(
                            source=source,
                            value=record[api_key],
                            keyword=category,
                            year=record.get("year") or record.get("TimeDim"),
                            region=record.get("country", "Indonesia"),
                            sex=record.get("sex"),
                        )
                    )
        return normalized
