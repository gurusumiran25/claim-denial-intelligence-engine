"""Offline retrieval over the policy notes (TF-IDF). No network, no model download, no API key."""

from __future__ import annotations

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import linear_kernel

MIN_SCORE = 0.12  # below this a note is not cited (cite-or-abstain)


def _document(note: dict) -> str:
    keywords = " ".join(note["keywords"])
    return f"{note['title']} {keywords} {keywords} {note['text']}"


class PolicyRetriever:
    def __init__(self, notes: list[dict]) -> None:
        self.notes = notes
        self._vec = TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True, stop_words="english")
        self._matrix = self._vec.fit_transform([_document(n) for n in notes])

    def search(self, query: str, k: int = 3, min_score: float = 0.0) -> list[tuple[dict, float]]:
        scores = linear_kernel(self._vec.transform([query]), self._matrix).ravel()
        order = scores.argsort()[::-1][:k]
        return [(self.notes[i], float(scores[i])) for i in order if scores[i] >= min_score]
