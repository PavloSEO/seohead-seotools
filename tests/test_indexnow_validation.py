"""IndexNow must reject invalid batches before credentials or network access."""

import pytest

from seohead.data_sources import credentials, indexnow


@pytest.mark.parametrize(
    "url",
    [
        "https://unrelated.example/path",
        "https://owned.example.unrelated.example/path",
        "https://www.owned.example/path",
        "https://owned.example@unrelated.example/path",
        "https://user:password@owned.example/path",
        "/relative/path",
        "//owned.example/path",
        "https:///path",
        "ftp://owned.example/path",
        "https://[owned.example/path",
        "https://owned.example:invalid/path",
        "https://owned.example:65536/path",
        "https://owned.example:/path",
        "https://owned.example/has space",
        "https://owned.example/line\nbreak",
        "https://owned.example/control\x80",
        "https://owned.example/a%zz",
        "https://owned.example/%",
        "https://owned.example/%2",
        "https://owned.example\\@unrelated.example/path",
    ],
)
def test_invalid_url_rejects_the_entire_batch_before_credentials_or_network(monkeypatch, url):
    def forbidden(*args):
        pytest.fail("invalid input must not load a key or submit any URLs")

    monkeypatch.setattr(credentials, "indexnow_key", forbidden)
    result = indexnow.submit(
        ["https://owned.example/valid", url], host="owned.example", fetcher=forbidden
    )
    assert result["ok"] is False
    assert "URL 2" in result["error"]


@pytest.mark.parametrize(
    "host",
    ["https://owned.example", "owned.example/path", "owned.example:443", "owned..example"],
)
def test_invalid_host_fails_locally(monkeypatch, host):
    def forbidden(*args):
        pytest.fail("invalid host must not load a key or submit URLs")

    monkeypatch.setattr(credentials, "indexnow_key", forbidden)
    result = indexnow.submit(["https://owned.example/"], host=host, fetcher=forbidden)
    assert result["ok"] is False
    assert "host" in result["error"]


@pytest.mark.parametrize(
    ("host", "url"),
    [("fass.de", "https://faß.de/a"), ("faß.de", "https://fass.de/a")],
)
def test_idna2008_keeps_distinct_hosts_separate(monkeypatch, host, url):
    def forbidden(*args):
        pytest.fail("a distinct IDNA hostname must not load a key or submit URLs")

    monkeypatch.setattr(credentials, "indexnow_key", forbidden)
    result = indexnow.submit([url], host=host, fetcher=forbidden)
    assert result["ok"] is False


@pytest.mark.parametrize(
    ("host", "urls", "expected_host"),
    [
        (
            "OWNED.example.",
            [
                "http://owned.example/a",
                "https://OWNED.example./b?x=1",
                "http://owned.example:80/c",
                "https://owned.example:443/d",
                "https://owned.example:8443/e",
                "https://owned.example/encoded%20path?x=%25",
            ],
            "owned.example",
        ),
        ("bücher.example", ["https://xn--bcher-kva.example/a"], "xn--bcher-kva.example"),
        ("faß.de", ["https://xn--fa-hia.de/a"], "xn--fa-hia.de"),
    ],
)
def test_same_host_urls_preserve_payload(host, urls, expected_host):
    sent = []
    result = indexnow.submit(
        urls,
        host=host,
        key="synthetic-key",
        fetcher=lambda payload: sent.append(payload) or (202, ""),
    )
    assert sent == [{"host": expected_host, "key": "synthetic-key", "urlList": urls}]
    assert result["ok"] is True
    assert result["submitted"] == len(urls)
    assert "key validation pending" in result["message"]
    assert "indexing" in result["message"]
