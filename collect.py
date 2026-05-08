#!/usr/bin/env python3
"""
================================================================================
collect.py — Main Orchestrator
Sistem Analisis Popularitas Topik Lansia di Media Digital

Project   : Big Data — Analisis Popularitas Topik Lansia di Media Digital
Mata Kuliah : Big Data
================================================================================

Alur Utama:
1. Load .env untuk API keys (YouTube, Reddit)
2. Instansiasi semua collector (WHO, Google Trends, YouTube, Reddit)
3. Jalankan tiap collector secara sequential:
   - fetch()  → ambil data dari API
   - normalize() → transformasi ke schema standar
   - save()   → simpan ke file JSON di folder output/
4. Aggregasi semua hasil ke satu file summary JSON
5. Build frontend data untuk dashboard

Cara Menjalankan:
   cp .env.example .env
   # Isi YOUTUBE_API_KEY, REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET
   python collect.py

   # Atau di Google Colab:
   # Set environment variables dulu, lalu:
   !python collect.py

Persyaratan:
   - Python 3.8+
   - pip install -r requirements.txt
   - .env dengan API keys (opsional: tanpa YouTube & Reddit, hanya WHO & Google Trends)
================================================================================
"""

import json
import os
import sys
import time
from typing import Dict, List

from dotenv import load_dotenv

from collectors import (
    WHOCollector,
    GoogleTrendsCollector,
    YouTubeCollector,
)
from utils.logger import setup_logger

# Load .env di awal
load_dotenv()


# =============================================================================
# Konfigurasi
# =============================================================================

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")

# Daftar collector aktif — semua menggunakan API nyata
COLLECTORS = {
    "WHO": WHOCollector,
    "Google Trends": GoogleTrendsCollector,
    "YouTube": YouTubeCollector,
}


# =============================================================================
# Orchestrator
# =============================================================================

def run_collection() -> Dict[str, List[Dict]]:
    """
    Menjalankan seluruh pipeline data collection.

    Returns:
        Dict[str, List[Dict]]: Mapping nama_collector -> list data normalized
    """
    logger = setup_logger("orchestrator")
    logger.info("=" * 70)
    logger.info("ANALISIS POPULARITAS TOPIK LANSIA DI MEDIA DIGITAL")
    logger.info("Target: WHO • Google Trends • YouTube")
    logger.info("=" * 70)

    results = {}
    total_success = 0
    total_error = 0
    start_time = time.time()

    for name, CollectorClass in COLLECTORS.items():
        logger.info(f"\n{'─' * 50}")
        logger.info(f"Memproses: {name}")

        try:
            collector = CollectorClass(output_dir=OUTPUT_DIR)
            data = collector.collect()
            results[name] = data
            total_success += 1
            logger.info(f"✓ {name} selesai — {len(data)} record terkumpul")

        except Exception as e:
            logger.error(f"✗ {name} GAGAL: {e}")
            results[name] = []
            total_error += 1

    elapsed = time.time() - start_time

    # Ringkasan
    logger.info(f"\n{'=' * 70}")
    logger.info("RINGKASAN KOLEKSI DATA")
    logger.info(f"{'=' * 70}")
    logger.info(f"Total source berhasil : {total_success}/{len(COLLECTORS)}")
    logger.info(f"Total source gagal   : {total_error}/{len(COLLECTORS)}")
    logger.info(f"Waktu eksekusi       : {elapsed:.2f} detik")

    total_records = sum(len(v) for v in results.values())
    logger.info(f"Total record         : {total_records}")

    for name, records in results.items():
        if records:
            keywords = set(r.get("keyword", "?") for r in records)
            logger.info(f"  {name:15s} → {len(records):3d} record")
        else:
            logger.info(f"  {name:15s} → GAGAL")

    return results


def save_summary(results: Dict[str, List[Dict]]) -> str:
    """
    Simpan file ringkasan (summary) semua hasil collection ke satu JSON.

    Args:
        results: Dict hasil run_collection()

    Returns:
        str: Path file summary JSON
    """
    logger = setup_logger("orchestrator.summary")

    total_records = sum(len(v) for v in results.values())

    summary = {
        "project": "Analisis Popularitas Topik Lansia di Media Digital — Big Data",
        "description": "Dataset popularitas, engagement, dan sentimen topik lansia dari Google Trends, YouTube, Reddit, dan WHO",
        "sources": list(COLLECTORS.keys()),
        "total_records": total_records,
        "records_per_source": {
            name: len(records) for name, records in results.items()
        },
        "keywords": sorted(
            set(
                r.get("keyword", "")
                for records in results.values()
                for r in records
                if r.get("keyword")
            )
        ),
        "data": results,
    }

    filepath = os.path.join(OUTPUT_DIR, "summary_elderly_digital.json")
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    logger.info(f"Ringkasan disimpan ke: {filepath}")
    return filepath


# =============================================================================
# Entry Point
# =============================================================================

if __name__ == "__main__":
    logger = setup_logger("main")

    try:
        logger.info("Memulai sistem analisis popularitas topik lansia...")
        logger.info(f"Output directory: {OUTPUT_DIR}")

        # Jalankan collection
        results = run_collection()

        # Simpan summary gabungan
        summary_path = save_summary(results)

        logger.info("\n" + "=" * 70)
        logger.info("SELESAI.")
        logger.info(f"Semua hasil ada di folder: {OUTPUT_DIR}/")
        logger.info("File-file output:")
        for f in sorted(os.listdir(OUTPUT_DIR)):
            fpath = os.path.join(OUTPUT_DIR, f)
            size_kb = os.path.getsize(fpath) / 1024
            logger.info(f"  • {f} ({size_kb:.1f} KB)")
        logger.info("=" * 70)

    except KeyboardInterrupt:
        logger.warning("Collection dihentikan oleh pengguna (Ctrl+C)")
        sys.exit(0)

    except Exception as e:
        logger.critical(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)
