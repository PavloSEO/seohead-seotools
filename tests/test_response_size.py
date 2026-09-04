"""``size_bytes`` is the response as it arrived, not its decoded text (issue #99).

Every fixture in the rest of the suite is valid UTF-8, which round-trips exactly — which is
precisely why measuring the decoded string looked correct for as long as it did. These cases
are the ones where the two numbers differ: a binary body, and HTML in a legacy charset.
"""

from __future__ import annotations

from seohead.crawl.cache import ResponseCache
from seohead.crawl.collect import fetch_one


class ByteResponse:
    """A response the way httpx presents one: bytes on the wire, plus a decoded view."""

    def __init__(self, content: bytes, headers: dict[str, str], encoding: str = "utf-8"):
        self.content = content
        self.text = content.decode(encoding, "replace")
        self.status_code = 200
        self.headers = headers


def _patched(monkeypatch):
    import seohead.crawl.collect as collect_mod

    monkeypatch.setattr(collect_mod, "validate_url", lambda u: u)
    monkeypatch.setattr(collect_mod, "pinned_target", lambda u: (u, {"Host": "example.com"}, {}))


class OneShotClient:
    def __init__(self, response):
        self.response = response
        self.requests: list[dict] = []

    def get(self, target, *, headers, extensions):
        self.requests.append({"target": target, "headers": headers})
        return self.response


# A WebP header followed by bytes that are not valid UTF-8 — the shape of the real case:
# a 851 KB image the crawl reported as 1.5 MB.
BINARY = b"RIFF\x00\x00\x01\x00WEBPVP8 " + bytes(range(128, 256)) * 8


def test_a_binary_response_is_measured_by_its_bytes(monkeypatch):
    _patched(monkeypatch)
    response = ByteResponse(BINARY, {"content-type": "image/webp"})
    # The decoded form is longer: every undecodable byte became U+FFFD, three bytes re-encoded.
    assert len(response.text.encode("utf-8", "ignore")) > len(BINARY)

    record, parsed = fetch_one("https://example.com/i.webp", client=OneShotClient(response))

    assert record.size_bytes == len(BINARY)
    assert parsed is None  # not HTML, nothing to parse


def test_legacy_charset_html_is_measured_by_its_bytes_and_its_text_ratio_follows(monkeypatch):
    _patched(monkeypatch)
    html = (
        "<html><head><meta charset='windows-1251'><title>Тест</title></head>"
        "<body><h1>Заголовок</h1><p>Текст страницы для проверки.</p></body></html>"
    )
    content = html.encode("windows-1251")
    response = ByteResponse(
        content, {"content-type": "text/html; charset=windows-1251"}, encoding="windows-1251"
    )

    record, _ = fetch_one("https://example.com/", client=OneShotClient(response))

    assert record.size_bytes == len(content)
    # The denominator of the ratio is the same true size, so the ratio is a real percentage.
    assert record.text_ratio is not None
    assert 0 < record.text_ratio <= 100


def test_a_fetcher_with_no_byte_view_still_reports_a_size(monkeypatch):
    """An injected fetcher hands back only ``.text``; the encoded length is the honest
    fallback there, and it is exact for the UTF-8 fixtures such a fetcher returns."""
    _patched(monkeypatch)
    html = "<html><head><title>t</title></head><body>hi</body></html>"

    class TextOnly:
        def __init__(self) -> None:
            self.text = html
            self.status_code = 200
            self.headers = {"content-type": "text/html"}

    record, _ = fetch_one("https://example.com/", fetcher=lambda url: TextOnly())
    assert record.size_bytes == len(html.encode("utf-8"))


def test_a_replayed_page_reports_the_size_the_live_fetch_reported(monkeypatch, tmp_path):
    """The cache stores the wire size, because it cannot be recovered from the stored text."""
    _patched(monkeypatch)
    cache = ResponseCache(tmp_path)
    response = ByteResponse(BINARY, {"content-type": "image/webp", "cache-control": "max-age=3600"})
    client = OneShotClient(response)

    first, _ = fetch_one("https://example.com/i.webp", client=client, cache=cache)
    assert first.cache_status == "miss"

    second, _ = fetch_one("https://example.com/i.webp", client=client, cache=cache)
    assert second.cache_status == "hit"
    assert len(client.requests) == 1, "a hit must never call the client again"
    assert second.size_bytes == first.size_bytes == len(BINARY)
