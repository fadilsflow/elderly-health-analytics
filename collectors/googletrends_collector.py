"""
Google Trends Collector — via pytrends library.

Mengumpulkan data popularitas pencarian keyword seputar lansia
di Google Trends untuk Indonesia.

Tidak memerlukan API key.
Data yang dikumpulkan:
- Interest over time (5 tahun terakhir, granularity bulanan)
- Interest by region (34 provinsi Indonesia)

Library: pytrends (unofficial Google Trends API wrapper)

Catatan: Google Trends sering rate-limit. Collector ini menggunakan
retry dengan backoff untuk menangani 429 response.
"""

import time
from datetime import datetime
from typing import Dict, List

import pandas as pd
from pytrends.request import TrendReq

from collectors.base import BaseCollector


# =============================================================================
# Konfigurasi
# =============================================================================

# Keywords target — maksimal 5 keyword dalam 1 request (batasan Google Trends)
# Lebih dari 5 akan di-split otomatis
KEYWORDS = [
    "lansia",
    "perawatan lansia",
    "kesehatan lansia",
    "senam lansia",
    "posyandu lansia",
]

REQUEST_DELAY = 3
MAX_RETRIES = 1


# =============================================================================
# Collector Class
# =============================================================================

class GoogleTrendsCollector(BaseCollector):
    """
    Collector untuk Google Trends menggunakan pytrends.

    Flow:
    1. Koneksi ke Google Trends (pytrends.TrendReq)
    2. Build payload dengan KEYWORDS, timeframe 5 tahun, geo=ID
    3. Fetch interest_over_time() — time series bulanan
    4. Fetch interest_by_region() — per provinsi
    5. Transform DataFrame ke list of dict untuk normalisasi
    """

    def __init__(self, output_dir: str = "output"):
        super().__init__(name="Google Trends", output_dir=output_dir)
        # hl=en-US tz=360 untuk akses dari luar Indonesia — lebih stabil
        self.pytrends = TrendReq(
            hl="en-US",
            tz=360,
            timeout=(15, 30),
            retries=1,
            backoff_factor=1,
        )

    def fetch(self) -> List[Dict]:
        """
        Ambil data Google Trends — single request dengan max 5 keyword.

        Strategi: 1 request untuk menghindari rate limit Google.
        Google Trends API membatasi ~5 keyword per request.

        Returns:
            List[Dict]: Data mentah dengan type 'time_series' atau 'region'
        """
        raw_records = []
        timeframe = "today 5-y"

        # Filter keyword yang sudah digunakan
        keywords = KEYWORDS[:5]  # Max 5 keyword per request
        self.logger.info(f"Keyword ({len(keywords)}): {', '.join(keywords)}")

        for attempt in range(MAX_RETRIES + 1):
            if attempt > 0:
                wait = REQUEST_DELAY * 3
                self.logger.info(f"Retry {attempt}... menunggu {wait}s")
                time.sleep(wait)

            try:
                self.pytrends.build_payload(
                    kw_list=keywords,
                    cat=0,
                    timeframe=timeframe,
                    geo="ID",
                    gprop="",
                )

                # --- Interest Over Time ---
                interest_time = self.pytrends.interest_over_time()
                if not interest_time.empty:
                    if "isPartial" in interest_time.columns:
                        interest_time = interest_time.drop(columns=["isPartial"])

                    for timestamp, row in interest_time.iterrows():
                        for kw in keywords:
                            if kw in row and row[kw] > 0:
                                raw_records.append({
                                    "_type": "time_series",
                                    "_keyword": kw,
                                    "_value": float(row[kw]),
                                    "_timestamp": timestamp.strftime("%Y-%m-%d"),
                                })
                    self.logger.info(
                        f"  -> ~{len(interest_time) * len(keywords)} record time series"
                    )

                # --- Interest by Region (hanya jika time series berhasil) ---
                if raw_records:
                    time.sleep(2)

                    self.pytrends.build_payload(
                        kw_list=keywords,
                        cat=0,
                        timeframe=timeframe,
                        geo="ID",
                        gprop="",
                    )

                    interest_region = self.pytrends.interest_by_region(
                        resolution="REGION",
                        inc_low_vol=True,
                        inc_geo_code=True,
                    )

                    if not interest_region.empty:
                        for region_name, row in interest_region.iterrows():
                            for kw in keywords:
                                if kw in row and row[kw] > 0:
                                    raw_records.append({
                                        "_type": "region",
                                        "_keyword": kw,
                                        "_value": float(row[kw]),
                                        "_region": region_name,
                                        "_timestamp": datetime.now().strftime("%Y-%m-%d"),
                                    })
                        count = len(interest_region) * len(keywords)
                        self.logger.info(f"  -> ~{count} record region")

                break  # Berhasil

            except Exception as e:
                err_msg = str(e)
                if "429" in err_msg or "rate" in err_msg.lower():
                    self.logger.warning(f"Rate limited (attempt {attempt + 1})")
                else:
                    self.logger.error(f"Gagal: {e}")
                    break  # Non-429 error, jangan retry

        if not raw_records:
            raise RuntimeError(
                "Google Trends rate-limited. "
                "Tunggu 5-10 menit lalu coba lagi, atau gunakan VPN."
            )

        return raw_records

    def normalize(self, raw_data: List[Dict]) -> List[Dict]:
        """
        Normalisasi data Google Trends ke schema standar.
        """
        normalized = []

        for record in raw_data:
            try:
                data_type = record.get("_type", "unknown")
                keyword = record.get("_keyword", "")
                value = record.get("_value", 0)
                timestamp = record.get("_timestamp", "")
                region = record.get("_region", "Indonesia")

                normalized.append(
                    self.normalizer.normalize_record(
                        source="Google Trends",
                        category=keyword,
                        value=value,
                        year=None,
                        age_group=None,
                        country=region,
                        sex=None,
                        unit="interest_score",
                        indicator_code=None,
                        notes=f"Google Trends — {data_type}",
                    )
                )
            except Exception as e:
                self.logger.error(f"Error normalisasi record Google Trends: {e}")
                continue

        return normalized
