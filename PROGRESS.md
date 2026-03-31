# Unigliss Trend Radar — Build Progress

**Last updated:** 2026-03-31
**Total tests:** 133 passing, 0 failing

---

## Module Status

| Module | Status | Tests | Description |
|--------|--------|-------|-------------|
| `pipeline/config.py` | Built | 10 | Central config, env loading, validation |
| `pipeline/knowledge_base.py` | Built | 11 | Tiered prompt builders (Gemini + Sonnet) |
| `pipeline/scrapers/_common.py` | Built | 48 | Shared schema, normalization, dedup |
| `pipeline/scrapers/tiktok.py` | Built | — | TikTok scraping via Scraptik |
| `pipeline/scrapers/instagram.py` | Built | — | Instagram scraping via Scraptik |
| `pipeline/analyzer.py` | Built | 23 | Gemini Tier 1 analysis + scoring |
| `pipeline/script_generator.py` | Built | 15 | Sonnet Tier 2 creative briefs |
| `pipeline/delivery.py` | Built | 14 | Telegram message delivery |
| `pipeline/main.py` | Built | 7 | CLI orchestrator |

## Test Counts by File

| Test File | Tests |
|-----------|-------|
| `tests/test_config.py` | 10 |
| `tests/test_knowledge_base.py` | 11 |
| `tests/test_scrapers.py` | 48 |
| `tests/test_analyzer.py` | 23 |
| `tests/test_script_generator.py` | 15 |
| `tests/test_delivery.py` | 14 |
| `tests/test_main.py` | 7 |
| **Total** | **133** |

## Architecture

Two-tier AI pipeline:
1. **Gemini Flash-Lite** (free) — batch analysis, scoring, filtering
2. **Claude Sonnet** (paid) — campus-specific creative brief generation

See `ARCHITECTURE.md` for full details.
