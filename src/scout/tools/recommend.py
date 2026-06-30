"""Flag unconfigured-but-relevant tools so the operator knows what to enable.

Unavailable tools are invisible to the agents (they can't be called), so the
agent can't suggest them. This pass inspects the mission brief and the planned
tasks for terms that imply a specialized tool would help, and surfaces any such
tool that isn't currently available - along with the exact step to turn it on.

Matching is deterministic keyword-based: no extra model calls, works in mock
mode, and never fabricates a recommendation. It is *inflection-aware* - a
singular keyword (``email``) matches plural mentions (``emails``) and vice
versa - while still requiring whole-word/phrase boundaries so ``face`` never
fires on ``surface`` nor ``tor`` on ``actor``.
"""

from __future__ import annotations

import re

from ..models import Mission, ToolSuggestion
from .registry import discover_tools

# Words whose trailing 's' is not a plural; never strip it.
_NON_PLURAL = ("ss", "us", "is", "as", "os")


def _inflections(word: str) -> set[str]:
    """Return the common singular/plural surface forms of a single word."""
    forms = {word}
    if len(word) <= 2:
        return forms
    # Singular -> plural
    if word.endswith("y") and word[-2:-1] not in "aeiou":
        forms.add(word[:-1] + "ies")
    elif word.endswith(("s", "x", "z", "ch", "sh")):
        forms.add(word + "es")
    else:
        forms.add(word + "s")
    # Plural -> singular
    if word.endswith("ies") and len(word) > 4:
        forms.add(word[:-3] + "y")
    if word.endswith("es") and len(word) > 4 and not word.endswith(_NON_PLURAL):
        forms.add(word[:-2])
    if word.endswith("s") and len(word) > 3 and not word.endswith(_NON_PLURAL):
        forms.add(word[:-1])
    return forms


def _pattern_for(keyword: str) -> re.Pattern[str]:
    """Build a whole-word/phrase regex, inflecting only the final word.

    Lookarounds handle leading symbols ('@gmail') and internal hyphens ('wi-fi')
    so a keyword stays anchored to word boundaries.
    """
    head, _, last = keyword.rpartition(" ")
    forms = sorted(_inflections(last), key=len, reverse=True)
    alt = "|".join(re.escape(f) for f in forms)
    prefix = re.escape(head + " ") if head else ""
    return re.compile(rf"(?<!\w){prefix}(?:{alt})(?!\w)")


def _matches(keyword: str, haystack: str) -> bool:
    return _pattern_for(keyword).search(haystack) is not None


def _same_concept(a: str, b: str) -> bool:
    """True if two keywords are inflectional variants (subdomain ~ subdomains)."""
    a_head, _, a_last = a.rpartition(" ")
    b_head, _, b_last = b.rpartition(" ")
    return a_head == b_head and bool(_inflections(a_last) & _inflections(b_last))


def _dedupe_why(matched: list[str]) -> list[str]:
    """Collapse inflectional duplicates, preferring the shortest surface form."""
    kept: list[str] = []
    for kw in sorted(matched, key=len):
        if not any(_same_concept(kw, k) for k in kept):
            kept.append(kw)
    return kept


def recommend_tools(mission: Mission) -> list[ToolSuggestion]:
    haystack = " ".join(
        [mission.brief]
        + [t.objective for t in mission.tasks]
        + [t.rationale for t in mission.tasks]
        + [s for t in mission.tasks for s in t.suggested_sources]
    ).lower()

    scored: list[tuple[int, ToolSuggestion]] = []
    for found in discover_tools():
        spec = found.spec
        # Only recommend tools that exist but aren't usable yet.
        if found.available or not spec.keywords:
            continue
        matched = [kw for kw in spec.keywords if _matches(kw, haystack)]
        if not matched:
            continue
        why_terms = _dedupe_why(matched)
        scored.append((
            len(why_terms),
            ToolSuggestion(
                tool_id=spec.id,
                name=spec.name,
                summary=spec.summary,
                why=f"mission mentions {', '.join(why_terms[:3])}",
                how_to_enable=found.reason,
            ),
        ))
    # Strongest matches first; stable by name within the same score.
    scored.sort(key=lambda x: (-x[0], x[1].name.lower()))
    return [s for _, s in scored]
