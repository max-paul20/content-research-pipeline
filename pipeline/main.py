"""Unigliss Trend Radar pipeline orchestrator.

Wires together scraping, analysis, script generation, and delivery into a
single CLI-driven pipeline.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List

from . import config
from .analyzer import analyze_posts
from .delivery import deliver_scripts
from .scrapers import scrape_instagram, scrape_tiktok
from .script_generator import generate_scripts

logger = logging.getLogger(__name__)

_CACHE_FILE = config.DATA_DIR / "cached_posts.json"


def run_pipeline(
    dry_run: bool = False,
    campus: str | None = None,
    skip_scrape: bool = False,
) -> None:
    """Execute the full Trend Radar pipeline.

    Args:
        dry_run: Run all stages in test_mode (no real API calls).
        campus: Limit to ``"arizona"`` or ``"calpoly"`` (None = both).
        skip_scrape: Load cached scraper output instead of scraping.
    """

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )

    # Validate config
    status = config.validate_config()
    failures = {k: v for k, v in status.items() if v not in ("ok", "ok (exists)", "ok (created)", "skipped (TEST_MODE enabled)")}
    if failures and not dry_run:
        logger.error("Configuration errors: %s", failures)
        sys.exit(1)

    target_campus = _normalize_campus(campus) if campus else None
    post_source_label = "loaded from cache" if skip_scrape else "scraped"

    # Scrape or load cache
    if skip_scrape:
        posts = _load_cache()
        logger.info("Loaded %d posts from cache.", len(posts))
    else:
        tiktok_posts = scrape_tiktok(test_mode=dry_run)
        instagram_posts = scrape_instagram(test_mode=dry_run)
        posts = tiktok_posts + instagram_posts
        logger.info("Scraped %d posts (%d TikTok, %d Instagram).",
                     len(posts), len(tiktok_posts), len(instagram_posts))
        _save_cache(posts)

    if not posts:
        logger.warning("No posts to process. Exiting.")
        return

    # Analyze
    analyzed = analyze_posts(posts, test_mode=dry_run)
    logger.info("Analyzed: %d posts passed scoring threshold.", len(analyzed))

    if not analyzed:
        logger.warning("No posts passed analysis threshold. Exiting.")
        return

    # Filter by campus if specified
    if target_campus:
        analyzed = [
            p for p in analyzed
            if p.get("recommended_campus") in (target_campus, "both")
        ]
        logger.info("Filtered to %d posts for campus '%s'.", len(analyzed), target_campus)

    # Generate scripts
    scripts = generate_scripts(
        analyzed,
        test_mode=dry_run,
        target_campus=target_campus,
    )
    logger.info("Generated %d scripts.", len(scripts))

    # Filter scripts by campus if specified
    if target_campus:
        scripts = [s for s in scripts if s.get("campus") == target_campus]

    # Deliver
    result = deliver_scripts(scripts, test_mode=dry_run)
    logger.info(
        "Pipeline complete: %d %s, %d analyzed, %d scripts, %d delivered, %d failed.",
        len(posts),
        post_source_label,
        len(analyzed),
        len(scripts),
        result["sent"],
        result["failed"],
    )


def _normalize_campus(campus: str) -> str | None:
    """Map CLI campus names to internal keys."""

    mapping = {
        "arizona": "uofa",
        "uofa": "uofa",
        "calpoly": "calpoly",
        "cal_poly": "calpoly",
    }
    return mapping.get(campus.lower().strip())


def _load_cache() -> List[Dict[str, Any]]:
    """Load cached posts from disk."""

    if not _CACHE_FILE.exists():
        logger.warning("No cache file found at %s.", _CACHE_FILE)
        return []
    try:
        with open(_CACHE_FILE, "r") as f:
            data = json.load(f)
        if isinstance(data, list):
            return data
        logger.warning("Cache file is not a list.")
        return []
    except (json.JSONDecodeError, OSError) as exc:
        logger.error("Failed to load cache: %s", exc)
        return []


def _save_cache(posts: List[Dict[str, Any]]) -> None:
    """Save posts to cache for --skip-scrape reruns."""

    try:
        _CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(_CACHE_FILE, "w") as f:
            json.dump(posts, f, indent=2, default=str)
        logger.info("Cached %d posts to %s.", len(posts), _CACHE_FILE)
    except OSError as exc:
        logger.error("Failed to save cache: %s", exc)


def main() -> None:
    """CLI entry point."""

    parser = argparse.ArgumentParser(
        description="Unigliss Trend Radar — two-tier content intelligence pipeline"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run all stages in test mode (no real API calls)",
    )
    parser.add_argument(
        "--campus",
        choices=["arizona", "calpoly"],
        default=None,
        help="Limit pipeline to a single campus",
    )
    parser.add_argument(
        "--skip-scrape",
        action="store_true",
        help="Load cached scraper output from last run",
    )
    args = parser.parse_args()

    run_pipeline(
        dry_run=args.dry_run,
        campus=args.campus,
        skip_scrape=args.skip_scrape,
    )


if __name__ == "__main__":
    main()
