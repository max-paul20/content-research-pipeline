"""Markdown skill loader for the multi-agent analysis layer.

Skills live as flat markdown files under ``<repo>/skills/`` and are loaded
once per process and cached by name. Each skill file is the system prompt
for one Gemini or Claude call elsewhere in the pipeline.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict

SKILLS_DIR = Path(__file__).resolve().parent.parent / "skills"

_CACHE: Dict[str, str] = {}


def load_skill(name: str) -> str:
    """Return the markdown body of ``skills/<name>.md``, cached after first read."""

    if name in _CACHE:
        return _CACHE[name]

    path = SKILLS_DIR / f"{name}.md"
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise FileNotFoundError(f"Skill not found: {path}") from exc

    _CACHE[name] = text
    return text


__all__ = ["SKILLS_DIR", "load_skill"]
