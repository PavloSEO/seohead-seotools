"""Politeness that reacts to the origin, not just to a configured ceiling.

Measured on a real shared-hosting catalogue: under a polite 1.5 URL/s the origin
degraded from 1 196 ms to 16 455 ms TTFB and then began refusing TLS handshakes,
without ever returning an error status. A throttle that only widens on non-200
would have kept pushing, so latency widens the delay and a timeout widens it
hard — a timeout is the strongest signal available, never a reason to retry
immediately.

The same object also tracks how many requests may be in flight to this origin
at once. That number starts conservative and only widens on sustained success;
a timeout or a server refusal collapses it back to one immediately — the same
asymmetry the delay itself uses, and for the same reason: fetching more from an
origin that just showed it is struggling turns an audit into a load test.

Both the delay and the concurrency level are read and mutated from whichever
thread is fetching the corresponding URL when the crawler runs several requests
at once, so every mutating method is serialized behind one lock.

The two adapt together, not independently: the delay is nudged toward
``latency / concurrency``, not toward raw latency. At concurrency 1 that is
just latency, unchanged from a strictly sequential crawler. At a higher earned
concurrency it is the spacing that keeps that many requests landing back to
back — the pacing a level-batched crawler needs to turn overlapped wait time
into real throughput instead of quietly re-serializing dispatch to the same
one-at-a-time rate.
"""

from __future__ import annotations

import threading

TIMEOUT_PENALTY = 4.0
MAX_DELAY_S = 60.0

# How many consecutive good responses it takes to trust the origin with one
# more concurrent request. Slow to grow, fast to collapse.
WIDEN_AFTER_CONSECUTIVE_OK = 3


class Throttle:
    """Adaptive delay and concurrency for one origin."""

    def __init__(
        self, start_delay: float = 0.0, min_delay: float = 0.0, max_concurrency: int = 1
    ) -> None:
        self.min_delay = max(0.0, float(min_delay))
        self.delay = max(self.min_delay, float(start_delay))
        self.timeouts = 0
        self.server_errors = 0
        # The ceiling is a configured, bounded fact; ``concurrency`` is what the
        # origin has earned so far, never more than the ceiling allows.
        self.max_concurrency = max(1, int(max_concurrency))
        self.concurrency = min(2, self.max_concurrency)
        self._consecutive_ok = 0
        self._lock = threading.Lock()

    def record_response(self, latency_s: float, ok: bool) -> None:
        """Fold one completed response into the delay and the concurrency level.

        A non-2xx response may raise the delay but never lower it: a fast 500 is
        not evidence that the origin is healthy.
        """
        with self._lock:
            target = max(latency_s, 0.0) / self.concurrency
            new_delay = (self.delay + target) / 2
            if not ok:
                new_delay = max(new_delay, self.delay)
            self.delay = min(MAX_DELAY_S, max(self.min_delay, new_delay))
            if ok:
                self._consecutive_ok += 1
                if (
                    self._consecutive_ok >= WIDEN_AFTER_CONSECUTIVE_OK
                    and self.concurrency < self.max_concurrency
                ):
                    self.concurrency += 1
                    self._consecutive_ok = 0
            else:
                self._consecutive_ok = 0

    def record_timeout(self) -> None:
        """A connection, TLS or read timeout: the origin is failing, back off hard."""
        with self._lock:
            self.timeouts += 1
            base = max(self.delay, self.min_delay, 0.5)
            self.delay = min(MAX_DELAY_S, base * TIMEOUT_PENALTY)
            self._consecutive_ok = 0
            self.concurrency = 1

    def should_stop(self, limit: int = 5) -> bool:
        """Consecutive timeouts mean the origin is down; stop rather than hammer it.

        The count is shared across every concurrent worker: three of four
        workers seeing a timeout is the same "origin is failing" signal as one
        worker seeing three in a row.
        """
        with self._lock:
            return self.timeouts >= limit

    def record_success(self) -> None:
        with self._lock:
            self.timeouts = 0
            self.server_errors = 0

    def record_server_error(self, status_code: int, retry_after: float | None = None) -> None:
        """A host answering 429 or 5xx is already struggling.

        Treat a single 429 as an overload signal rather than a retryable blip:
        it is the server explicitly asking for less, and continuing at the same
        rate turns an audit into a load test.
        """
        with self._lock:
            self.server_errors += 1
            base = max(self.delay, self.min_delay, 0.5)
            widened = base * TIMEOUT_PENALTY if status_code == 429 else base * 2
            if retry_after is not None:
                widened = max(widened, retry_after)
            self.delay = min(MAX_DELAY_S, widened)
            self._consecutive_ok = 0
            self.concurrency = 1

    def host_is_failing(self, limit: int = 5) -> bool:
        """Consecutive server refusals mean stop, not retry harder.

        Shared across workers for the same reason as ``should_stop``: the
        signal is about the origin, not about which worker happened to see it.
        """
        with self._lock:
            return self.server_errors >= limit
