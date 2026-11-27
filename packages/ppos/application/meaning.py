"""Similarity by meaning, using the local embedding model when one is configured.

Used to suggest evidence whose words differ from an expectation or skill
("coached Ana" for "mentors engineers"). Every failure degrades to "no
opinion" so callers fall back to word overlap; vectors are cached in memory.
"""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable, Mapping

from ppos.domain.assistant import pack, unpack

log = logging.getLogger("ppos")
MAX_CACHE = 5000
RETRY_AFTER_S = 60.0  # after a failure, word matching only for a minute


class MeaningMatcher:
    def __init__(
        self, embed: Callable[[list[str]], list[list[float]]], model: Callable[[], str]
    ) -> None:
        self._embed = embed
        self._model = model
        self._cache: dict[tuple[str, str], bytes] = {}
        self._lock = threading.Lock()
        self._down_until = 0.0

    @property
    def enabled(self) -> bool:
        return bool(self._model())

    def warm(self, texts: list[str]) -> None:
        """Embed texts ahead of time (outside any database transaction)."""
        if texts:
            self.similarities(texts[0], {str(i): t for i, t in enumerate(texts)})

    def similarities(
        self, query: str, texts: Mapping[str, str], *, cached_only: bool = False
    ) -> dict[str, float]:
        """Cosine similarity of each text to the query; {} when meaning search is off.

        ``cached_only`` never calls the model (for use inside a transaction).
        """
        model = self._model()
        if not model or not texts or not query.strip():
            return {}
        wanted = list(dict.fromkeys([query, *texts.values()]))
        with self._lock:
            vecs = {t: self._cache[(model, t)] for t in wanted if (model, t) in self._cache}
        missing = [t for t in wanted if t not in vecs]
        if missing and (cached_only or time.monotonic() < self._down_until):
            return {}
        if missing:
            try:
                fresh = self._embed(missing)
            except Exception as exc:  # server down, wrong model: fall back to words
                log.info("meaning match unavailable: %s", exc)
                self._down_until = time.monotonic() + RETRY_AFTER_S
                return {}
            with self._lock:
                if len(self._cache) + len(missing) > MAX_CACHE:
                    self._cache.clear()
                for t, vec in zip(missing, fresh, strict=True):
                    vecs[t] = self._cache[(model, t)] = pack(vec)
        q = unpack(vecs[query])
        out: dict[str, float] = {}
        for key, text in texts.items():
            v = unpack(vecs[text])
            if len(v) == len(q):
                out[key] = sum(a * b for a, b in zip(q, v, strict=True))
        return out
