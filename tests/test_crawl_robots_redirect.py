"""Regression test for #135: a redirected robots.txt must still govern the crawl.

``crawl_site`` fetches content with ``follow_redirects=False`` on purpose (see
``seohead/crawl/spider.py``), and used to reuse that same client verbatim for
robots.txt — so a 301 on ``/robots.txt`` was read as *itself*: an empty body,
parsed into an empty, fully permissive ruleset. This serves the real case that
surfaced it: an http->https or bare-domain->www redirect on ``/robots.txt``,
which is unremarkable on the live web and must not silently disable robots
enforcement. Run over loopback so the fix is exercised through the real HTTP
client, not the ``fetcher`` test double the rest of the spider suite uses.
"""

from __future__ import annotations

import contextlib
import http.server
import threading
from collections.abc import Iterator

from seohead.crawl.spider import crawl_site

REAL_ROBOTS = "User-agent: *\nDisallow: /secret\n"


class _Handler(http.server.BaseHTTPRequestHandler):
    def _send(self, body: bytes, content_type: str, status: int = 200, extra=None) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        for key, value in (extra or {}).items():
            self.send_header(key, value)
        self.end_headers()
        if body:
            self.wfile.write(body)

    def do_GET(self) -> None:
        path = self.path.split("?", 1)[0]
        if path == "/robots.txt":
            # The redirect this issue is about: the request itself carries no
            # rules, only a pointer to where they actually live.
            return self._send(b"", "text/html", status=301, extra={"Location": "/robots-real.txt"})
        if path == "/robots-real.txt":
            return self._send(REAL_ROBOTS.encode(), "text/plain; charset=utf-8")
        if path == "/secret":
            return self._send(b"<html><body>secret</body></html>", "text/html")
        if path == "/":
            html = '<html><body><h1>home</h1><a href="/secret">secret</a></body></html>'
            return self._send(html.encode(), "text/html; charset=utf-8")
        self._send(b"not found", "text/plain", status=404)

    def log_message(self, format: str, *args) -> None:
        pass


@contextlib.contextmanager
def _run_site() -> Iterator[str]:
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_a_redirected_robots_txt_is_still_respected(monkeypatch):
    monkeypatch.setenv("SEOHEAD_ALLOW_PRIVATE_NETWORKS", "1")
    with _run_site() as base_url:
        result = crawl_site(f"{base_url}/", min_delay=0, sleeper=lambda _s: None)

    fetched = {p.url for p in result.pages}
    assert f"{base_url}/secret" not in fetched, (
        "the redirected robots.txt's Disallow was not applied"
    )
    assert result.robots_blocked == [f"{base_url}/secret"]
    assert result.stopped_reason == ""
    assert "redirected" in result.robots_note
