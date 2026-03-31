# Architecture — Unigliss Trend Radar

## Two-Tier AI Hierarchy

The pipeline uses two AI tiers to balance cost and quality:

**Tier 1 — Gemini Flash-Lite (free)**
- High-volume preprocessing: up to 26 API calls per run
- Batches 5 posts per call for efficiency
- Returns structured JSON: virality score, trend classification, audio lifecycle, campus relevance
- Filters up to 130 scraped posts down to 10-15 top candidates
- Budget: 500 calls/run cap, well within 1,000/day free limit across 2 runs

**Tier 2 — Claude Sonnet (paid)**
- Low-volume creative generation: ~6 API calls per run
- Receives Gemini's top candidates + campus context from knowledge base
- Generates lean creative briefs (100-200 words) with Gen Z tone
- Up to 3 scripts per campus = up to 6 total per run
- Cost: ~$0.40-0.60/day ≈ $12-18/month

**Why two tiers?** Gemini is free but less creative. Sonnet is excellent at tone and format but costs money. By using Gemini to filter up to 130 posts down to up to 6, we minimize Sonnet calls while maximizing creative quality.

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
        │ (≤130 posts)  │  {post_id, platform, caption, views, ...}
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
        │ (≤6 scripts)  │  Up to 3 Arizona + up to 3 Cal Poly
        └───────┬───────┘
                │
        ┌───────▼───────┐
        │   Delivery    │  Telegram Bot API
        │               │  Arizona first → separator → Cal Poly
        └───────────────┘
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

## Cost Breakdown

| Component | Calls/Run | Runs/Day | Daily Calls | Cost |
|-----------|-----------|----------|-------------|------|
| Gemini Flash-Lite | 26 max | 2 | 52 max | Free |
| Claude Sonnet | 6 | 2 | 12 | ~$0.40-0.60 |
| RapidAPI/Scraptik | 20 max | 2 | 40 max | Free tier |
| **Monthly total** | | | | **~$12-18** |

## What's NOT in v1

- **Pinterest scraping** — planned for future, not prioritized
- **Standalone audio tracker** — audio lifecycle is tagged by Gemini, not tracked independently
- **Obsidian vault output** — Telegram delivery only for now
- **Local LLM (Ollama/Qwen)** — replaced by cloud API approach for reliability
- **Two-node Pi+Mac architecture** — consolidated to single Pi 5
- **Multiple Telegram channels** — single private channel, owner forwards manually
