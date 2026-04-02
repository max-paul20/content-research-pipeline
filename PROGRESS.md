# Unigliss Trend Radar — Build Progress

**Last updated:** 2026-04-02
**Total tests:** 155 passing, 0 failing

---

## Module Status

| Module | Status | Tests | Description |
|--------|--------|-------|-------------|
| `pipeline/config.py` | Built + verified | 10 | Central config, env loading, validation |
| `pipeline/knowledge_base.py` | Built + verified | 11 | Tiered prompt builders (Gemini + Sonnet) |
| `pipeline/scrapers/_common.py` | Built + verified | 49 (shared scraper coverage) | Shared schema, normalization, endpoint handling, dedup helpers |
| `pipeline/scrapers/tiktok.py` | Built + verified | Covered in `tests/test_scrapers.py` | TikTok scraping via Scraptik + seen-post dedup |
| `pipeline/scrapers/instagram.py` | Built + verified | Covered in `tests/test_scrapers.py` | Instagram scraping via Scraptik + seen-post dedup |
| `pipeline/analyzer.py` | Built + verified | 28 | Gemini Tier 1 analysis, JSON recovery, scoring, retry-path handling |
| `pipeline/script_generator.py` | Built + verified | 21 | Sonnet Tier 2 creative briefs, campus split, retry-path handling |
| `pipeline/delivery.py` | Built + verified | 18 | Telegram formatting, ordering, dry-run delivery, retry-path handling |
| `pipeline/main.py` | Built + verified | 13 | CLI orchestrator, cache loading, campus filtering, run summaries |
| `pipeline/history.py` | Built + verified | 3 | Cross-run scripted-post history, 7-day expiry, pre-analysis dedup |
| `pipeline/http_utils.py` | Built + verified | Shared via analyzer/script generator/delivery tests | Shared retry helper with exponential backoff and 401 short-circuit |
| `logging_utils.py` | Built + verified | 2 | Console + rotating file logging setup |

## Operational Hardening

- Complete: cross-run dedup via `data/scripted_posts.json`, with filtering before analyzer execution and 7-day expiry.
- Complete: console logging plus rotating file logging at `data/logs/pipeline.log`.
- Complete: shared exponential-backoff retries for Gemini, Anthropic, and Telegram, with `401` treated as terminal.
- Complete: cron wrapper via executable `run.sh`, including venv activation and stdout/stderr capture to `data/logs/cron.log`.

## Test Counts by File

| Test File | Tests |
|-----------|-------|
| `tests/test_config.py` | 10 |
| `tests/test_knowledge_base.py` | 11 |
| `tests/test_scrapers.py` | 49 |
| `tests/test_analyzer.py` | 28 |
| `tests/test_script_generator.py` | 21 |
| `tests/test_delivery.py` | 18 |
| `tests/test_main.py` | 13 |
| `tests/test_history.py` | 3 |
| `tests/test_logging_setup.py` | 2 |
| **Total** | **155** |

## Architecture

Two-tier AI pipeline:
1. **Gemini Flash-Lite** (free) — batch analysis, scoring, filtering
2. **Claude Sonnet** (paid) — campus-specific creative brief generation

Operational hardening is complete: seen-post dedup in scrapers, scripted-post history before analysis, rotating logs, shared retry/backoff, and cron-safe startup.

See `ARCHITECTURE.md` for full details.
