"""On-page link checker behaviour at the HTTP target boundary."""

from types import SimpleNamespace

from seohead.tools import links


class _Client:
    def __init__(self):
        self.head_urls: list[str] = []

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def head(self, url):
        self.head_urls.append(url)
        return SimpleNamespace(status_code=200, headers={})


def test_fragment_variants_share_one_probe_without_displacing_a_unique_target(monkeypatch):
    client = _Client()
    monkeypatch.setattr(
        "seohead.tools.parser.parse_url",
        lambda *_args: {
            "ok": True,
            "links": [
                {"href": "https://example.com/guide#first", "external": False},
                {"href": "https://example.com/guide#second", "external": False},
                {"href": "https://example.com/other", "external": False},
            ],
        },
    )
    monkeypatch.setattr(links, "http_client", lambda *_args, **_kwargs: (client, False))

    result = links.check_links("https://example.com/", limit=2)

    assert client.head_urls == ["https://example.com/guide", "https://example.com/other"]
    assert result["checked"] == 2
    assert result["truncated"] is False
