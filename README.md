# Unigliss Trend Radar

Content intelligence pipeline for [Unigliss](https://unigliss.com), a peer-to-peer beauty marketplace on college campuses. Scrapes viral beauty and lifestyle content from TikTok and Instagram, scores it with Gemini, generates a cross-campus insight report with Claude Sonnet (verified by Gemini Flash-Lite), generates campus-specific creator briefs with Claude Sonnet, and delivers everything via Telegram.

**Live campuses:** University of Arizona and Cal Poly SLO.
**Verification status:** 228 tests passing as of 2026-04-16.

## Architecture

```
CLI / CRON
  │  `main.py`, `python -m pipeline.main`, or `run.sh`
  ▼
STARTUP
  │  Configure logging, validate config, load 7-day scripted history
  ▼
SCRAPE OR LOAD CACHE
  │  Up to 130 posts/run at current defaults
  │  TikTok + Instagram, or `--skip-scrape` from `data/cached_posts.json`
  ▼
PRE-ANALYSIS FILTER
  │  Drop posts already present in `data/scripted_posts.json`
  ▼
GEMINI FLASH-LITE (parallel)
  │  Legacy analyzer: batch 5, up to 26 calls, ranks up to 15 candidates
  │  4 lens agents (engagement, trends, competitors, content themes),
  │  1 call each against the shared batch
  ▼
CAMPUS FILTER
  │  Optional `--campus arizona|calpoly`
  ▼
CLAUDE SONNET (parallel)
  │  Script generator: up to 3 briefs per campus, up to 6 calls total
  │  Report writer: 1 cross-campus insight report (ephemeral prompt cache)
  ▼
GEMINI FLASH-LITE VERIFIER
  │  1 call per cycle against the Sonnet report; fails open on error
  │  If `overallPass=false AND retryInstructions` → 1 Sonnet regeneration,
  │  delivered regardless of second verdict
  ▼
TELEGRAM DELIVERY
  │  Arizona scripts, separator when both campuses exist, Cal Poly scripts
  │  Report chunked at 4000 chars, sent as plain text after the scripts
  ▼
POST-RUN HISTORY SAVE
  │  Live sends only; delivered source posts are written back to history
```

## Tech Stack

- **Runtime:** Python 3, Raspberry Pi 5
- **Scraping:** RapidAPI / Scraptik (TikTok + Instagram)
- **Tier 1 Analysis:** Gemini Flash-Lite (free tier, raw HTTP)
- **Tier 2 Scripts:** Claude Sonnet (Anthropic API, raw HTTP)
- **Delivery:** Telegram Bot API
- **Dependencies:** `requests`, `python-dotenv`

## Module Status

| Module | Status | Coverage |
|--------|--------|----------|
| `pipeline/config.py` | Built + verified | `tests/test_config.py` (10) |
| `pipeline/knowledge_base.py` | Built + verified | `tests/test_knowledge_base.py` (11) |
| `pipeline/scrapers/_common.py` | Built + verified | `tests/test_scrapers.py` (49 shared scraper tests) |
| `pipeline/scrapers/tiktok.py` | Built + verified | `tests/test_scrapers.py` |
| `pipeline/scrapers/instagram.py` | Built + verified | `tests/test_scrapers.py` |
| `pipeline/analyzer_legacy.py` | Built + verified | `tests/test_analyzer.py` (28) |
| `pipeline/script_generator.py` | Built + verified | `tests/test_script_generator.py` (21) |
| `pipeline/delivery.py` | Built + verified | `tests/test_delivery.py` (29) |
| `pipeline/main.py` | Built + verified | `tests/test_main.py` (13) + `tests/test_orchestrator.py` (5) |
| `pipeline/history.py` | Built + verified | `tests/test_history.py` (3) |
| `pipeline/http_utils.py` | Built + verified | Shared retry coverage via analyzer/script generator/delivery tests |
| `pipeline/gemini_utils.py` | Built + verified | `tests/test_gemini_utils.py` (15) |
| `pipeline/skills.py` | Built + verified | `tests/test_skills.py` (5) |
| `pipeline/agents.py` | Built + verified | `tests/test_agents.py` (15) |
| `pipeline/report_writer.py` | Built + verified | `tests/test_report_writer.py` (8) |
| `pipeline/report_verifier.py` | Built + verified | `tests/test_report_verifier.py` (14) |
| `logging_utils.py` | Built + verified | `tests/test_logging_setup.py` (2) |

Full suite: **228 tests**

## Setup

```bash
git clone https://github.com/max-paul20/content-research-pipeline.git
cd content-research-pipeline
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.template .env
# Replace the placeholder values in .env with real credentials
python3 -m unittest discover -s tests -v  # Verify setup (228 tests)
```

## Usage

```bash
# Full pipeline dry run (no real API calls, uses mock data)
python3 main.py --dry-run
python3 -m pipeline.main --dry-run

# Production run
python3 main.py
python3 -m pipeline.main

# Single campus only
python3 main.py --campus arizona
python3 main.py --campus calpoly
python3 -m pipeline.main --campus arizona
python3 -m pipeline.main --campus calpoly

# Skip scraping, reuse cached posts from last run
python3 main.py --skip-scrape
python3 -m pipeline.main --skip-scrape
```

## Cron

Use the repo-local wrapper so cron does not depend on shell profile state:

```bash
./run.sh
```

Example crontab:

```cron
# Unigliss Trend Radar — 12pm and 7pm MST (19:00 and 02:00 UTC)
0 19 * * * /home/maxdabeast124/content-research-pipeline/run.sh
0 2 * * * /home/maxdabeast124/content-research-pipeline/run.sh
```

Runtime logs:

- `data/logs/pipeline.log` — rotating application log (5 MB, 3 backups)
- `data/logs/cron.log` — stdout/stderr captured by `run.sh`

## Operational Hardening

- Cross-run dedup:
  scraper-level seen-post cache in `data/seen_posts.json`
  delivered-script history in `data/scripted_posts.json`
- Script history is filtered before Gemini analysis and expires entries older than 7 days.
- Logging writes to both console and `data/logs/pipeline.log` through `RotatingFileHandler`.
- Gemini, Anthropic, and Telegram API calls use shared exponential-backoff retries, while `401` errors fail fast without retry.

## Cost

- **Gemini Flash-Lite:** up to 31 calls/run and 62 calls/day (26 legacy analyzer + 4 lens agents + 1 verifier, twice daily).
- **RapidAPI / Scraptik:** 20 requests/run and 40 requests/day at the default twice-daily schedule.
- **Claude Sonnet 4:** up to 8 calls/run and 16 calls/day (6 scripts + 1 report + 1 optional retry, twice daily).
- **Pricing note:** dollar cost is not fixed in the repo; it depends on the current Gemini, Anthropic, and Scraptik pricing active at runtime.

## Development

Built and iterated with [Claude Code](https://claude.com/claude-code). Repository: [max-paul20](https://github.com/max-paul20).
