"""
Abstract Base Collector — template untuk semua data source collector.

Setiap collector harus meng-extend BaseCollector dan
mengimplementasikan 3 method:
1. fetch()      — Ambil data dari API / scraping / simulated
2. normalize()  — Ubah data mentah ke schema standar
3. save()       — Simpan hasil ke file JSON

Alur eksekusi per collector (via collect()):
    fetch() -> normalize() -> save() -> return hasil

Pattern: Template Method + Strategy
"""

import json
import os
from abc import ABC, abstractmethod
from typing import Dict, List

from utils.logger import setup_logger
from utils.normalizer import Normalizer


class BaseCollector(ABC):
    """
    Abstract Base Class untuk semua collector.

    Attributes:
        name: Nama collector (digunakan untuk logging dan nama file output)
        output_dir: Direktori penyimpanan file JSON output
        logger: Logger instance
        normalizer: Normalizer instance untuk transformasi data
    """

    def __init__(self, name: str, output_dir: str = "output"):
        """
        Args:
            name: Nama collector (contoh: "WHO", "Kemkes", "BPS", "data.go.id")
            output_dir: Path direktori output (relative atau absolute)
        """
        self.name = name
        self.output_dir = output_dir
        self.logger = setup_logger(f"collector.{name}")
        self.normalizer = Normalizer()

        # Pastikan direktori output tersedia
        os.makedirs(self.output_dir, exist_ok=True)

    @abstractmethod
    def fetch(self) -> List[Dict]:
        """
        Ambil data mentah dari sumber data.

        Method ini harus di-override oleh subclass.
        Prioritas: API (jika tersedia) -> scraping ringan -> simulated fallback.

        Returns:
            List[Dict]: Data mentah dari sumber

        Raises:
            Exception: Jika fetch gagal total (tanpa fallback)
        """
        pass

    @abstractmethod
    def normalize(self, raw_data: List[Dict]) -> List[Dict]:
        """
        Normalisasi data mentah ke schema standar.

        Args:
            raw_data: Data mentah hasil fetch()

        Returns:
            List[Dict]: Data yang sudah dinormalisasi ke schema standard
        """
        pass

    def collect(self) -> List[Dict]:
        """
        Menjalankan pipeline collection lengkap: fetch -> normalize -> save.

        Method ini di-overridable tapi biasanya tidak perlu diubah.
        Return hasil normalized untuk aggregasi oleh collect.py.

        Returns:
            List[Dict]: Data yang sudah dinormalisasi
        """
        self.logger.info(f"Memulai collection dari {self.name}")

        try:
            raw_data = self.fetch()
            self.logger.info(f"Berhasil fetch {len(raw_data)} record mentah")
        except Exception as e:
            self.logger.error(f"Gagal fetch dari {self.name}: {e}")
            raise

        normalized = self.normalize(raw_data)
        self.logger.info(f"Berhasil normalisasi {len(normalized)} record")

        filepath = self.save(normalized)
        self.logger.info(f"Data disimpan ke {filepath}")

        return normalized

    def save(self, data: List[Dict], filename: str = None) -> str:
        """
        Simpan data ke file JSON di output_dir.

        Args:
            data: List record yang sudah dinormalisasi
            filename: Nama file (default: auto-generated dari nama collector)

        Returns:
            str: Path lengkap file yang disimpan
        """
        if filename is None:
            filename = f"{self.name.lower().replace('.', '_')}_health_data.json"

        filepath = os.path.join(self.output_dir, filename)

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        return filepath
