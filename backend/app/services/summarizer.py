from __future__ import annotations

"""Lightweight message summarizer for AI search conversation titles.

Uses rule-based extraction (regex) — no LLM API call.
Generates a short title from the user's first travel-search message.
"""

import re

# ── city pair patterns ──────────────────────────────────────────────

_CITY_PAIR_ZH = re.compile(
    r"([一-鿿]{2,4})\s*(?:到|去|至|飞|→|达)\s*([一-鿿]{2,4})"
)
_CITY_PAIR_EN = re.compile(
    r"([A-Z][a-z]+(?:\s[A-Z][a-z]+)?)\s+(?:to|→)\s+([A-Z][a-z]+(?:\s[A-Z][a-z]+)?)",
    re.IGNORECASE,
)

# ── constraint detectors ────────────────────────────────────────────

_PRICE_RE = re.compile(
    r"(?:预算|价格|费用|budget|under|within|below)\s*(\d+)", re.IGNORECASE
)

_OPT_FASTEST_ZH = re.compile(r"最快|时间短|赶时间")
_OPT_FASTEST_EN = re.compile(r"fastest|quickest|shortest\s+time", re.IGNORECASE)
_OPT_CHEAPEST_ZH = re.compile(r"最便宜|便宜|省钱")
_OPT_CHEAPEST_EN = re.compile(r"cheapest|cheap|lowest\s+price", re.IGNORECASE)
_OPT_FEWEST_ZH = re.compile(r"少换乘|直达|直飞|不要转|尽量少换")
_OPT_FEWEST_EN = re.compile(r"fewest|direct|no\s+transfer", re.IGNORECASE)

_DATE_ZH = re.compile(r"(明天|后天|今天)")
_DATE_EN = re.compile(r"(tomorrow|today)", re.IGNORECASE)

# ── helpers ──────────────────────────────────────────────────────────

def _extract_city_pair(message: str) -> tuple[str, str] | None:
    match = _CITY_PAIR_ZH.search(message)
    if match:
        return match.group(1).strip(), match.group(2).strip()
    match = _CITY_PAIR_EN.search(message)
    if match:
        return match.group(1).strip(), match.group(2).strip()
    return None


def _detect_constraint(message: str, language: str) -> str:
    """Return a short constraint label, or empty string."""
    price = _PRICE_RE.search(message)
    if price:
        prefix = "预算" if language == "zh" else "≤"
        return f"{prefix}{price.group(1)}"

    if language == "zh":
        if _OPT_CHEAPEST_ZH.search(message):
            return "最便宜"
        if _OPT_FASTEST_ZH.search(message):
            return "最快"
        if _OPT_FEWEST_ZH.search(message):
            return "少换乘"
    else:
        if _OPT_CHEAPEST_EN.search(message):
            return "Cheapest"
        if _OPT_FASTEST_EN.search(message):
            return "Fastest"
        if _OPT_FEWEST_EN.search(message):
            return "Fewest"

    date_match = _DATE_ZH.search(message) or _DATE_EN.search(message)
    if date_match:
        return date_match.group(0)

    return ""


# ── public API ───────────────────────────────────────────────────────

def summarize_message(message: str, language: str = "zh") -> str:
    """Produce a concise conversation title (≤ 30 chars) from a travel query.

    Strategy (best-effort, falls back to truncation):
      1. Extract from_city → to_city.
      2. Detect a single constraint keyword (price / opt-target / date).
      3. Combine as  "{from}→{to} {constraint}".
      4. If no cities detected, truncate the cleaned message.
    """
    pair = _extract_city_pair(message)
    if pair:
        arrow = "→" if language == "zh" else " → "
        title = f"{pair[0]}{arrow}{pair[1]}"
        constraint = _detect_constraint(message, language)
        if constraint:
            title += f" {constraint}"
        return title[:30]

    # Fallback — clean whitespace and truncate
    clean = re.sub(r"\s+", " ", message).strip()
    if len(clean) <= 20:
        return clean
    return clean[:18] + "…"
