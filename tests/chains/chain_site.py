"""A fixture site built out of the shapes that actually break chains.

The rest of the suite's fixtures are small, clean, valid-UTF-8 HTML pages, which is why every
defect found on live sites survived them. This site is the opposite: each page here exists
because a real crawl of a real site produced a wrong number on a page of that shape.

| Path | Why it is here |
|---|---|
| `/` | a masthead and a skip link **outside** `<main>` — the 29% template inflation (#96) |
| `/a/` and `/a` | both slash forms of one URL, 200 and 301 — one normalised key, two pages (#95) |
| `/photo.webp` | a body that is not valid UTF-8 — the 1.72x size inflation (#99) |
| `/legacy` | `text/html; charset=windows-1251` — decoded length is not byte length (#99) |
| `/gallery` | an `<a>` straight to an image file — not a page a sitemap should declare (#94) |
| off-host link | a destination on another host — never fetched, never a sitemap defect (#94) |
| `/b/` | canonicalises to the slashless form of `/a/`, the one that 301s (#95) |
| `/private/` | disallowed in robots.txt — must be excluded, and counted as excluded |

Served over loopback, so a chain test exercises the real fetch, parse, audit and export path
end to end without touching the network.
"""

from __future__ import annotations

import contextlib
import http.server
import threading
from collections.abc import Iterator

HOME = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>Chain fixture home</title>
<meta name="description" content="The home page of the chain fixture site, long enough to pass description length validation.">
</head><body>
<a class="skip-link" href="#content">Skip to content</a>
<header><div class="branding">header</div><p>Call us any time on 555 0100</p></header>
<nav><a href="/a/">Alpha</a> <a href="/a">Alpha again, no slash</a>
<a href="/b/">Beta</a> <a href="/legacy">Legacy</a></nav>
<main id="content">
  <h1>Chain fixture home</h1>
  <p>The body of the home page, with enough words in it that the content region and the whole
  body are measurably different sizes rather than accidentally equal.</p>
  <p><a href="/gallery">Gallery</a> links straight to <a href="/photo.webp">a photo file</a>.</p>
  <p>An outbound link to <a href="https://other.example/x">another host</a>.</p>
  <p><a href="/private/">A path robots.txt disallows</a>.</p>
</main>
<footer>Copyright notice, terms, privacy, sitemap, careers, investors, press</footer>
</body></html>"""

PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>{title}</title>
<meta name="description" content="A fixture page with a description long enough to clear the validation threshold used by the audit.">
<link rel="canonical" href="{canonical}">
</head><body>
<header>header</header>
<main><h1>{title}</h1><p>{body}</p><p><a href="/">Home</a></p></main>
<footer>footer</footer>
</body></html>"""

LEGACY_HTML = (
    "<!doctype html><html lang='ru'><head><meta charset='windows-1251'>"
    "<title>Страница в старой кодировке</title>"
    "<meta name='description' content='Описание страницы, достаточно длинное для проверки.'>"
    "</head><body><main><h1>Заголовок</h1>"
    "<p>Текст страницы, записанный в кодировке windows-1251, чтобы длина в байтах "
    "отличалась от длины декодированной строки.</p></main></body></html>"
)

# Not valid UTF-8: every byte above 0x7F here decodes to U+FFFD, which re-encodes to three
# bytes. That is the whole mechanism behind the 1.72x size inflation.
PHOTO_BYTES = b"RIFF\x00\x00\x02\x00WEBPVP8 " + bytes(range(128, 256)) * 24

ROBOTS = "User-agent: *\nAllow: /\nDisallow: /private/\n"

SITEMAP = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>{base}/</loc></url>
  <url><loc>{base}/a/</loc></url>
  <url><loc>{base}/orphan/</loc></url>
</urlset>
"""


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
        base = f"http://{self.headers.get('Host', '127.0.0.1')}"
        path = self.path.split("?", 1)[0]

        if path == "/robots.txt":
            return self._send(ROBOTS.encode(), "text/plain; charset=utf-8")
        if path == "/sitemap.xml":
            return self._send(SITEMAP.format(base=base).encode(), "application/xml")
        if path == "/photo.webp":
            return self._send(PHOTO_BYTES, "image/webp")
        if path == "/legacy":
            return self._send(LEGACY_HTML.encode("windows-1251"), "text/html; charset=windows-1251")
        if path == "/a":
            # The slash-form redirect: this is what makes two crawled URLs share one key.
            return self._send(b"", "text/html", status=301, extra={"Location": f"{base}/a/"})
        if path == "/":
            return self._send(HOME.encode(), "text/html; charset=utf-8")
        if path in ("/a/", "/b/", "/gallery", "/private/", "/orphan/"):
            title = path.strip("/").title() or "Page"
            body = "Body text for the fixture page, long enough to be measured meaningfully."
            # /b/ canonicalises to the *slashless* form of /a/, which is the 301. Both forms
            # are in the crawl, so this is the exact shape that made CANONICAL_TO_REDIRECT
            # fire on 78 live pages whose canonical answers 200 (#95).
            canonical = f"{base}/a" if path == "/b/" else f"{base}{path}"
            html = PAGE.format(title=title, canonical=canonical, body=body)
            return self._send(html.encode(), "text/html; charset=utf-8")
        self._send(b"<html><body>not found</body></html>", "text/html", status=404)

    def log_message(self, format: str, *args) -> None:
        pass


@contextlib.contextmanager
def run_chain_site() -> Iterator[str]:
    """Serve the fixture site on an OS-assigned loopback port for the duration of the block."""
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
