"""HTML and text extraction utilities for live filing ingestion.

All parsing uses only the Python stdlib (html.parser, re) to keep
the zero-dependency core intact.
"""

from __future__ import annotations

import html
import re
from html.parser import HTMLParser


# ---------------------------------------------------------------------------
# HTML → plain-text extractor
# ---------------------------------------------------------------------------

_SKIP_TAGS = frozenset({
    "script", "style", "noscript", "nav", "header", "footer",
    "aside", "figure", "figcaption", "form", "button", "input",
    "select", "option", "meta", "link", "head",
})

_BLOCK_TAGS = frozenset({
    "p", "div", "section", "article", "h1", "h2", "h3", "h4", "h5", "h6",
    "li", "td", "th", "blockquote", "pre", "table", "tr", "br", "hr",
})


class _TextExtractorParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self._skip_depth: int = 0
        self._parts: list[str] = []

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag in _SKIP_TAGS:
            self._skip_depth += 1
        elif tag in _BLOCK_TAGS and self._skip_depth == 0:
            self._parts.append("\n")

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in _SKIP_TAGS:
            self._skip_depth = max(0, self._skip_depth - 1)

    def handle_data(self, data):
        if self._skip_depth == 0:
            self._parts.append(data)

    def handle_entityref(self, name):
        if self._skip_depth == 0:
            self._parts.append(html.unescape(f"&{name};"))

    def handle_charref(self, name):
        if self._skip_depth == 0:
            self._parts.append(html.unescape(f"&#{name};"))


def html_to_text(html_content: str, max_chars: int = 80_000) -> str:
    """Extract readable plain text from an HTML document.

    Strips scripts, styles, navigation elements, and excess whitespace.
    Truncates at *max_chars* to keep texts within LLM token budgets.

    Args:
        html_content: Raw HTML string.
        max_chars: Character limit applied after extraction (default 80 000).

    Returns:
        Cleaned plain text, truncated if necessary.
    """
    parser = _TextExtractorParser()
    try:
        parser.feed(html_content)
    except Exception:
        # Fallback: strip all tags with a regex
        return _regex_strip_tags(html_content)[:max_chars]

    raw = "".join(parser._parts)
    # Collapse multiple blank lines
    text = re.sub(r"\n{3,}", "\n\n", raw)
    # Collapse multiple spaces within lines
    text = re.sub(r"[ \t]{2,}", " ", text)
    text = text.strip()
    if len(text) > max_chars:
        text = text[:max_chars] + "\n[…truncated at document limit]"
    return text


def _regex_strip_tags(html_content: str) -> str:
    """Fallback: remove HTML tags with a regex (less accurate but safe)."""
    text = re.sub(r"<[^>]+>", " ", html_content)
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


# ---------------------------------------------------------------------------
# Normalisation helpers
# ---------------------------------------------------------------------------

def normalise_whitespace(text: str) -> str:
    """Collapse whitespace and strip leading/trailing space."""
    return re.sub(r"\s+", " ", text).strip()


def truncate(text: str, max_chars: int = 80_000) -> str:
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "\n[…truncated]"


# ---------------------------------------------------------------------------
# Change-type detection from document text / title
# ---------------------------------------------------------------------------

_CHANGE_TYPE_PATTERNS: list[tuple[str, str]] = [
    (r"final rule|final regulations?", "final_rule"),
    (r"proposed rule|notice of proposed rulemaking|nprm", "proposed_rule"),
    (r"advance notice of proposed rulemaking|anprm", "proposed_rule"),
    (r"enforcement action|cease.and.desist|consent order|civil money penalty", "enforcement"),
    (r"executive order", "executive_order"),
    (r"amendment|amend(?:ment)?s? to", "amendment"),
    (r"guidance|supervisory letter|staff guidance|interpretive letter", "guidance"),
]


def detect_change_type(text: str) -> str:
    """Heuristically detect change_type from free text (title + abstract)."""
    lower = text.lower()
    for pattern, change_type in _CHANGE_TYPE_PATTERNS:
        if re.search(pattern, lower):
            return change_type
    return "notice"
