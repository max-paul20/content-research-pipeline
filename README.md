# Unigliss Trend Radar v3 — Product Requirements Document

**Version:** 3.0  
**Author:** Claude (Software Architect) + Unc (Product Owner)  
**Date:** March 30, 2026  
**Status:** Pre-Development

---

## 1. Executive Summary

Trend Radar is a two-node content intelligence system that scrapes viral beauty and college lifestyle content from TikTok and Instagram, enriches it with hashtag co-occurrence analysis and trending audio data, then feeds everything into a locally-hosted LLM on a MacBook Air M2 via Ollama. The model — running a deeply-prompted Qwen 3 8B — produces campus-specific, algorithm-optimized creative briefs for Unigliss's central brand accounts (@unigliss.arizona, @unigliss.calpoly). All outputs land as structured markdown files in an Obsidian vault, forming a compounding knowledge graph over time.

The system supports two campuses at launch: University of Arizona (Tucson) and Cal Poly SLO. It tracks both macro beauty trends (what's blowing up nationally) and micro campus-specific signals (local hashtags, campus events, location-tagged content). Scripts blend both layers into hyper-relevant creative briefs that no generic tool can match.

---

## 2. System Architecture

### 2.1 Two-Node Design

```
┌─────────────────────────────────────────────────┐
│  NODE 1: Raspberry Pi 5 (The Scout)             │
│  Location: San Luis Obispo                      │
│  Runs: 24/7 headless on cron                    │
│                                                 │
│  ┌──────────────┐  ┌──────────────┐             │
│  │ TikTok       │  │ Instagram    │             │
│  │ Scraper      │  │ Scraper      │             │
│  │ (RapidAPI)   │  │ (RapidAPI)   │             │
│  └──────┬───────┘  └──────┬───────┘             │
│         │                 │                     │
│  ┌──────▼─────────────────▼──────┐              │
│  │ Data Collector & Enrichment   │              │
│  │ - Hashtag co-occurrence       │              │
│  │ - Audio metadata extraction   │              │
│  │ - Engagement velocity calc    │              │
│  │ - Campus-specific filtering   │              │
│  └──────────────┬────────────────┘              │
│                 │                               │
│  ┌──────────────▼────────────────┐              │
│  │ Raw Data Package (JSON)       │              │
│  │ → Push via Tailscale tunnel   │              │
│  └───────────────────────────────┘              │
└─────────────────────────────────────────────────┘
                    │
                    │ Tailscale (encrypted P2P)
                    ▼
┌─────────────────────────────────────────────────┐
│  NODE 2: MacBook Air M2 (The Brain)             │
│  Location: wherever Unc is                      │
│                                                 │
│  ┌───────────────────────────────┐              │
│  │ Ingestion Layer               │              │
│  │ - Receives raw JSON from Pi   │              │
│  │ - Validates & deduplicates    │              │
│  │ - Merges with Obsidian vault  │              │
│  └──────────────┬────────────────┘              │
│                 │                               │
│  ┌──────────────▼────────────────┐              │
│  │ Enrichment Layer              │              │
│  │ - Audio lifecycle tracking    │              │
│  │ - Trend velocity scoring      │              │
│  │ - Campus event calendar merge │              │
│  │ - Historical pattern matching │              │
│  └──────────────┬────────────────┘              │
│                 │                               │
│  ┌──────────────▼────────────────┐              │
│  │ Ollama (Qwen 3 8B / Q4_K_M)  │              │
│  │ + Deep system prompt          │              │
│  │ + Knowledge base injection    │              │
│  │ + Campus-specific context     │              │
│  └──────────────┬────────────────┘              │
│                 │                               │
│  ┌──────────────▼────────────────┐              │
│  │ Output: Obsidian Vault        │              │
│  │ - /scripts/ (creative briefs) │              │
│  │ - /trends/ (trend tracking)   │              │
│  │ - /audio/ (sound lifecycle)   │              │
│  │ - /campuses/ (local intel)    │              │
│  │ - /providers/ (profiles)      │              │
│  └───────────────────────────────┘              │
└─────────────────────────────────────────────────┘
```

### 2.2 Data Flow

1. **Pi scrapes** TikTok + Instagram every 6 hours via RapidAPI/Scraptik endpoints
2. **Pi enriches** raw data with hashtag analysis, audio metadata, engagement velocity
3. **Pi pushes** a JSON data package to Mac over Tailscale tunnel (SCP or lightweight HTTP POST)
4. **Mac ingestion layer** receives, validates, deduplicates, merges with historical vault data
5. **Mac enrichment layer** scores trends, tracks audio lifecycle, injects campus calendar events
6. **Ollama generates** creative briefs using enriched data + knowledge base + campus context
7. **Output lands** in Obsidian vault as structured markdown with YAML frontmatter

---

## 3. Scraping Layer (Pi)

### 3.1 Data Sources

| Source | Method | What We Pull | Frequency |
|--------|--------|-------------|-----------|
| TikTok trending | RapidAPI / Scraptik | Top trending posts, audio metadata, hashtag data | Every 6h |
| TikTok hashtag search | RapidAPI / Scraptik | Posts by campus-specific hashtags | Every 6h |
| TikTok audio/music | RapidAPI / Scraptik | Trending sounds, usage counts, lifecycle stage | Every 6h |
| Instagram Reels | RapidAPI / Scraptik | Trending Reels, audio, location-tagged posts | Every 6h |
| Instagram hashtag search | RapidAPI / Scraptik | Campus-specific hashtag content | Every 6h |

### 3.2 Scraping Targets

**Macro (national beauty/lifestyle) hashtags:**
- #beautytok, #nailsoftiktok, #lashtok, #hairtok
- #grwm, #getreadywithme, #makeuptutorial
- #cleangirlasthetic, #thatgirl, #hotgirlwalk
- #collegelife, #sorority, #gameday
- #nailart, #gelnails, #chromenails, #frenchnails

**Micro (University of Arizona) hashtags:**
- #uofa, #universityofarizona, #beardown, #wildcats
- #tucson, #tucsonnails, #tucsonbeauty, #tucsonlashes
- #uarizona, #wildcatbeauty, #uofagreeklife
- #maingate, #universityblvd, #4thave

**Micro (Cal Poly SLO) hashtags:**
- #calpoly, #calpolyslo, #slo, #sanluisobispo
- #slobeauty, #slonails, #calpolygreeklife
- #mustangs, #cpmustangs, #downtownslo
- #higuera, #bishoppeak, #montanadeoro

**Competitor / inspiration accounts to monitor:**
- Top beauty creators in Tucson (identified by location tags)
- Top beauty creators in SLO (identified by location tags)
- National beauty marketplace accounts (StyleSeat, Booksy, GlossGenius)

### 3.3 Audio Tracking Module

This is a dedicated sub-system within the scraper. For every trending post scraped, the audio metadata is extracted and tracked separately.

**Audio data points collected:**
- Audio ID (platform-specific)
- Audio title and artist
- Current usage count (how many videos use this sound)
- Usage velocity (growth rate over 6h intervals)
- Audio duration
- Audio category (original sound, commercial music, remix, voiceover)
- Platform of origin (TikTok-native vs migrated from IG, or vice versa)

**Audio lifecycle classification (computed on Mac):**
- **Emerging** (< 5K uses, high velocity): catch-early opportunity
- **Rising** (5K–50K uses, sustained velocity): best window for engagement
- **Peak** (50K–500K uses, velocity plateauing): still viable, getting crowded
- **Saturated** (500K+ uses or velocity declining): too late for maximum impact
- **Long-form compatible** flag: sounds > 30 seconds suitable for 60–90+ sec content
- **Beat-switch timestamp**: if the audio has a notable transition point (for editing)

### 3.4 Open-Source Tooling on Pi

These tools run on the Pi to enrich raw scrape data before sending to Mac:

| Tool | GitHub | Purpose | Stars |
|------|--------|---------|-------|
| bellingcat/tiktok-hashtag-analysis | github.com/bellingcat/tiktok-hashtag-analysis | Hashtag co-occurrence analysis, frequency plotting, batch scraping | ~350 |
| davidteather/TikTok-Api | github.com/davidteather/TikTok-Api | Unofficial TikTok API wrapper — user, hashtag, trending, music, sound endpoints | 6.1K |
| drawrowfly/tiktok-scraper | github.com/drawrowfly/tiktok-scraper | CLI scraper for user/hashtag/trend/music feeds with batch mode | N/A |
| Q-Bukold/TikTok-Content-Scraper | github.com/Q-Bukold/TikTok-Content-Scraper | No-API-key scraper, 90+ metadata elements, SQLite progress tracking | N/A |

**Note on feasibility:** TikTok's anti-scraping measures in 2026 are aggressive. Direct scraping via open-source tools often requires browser automation (Playwright), cookies, and proxy rotation. RapidAPI/Scraptik endpoints abstract this away and are the primary scraping method. The open-source tools above serve as:
- Supplementary data enrichment (especially bellingcat for hashtag co-occurrence)
- Fallback if API endpoints have issues
- Research tools for initial campus hashtag discovery

**Recommended primary approach:** RapidAPI/Scraptik for reliable data, bellingcat tool for hashtag analysis enrichment, davidteather/TikTok-Api for sound/music metadata when Scraptik doesn't cover it.

---

## 4. Enrichment & Analysis Layer (Mac)

### 4.1 Trend Scoring Engine

Every scraped post gets a composite score based on platform-specific algorithm signals:

**TikTok Virality Score (0–100):**
- Share-to-view ratio (weight: 35%) — shares are king in 2026 TikTok
- Save-to-view ratio (weight: 20%)
- Comment quality signal (weight: 15%) — longer comments weighted higher
- Completion rate proxy (weight: 20%) — estimated from duration vs engagement
- Like-to-view ratio (weight: 5%) — nearly worthless signal
- Recency bonus (weight: 5%) — posts < 6h old get boosted

**Instagram Reels Virality Score (0–100):**
- Send/share-to-reach ratio (weight: 35%) — DM shares are 3–5x more valuable
- Save-to-reach ratio (weight: 25%) — saves weighted ~3x more than likes
- Watch time proxy (weight: 25%) — derived from engagement patterns
- Like-to-reach ratio (weight: 10%)
- Recency bonus (weight: 5%)

### 4.2 Campus Event Calendar Integration

Maintained as a JSON file, manually updated (or scraped from university event pages later).

```json
{
  "uofa": {
    "events": [
      {"date": "2026-09-05", "name": "First day of classes", "content_angle": "back-to-school looks"},
      {"date": "2026-09-12", "name": "Football home opener", "content_angle": "game day nails, red/blue themes"},
      {"date": "2026-10-01", "name": "Homecoming week", "content_angle": "homecoming glam, group content"},
      {"date": "2026-10-31", "name": "Halloween", "content_angle": "halloween nails, costume makeup"},
      {"date": "2026-11-29", "name": "Territorial Cup (vs ASU)", "content_angle": "rivalry game day content"},
      {"date": "2026-01-15", "name": "Rush/recruitment week", "content_angle": "rush outfits, first impression nails"}
    ],
    "greek_life": ["Alpha Phi", "Kappa Kappa Gamma", "Pi Beta Phi", "Chi Omega", "Gamma Phi Beta"],
    "landmarks": ["Old Main", "UA Mall fountain", "Bear Down Gym", "Main Gate Square", "4th Avenue", "University Blvd"],
    "local_beauty_context": "Full glam culture. High demand for lash extensions, acrylic nails, spray tans. Greek life drives beauty spend. Hot weather means sweat-proof everything. Game day is a major content moment.",
    "weather_profile": "Hot and dry. 100°F+ in early fall. Mild winters. Monsoon season July-Sept."
  },
  "calpoly": {
    "events": [
      {"date": "2026-09-21", "name": "WOW Week (orientation)", "content_angle": "new student looks, campus exploration"},
      {"date": "2026-10-15", "name": "Homecoming", "content_angle": "school spirit, green/gold themes"},
      {"date": "2026-02-01", "name": "Open House", "content_angle": "campus showcase content"},
      {"date": "2026-05-01", "name": "Rose Float reveal", "content_angle": "end-of-year celebration content"}
    ],
    "greek_life": ["Alpha Phi", "Kappa Alpha Theta", "Delta Delta Delta", "Chi Omega"],
    "landmarks": ["Dexter Lawn", "Bishop Peak", "Montana de Oro", "Downtown Higuera St", "Bubblegum Alley", "Avila Beach", "Pismo Beach"],
    "local_beauty_context": "Effortless California coastal vibe. Less full-glam, more natural beauty with pops of color. Nails are big but styles lean minimalist/clean. Outdoor lifestyle means low-maintenance beauty that photographs well. Beach and hiking content opportunities.",
    "weather_profile": "Mediterranean climate. 70s most of year. Foggy mornings. Cool evenings. No extreme heat."
  }
}
```

### 4.3 Historical Pattern Matching (Obsidian-Powered)

Over time, the vault accumulates data on what works. Before generating a new script, the system queries the vault for:
- Previous scripts that used similar trends (by tag)
- Audio that has performed well at this campus before
- Content types that got the most engagement (by YAML metadata)
- Seasonal patterns (what worked this time last year)

This is a v2 feature but the vault structure is designed for it from day one.

---

## 5. AI Script Generation (Ollama)

### 5.1 Model Selection

**Primary: Qwen 3 8B (Q4_K_M quantization)**

Rationale based on research:
- Best all-rounder for 8B class models in 2026 on Apple Silicon
- Runs at ~30–50 tokens/second on M2 MacBook Air at Q4_K_M
- Strong instruction following and structured output
- Fits comfortably in 8GB unified memory (model file ~5GB, leaves headroom)
- /think mode available for chain-of-thought when analyzing complex trends

**Backup: Llama 3.1 8B**
- If Qwen 3 has issues with the specific prompt structure
- Slightly less capable but more battle-tested

**Future upgrade path:**
- Once real performance data exists (which scripts → which videos → which engagement), fine-tune a LoRA adapter on winning scripts
- Move to Qwen 3 14B if Mac memory allows (would need ~10GB)

### 5.2 System Prompt Architecture

The system prompt is the single most important piece of the system. It has four layers:

**Layer 1 — Identity & Role:**
```
You are a beauty content strategist for Unigliss, a peer-to-peer beauty services marketplace launching at college campuses. You specialize in creating viral short-form video concepts that blend trending content with hyper-local campus culture. You think like a 20-year-old college girl who is also a data scientist — you understand both the vibe and the algorithm.
```

**Layer 2 — Algorithm Knowledge Base:**
(Full TikTok 2026 algorithm intelligence + Instagram Reels 2026 algorithm intelligence — same content as knowledge_base.py from v2, injected here)

**Layer 3 — Campus Context:**
(Dynamically injected per-campus: landmarks, events, Greek life, weather, beauty culture, local hashtags)

**Layer 4 — Output Format:**
(Strict markdown template the model must follow — see section 5.3)

### 5.3 Script Output Format

Every generated script follows this exact structure, output as a markdown file:

```markdown
---
type: creative-brief
campus: uofa
trend_source: tiktok
trend_category: macro+micro
audio_primary: "original sound - @username"
audio_primary_lifecycle: rising
audio_secondary: null
date_generated: 2026-03-30
content_bucket: trend-driven
video_length: short
tags: [chrome-nails, game-day, tutorial]
---

# Chrome Game Day Nails — 15s Tutorial

## Trend Context
Chrome nails are surging nationally (+340% in 7 days on TikTok). U of A has a 
home football game this Saturday. No one on #uofa or #tucsonbeauty has done a 
chrome + school colors combo yet. First-mover opportunity.

## The Brief
**Hook (first 3 seconds):** Close-up of plain nails → camera pulls back to 
reveal a full chrome red-and-blue set. Text overlay: "pov: your nail tech 
understood the assignment"

**Beat 1:** Quick transition to the filing/prep stage. Keep it satisfying — 
ASMR-adjacent nail sounds work well here.

**Beat 2:** Chrome powder application. This is the money shot. Slow it down 
slightly. The shimmer catches light.

**Beat 3:** Final reveal with hand posed against something recognizably U of A 
— a Wildcats jersey, a Bear Down sign, Main Gate in the background.

**Unigliss Moment:** Text overlay on the final reveal: "my unigliss girl never 
misses" — casual, not a pitch. Don't say it out loud.

**CTA (end screen or caption):** "link in bio if you want nails like this for 
Saturday 🏈" — drives to Unigliss booking page.

## Audio
**Primary:** [Sound name] — currently at ~12K uses, rising phase. The beat 
switch at 0:08 is perfect for the chrome reveal transition.  
**Alternative for longer version:** [Ambient sound name] if extending to 60s 
tutorial format.

## Posting Details
- **Best time:** Thursday 6–8 PM (pre-game-day engagement window)
- **Platforms:** TikTok first, Instagram Reel 24h later (remove TikTok watermark)
- **Hashtags (TikTok):** #chromenails #gamedaynails #uofa #beardown #tucsonbeauty
- **Hashtags (Instagram):** #chromenails #gamedaynails #uofabeauty #wildcatnails
- **Location tag:** University of Arizona (TikTok), Tucson, Arizona (IG)

## Pro Tips
- Film at Main Gate Square or University Blvd for recognizable background
- Chrome powder application is inherently satisfying — lean into the ASMR angle
- Post a "which color for game day?" poll story 24h before to build anticipation
- This could also work as a provider spotlight (bucket 2) if the nail tech is on Unigliss

## Referral Integration
If the client who gets these nails posts about it:
- They use their referral code in the caption
- 3 friends sign up = $5 reward
- The client's post becomes organic user-generated content (bucket 3)
```

### 5.4 Content Buckets (Blended)

Every script gets tagged with one or more content buckets. The model is instructed to blend buckets when natural:

| Bucket | Description | Example |
|--------|-------------|---------|
| **Trend-driven** | Riding a macro or micro trend | Chrome nails tutorial using trending sound |
| **Provider spotlight** | Showcasing a service provider's work | "Watch Sarah do a full set" — also uses a trending format |
| **Social proof** | Client transformations, referral content | Before/after that also uses a trending sound and tags the campus |

The model is told: "Always look for opportunities to blend buckets. A provider spotlight that uses a trending sound and references a campus event is worth 3x a single-bucket script."

---

## 6. Obsidian Vault Structure

```
unigliss-vault/
├── README.md
├── _templates/
│   ├── creative-brief.md          # Template for generated scripts
│   ├── trend-note.md              # Template for trend tracking
│   ├── audio-note.md              # Template for audio lifecycle
│   └── provider-profile.md        # Template for provider profiles
├── scripts/
│   ├── uofa/                      # U of A creative briefs
│   │   ├── 2026-03-30-chrome-game-day-nails.md
│   │   └── ...
│   └── calpoly/                   # Cal Poly creative briefs
│       ├── 2026-03-30-coastal-clean-girl-nails.md
│       └── ...
├── trends/
│   ├── macro/                     # National beauty trends
│   │   ├── chrome-nails.md        # Linked to scripts that use this trend
│   │   └── clean-girl-aesthetic.md
│   └── micro/                     # Campus-specific trends
│       ├── uofa-game-day-beauty.md
│       └── calpoly-beach-day-looks.md
├── audio/
│   ├── trending-sounds-log.md     # Running log of all tracked sounds
│   ├── original-sound-xyz.md      # Individual audio notes with lifecycle
│   └── ...
├── campuses/
│   ├── uofa/
│   │   ├── campus-intel.md        # Events, landmarks, culture
│   │   ├── hashtag-performance.md # Which hashtags are working
│   │   └── local-creators.md      # Creators to watch/collaborate with
│   └── calpoly/
│       ├── campus-intel.md
│       ├── hashtag-performance.md
│       └── local-creators.md
├── providers/
│   ├── provider-name.md           # Individual provider profiles
│   └── ...
├── data/
│   ├── raw/                       # Raw JSON from Pi (archived)
│   ├── processed/                 # Enriched data post-analysis
│   └── performance/               # Video performance tracking (manual for now)
└── config/
    ├── campus-events.json         # Event calendar
    ├── hashtag-targets.json       # Scraping targets
    └── system-prompt.md           # The full system prompt (version controlled)
```

### 6.1 YAML Frontmatter Schema

Every note type has mandatory YAML frontmatter that enables Obsidian's Dataview plugin to query across the vault:

**Creative Brief:**
```yaml
type: creative-brief
campus: uofa | calpoly
trend_source: tiktok | instagram | both
trend_category: macro | micro | macro+micro
audio_primary: "sound name"
audio_primary_lifecycle: emerging | rising | peak | saturated
content_bucket: [trend-driven, provider-spotlight, social-proof]
video_length: short | medium | long
date_generated: 2026-03-30
was_filmed: false        # Updated manually
video_url: null           # Updated manually
performance_views: null   # Updated manually
performance_likes: null   # Updated manually
performance_shares: null  # Updated manually
tags: [chrome-nails, game-day, tutorial]
```

**Audio Note:**
```yaml
type: audio
audio_id: "platform_id"
title: "sound name"
artist: "creator"
platform_origin: tiktok | instagram
lifecycle: emerging | rising | peak | saturated
usage_count: 12000
velocity: +3400/6h
long_form_compatible: true
beat_switch_timestamp: "0:08"
first_seen: 2026-03-28
scripts_using: [[chrome-game-day-nails]]
```

---

## 7. Communication Layer (Tailscale)

### 7.1 Setup Requirements

- Tailscale already installed on MacBook
- Tailscale needs to be installed on Pi (once WiFi is fixed)
- Both devices join the same Tailnet
- Pi gets a stable Tailscale IP (e.g., 100.x.x.x)

### 7.2 Data Transfer Protocol

**Pi → Mac (every 6 hours after scrape completes):**

```bash
# On Pi, after scrape completes:
scp /home/maxdabeast124/unigliss-radar/data/latest-scrape.json \
    unc@100.x.x.x:~/unigliss-vault/data/raw/$(date +%Y-%m-%d-%H%M).json
```

**Mac pull (alternative, triggered manually or on schedule):**

```bash
# On Mac, pull latest from Pi:
scp maxdabeast124@100.x.x.x:~/unigliss-radar/data/latest-scrape.json \
    ~/unigliss-vault/data/raw/$(date +%Y-%m-%d-%H%M).json
```

### 7.3 Future: Lightweight API

Eventually, Pi runs a tiny Flask/FastAPI server on its Tailscale IP. Mac hits the endpoint to pull data on demand. This enables the Mac-side orchestrator to trigger scrapes, check status, and pull data programmatically. But SCP is fine for v1.

---

## 8. Referral Content Engine

### 8.1 The Flywheel

```
Service provider does appointment
        ↓
Client posts content about it (organic)
        ↓
Client includes referral code in caption
        ↓
3 friends sign up via code → client gets $5
        ↓
Those 3 friends book appointments
        ↓
They post content → more referrals
        ↓
(cycle repeats)
```

### 8.2 Referral Content Templates

The system generates not just scripts for the central account, but also lightweight posting templates for clients:

```markdown
---
type: referral-template
campus: uofa
service: nails
---

# Post-Appointment Content Template

## For the client to post:

**Caption option 1 (casual):**
"obsessed with my new set 💅 [provider name] is insane — found her on unigliss 
btw. use my code [CODE] if you want to book her, you literally won't regret it"

**Caption option 2 (transformation):**
"the before vs after is CRIMINAL 😭 if you need nails in tucson go to 
[provider name] on unigliss. code [CODE] gets you in"

**Posting tips:**
- Film a 5-second hand reveal with good lighting
- Tag your location (University of Arizona or Tucson)
- Use hashtags: #tucsonbeauty #uofanails #nailsoftiktok
- Post within 2 hours of appointment (fresh nails photograph best)
```

---

## 9. File Structure (Codebase)

```
unigliss-radar/
├── pi/                              # Runs on Raspberry Pi
│   ├── main.py                      # Orchestrator: scrape → enrich → push
│   ├── config.py                    # API keys, endpoints, campus configs
│   ├── scrapers/
│   │   ├── __init__.py
│   │   ├── tiktok.py                # TikTok scraping via RapidAPI
│   │   ├── instagram.py             # Instagram scraping via RapidAPI
│   │   └── audio.py                 # Dedicated audio/sound tracker
│   ├── enrichment/
│   │   ├── __init__.py
│   │   ├── hashtag_analyzer.py      # Co-occurrence analysis (bellingcat-inspired)
│   │   ├── engagement_scorer.py     # Platform-specific virality scoring
│   │   └── deduplicator.py          # Seen-post tracking, cache management
│   ├── transport/
│   │   ├── __init__.py
│   │   └── push_to_mac.py           # SCP/API push over Tailscale
│   ├── data/
│   │   ├── seen_posts.json          # Cache of already-processed post IDs
│   │   └── audio_history.json       # Audio usage count history for velocity calc
│   ├── logs/
│   ├── requirements.txt
│   ├── .env.template
│   └── setup_pi.sh                  # One-command Pi setup
│
├── mac/                             # Runs on MacBook Air M2
│   ├── main.py                      # Orchestrator: ingest → enrich → generate → output
│   ├── config.py                    # Ollama settings, vault paths, campus configs
│   ├── ingestion/
│   │   ├── __init__.py
│   │   └── receiver.py              # Watches for new data from Pi, validates
│   ├── enrichment/
│   │   ├── __init__.py
│   │   ├── audio_lifecycle.py       # Classifies audio lifecycle stage
│   │   ├── trend_scorer.py          # Composite trend scoring
│   │   ├── campus_context.py        # Injects campus events, weather, culture
│   │   └── vault_query.py           # Queries Obsidian vault for historical patterns
│   ├── generation/
│   │   ├── __init__.py
│   │   ├── ollama_client.py         # Ollama API wrapper
│   │   ├── prompt_builder.py        # Assembles the 4-layer system prompt
│   │   ├── script_generator.py      # Generates creative briefs
│   │   └── referral_templates.py    # Generates referral content templates
│   ├── output/
│   │   ├── __init__.py
│   │   ├── markdown_writer.py       # Writes structured .md files with YAML frontmatter
│   │   └── vault_organizer.py       # Places files in correct Obsidian folders
│   ├── knowledge/
│   │   ├── tiktok_algorithm.md      # TikTok 2026 algorithm intelligence
│   │   ├── instagram_algorithm.md   # Instagram 2026 algorithm intelligence
│   │   └── content_strategy.md      # Unigliss content strategy principles
│   ├── requirements.txt
│   └── .env.template
│
├── shared/
│   ├── campus_events.json           # Event calendars for all campuses
│   ├── hashtag_targets.json         # Scraping targets per campus
│   └── scoring_weights.json         # Algorithm-specific engagement weights
│
└── docs/
    ├── PRD.md                       # This document
    ├── SETUP.md                     # Full setup guide
    └── TROUBLESHOOTING.md
```

---

## 10. API Keys & External Dependencies

| Service | Purpose | Tier | Cost | Rate Limits |
|---------|---------|------|------|-------------|
| RapidAPI / Scraptik | TikTok + Instagram scraping | Free | $0 | ~500 req/day |
| Ollama (local) | LLM inference | N/A | $0 | Unlimited (local) |
| Tailscale | Pi ↔ Mac encrypted tunnel | Free (personal) | $0 | Unlimited |
| Obsidian | Knowledge vault | Free | $0 | N/A |

**No Gemini API needed.** No Telegram bot needed. The entire system runs on free tiers + local compute.

---

## 11. Development Phases

### Phase 1: Foundation (Week 1)

- [ ] Install Ollama on Mac, pull Qwen 3 8B, test basic prompting
- [ ] Create Obsidian vault structure with templates
- [ ] Build Mac-side script generator with hardcoded test data (no Pi needed)
- [ ] Iterate on system prompt until script quality is dialed
- [ ] Set up campus event calendars and hashtag target lists

### Phase 2: Pi Scraping (Week 2)

- [ ] Fix Pi WiFi connectivity at SLO location
- [ ] Install Tailscale on Pi, verify Mac ↔ Pi tunnel
- [ ] Build Pi scraping layer (TikTok + Instagram via RapidAPI)
- [ ] Build audio tracking module
- [ ] Build hashtag co-occurrence analyzer
- [ ] Test scraping on both campus hashtag sets
- [ ] Build SCP push script

### Phase 3: Integration (Week 3)

- [ ] Connect Pi output → Mac ingestion layer
- [ ] Build trend scoring engine
- [ ] Build audio lifecycle classifier
- [ ] Wire enriched data into Ollama prompt builder
- [ ] End-to-end test: scrape → enrich → generate → Obsidian

### Phase 4: Optimization (Week 4+)

- [ ] Refine system prompt based on output quality
- [ ] Add campus event calendar integration
- [ ] Build referral content template generator
- [ ] Set up cron on Pi for automated 6-hour cycles
- [ ] Add vault query layer for historical pattern matching
- [ ] Manual feedback loop: tag scripts that get filmed, record performance

---

## 12. Success Metrics

| Metric | Target | How Measured |
|--------|--------|-------------|
| Scripts generated per day | 4–8 (across both campuses) | Count files in Obsidian |
| Script-to-filmed ratio | > 50% (of generated scripts actually get filmed) | Manual tracking |
| Average views per video | > 1,000 within first 48h | Manual tracking in vault |
| Trending audio catch rate | > 70% of scripts use audio in rising phase | YAML metadata analysis |
| Time from trend emergence to script | < 12 hours | Timestamp comparison |
| Referral signups per content piece | > 0.5 average | Unigliss app data |

---

## 13. Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| RapidAPI/Scraptik rate limits or downtime | No new scrape data | Cache last 48h of data; generate scripts from cached trends |
| TikTok blocks scraping endpoints | Core data source lost | Multiple API providers on RapidAPI; fallback to manual trend identification |
| Ollama output quality inconsistent | Bad scripts waste creator time | Aggressive prompt engineering; human review before filming |
| Pi WiFi drops at SLO location | Scraping stops | Tailscale reconnects automatically; set up cron health checks |
| Audio trends move faster than 6h cycle | Miss the window | Add "fast-track" mode that Unc can trigger manually for urgent trends |
| Qwen 3 8B isn't creative enough | Scripts feel generic | Test Llama 3.1 8B as alternative; upgrade to 14B if Mac memory allows |

---

## 14. Open Questions

1. **Mac always-on?** — If the Mac sleeps, the generation pipeline pauses. Options: set Mac to stay awake, or batch-process when Unc opens it each morning.
2. **Content calendar cadence** — How many posts per week per campus account? This determines how many scripts need to be generated vs. stockpiled.
3. **Provider recruitment** — When do we start onboarding providers to Unigliss? Scripts can be generated now but filming requires people.
4. **Instagram scraping scope** — Should we also track Instagram Stories mentions of campus hashtags, or just Reels?
5. **Pinterest timeline** — When does Pinterest get added as a third scraping source?

---

## 15. Glossary

| Term | Definition |
|------|-----------|
| **Macro trend** | A beauty or content trend trending nationally across all of TikTok/Instagram |
| **Micro trend** | A trend specific to a campus, city, or local creator community |
| **Audio lifecycle** | The stages a trending sound goes through: emerging → rising → peak → saturated |
| **Creative brief** | The output script — a structured guide for filming a video |
| **Content bucket** | One of three categories: trend-driven, provider spotlight, social proof |
| **Engagement velocity** | The rate of change in engagement metrics over time (not just total count) |
| **The Scout** | Raspberry Pi 5 — scrapes and enriches data |
| **The Brain** | MacBook Air M2 — runs Ollama and generates scripts |
| **The Vault** | Obsidian knowledge base — stores everything, compounds over time |
