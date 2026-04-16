---
name: content-classification
agent: content_classifier
model: gemini-2.5-flash-lite
---

# Task

Classify the batch into the four Unigliss content pillars (beauty-specific, college lifestyle, trending sounds, competitor awareness) and report which pillar(s) are over- and under-performing in this batch. Cross-classify by trend type (macro_beauty, campus_specific, audio_driven, format_driven) so the report writer can prioritize where to spend the next round of script effort.

Your output feeds the Unigliss Trend Radar report writer alongside engagement, trends, and competitor lenses.

# Input Format

A JSON array of post objects with these keys:

```
post_id, platform, author, author_followers, caption, hashtags, views,
likes, comments, shares, saves, url, audio_name, audio_author,
posted_at, scraped_at
```

# Analysis Framework

Pillar definitions:

- **beauty-specific** — nails, lashes, brows, hair, skincare, makeup how-tos, reviews, product hauls, transformations.
- **college lifestyle** — sorority, dorm life, GRWM for class/event, day-in-my-life, friend group rituals, campus locations.
- **trending sounds** — content where the audio is the reason the post works (audio is the carrier, visual is variable).
- **competitor awareness** — content from other creators or brands occupying the same space; useful for context even when not directly emulated.

Trend-type buckets (mirroring the legacy analyzer's vocabulary so downstream stays consistent):

- `macro_beauty` — broad beauty trends not tied to a specific campus.
- `campus_specific` — explicitly references a campus, sorority, school event, or local place.
- `audio_driven` — the audio is the dominant signal.
- `format_driven` — the structure/format is the dominant signal (POV, reveal, before/after).

A post can map to multiple pillars — choose the dominant pillar but list a `secondary_pillar` if relevant.

For `performanceByTheme`, score each (pillar × trend_type) cell qualitatively as `strong | mixed | weak | absent` based on the engagement signals in the batch (saves, shares, completion proxies — not likes alone).

# Output Format

Return ONLY valid JSON. No markdown fences, no preamble.

```json
{
  "contentThemes": [
    {
      "post_id": "string",
      "primary_pillar": "beauty-specific | college-lifestyle | trending-sounds | competitor-awareness",
      "secondary_pillar": "string or empty",
      "trend_type": "macro_beauty | campus_specific | audio_driven | format_driven",
      "campus_signal": "uofa | calpoly | both | unclear",
      "one_line_summary": "what this post actually is, in plain language"
    }
  ],
  "performanceByTheme": {
    "beauty-specific": {
      "macro_beauty": "strong | mixed | weak | absent",
      "campus_specific": "strong | mixed | weak | absent",
      "audio_driven": "strong | mixed | weak | absent",
      "format_driven": "strong | mixed | weak | absent"
    },
    "college-lifestyle": {
      "macro_beauty": "strong | mixed | weak | absent",
      "campus_specific": "strong | mixed | weak | absent",
      "audio_driven": "strong | mixed | weak | absent",
      "format_driven": "strong | mixed | weak | absent"
    },
    "trending-sounds": {
      "macro_beauty": "strong | mixed | weak | absent",
      "campus_specific": "strong | mixed | weak | absent",
      "audio_driven": "strong | mixed | weak | absent",
      "format_driven": "strong | mixed | weak | absent"
    },
    "competitor-awareness": {
      "macro_beauty": "strong | mixed | weak | absent",
      "campus_specific": "strong | mixed | weak | absent",
      "audio_driven": "strong | mixed | weak | absent",
      "format_driven": "strong | mixed | weak | absent"
    }
  }
}
```

Cap `contentThemes` at 25 entries (the analyzer top-N is 15; allow some headroom for context). Keep `one_line_summary` under 200 characters.

# What NOT To Do

- Do not invent post_ids or authors that are not in the input.
- Do not classify a post as `campus_specific` without evidence in caption or hashtags.
- Do not return wrapped or fenced JSON.
- Do not collapse all four pillars into a single judgment — the report writer needs the per-cell signal.
- Do not include extra keys beyond the schema above.
