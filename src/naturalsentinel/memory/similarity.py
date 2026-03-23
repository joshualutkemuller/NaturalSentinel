"""Similarity search engine with optional sklearn acceleration."""

import logging

from naturalsentinel.utils.text import keyword_similarity, tokenize

logger = logging.getLogger(__name__)


class SimilarityEngine:
    """
    Attempts sklearn TF-IDF for cosine similarity.
    Falls back gracefully to keyword overlap if sklearn is unavailable.
    """

    def __init__(self):
        self._use_sklearn = False
        self._vectorizer = None
        self._matrix = None
        self._cosine_similarity = None
        self._doc_ids: list[str] = []
        self._doc_tokens: dict[str, list[str]] = {}

        try:
            from sklearn.feature_extraction.text import TfidfVectorizer
            from sklearn.metrics.pairwise import cosine_similarity

            self._vectorizer = TfidfVectorizer(max_features=5000, stop_words="english")
            self._cosine_similarity = cosine_similarity
            self._use_sklearn = True
            logger.debug("SimilarityEngine: using sklearn TF-IDF")
        except ImportError:
            logger.debug("SimilarityEngine: sklearn unavailable, using keyword fallback")

    @property
    def backend(self) -> str:
        return "sklearn" if self._use_sklearn else "keyword"

    def index(self, documents: dict[str, str]):
        """Index a batch of {id: text} documents."""
        self._doc_ids = list(documents.keys())
        texts = list(documents.values())

        if self._use_sklearn and texts:
            try:
                self._matrix = self._vectorizer.fit_transform(texts)
            except ValueError:
                # Documents too short or all stop words — fall back to keyword
                logger.debug("TF-IDF fit failed (short docs?), falling back to keyword")
                self._matrix = None
                self._doc_tokens = {did: tokenize(text) for did, text in documents.items()}
        else:
            self._doc_tokens = {did: tokenize(text) for did, text in documents.items()}

    def search(self, query: str, top_k: int = 5) -> list[tuple[str, float]]:
        """Return [(doc_id, score), ...] sorted by descending similarity."""
        if not self._doc_ids:
            return []

        if self._use_sklearn and self._matrix is not None:
            q_vec = self._vectorizer.transform([query])
            scores = self._cosine_similarity(q_vec, self._matrix).flatten()
            ranked = sorted(zip(self._doc_ids, scores), key=lambda x: x[1], reverse=True)
            return ranked[:top_k]
        else:
            q_tokens = tokenize(query)
            scored = [
                (did, keyword_similarity(q_tokens, tokens))
                for did, tokens in self._doc_tokens.items()
            ]
            scored.sort(key=lambda x: x[1], reverse=True)
            return scored[:top_k]
