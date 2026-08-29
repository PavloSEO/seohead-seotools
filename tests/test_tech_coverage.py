"""Coverage and validity checks for tech-detect signatures."""

from seohead.recon import tech

_VALID_KINDS = {"header", "value", "cookie", "html", "script"}


def test_all_signature_kinds_are_valid():
    bad = [(c, n, k) for c, n, k, _ in tech.SIGNATURES if k not in _VALID_KINDS]
    assert not bad, f"unsupported signature kinds: {bad}"


def test_signature_count_grew_significantly():
    # The 2026-08-12 expansion grew the registry from 81 to about 200 signatures.
    # Keep both signature and unique-technology coverage above this baseline.
    assert len(tech.SIGNATURES) >= 150
    assert len({n for _, n, _, _ in tech.SIGNATURES}) >= 140


def test_new_signatures_match_through_engine():
    # Use ant-design rather than the broad "ant-" marker, which matched
    # Tailwind's font-variant-numeric property.
    ctx_html = (
        '<div class="tailwind"><link href="/ant-design.min.css">'
        '<span class="ant-btn">x</span></div>'
    )
    ctx_headers = {"server": "Vercel", "cf-ray": "abc123", "x-served-by": "cache-fra"}
    ctx_scripts = "https://js.stripe.com/v3 swiper.js cdn.jsdelivr.net/npm/lodash"
    ctx_cookies = {"laravel_session": "x", "csrftoken": "y"}

    def matches(name):
        for _cat, n, kind, marker in tech.SIGNATURES:
            if n != name:
                continue
            return (
                tech._match(
                    kind,
                    marker,
                    html_low=ctx_html,
                    headers=ctx_headers,
                    cookies=ctx_cookies,
                    scripts_low=ctx_scripts,
                )
                is not None
            )
        return False

    for nm in (
        "Tailwind CSS",
        "Ant Design",
        "Vercel",
        "Cloudflare",
        "Fastly",
        "Stripe",
        "jsDelivr",
        "Lodash",
        "Laravel",
        "Django",
    ):
        assert matches(nm), f"the new {nm} signature did not match"
