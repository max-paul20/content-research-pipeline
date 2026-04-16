# Unigliss Trend Radar — Build Progress

**Last updated:** 2026-04-16
**Total tests:** 228 passing, 0 failing

---

## Pre-Refactor Audit — 2026-04-16 (feat/multi-agent-architecture)

Grounding snapshot before the multi-agent refactor. Recorded so the implementation matches real code, not plan assumptions.

**(a) http_utils surface**
- Single public helper: `request_with_retries(requester, *, service, operation, logger) -> requests.Response | None`.
- No Gemini- or Claude-specific wrapper exists. Every caller builds a `lambda: requests.post(...)` and passes it in. New agents will follow the same pattern — no new HTTP module, no SDK.

**(b) current `analyze_posts` output shape**
- Returns `List[Dict[str, Any]]`, each dict = original `STANDARD_POST_KEYS` + analysis fields (`virality_score`, `engagement_velocity`, `trend_type`, `virality_reason`, `audio_lifecycle`, `relevance_score`, `recommended_campus`) + `composite_score`.
- NOT a dict. `script_generator.generate_scripts` consumes this list directly.

**(c) `generate_scripts` signature**
- `generate_scripts(analyzed_posts: List[Dict[str, Any]], test_mode: bool = False, target_campus: str | None = None) -> List[Dict[str, Any]]`.
- Must keep receiving the ranked-posts list — not the new enriched dict.

**(d) `deliver_scripts` signature**
- `deliver_scripts(scripts: List[Dict[str, Any]], test_mode: bool = False, *, include_details: bool = False) -> Dict[str, Any]`.
- Accepts only a list of script dicts formatted via `_format_message` (expects `campus`, `brief`, `source_url`, `generated_at`). It cannot natively carry a free-form report.
- Plan-consistent mitigation: add a small additive `deliver_report(report, test_mode=...)` helper in `delivery.py` that sends one Telegram message. This is the minimal modification to a "preserved" file.

**(e) test count**
- 155 tests pass locally on `main`. Baseline for Phase 5.

**(f) plan assumptions contradicted by code**
1. Plan names separate "http_utils Gemini helper" and "http_utils Claude helper". Reality: one generic `request_with_retries`. Agents + report writer/verifier will build callables inline, same shape as `analyzer.py` and `script_generator.py` do today.
2. Plan treats `enriched` as a single dict that flows into both the report writer and `script_generator`. Reality: `script_generator` takes a LIST. The orchestrator will (i) run the legacy `analyze_posts` for the ranked-posts list `script_generator` still needs, (ii) run the four new lens agents in parallel for the report-writer dict, and (iii) expose both under one `enriched` dict (`{"engagement":..., "trends":..., "competitors":..., "contentThemes":..., "rankedPosts":[...]}`) but pass `enriched["rankedPosts"]` into `script_generator` rather than the full dict.
3. Delivery does not accept a second payload type — handled via the additive `deliver_report` helper noted above.
4. `posts_text` is a list-of-dicts from scrapers, not a string. Agents JSON-serialize it into their user-turn prompts (mirroring `analyzer._format_batch`).
5. `knowledge_base.py::get_gemini_analysis_prompt()` stays in place for the legacy analyzer; the new skill files are for the four new lens agents only. Script-generator's prompt remains sourced from `get_sonnet_script_prompt(campus)` — it is NOT moved into `skills/script-generator.md`. Rationale: that prompt is campus-parameterized, and lifting it into a skill would either need runtime templating in the skill loader (not in plan) or lose the campus context. A skill file can still be added later if we decide to template skills; keeping the existing contract green is the priority for this refactor.
6. JSON-parse helpers (`_parse_gemini_response`, `_extract_json_array`, `_clean_gemini_json_text`, `_normalize_analysis_items`-style shaping) live private in `analyzer.py`. The new agents need the three generic ones. Phase 2 lifts them into a shared module (or re-imports them) — whichever yields fewer cross-file changes.

Impact on plan: all six items are implementation-level and do not change the public shape of the refactor (skills layer, four parallel agents, report writer, verifier, phased async orchestrator, fail-open retry). The skill-file for `script-generator` is dropped from the 7-file list; we end with 6 skill files.

---

## Module Status

| Module | Status | Tests | Description |
|--------|--------|-------|-------------|
| `pipeline/config.py` | Built + verified | 10 | Central config, env loading, validation |
| `pipeline/knowledge_base.py` | Built + verified | 11 | Tiered prompt builders (Gemini + Sonnet) |
| `pipeline/scrapers/_common.py` | Built + verified | 49 (shared scraper coverage) | Shared schema, normalization, endpoint handling, dedup helpers |
| `pipeline/scrapers/tiktok.py` | Built + verified | Covered in `tests/test_scrapers.py` | TikTok scraping via Scraptik + seen-post dedup |
| `pipeline/scrapers/instagram.py` | Built + verified | Covered in `tests/test_scrapers.py` | Instagram scraping via Scraptik + seen-post dedup |
| `pipeline/analyzer_legacy.py` | Built + verified | 28 | Gemini Tier 1 analysis, JSON recovery, scoring, retry-path handling (renamed from `analyzer.py` in Phase 4) |
| `pipeline/script_generator.py` | Built + verified | 21 | Sonnet Tier 2 creative briefs, campus split, retry-path handling |
| `pipeline/delivery.py` | Built + verified | 29 | Telegram formatting, ordering, dry-run delivery, `deliver_report` with 4000-char chunking and plain-text send, retry-path handling |
| `pipeline/main.py` | Built + verified | 13 sync + 5 async | CLI orchestrator, async verify-retry loop (`test_orchestrator.py`), cache loading, campus filtering, run summaries |
| `pipeline/history.py` | Built + verified | 3 | Cross-run scripted-post history, 7-day expiry, pre-analysis dedup |
| `pipeline/http_utils.py` | Built + verified | Shared via analyzer/script generator/delivery tests | Shared retry helper with exponential backoff and 401 short-circuit |
| `pipeline/gemini_utils.py` | Built + verified | 15 | Shared Gemini transport + JSON parse helpers (lifted from analyzer/agents in Phase 4) |
| `pipeline/skills.py` | Built + verified | 5 | Markdown skill loader for the multi-agent layer |
| `pipeline/agents.py` | Built + verified | 15 | Four parallel Gemini lens agents + `run_parallel_analysis` merge |
| `pipeline/report_writer.py` | Built + verified | 8 | Claude Sonnet insight-report writer with `cache_control: ephemeral` |
| `pipeline/report_verifier.py` | Built + verified | 14 | Gemini Flash-Lite verifier with fail-open semantics |
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
| `tests/test_delivery.py` | 29 |
| `tests/test_main.py` | 13 |
| `tests/test_history.py` | 3 |
| `tests/test_logging_setup.py` | 2 |
| `tests/test_skills.py` | 5 |
| `tests/test_gemini_utils.py` | 15 |
| `tests/test_agents.py` | 15 |
| `tests/test_report_writer.py` | 8 |
| `tests/test_report_verifier.py` | 14 |
| `tests/test_orchestrator.py` | 5 |
| **Total** | **228** |

## Architecture

Two-tier AI pipeline:
1. **Gemini Flash-Lite** (free) — legacy post ranker + four parallel lens agents (engagement, trends, competitors, content classification) + report verifier.
2. **Claude Sonnet** (paid) — campus-specific creative briefs and a cross-campus insight report (with `cache_control: ephemeral` on the writer's system block).

The async orchestrator (`pipeline/main.py::run_pipeline_async`) runs the legacy ranker and the four lens agents in parallel, then fans out report generation and script generation, then runs the verify-retry loop (max 1 retry, deliver regardless), then delivers scripts followed by the report.

Operational hardening is complete: seen-post dedup in scrapers, scripted-post history before analysis, rotating logs, shared retry/backoff, and cron-safe startup.

See `ARCHITECTURE.md` for full details.
