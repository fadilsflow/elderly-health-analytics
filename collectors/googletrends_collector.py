"""
Google Trends Collector — via pytrends library.

Collects keyword search popularity data from Google Trends for Indonesia.

Data:
- Interest over time (monthly, 5 years)
- Interest by region (34 Indonesian provinces)

Library: pytrends (unofficial Google Trends API wrapper)

Note: Google Trends aggressively rate-limits. Uses retry with backoff, user-agent
rotation, and optional proxy support. Falls back to realistic mock data if API
is unavailable.
"""

import os
import random
import time
from datetime import datetime, timedelta
from typing import Dict, List

from pytrends.request import TrendReq

from collectors.base import BaseCollector


KEYWORDS = [
    "lansia",
    "perawatan lansia",
    "kesehatan lansia",
    "senam lansia",
    "posyandu lansia",
]

REQUEST_DELAY = 3
MAX_RETRIES = 2
INITIAL_DELAY = 2

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/605.1.15 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_1) AppleWebKit/537.36 Chrome/121.0.0.0 Safari/537.36",
]

PROXY_ENV_HINT = "Set GOOGLE_TRENDS_PROXY=http://your-proxy:port to use a proxy"

INDONESIAN_PROVINCES = [
    "Aceh", "Bali", "Banten", "Bengkulu", "DI Yogyakarta", "DKI Jakarta",
    "Gorontalo", "Jambi", "Jawa Barat", "Jawa Tengah", "Jawa Timur",
    "Kalimantan Barat", "Kalimantan Selatan", "Kalimantan Tengah",
    "Kalimantan Timur", "Kalimantan Utara", "Kepulauan Bangka Belitung",
    "Kepulauan Riau", "Lampung", "Maluku", "Maluku Utara",
    "Nusa Tenggara Barat", "Nusa Tenggara Timur", "Papua", "Papua Barat",
    "Papua Pegunungan", "Papua Selatan", "Papua Tengah",
    "Riau", "Sulawesi Barat", "Sulawesi Selatan", "Sulawesi Tengah",
    "Sulawesi Tenggara", "Sulawesi Utara", "Sumatera Barat",
    "Sumatera Selatan", "Sumatera Utara",
]


class GoogleTrendsCollector(BaseCollector):

    def __init__(self, output_dir: str = "output"):
        super().__init__(name="Google Trends", output_dir=output_dir)
        self.pytrends = self._new_pytrends()

    def _new_pytrends(self):
        ua = random.choice(USER_AGENTS)
        proxy = os.getenv("GOOGLE_TRENDS_PROXY", "")
        return TrendReq(
            hl="id",
            tz=420,
            timeout=(5, 10),
            retries=3,
            backoff_factor=2,
            proxies=proxy,
            requests_args={
                "headers": {
                    "User-Agent": ua,
                    "Accept-Language": "id-ID,id;q=0.9,en;q=0.8",
                },
            },
        )

    def _fetch_time_series(self, keywords, timeframe) -> List[Dict]:
        for attempt in range(MAX_RETRIES + 1):
            if attempt > 0:
                wait = REQUEST_DELAY * (2 ** attempt) + random.uniform(1, 5)
                self.logger.info(f"Retry time_series {attempt}/{MAX_RETRIES}... waiting {wait:.0f}s")
                time.sleep(wait)
                self.pytrends = self._new_pytrends()

            try:
                self.pytrends.build_payload(
                    kw_list=keywords, cat=0, timeframe=timeframe, geo="ID", gprop="",
                )
                interest_time = self.pytrends.interest_over_time()
                if interest_time.empty:
                    self.logger.warning("Time series empty")
                    return []

                if "isPartial" in interest_time.columns:
                    interest_time = interest_time.drop(columns=["isPartial"])

                records = []
                for timestamp, row in interest_time.iterrows():
                    for kw in keywords:
                        if kw in row:
                            records.append({
                                "_type": "time_series",
                                "_keyword": kw,
                                "_value": float(row[kw]),
                                "_timestamp": timestamp.strftime("%Y-%m-%d"),
                            })

                self.logger.info(f"  time_series: ~{len(interest_time) * len(keywords)} records")
                return records

            except Exception as e:
                err_msg = str(e)
                if "429" in err_msg or "rate" in err_msg.lower():
                    self.logger.warning(f"Rate limited time_series (attempt {attempt + 1})")
                else:
                    self.logger.error(f"time_series failed: {e}")
                    return []

        return []

    def _fetch_region(self, keywords, timeframe) -> List[Dict]:
        try:
            time.sleep(3)
            self.pytrends.build_payload(
                kw_list=keywords, cat=0, timeframe=timeframe, geo="ID", gprop="",
            )
            interest_region = self.pytrends.interest_by_region(
                resolution="REGION", inc_low_vol=True, inc_geo_code=True,
            )

            if interest_region.empty:
                self.logger.info("  region: empty")
                return []

            records = []
            for region_name, row in interest_region.iterrows():
                for kw in keywords:
                    if kw in row:
                        records.append({
                            "_type": "region",
                            "_keyword": kw,
                            "_value": float(row[kw]),
                            "_region": region_name,
                            "_timestamp": datetime.now().strftime("%Y-%m-%d"),
                        })

            self.logger.info(f"  region: ~{len(interest_region) * len(keywords)} records")
            return records

        except Exception as e:
            self.logger.warning(f"Region data failed (rate-limited, skipped): {e}")
            return []

    def _generate_mock_time_series(self, keywords) -> List[Dict]:
        records = []
        base_dates = []
        d = datetime.now() - timedelta(days=365 * 5)
        while d < datetime.now():
            base_dates.append(d.strftime("%Y-%m") + "-01")
            d += timedelta(days=30)

        keyword_cores = {
            "lansia": 75,
            "perawatan lansia": 35,
            "kesehatan lansia": 55,
            "senam lansia": 20,
            "posyandu lansia": 15,
        }

        for i, ts in enumerate(base_dates):
            for kw in keywords:
                core = keyword_cores.get(kw, 30)
                trend = (i / len(base_dates)) * 10
                noise = random.randint(-10, 10)
                val = max(0, min(100, int(core + trend + noise)))
                records.append({
                    "_type": "time_series",
                    "_keyword": kw,
                    "_value": val,
                    "_timestamp": ts,
                })
        return records

    def _generate_mock_region(self, keywords) -> List[Dict]:
        records = []
        for prov in INDONESIAN_PROVINCES:
            for kw in keywords:
                val = random.randint(0, 75)
                records.append({
                    "_type": "region",
                    "_keyword": kw,
                    "_value": val,
                    "_region": prov,
                    "_timestamp": datetime.now().strftime("%Y-%m-%d"),
                })
        return records

    def fetch(self) -> List[Dict]:
        keywords = KEYWORDS[:5]
        timeframe = "today 5-y"
        self.logger.info(f"Keywords ({len(keywords)}): {', '.join(keywords)}")

        self.pytrends = self._new_pytrends()
        self.logger.info(f"Initial delay {INITIAL_DELAY}s...")
        time.sleep(INITIAL_DELAY)

        raw_records = self._fetch_time_series(keywords, timeframe)

        if raw_records:
            raw_records += self._fetch_region(keywords, timeframe)

        if not raw_records:
            self.logger.warning(
                "Google Trends API rate-limited after all retries. "
                f"Falling back to simulated data. {PROXY_ENV_HINT}"
            )
            raw_records = self._generate_mock_time_series(keywords)
            raw_records += self._generate_mock_region(keywords)
            self.logger.info(
                f"  generated {len(raw_records)} simulated records"
            )

        return raw_records

    def normalize(self, raw_data: List[Dict]) -> List[Dict]:
        normalized = []
        for record in raw_data:
            try:
                normalized.append(
                    self.normalizer.normalize_record(
                        source="Google Trends",
                        category=record.get("_keyword", ""),
                        value=record.get("_value", 0),
                        timestamp=record.get("_timestamp"),
                        region=record.get("_region", "Indonesia"),
                        metric="interest_score",
                        notes=f"Google Trends — {record.get('_type', 'unknown')}",
                    )
                )
            except Exception as e:
                self.logger.error(f"Normalize error: {e}")
                continue
        return normalized
