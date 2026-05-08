"""
Konfigurasi logging untuk project.

Menyediakan setup_logger() yang mengatur format dan level logging standar.
Digunakan oleh semua collector dan collect.py agar output terminal konsisten.
"""

import logging
import sys


def setup_logger(name: str = None, level: int = logging.INFO) -> logging.Logger:
    """
    Setup logger dengan format: [LEVEL] [TIMESTAMP] [MODULE] PESAN

    Args:
        name: Nama logger (biasanya __name__ dari modul pemanggil)
        level: Level logging (default INFO)

    Returns:
        logging.Logger instance yang sudah dikonfigurasi
    """
    fmt = logging.Formatter(
        "[%(levelname)s] [%(asctime)s] [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(fmt)

    logger = logging.getLogger(name or __name__)
    logger.setLevel(level)

    # Hindari duplicate handler saat module di-reload (umum di Colab/Jupyter)
    if not logger.handlers:
        logger.addHandler(handler)

    return logger
