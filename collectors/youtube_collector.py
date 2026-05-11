"""
YouTube Data API v3 Collector.

Mengumpulkan data video YouTube terkait topik lansia.

Data yang dikumpulkan:
- Video ID, title, channel, views, likes, comments, publish date
- Top 50 video per keyword

Requirements:
- YOUTUBE_API_KEY dari .env
- Google Cloud Console → YouTube Data API v3 (gratis, quota 10k unit/hari)
"""

import os
from typing import Dict, List

from dotenv import load_dotenv
from googleapiclient.discovery import build

from collectors.base import BaseCollector

load_dotenv()


# =============================================================================
# Konfigurasi
# =============================================================================

# Keyword pencarian
SEARCH_QUERIES = [
    "lansia",
    "perawatan lansia",
    "kesehatan lansia",
    "senam lansia",
    "posyandu lansia",
    "demensia lansia",
    "aktivitas lansia",
    "makanan sehat lansia",
]

# Max hasil per keyword (quota: 100 unit per search.list + 1 per video.list)
MAX_RESULTS = 25


# =============================================================================
# Collector Class
# =============================================================================

class YouTubeCollector(BaseCollector):
    """
    Collector untuk YouTube Data API v3.

    Flow:
    1. Auth dengan YOUTUBE_API_KEY dari .env
    2. Search video per keyword (search.list)
    3. Ambil statistics + snippet untuk setiap video (videos.list)
    4. Normalisasi ke schema standar
    """

    def __init__(self, output_dir: str = "output"):
        super().__init__(name="YouTube", output_dir=output_dir)

        api_key = os.getenv("YOUTUBE_API_KEY")
        if not api_key:
            raise RuntimeError(
                "YOUTUBE_API_KEY harus di-set di .env. "
                "Dapatkan gratis di https://console.cloud.google.com/apis/credentials"
            )

        self.youtube = build("youtube", "v3", developerKey=api_key)

    def fetch(self) -> List[Dict]:
        """
        Search video YouTube untuk setiap keyword.

        Returns:
            List[Dict]: Data mentah video YouTube
        """
        raw_records = []
        video_ids_seen = set()

        for query in SEARCH_QUERIES:
            self.logger.info(f"Mencari video: '{query}'")

            try:
                # Step 1: Search video
                search_response = self.youtube.search().list(
                    q=query,
                    type="video",
                    part="id",
                    maxResults=MAX_RESULTS,
                    relevanceLanguage="id",
                    regionCode="ID",
                ).execute()

                ids = [
                    item["id"]["videoId"]
                    for item in search_response.get("items", [])
                    if item["id"]["videoId"] not in video_ids_seen
                ]

                if not ids:
                    self.logger.info(f"  -> Tidak ada hasil untuk '{query}'")
                    continue

                for vid in ids:
                    video_ids_seen.add(vid)

                # Step 2: Ambil detail video (statistics + snippet)
                vid_response = self.youtube.videos().list(
                    id=",".join(ids),
                    part="statistics,snippet",
                ).execute()

                for item in vid_response.get("items", []):
                    snippet = item.get("snippet", {})
                    stats = item.get("statistics", {})

                    raw_records.append({
                        "_query": query,
                        "_video_id": item["id"],
                        "_title": snippet.get("title", ""),
                        "_channel": snippet.get("channelTitle", ""),
                        "_published_at": snippet.get("publishedAt", ""),
                        "_views": int(stats.get("viewCount", 0)),
                        "_likes": int(stats.get("likeCount", 0)),
                        "_comments": int(stats.get("commentCount", 0)),
                        "_description": snippet.get("description", "")[:300],
                    })

                self.logger.info(f"  -> {len(ids)} video dari '{query}'")

            except Exception as e:
                self.logger.error(f"  -> Gagal fetch '{query}': {e}")
                continue

        self.logger.info(f"Total {len(raw_records)} video YouTube ditemukan")

        if not raw_records:
            raise RuntimeError(
                "Tidak ada video YouTube ditemukan. "
                "Periksa YOUTUBE_API_KEY di .env."
            )

        return raw_records

    def normalize(self, raw_data: List[Dict]) -> List[Dict]:
        """
        Normalisasi data YouTube ke schema standar.
        """
        from utils.sentiment import SentimentAnalyzer
        sentiment = SentimentAnalyzer()

        normalized = []

        for record in raw_data:
            try:
                title = record.get("_title", "")
                views = record.get("_views", 0)
                likes = record.get("_likes", 0)
                comments = record.get("_comments", 0)
                published = record.get("_published_at", "")

                # Sentimen pada title
                sent_label, sent_score = sentiment.analyze(title)

                # Engagement score
                engagement = views + (likes * 2) + (comments * 5)

                # Parse publish date
                if published:
                    ts = published[:10]
                else:
                    ts = None

                normalized.append(
                    self.normalizer.normalize_record(
                        source="YouTube",
                        keyword=record.get("_query", ""),
                        value=float(engagement),
                        timestamp=published[:10] if published else None,
                        region="Indonesia",
                        platform="youtube",
                        metric="engagement_score",
                        sentiment=sent_label,
                        sentiment_score=sent_score,
                        notes=f"YouTube {record.get('_channel', '')} — Sentimen: {sent_label} ({sent_score:+.2f}) | {title[:100]}",
                        metadata_extra={
                            "video_id": record.get("_video_id"),
                            "channel": record.get("_channel"),
                            "title": title[:200],
                        },
                    )
                )
            except Exception as e:
                self.logger.error(f"Error normalisasi record YouTube: {e}")
                continue

        return normalized
