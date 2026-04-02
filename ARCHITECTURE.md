# Architecture — Unigliss Trend Radar

## Two-Tier AI Hierarchy

The pipeline uses two AI tiers to balance cost and quality:

**Tier 1 — Gemini Flash-Lite (free)**
- High-volume preprocessing: up to 26 API calls per run at the current scrape ceiling
- Batches 5 posts per call for efficiency
- Returns structured JSON: virality score, trend classification, audio lifecycle, campus relevance
- Filters up to 130 scraped posts down to at most 15 ranked candidates
- Budget guardrail: `MAX_GEMINI_CALLS_PER_RUN=500`

**Tier 2 — Claude Sonnet (paid)**
- Low-volume creative generation: up to 6 API calls per run
- Receives Gemini's top candidates + campus context from knowledge base
- Generates lean creative briefs (100-200 words) with Gen Z tone
- Up to 3 scripts per campus = up to 6 total per run
- Delivery volume is capped by `SCRIPTS_PER_CAMPUS=3`; see the usage section below

**Why two tiers?** Gemini is free but less creative. Sonnet is excellent at tone and format but costs money. By using Gemini to filter up to 130 posts down to up to 6, we minimize Sonnet calls while maximizing creative quality.

## Operational Hardening

- Scraper-level dedup persists seen posts to `data/seen_posts.json`.
- Delivered-script history persists to `data/scripted_posts.json`, is checked before analyzer runs, and expires entries older than 7 days.
- Startup logging is dual-path: console plus rotating file logging at `data/logs/pipeline.log`.
- Gemini, Anthropic, and Telegram use shared retry logic with exponential backoff and no retries on `401`.
- `run.sh` activates the repo venv and captures stdout/stderr to `data/logs/cron.log` for cron-safe execution.

## Data Flow

```
┌──────────────┐
│ CLI / Cron   │  `main.py`, `python -m pipeline.main`, or `run.sh`
└──────┬───────┘
       │
       ▼
┌──────────────┐
│ Startup      │  `configure_logging()` + `config.validate_config()`
│ Validation   │  load `data/scripted_posts.json`
└──────┬───────┘
       │
       ▼
┌──────────────┐
│ Scrape Or    │  TikTok + Instagram, or `--skip-scrape` cache load
│ Load Cache   │  cache writes to `data/cached_posts.json`
└──────┬───────┘
       │
       ▼
┌──────────────┐
│ Scraper      │  endpoint failure isolation + seen-post dedup in
│ Hardening    │  `data/seen_posts.json`
└──────┬───────┘
       │
       ▼
┌──────────────┐
│ History      │  drop already-scripted posts before Gemini analysis
│ Filter       │  using 7-day `scripted_posts.json` history
└──────┬───────┘
       │
       ▼
┌──────────────┐
│ Analyzer     │  Gemini Flash-Lite
│ (Tier 1)     │  batches of 5, JSON recovery, retry/backoff
└──────┬───────┘
       │
       ▼
┌──────────────┐
│ Campus       │  optional `--campus arizona|calpoly`
│ Filter       │  keeps `uofa`, `calpoly`, or `both`
└──────┬───────┘
       │
       ▼
┌──────────────┐
│ Script       │  Claude Sonnet
│ Generator    │  up to `SCRIPTS_PER_CAMPUS` per campus bucket
└──────┬───────┘
       │
       ▼
┌──────────────┐
│ Delivery     │  Telegram, Arizona first, optional separator,
│               │  Cal Poly second
└──────┬───────┘
       │
       ▼
┌──────────────┐
│ Post-Run     │  on live sends only, persist delivered source posts
│ History Save │  back to `data/scripted_posts.json`
└──────────────┘
```

## Campus Configuration

Campus configuration lives in `pipeline/knowledge_base.py` → `CAMPUS_REGISTRY`. Adding a new campus requires:

1. Add a new entry to `CAMPUS_REGISTRY` with `display_name`, `emoji`, `hashtags`, and `context`
2. The `SUPPORTED_CAMPUSES` tuple and scraper hashtag seeds derive automatically from that registry
3. Review any campus-specific tests or mock content for new local references

This data should be reviewed and updated regularly. The more specific and current the campus context, the better the scripts.

## Cron Schedule

Two daily runs, timed for peak posting windows across both campus timezones:

- **12:00 PM MST** — catches morning trends, scripts ready for afternoon posting
- **7:00 PM MST** — catches afternoon trends, scripts ready for evening posting

Arizona (MST) and Cal Poly (PST) are 1 hour apart, so both windows work well for both campuses.

## Usage Ceilings

| Component | Calls/Run | Runs/Day | Daily Calls | Source |
|-----------|-----------|----------|-------------|--------|
| Gemini Flash-Lite | 26 max | 2 | 52 max | `SCRAPE_LIMIT=20`, 2 platforms, 9 hashtags/platform, batch size 5 |
| Claude Sonnet 4 | 6 max | 2 | 12 max | `SCRIPTS_PER_CAMPUS=3`, 2 campuses |
| RapidAPI/Scraptik | 20 max | 2 | 40 max | 10 scraper requests/platform/run, 2 platforms |

Pricing is intentionally not hard-coded here because vendor pricing changes independently of the repo. The codebase fixes the usage ceilings above; actual spend depends on the current Gemini, Anthropic, and Scraptik pricing active at runtime.

## What's NOT in v1

- **Pinterest scraping** — planned for future, not prioritized
- **Standalone audio tracker** — audio lifecycle is tagged by Gemini, not tracked independently
- **Obsidian vault output** — Telegram delivery only for now
- **Local LLM (Ollama/Qwen)** — replaced by cloud API approach for reliability
- **Two-node Pi+Mac architecture** — consolidated to single Pi 5
- **Multiple Telegram channels** — single private channel, owner forwards manually
