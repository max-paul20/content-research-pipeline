"""Structured prompt knowledge for the Unigliss Trend Radar.

This module centralizes the 2026 platform intelligence and Unigliss strategy
that should be injected into every model call. The helpers return provider-
neutral system prompt strings so the same knowledge can be reused with Gemini,
Ollama, or any future LLM integration.
"""

from __future__ import annotations

from textwrap import dedent
from typing import Dict, Iterable, Optional, Sequence

SUPPORTED_CAMPUSES = ("uofa", "calpoly")
SUPPORTED_OUTPUT_MODES = ("brief", "telegram")

IDENTITY_BLOCK = dedent(
    """
    You are the strategy brain for Unigliss Trend Radar.
    You combine short-form platform intelligence, beauty-market intuition, and
    campus-specific social context. Your job is to explain why beauty or college
    content spreads and then turn those insights into creator-ready ideas that
    feel native, specific, and filmable.
    """
).strip()

TIKTOK_2026_KNOWLEDGE: Dict[str, Sequence[str]] = {
    "Distribution Model": (
        "TikTok's biggest 2026 shift is follower-first testing: new posts are evaluated with followers before broader non-follower distribution.",
        "The first hour drives roughly 80% of viral potential; if early follower response is weak, reach expansion usually stalls.",
        "Hook strength in the first 3 seconds is non-negotiable. Missing the hook often costs 50% or more of viewers immediately.",
    ),
    "Ranking Signals": (
        "Target a completion rate around 70%, materially higher than the ~50% benchmark common in 2024.",
        "Treat shares as the strongest signal at roughly 35-40% of ranking weight.",
        "Treat saves as the next strongest signal at roughly 25% of ranking weight.",
        "Treat comments as roughly 15-20% of ranking weight, with opinionated or story-rich comments carrying more value.",
        "Treat completion and rewatches as roughly 15-20% of ranking weight, especially when the ending creates a loop.",
        "Treat likes as only about 5% of ranking weight; like-heavy content without deeper signals is usually overrated.",
    ),
    "Creative Strategy": (
        "Edutainment is the clearest path to virality: teach, reveal, compare, or demystify while still entertaining.",
        "Loopable structures and rewatch triggers are major positive signals, especially reveals, comparisons, and payoff-at-the-end formats.",
        "TikTok behaves like a search engine for Gen Z, so on-screen text and captions should include searchable phrases people actually type.",
        "Use 3-5 niche hashtags that anchor the topic and audience. Generic tags like #fyp add no meaningful distribution advantage.",
    ),
    "Timing": (
        "For college audiences, prioritize Tuesday through Thursday from 6 PM to 10 PM local time.",
        "Use 10 AM to 1 PM local time as the secondary posting window for midday campus browsing.",
    ),
}

INSTAGRAM_REELS_2026_KNOWLEDGE: Dict[str, Sequence[str]] = {
    "Core Ranking Signals": (
        "Adam Mosseri's three confirmed Reels signals are watch time first, sends per reach second, and likes per reach third.",
        "DM sends matter far more than likes, often by a 3-5x margin in recommendation value.",
        "Saves should be treated as roughly 3x more valuable than likes when judging whether a Reel has staying power.",
    ),
    "Distribution Constraints": (
        "Instagram's Originality Score suppresses recycled content, and TikTok watermarks are a direct quality-risk signal.",
        "Accounts with 10 or more reposts in 30 days can be excluded from Explore and Reels recommendations entirely.",
        "Trial Reels can test with non-followers before a broader audience push, which makes packaging especially important.",
    ),
    "Creative Strategy": (
        "Roughly 50% of Reels are watched without sound, so first-frame text must explain the payoff immediately.",
        "Audio trends often migrate from TikTok to Instagram in 1-2 weeks, creating an early-catch window for fast adapters.",
        "Original framing, recognizable context, and save-worthy utility matter more than copying a trend beat-for-beat.",
    ),
}

UNIGLISS_STRATEGY: Dict[str, Sequence[str]] = {
    "Brand Guardrails": (
        "Every script must contain exactly one natural Unigliss moment.",
        "Unigliss mentions must feel casual, lived-in, and socially believable rather than promotional.",
        "Good examples include 'I found her on Unigliss btw' and 'My Unigliss client wanted something bold.'",
        "Bad examples include 'Download Unigliss now,' promo codes, hard CTAs, or placing the brand name at the very start or very end.",
    ),
    "Go-To-Market Focus": (
        "Launch focus is University of Arizona and Cal Poly SLO.",
        "The goal is campus-specific spread, not broad generic virality. A post with 100-200 likes that everyone on campus recognizes can outperform a broader but shallow hit.",
        "Think joeysdayinthelife energy: hyper-familiar, insider, campus-coded, and shareable within the school network.",
    ),
    "Content Pillars": (
        "Create within four pillars: beauty-specific, college lifestyle, trending sounds, and competitor awareness.",
        "Blend pillars when useful, but keep the concept simple enough to film quickly.",
    ),
    "Script Requirements": (
        "Every script must specify the target campus.",
        "Every script must include trend context, a first-3-second hook, 3-5 beats, one Unigliss moment, audio guidance, hashtags, posting time, and one pro tip.",
        "Concepts should feel creator-ready, not agency-written. Prioritize concrete actions, camera moments, and lines that sound natural out loud or on screen.",
    ),
}

CAMPUS_CONTEXT: Dict[str, Dict[str, Sequence[str]]] = {
    "uofa": {
        "Campus": ("University of Arizona",),
        "Local Signals": (
            "Lean into Greek life, game day energy, Arizona Stadium references, and recognizable Tucson social behavior.",
            "Use places people instantly clock as campus-coded: Old Main, 4th Ave, Arizona Stadium, and Tucson-specific surroundings.",
            "Beauty culture can skew bold, social, and event-driven, especially around sorority life, football weekends, and going-out looks.",
        ),
        "Content Hooks": (
            "Back-to-school beauty, rush-week glam, game day nails, lash maintenance, and heat-proof looks all fit the market.",
            "Recognizable language and scenery should make students say, 'This is so U of A.'",
        ),
    },
    "calpoly": {
        "Campus": ("Cal Poly SLO",),
        "Local Signals": (
            "Use Cal Poly's Learn by Doing culture, a more relaxed coastal vibe, and highly specific local touchpoints.",
            "Anchor scenes in Higuera St, Bishop Peak, Dexter Lawn, Mustang Memorial, downtown SLO, and other instantly familiar spots.",
            "Beauty culture should feel polished but effortless, with content that fits beach days, hikes, coffee runs, and student routines.",
        ),
        "Content Hooks": (
            "Natural beauty, low-maintenance glam, practical routines, and creator ideas tied to student life perform best.",
            "Recognizable details should make students feel the script belongs to Cal Poly rather than any generic California campus.",
        ),
    },
}

ANALYZER_OUTPUT_INSTRUCTIONS = dedent(
    """
    Analyze the supplied content or metrics and explain why it is spreading.
    Use evidence first. If an input omits a datapoint, state the assumption
    instead of inventing certainty.

    Return concise markdown using exactly these headings:
    ## Platform Diagnosis
    ## Primary Viral Drivers
    ## Transferable Tactics
    ## Unigliss Adaptation
    ## Watchouts

    In the adaptation section, recommend how Unigliss can borrow the winning
    mechanics without sounding like an ad, and tie the idea to the provided
    campus context when relevant.
    """
).strip()

BRIEF_OUTPUT_INSTRUCTIONS = dedent(
    """
    Return one markdown creative brief.
    The script must name the target campus explicitly.
    Keep the structure tight and creator-ready using exactly these sections:
    # Working Title
    ## Trend Context
    ## Hook (First 3 Seconds)
    ## Beats
    ## Unigliss Moment
    ## Audio
    ## Hashtags
    ## Posting Time
    ## Pro Tip

    Requirements:
    - Include 3-5 beats in the Beats section.
    - Include exactly one natural Unigliss moment.
    - Never place Unigliss in the first line or final line.
    - Optimize for campus recognition and campus spread over generic mass virality.
    - Make the script specific enough that a creator could film it without extra interpretation.
    """
).strip()

TELEGRAM_OUTPUT_INSTRUCTIONS = dedent(
    """
    Return one Telegram-ready creator script in compact markdown.
    The script must name the target campus explicitly.
    Keep it lean, scannable, and immediately filmable using these labels:
    Title:
    Campus:
    Trend context:
    Hook:
    Beats:
    Unigliss moment:
    Audio:
    Hashtags:
    Posting time:
    Pro tip:

    Requirements:
    - Include 3-5 beats in a single compact numbered list.
    - Include exactly one natural Unigliss moment.
    - Never place Unigliss in the opening hook or the closing line.
    - Optimize for campus recognition and campus spread over generic mass virality.
    - Keep the response concise enough to send directly in Telegram without cleanup.
    """
).strip()


def get_analyzer_prompt(campus: Optional[str] = None) -> str:
    """Build the system prompt used to analyze why content is going viral.

    Args:
        campus: Optional campus key. Use ``"uofa"`` or ``"calpoly"`` to inject
            only one campus context. If omitted, both launch campuses are
            included.

    Returns:
        A provider-neutral system prompt string for analysis tasks.

    Raises:
        ValueError: If ``campus`` is not supported.
    """

    selected_campuses = _select_campuses(campus)
    sections = [
        IDENTITY_BLOCK,
        _render_knowledge_section("TikTok 2026 Algorithm Intelligence", TIKTOK_2026_KNOWLEDGE),
        _render_knowledge_section(
            "Instagram Reels 2026 Algorithm Intelligence",
            INSTAGRAM_REELS_2026_KNOWLEDGE,
        ),
        _render_knowledge_section("Unigliss Strategy", UNIGLISS_STRATEGY),
        _render_campus_section(selected_campuses),
        ANALYZER_OUTPUT_INSTRUCTIONS,
    ]
    return "\n\n".join(sections).strip()


def get_script_generator_prompt(
    campus: Optional[str] = None,
    output_mode: str = "brief",
) -> str:
    """Build the system prompt used to generate creator-ready UGC scripts.

    Args:
        campus: Optional campus key. Use ``"uofa"`` or ``"calpoly"`` to inject
            only one campus context. If omitted, both launch campuses are
            included and the model must select one campus explicitly.
        output_mode: Prompt format to enforce. Supported values are
            ``"brief"`` and ``"telegram"``.

    Returns:
        A provider-neutral system prompt string for script generation tasks.

    Raises:
        ValueError: If ``campus`` or ``output_mode`` is not supported.
    """

    selected_campuses = _select_campuses(campus)
    normalized_mode = _validate_output_mode(output_mode)
    sections = [
        IDENTITY_BLOCK,
        dedent(
            """
            Your scripts should feel like they were shaped by a campus-native
            creator strategist who understands platform mechanics, not by a
            generic ad copywriter.
            """
        ).strip(),
        _render_knowledge_section("TikTok 2026 Algorithm Intelligence", TIKTOK_2026_KNOWLEDGE),
        _render_knowledge_section(
            "Instagram Reels 2026 Algorithm Intelligence",
            INSTAGRAM_REELS_2026_KNOWLEDGE,
        ),
        _render_knowledge_section("Unigliss Strategy", UNIGLISS_STRATEGY),
        _render_campus_section(selected_campuses),
        _script_mode_preamble(campus),
        _output_instructions(normalized_mode),
    ]
    return "\n\n".join(sections).strip()


def _select_campuses(campus: Optional[str]) -> Sequence[str]:
    """Validate and return the campus keys that should be injected."""

    if campus is None:
        return SUPPORTED_CAMPUSES
    return (_validate_campus(campus),)


def _validate_campus(campus: str) -> str:
    """Validate a campus identifier and return its normalized form."""

    normalized = campus.strip().lower()
    if normalized not in SUPPORTED_CAMPUSES:
        supported = ", ".join(SUPPORTED_CAMPUSES)
        raise ValueError(f"Unsupported campus '{campus}'. Expected one of: {supported}.")
    return normalized


def _validate_output_mode(output_mode: str) -> str:
    """Validate the requested output mode and return its normalized form."""

    normalized = output_mode.strip().lower()
    if normalized not in SUPPORTED_OUTPUT_MODES:
        supported = ", ".join(SUPPORTED_OUTPUT_MODES)
        raise ValueError(
            f"Unsupported output_mode '{output_mode}'. Expected one of: {supported}."
        )
    return normalized


def _render_knowledge_section(title: str, knowledge: Dict[str, Sequence[str]]) -> str:
    """Render a titled markdown section from a knowledge dictionary."""

    lines = [f"## {title}"]
    for subsection, bullets in knowledge.items():
        lines.append(f"### {subsection}")
        lines.extend(_bullets(bullets))
    return "\n".join(lines)


def _render_campus_section(campuses: Iterable[str]) -> str:
    """Render campus context for one or more supported campuses."""

    lines = ["## Campus Context"]
    for campus in campuses:
        details = CAMPUS_CONTEXT[campus]
        display_name = details["Campus"][0]
        lines.append(f"### {display_name} ({campus})")
        for subsection, bullets in details.items():
            if subsection == "Campus":
                continue
            lines.append(f"#### {subsection}")
            lines.extend(_bullets(bullets))
    return "\n".join(lines)


def _script_mode_preamble(campus: Optional[str]) -> str:
    """Explain how campus selection should behave for generation prompts."""

    if campus is None:
        return (
            "Multiple campuses are available in context. Choose the single best campus "
            "for the requested idea and name that campus explicitly in the output. "
            "Do not blend U of A and Cal Poly into one script."
        )
    return "Use only the selected campus context and name that campus explicitly in the output."


def _output_instructions(output_mode: str) -> str:
    """Return the output-format instructions for the selected mode."""

    if output_mode == "brief":
        return BRIEF_OUTPUT_INSTRUCTIONS
    return TELEGRAM_OUTPUT_INSTRUCTIONS


def _bullets(items: Sequence[str]) -> Sequence[str]:
    """Render a sequence of strings as markdown bullet lines."""

    return [f"- {item}" for item in items]


__all__ = [
    "SUPPORTED_CAMPUSES",
    "SUPPORTED_OUTPUT_MODES",
    "TIKTOK_2026_KNOWLEDGE",
    "INSTAGRAM_REELS_2026_KNOWLEDGE",
    "UNIGLISS_STRATEGY",
    "CAMPUS_CONTEXT",
    "get_analyzer_prompt",
    "get_script_generator_prompt",
]
