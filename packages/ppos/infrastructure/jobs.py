"""In-process background jobs (one worker; the seam for a real queue later)."""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor

log = logging.getLogger("ppos.jobs")


class ThreadJobRunner:
    def __init__(self, workers: int = 1) -> None:
        self._pool = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="ppos-job")
        self._pending: set[Future[None]] = set()
        self._lock = threading.Lock()

    def submit(self, name: str, fn: Callable[[], None]) -> None:
        def run() -> None:
            try:
                fn()
            except Exception:
                log.exception("job %s failed", name)

        fut = self._pool.submit(run)
        with self._lock:
            self._pending.add(fut)
        fut.add_done_callback(lambda f: self._done(f))

    def _done(self, fut: Future[None]) -> None:
        with self._lock:
            self._pending.discard(fut)

    def wait_idle(self, timeout: float = 30) -> None:
        with self._lock:
            pending = list(self._pending)
        for f in pending:
            f.result(timeout=timeout)


class InlineJobRunner:
    """Runs jobs immediately (tests, CLI)."""

    def submit(self, name: str, fn: Callable[[], None]) -> None:
        fn()

    def wait_idle(self, timeout: float = 30) -> None:
        return None
