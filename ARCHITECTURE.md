# Architecture — Unigliss Trend Radar

## Two-Tier AI Hierarchy

The pipeline uses two AI tiers to balance cost and quality:

**Tier 1 — Gemini Flash-Lite (free)**
- High-volume preprocessing: ~40-70 API calls per run
- Batches 3-5 posts per call for efficiency
- Returns structured JSON: virality score, trend classification, audio lifecycle, campus relevance
- Filters ~200 scraped posts down to 10-15 top candidates
- Budget: 500 calls/run cap, well within 1,000/day free limit across 2 runs

**Tier 2 — Claude Sonnet (paid)**
- Low-volume creative generation: ~6 API calls per run
- Receives Gemini's top candidates + campus context from knowledge base
- Generates lean creative briefs (100-200 words) with Gen Z tone
- 3 scripts per campus = 6 total per run
- Cost: ~$0.40-0.60/day ≈ $12-18/month

**Why two tiers?** Gemini is free but less creative. Sonnet is excellent at tone and format but costs money. By using Gemini to filter 200 posts down to 6, we minimize Sonnet calls while maximizing creative quality.

## Data Flow

```
┌─────────────┐     ┌─────────────┐
│ TikTok API  │     │Instagram API│
│ (Scraptik)  │     │ (Scraptik)  │
└──────┬──────┘     └──────┬──────┘
       │                    │
       └────────┬───────────┘
                │
        ┌───────▼───────┐
        │ Raw Post Dicts│  17-field STANDARD_POST_KEYS schema
        │ (~200 posts)  │  {post_id, platform, caption, views, ...}
        └───────┬───────┘
                │
        ┌───────▼───────┐
        │   Analyzer    │  Gemini Flash-Lite
        │ (Tier 1)      │  Adds: virality_score, composite_score,
        │               │  trend_type, audio_lifecycle, recommended_campus
        └───────┬───────┘
                │
        ┌───────▼───────┐
        │  Enriched     │  Original 17 fields + 8 analysis fields
        │ (10-15 posts) │  Filtered by ANALYZER_MIN_SCORE, sorted by composite_score
        └───────┬───────┘
                │
        ┌───────▼───────┐
        │Script Generator│  Claude Sonnet
        │ (Tier 2)       │  Split by recommended_campus
        │                │  Top SCRIPTS_PER_CAMPUS per bucket
        └───────┬────────┘
                │
        ┌───────▼───────┐
        │  Script Dicts │  {campus, trend_type, brief, source_url, generated_at}
        │  (6 scripts)  │  3 Arizona + 3 Cal Poly
        └───────┬───────┘
                │
        ┌───────▼───────┐
        │   Delivery    │  Telegram Bot API
        │               │  Arizona first → separator → Cal Poly
        └───────────────┘
```

## Campus Configuration

Campus context lives in `pipeline/knowledge_base.py` → `CAMPUS_CONTEXT` dict. Adding a new campus requires:

1. Add a new entry to `CAMPUS_CONTEXT` with `Campus`, `Local Signals`, and `Content Hooks`
2. Add the campus key to `SUPPORTED_CAMPUSES` tuple
3. Add campus-specific hashtags to `scrapers/_common.py` → `HASHTAG_SEEDS["campus_specific"]`

This data should be reviewed and updated regularly. The more specific and current the campus context, the better the scripts.

## Cron Schedule

Two daily runs, timed for peak posting windows across both campus timezones:

- **12:00 PM MST** — catches morning trends, scripts ready for afternoon posting
- **7:00 PM MST** — catches afternoon trends, scripts ready for evening posting

Arizona (MST) and Cal Poly (PST) are 1 hour apart, so both windows work well for both campuses.

## Cost Breakdown

| Component | Calls/Run | Runs/Day | Daily Calls | Cost |
|-----------|-----------|----------|-------------|------|
| Gemini Flash-Lite | 40-70 | 2 | 80-140 | Free |
| Claude Sonnet | 6 | 2 | 12 | ~$0.40-0.60 |
| RapidAPI/Scraptik | ~30 | 2 | ~60 | Free tier |
| **Monthly total** | | | | **~$12-18** |

## What's NOT in v1

- **Pinterest scraping** — planned for future, not prioritized
- **Standalone audio tracker** — audio lifecycle is tagged by Gemini, not tracked independently
- **Obsidian vault output** — Telegram delivery only for now
- **Local LLM (Ollama/Qwen)** — replaced by cloud API approach for reliability
- **Two-node Pi+Mac architecture** — consolidated to single Pi 5
- **Multiple Telegram channels** — single private channel, owner forwards manually
