# Unigliss Trend Radar — Build Progress

**Last updated:** 2026-03-31  
**Total tests:** 66 passing, 0 failing

---

## Files Built

### `pipeline/knowledge_base.py`
LLM system prompt assembler. Centralizes all TikTok 2026 and Instagram Reels 2026 algorithm
intelligence, Unigliss brand guardrails, and campus context for UofA and Cal Poly SLO.

Public API:
- `get_analyzer_prompt(campus=None)` — builds the viral content analysis prompt
- `get_script_generator_prompt(campus=None, output_mode="brief"|"telegram")` — builds the creative brief generation prompt

Both functions are provider-neutral (Gemini, Ollama, or any future LLM).

---

### `pipeline/config.py`
Central configuration and environment loader. Reads from `.env`, exposes all runtime
constants (API keys, endpoints, scrape limits, Gemini model, directory paths), and provides
explicit validation.

Key exports: `GEMINI_API_KEY`, `RAPIDAPI_KEY`, `TELEGRAM_*`, `TIKTOK_ENDPOINTS`,
`INSTAGRAM_ENDPOINTS`, `SCRAPE_LIMIT`, `SEEN_POSTS_FILE`, `DATA_DIR`, `LOG_DIR`,
`validate_config()`, `is_test_mode()`

---

### `pipeline/scrapers/_common.py`
Shared helpers for all platform scrapers. Contains the standardized post schema, all
normalization utilities, and the dedup engine.

Key exports:
- `STANDARD_POST_KEYS` — the 17-field schema every scraper output must match
- `normalize_timestamp()` — handles Unix seconds/ms, ISO with offset, string digits
- `safe_int()` — coerces any numeric-ish value to int, returns 0 on failure
- `extract_items()` — unwraps variable API payload shapes into a flat list of dicts
- `load_seen_posts()` / `save_seen_posts()` — dedup cache persistence
- `dedupe_posts()` — filters already-seen posts, updates velocity tracking
- `select_rotating_hashtags()` — returns a deterministic, rotating hashtag slice per run

---

### `pipeline/scrapers/tiktok.py`
TikTok scraping entry point. Hits the trending feed and a rotating batch of 9 hashtags
per run via Scraptik/RapidAPI. Normalizes raw API items into `STANDARD_POST_KEYS` schema,
filters by relevance, deduplicates, and persists seen-post state.

- `scrape_tiktok(test_mode=False)` — production scrape or mock data
- `get_mock_posts()` — 6 realistic posts covering both UofA and Cal Poly themes

---

### `pipeline/scrapers/instagram.py`
Instagram Reels scraping entry point. Mirrors TikTok structure: hits the Reels feed and
rotating hashtag batches. Handles Instagram-specific field shapes (nested `caption.text`,
`clips_music_attribution_info`, `play_count`, etc.).

- `scrape_instagram(test_mode=False)` — production scrape or mock data
- `get_mock_posts()` — 6 realistic posts covering both campuses

---

### `pipeline/scrapers/__init__.py`
Clean re-export of all four public scraper functions. No circular imports.

---

## Test Counts

| File | Tests |
|---|---|
| `tests/test_knowledge_base.py` | 8 |
| `tests/test_config.py` | 10 |
| `tests/test_scrapers.py` | 48 |
| **Total** | **66** |

---

## Bugs Found and Fixed This Session

### Session 1 — `config.py` / `test_config.py`

**Bug: `reload_config()` leaked real `.env` values into tests**
`patch.dict(os.environ, ..., clear=True)` cleared the environment but `importlib.reload`
still triggered `load_dotenv(ENV_FILE)` inside the module. A developer with a populated
`.env` file would see `test_default_values_are_sane` fail on values like `GEMINI_MODEL`.
Fixed by adding `with patch("dotenv.load_dotenv")` inside `reload_config()`.

**Gap: only 2 of 9 placeholder patterns were tested**
`test_validate_config_catches_missing_and_placeholder_keys` only tested `"your-key-here"`
and `"REPLACE_ME"`. Added `test_all_placeholder_patterns_are_caught` covering all 9 entries
in `_PLACEHOLDER_VALUES` plus case variants and padded-whitespace variants.

**Gaps: missing default and behavioral coverage**
Added: `DRY_RUN`/`TEST_MODE` defaults in `test_default_values_are_sane`; explicit assertion
that `TEST_MODE` produces `"skipped (TEST_MODE enabled)"` for every required key; endpoint
dict key structure; invalid int/float env vars falling back to defaults.

**Gap: `.env.template` missing 8 optional override keys**
`GEMINI_MODEL`, `GEMINI_API_ENDPOINT`, `RAPIDAPI_BASE_URL`, and all 5 `SCRAPTIK_*` endpoint
path overrides existed in `config.py` but were invisible to any developer setting up the
project. Added as commented entries with defaults shown.

---

### Session 2 — `_common.py` / `tiktok.py` / `instagram.py` / `test_scrapers.py`

**Bug: `safe_int(float('inf'))` raised `OverflowError` and crashed the scrape run**
Both `except` clauses in `safe_int` caught `TypeError, ValueError` but not `OverflowError`.
`int(float('inf'))` raises `OverflowError`. Any API response with an astronomical numeric
value would crash the entire run instead of returning `0`. Fixed by adding `OverflowError`
to both `except` clauses in `_common.py`.

**Bug: `_API_KEY_PLACEHOLDERS` in both scrapers was a strict subset of `config._PLACEHOLDER_VALUES`**
Both `tiktok.py` and `instagram.py` defined `_API_KEY_PLACEHOLDERS` with only 4 entries.
`config._PLACEHOLDER_VALUES` has 11. The 7 missing patterns (`"null"`, `"none"`,
`"changeme"`, `"todo"`, `"your-token-here"`, `"your-bot-token"`, `"your-channel-id"`) were
already caught correctly by `validate_config()`, but both scrapers would proceed to make
real API calls with those values as the key. `RAPIDAPI_KEY=null` is a common mistake when
`.env` is edited with a YAML mindset. Fixed by expanding both sets to cover the full list.

**Gaps: 25 tests → 66 tests added across 7 new test classes**
New coverage: `safe_int` overflow/infinity values; all placeholder patterns in both scrapers;
429 rate-limit response returns `[]` and does not write `seen_posts.json`; first-run with
nonexistent cache file; corrupt JSON and list-shaped cache gracefully return `{}`; deep
parent directory creation on save; full roundtrip load→save→load; 8 `normalize_timestamp`
formats (Unix s/ms, ISO Z, timezone offset → UTC, date-only, string digits, garbage);
`extract_items` across 9 payload shapes; `_normalize_post` with real Scraptik field shapes
for both platforms; missing `post_id` → `None`; all-missing fields safe defaults; URL
fallback construction; dedup skip on malformed post with missing ID; ISO Z timestamp
enforcement on all mock posts; full hashtag rotation coverage across the complete period.

---

## What's Next to Build

The PRD (README.md) defines a 4-phase build. The Mac-side pipeline is the current focus.

### Phase 1 — Mac Script Generator (no Pi required)

**`pipeline/analyzer.py`**
Takes a list of standardized posts (from mock data or real scrape), scores them using
TikTok and Instagram virality weights from the PRD, and returns a ranked, enriched list
ready for the script generator. Inputs: `List[Dict]` from scrapers. Outputs: same schema
with added `virality_score` field.

**`pipeline/generator.py`**
Builds a prompt from `knowledge_base.get_script_generator_prompt()`, injects the top-scored
posts as user-turn context, calls Gemini (or Ollama), and returns the raw markdown brief.
Inputs: enriched post list + campus + output_mode. Outputs: markdown string.

**`pipeline/delivery.py`**
Sends generated briefs to the configured Telegram channels. Review channel gets all output;
creator channel gets only approved briefs (manual gate for now). Inputs: markdown string.
Outputs: Telegram message ID or None on failure.

**`pipeline/main.py`**
Orchestrator. Calls `scrape_tiktok` + `scrape_instagram` → `analyzer` → `generator` →
`delivery`. Supports `--dry-run`, `--test-mode`, `--campus`, `--check` (runs
`validate_config()` and exits). This is the entry point the cron job will call.

### Phase 2 — Pi Scraping Layer (requires Pi WiFi fix + Tailscale)

Build `pi/scrapers/` (same Scraptik endpoints, different host), audio metadata tracker,
hashtag co-occurrence enrichment (bellingcat tool wrapper), and `push_to_mac.py` (SCP over
Tailscale). The Pi output format must match `STANDARD_POST_KEYS` exactly so the Mac
ingestion layer needs no translation.

### Phase 3 — Integration

Wire Pi output into the Mac ingestion layer. Add audio lifecycle classification, trend
velocity scoring against historical data, and campus event calendar injection.

### Phase 4 — Obsidian Vault Output

Replace or supplement Telegram delivery with structured `.md` file output to the Obsidian
vault. YAML frontmatter must match the schema defined in the PRD (section 6.1).
