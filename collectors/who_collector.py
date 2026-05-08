"""
WHO GHO API Collector — 100% Real Data.

Mengakses WHO Global Health Observatory (GHO) OData API:
https://ghoapi.azureedge.net/api/

Indikator yang dikumpulkan:
- BP_04: Tekanan Darah Tinggi (Raised blood pressure, age-standardized)
- NCD_GLUC_02: Diabetes (Raised fasting blood glucose)
- NCD_BMI_30A: Obesitas (Obesity among adults, BMI >= 30)
- WHOSIS_000001: Life expectancy (kesehatan umum)

Tidak ada simulated data — API gagal berarti exception.
"""

import re
from typing import Dict, List, Optional

from collectors.base import BaseCollector
from utils.http_client import HttpClient


# =============================================================================
# Konfigurasi API WHO
# =============================================================================

WHO_BASE_URL = "https://ghoapi.azureedge.net/api"

# Target indicators — semua menggunakan API nyata
TARGET_INDICATORS = [
    {
        "code": "BP_04",
        "category": "Hypertension",
        "description": "Raised blood pressure (SBP>=140 OR DBP>=90), age-standardized estimate",
    },
    {
        "code": "NCD_GLUC_02",
        "category": "Diabetes",
        "description": "Raised fasting blood glucose (>=7.0 mmol/L), age-standardized",
    },
    {
        "code": "NCD_BMI_30A",
        "category": "Obesity",
        "description": "Obesity among adults, BMI >= 30, age-standardized estimate",
    },
    {
        "code": "WHOSIS_000001",
        "category": "Life Expectancy",
        "description": "Life expectancy at birth (years)",
    },
]


# =============================================================================
# Collector Class
# =============================================================================

class WHOCollector(BaseCollector):
    """
    Collector untuk WHO Global Health Observatory API.

    Flow:
    1. Iterasi list TARGET_INDICATORS
    2. GET /api/{code}?$filter=SpatialDim eq 'IDN'
    3. Parse response, ekstrak data Indonesia (SpatialDim == 'IDN')
    """

    def __init__(self, output_dir: str = "output"):
        super().__init__(name="WHO", output_dir=output_dir)
        self.client = HttpClient(timeout=30)

    def fetch(self) -> List[Dict]:
        """
        Ambil data dari WHO GHO API untuk semua indikator target.

        Returns:
            List[Dict]: Data mentah dengan key _indicator_code & _category

        Raises:
            RuntimeError: Jika semua indikator gagal di-fetch
        """
        raw_records = []
        any_success = False

        for indicator in TARGET_INDICATORS:
            code = indicator["code"]
            url = f"{WHO_BASE_URL}/{code}"

            # Filter untuk Indonesia (kode ISO: IDN)
            params = {"$filter": "SpatialDim eq 'IDN'"}

            try:
                self.logger.info(f"Mengambil {code} — {indicator['description']}")
                response = self.client.get(url, params=params)
                data = response.json()

                if "value" in data and len(data["value"]) > 0:
                    any_success = True
                    for record in data["value"]:
                        record["_indicator_code"] = code
                        record["_category"] = indicator["category"]
                        raw_records.append(record)
                    self.logger.info(
                        f"  -> {len(data['value'])} record dari API"
                    )
                else:
                    self.logger.warning(f"  -> Data kosong untuk {code}")

            except Exception as e:
                self.logger.error(f"  -> Gagal akses API untuk {code}: {e}")

        if not any_success:
            raise RuntimeError(
                "Semua indikator WHO GHO API gagal di-fetch. "
                "Periksa koneksi internet atau status API."
            )

        return raw_records

    @staticmethod
    def _normalize_sex(dim1: str) -> Optional[str]:
        """
        Konversi kode gender WHO ke label human-readable.

        Mapping:
        - SEX_BTSX → Both
        - SEX_MLE  → Male
        - SEX_FMLE → Female
        """
        sex_map = {
            "SEX_BTSX": "Both",
            "SEX_MLE": "Male",
            "SEX_FMLE": "Female",
        }
        return sex_map.get(dim1, dim1)

    @staticmethod
    def _parse_value(raw_value) -> Optional[float]:
        """
        Parsing nilai dari WHO API yang dapat berupa:
        - Numeric: 5.1
        - String dengan interval: "5.1 [4.7-5.6]"

        Returns:
            float atau None jika gagal parse
        """
        if raw_value is None:
            return None

        if isinstance(raw_value, (int, float)):
            return float(raw_value)

        match = re.match(r"([0-9]+\.?[0-9]*)", str(raw_value))
        if match:
            return float(match.group(1))

        return None

    def normalize(self, raw_data: List[Dict]) -> List[Dict]:
        """
        Normalisasi data WHO API ke schema standar.

        Post-filter: hanya record dengan SpatialDim == 'IDN' (Indonesia).
        Field yang di-parse: NumericValue, Value, TimeDim, Dim1 (sex).
        """
        normalized = []

        for record in raw_data:
            try:
                # Post-filter: hanya record untuk Indonesia
                country_code = record.get("SpatialDim")
                if country_code and country_code != "IDN":
                    continue

                # Value — prioritaskan NumericValue (float), fallback ke Value (string)
                raw_val = record.get("NumericValue") or record.get("Value")
                value = self._parse_value(raw_val)

                if value is None:
                    continue

                year = record.get("TimeDim")
                sex = self._normalize_sex(record.get("Dim1"))
                indicator_code = record.get("IndicatorCode") or record.get("_indicator_code")
                indicator_name = record.get("IndicatorName", "")

                normalized.append(
                    self.normalizer.normalize_record(
                        source="WHO",
                        category=record.get("_category", "Unknown"),
                        value=value,
                        year=year,
                        age_group="60+",
                        country="Indonesia",
                        sex=sex,
                        unit="percent",
                        indicator_code=indicator_code,
                        notes=f"WHO GHO API — {indicator_name}",
                    )
                )
            except Exception as e:
                self.logger.error(f"Error normalisasi record: {e}")
                continue

        return normalized

    def __del__(self):
        """Cleanup HTTP client saat collector di-destroy."""
        if hasattr(self, "client"):
            self.client.close()
