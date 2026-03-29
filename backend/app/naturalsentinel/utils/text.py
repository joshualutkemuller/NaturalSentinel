"""Text processing utilities used by the memory similarity engine."""

import re


def tokenize(text: str) -> list[str]:
    """Lowercase alphanumeric tokenizer. Splits on any non-alnum character."""
    return re.findall(r"[a-z0-9]+", text.lower())


def keyword_similarity(query_tokens: list[str], doc_tokens: list[str]) -> float:
    """
    Weighted Jaccard-like overlap: longer shared tokens score higher.

    Returns a float in [0.0, 1.0].
    """
    if not query_tokens or not doc_tokens:
        return 0.0
    q_set = set(query_tokens)
    d_set = set(doc_tokens)
    intersection = q_set & d_set
    if not intersection:
        return 0.0
    score = sum(len(t) for t in intersection)
    normalizer = sum(len(t) for t in q_set | d_set)
    return score / normalizer if normalizer else 0.0
