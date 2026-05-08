"""Collector modules — setiap modul menangani satu sumber data digital media."""

from .base import BaseCollector
from .who_collector import WHOCollector
from .googletrends_collector import GoogleTrendsCollector
from .youtube_collector import YouTubeCollector

__all__ = [
    "BaseCollector",
    "WHOCollector",
    "GoogleTrendsCollector",
    "YouTubeCollector",
]
