# Unigliss Trend Radar

Content intelligence pipeline for [Unigliss](https://unigliss.com), a peer-to-peer beauty marketplace on college campuses. Scrapes viral beauty and lifestyle content from TikTok and Instagram, scores it with Gemini, generates campus-specific creator briefs with Claude Sonnet, and delivers them via Telegram.

**Live campuses:** University of Arizona and Cal Poly SLO.

## Architecture

```
CRON (12:00 PM + 7:00 PM MST)
  │
  ▼
SCRAPERS (RapidAPI / Scraptik)
  │  ~200 posts from TikTok + Instagram
  │  Hashtag search + trending feed + campus-specific tags
  │
  ▼
TIER 1: GEMINI FLASH-LITE (free, ~40-70 API calls/run)
  │  Batch 3-5 posts per call
  │  Score virality, classify trend type, tag audio lifecycle
  │  Filter and rank → top 10-15 candidates
  │
  ▼
TIER 2: CLAUDE SONNET (paid, ~6 API calls/run)
  │  3 scripts for Arizona + 3 scripts for Cal Poly
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
- **Dependencies:** `requests`, `python-dotenv`, `python-telegram-bot`

## Module Status

| Module | Status | Tests |
|--------|--------|-------|
| `pipeline/config.py` | Built | 10 |
| `pipeline/knowledge_base.py` | Built | 11 |
| `pipeline/scrapers/_common.py` | Built | 48 |
| `pipeline/scrapers/tiktok.py` | Built | (in scrapers) |
| `pipeline/scrapers/instagram.py` | Built | (in scrapers) |
| `pipeline/analyzer.py` | Built | 23 |
| `pipeline/script_generator.py` | Built | 15 |
| `pipeline/delivery.py` | Built | 14 |
| `pipeline/main.py` | Built | 7 |
| **Total** | | **133** |

## Setup

```bash
git clone https://github.com/max-paul20/content-research-pipeline.git
cd content-research-pipeline
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.template .env
# Fill in API keys in .env
python3 -m unittest discover -s tests -v  # Verify setup
```

## Usage

```bash
# Full pipeline dry run (no real API calls, uses mock data)
python3 -m pipeline.main --dry-run

# Production run
python3 -m pipeline.main

# Single campus only
python3 -m pipeline.main --campus arizona
python3 -m pipeline.main --campus calpoly

# Skip scraping, reuse cached posts from last run
python3 -m pipeline.main --skip-scrape
```

## Cost

- **Gemini Flash-Lite:** Free (80-140 calls/day, well within 1,000 daily limit)
- **Claude Sonnet:** ~$0.40-0.60/day (~12 calls/day at ~2K input + ~500 output tokens)
- **Total:** ~$12-18/month

## Development

Built and iterated with [Claude Code](https://claude.com/claude-code). Repository: [max-paul20](https://github.com/max-paul20).
