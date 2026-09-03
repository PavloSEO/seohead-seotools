"""Politeness that reacts to the origin, not just to a configured ceiling.

Measured on a real shared-hosting catalogue: under a polite 1.5 URL/s the origin
degraded from 1 196 ms to 16 455 ms TTFB and then began refusing TLS handshakes,
without ever returning an error status. A throttle that only widens on non-200
would have kept pushing, so latency widens the delay and a timeout widens it
hard — a timeout is the strongest signal available, never a reason to retry
immediately.
"""

from __future__ import annotations

# The delay is nudged toward latency/target_concurrency and averaged with the
# current delay, so one fast response cannot undo a back-off.
TARGET_CONCURRENCY = 1.0
TIMEOUT_PENALTY = 4.0
MAX_DELAY_S = 60.0


class Throttle:
    """Adaptive delay between requests for one origin."""

    def __init__(self, start_delay: float = 0.0, min_delay: float = 0.0) -> None:
        self.min_delay = max(0.0, float(min_delay))
        self.delay = max(self.min_delay, float(start_delay))
        self.timeouts = 0
        self.server_errors = 0

    def record_response(self, latency_s: float, ok: bool) -> None:
        """Fold one completed response into the delay.

        A non-2xx response may raise the delay but never lower it: a fast 500 is
        not evidence that the origin is healthy.
        """
        target = max(latency_s, 0.0) / TARGET_CONCURRENCY
        new_delay = (self.delay + target) / 2
        if not ok:
            new_delay = max(new_delay, self.delay)
        self.delay = min(MAX_DELAY_S, max(self.min_delay, new_delay))

    def record_timeout(self) -> None:
        """A connection, TLS or read timeout: the origin is failing, back off hard."""
        self.timeouts += 1
        base = max(self.delay, self.min_delay, 0.5)
        self.delay = min(MAX_DELAY_S, base * TIMEOUT_PENALTY)

    def should_stop(self, limit: int = 5) -> bool:
        """Consecutive timeouts mean the origin is down; stop rather than hammer it."""
        return self.timeouts >= limit

    def record_success(self) -> None:
        self.timeouts = 0
        self.server_errors = 0

    def record_server_error(self, status_code: int, retry_after: float | None = None) -> None:
        """A host answering 429 or 5xx is already struggling.

        Treat a single 429 as an overload signal rather than a retryable blip:
        it is the server explicitly asking for less, and continuing at the same
        rate turns an audit into a load test.
        """
        self.server_errors += 1
        base = max(self.delay, self.min_delay, 0.5)
        widened = base * TIMEOUT_PENALTY if status_code == 429 else base * 2
        if retry_after is not None:
            widened = max(widened, retry_after)
        self.delay = min(MAX_DELAY_S, widened)

    def host_is_failing(self, limit: int = 5) -> bool:
        """Consecutive server refusals mean stop, not retry harder."""
        return self.server_errors >= limit
