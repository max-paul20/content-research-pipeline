"""Scraper entry points for the Unigliss content research pipeline."""

from .instagram import get_mock_posts as get_mock_instagram_posts
from .instagram import scrape_instagram
from .tiktok import get_mock_posts as get_mock_tiktok_posts
from .tiktok import scrape_tiktok

__all__ = [
    "get_mock_instagram_posts",
    "get_mock_tiktok_posts",
    "scrape_instagram",
    "scrape_tiktok",
]
