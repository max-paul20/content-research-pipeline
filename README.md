# Unigliss Trend Radar

Content intelligence pipeline for [Unigliss](https://unigliss.com), a peer-to-peer beauty marketplace on college campuses. Scrapes viral beauty and lifestyle content from TikTok and Instagram, scores it with Gemini, generates campus-specific creator briefs with Claude Sonnet, and delivers them via Telegram.

**Live campuses:** University of Arizona and Cal Poly SLO.
**Verification status:** 155 tests passing as of 2026-04-02.

## Architecture

```
CRON (12:00 PM + 7:00 PM MST)
  │
  ▼
SCRAPERS (RapidAPI / Scraptik)
  │  Up to 130 posts from TikTok + Instagram
  │  Hashtag search + trending feed + campus-specific tags
  │
  ▼
TIER 1: GEMINI FLASH-LITE (free, up to 26 API calls/run)
  │  Batch 5 posts per call
  │  Score virality, classify trend type, tag audio lifecycle
  │  Filter and rank → top 10-15 candidates
  │
  ▼
TIER 2: CLAUDE SONNET (paid, ~6 API calls/run)
  │  Up to 3 scripts for Arizona + up to 3 scripts for Cal Poly
  │  Lean creative briefs, 100-200 words each
  │
  ▼
TELEGRAM (private channel)
  │  Briefs sent to owner for review
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
| `pipeline/analyzer.py` | Built + verified | `tests/test_analyzer.py` (28) |
| `pipeline/script_generator.py` | Built + verified | `tests/test_script_generator.py` (21) |
| `pipeline/delivery.py` | Built + verified | `tests/test_delivery.py` (18) |
| `pipeline/main.py` | Built + verified | `tests/test_main.py` (13) |
| `pipeline/history.py` | Built + verified | `tests/test_history.py` (3) |
| `pipeline/http_utils.py` | Built + verified | Shared retry coverage via analyzer/script generator/delivery tests |
| `logging_utils.py` | Built + verified | `tests/test_logging_setup.py` (2) |

Full suite: **155 tests**

## Setup

```bash
git clone https://github.com/max-paul20/content-research-pipeline.git
cd content-research-pipeline
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.template .env
# Replace the placeholder values in .env with real credentials
python3 -m unittest discover -s tests -v  # Verify setup (155 tests)
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

- **Gemini Flash-Lite:** Free tier is available on the Gemini Developer API; at the repo's current ceilings this stage is still negligible even on paid token pricing.
- **RapidAPI / Scraptik:** 20 requests/run, 40 requests/day at the default twice-daily schedule. Actual cost depends on the current Scraptik plan.
- **Claude Sonnet 4:** At current Anthropic list pricing and the repo's current prompt sizes, roughly low single-digit dollars per month at the default ceiling (about 12 calls/day, up to 6 scripts/run).
- **Total:** Model spend remains modest at the current defaults; the main variable cost outside Sonnet is whichever Scraptik plan is active.

## Development

Built and iterated with [Claude Code](https://claude.com/claude-code). Repository: [max-paul20](https://github.com/max-paul20).
