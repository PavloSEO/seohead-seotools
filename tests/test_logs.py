"""Offline log-analysis tests that do not perform reverse-DNS lookups."""

from __future__ import annotations

from datetime import timezone

from seohead.tools.logs import (
    _section,
    analyze_log,
    detect_bot,
    detect_format,
    parse_apache_timestamp,
)

COMBINED = (
    '66.249.66.1 - - [18/Mar/2024:00:02:09 +0000] "GET /catalog/pumps HTTP/1.1" 200 5120 '
    '"-" "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"\n'
    '66.249.66.1 - - [18/Mar/2024:00:03:10 +0000] "GET /old-page HTTP/1.1" 404 0 '
    '"-" "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"\n'
    '20.15.1.2 - - [18/Mar/2024:01:00:00 +0000] "GET /blog/post HTTP/1.1" 200 8000 '
    '"-" "Mozilla/5.0 AppleWebKit (KHTML, like Gecko) Chrome/120 Safari/537.36"\n'
    '52.70.1.1 - - [19/Mar/2024:02:00:00 +0000] "GET /pricing HTTP/1.1" 200 3000 '
    '"-" "Mozilla/5.0 (compatible; GPTBot/1.0; +https://openai.com/gptbot)"\n'
    '1.2.3.4 - - [19/Mar/2024:03:00:00 +0000] "GET /catalog/x HTTP/1.1" 503 0 '
    '"-" "Mozilla/5.0 (compatible; AhrefsBot/7.0; +http://ahrefs.com/robot/)"\n'
)

COMMON = '24.5.66.10 - - [18/Mar/2024:00:02:09 +0000] "GET /old-pricing HTTP/1.1" 301 0\n'

IIS = (
    "#Software: Microsoft Internet Information Services 10.0\n"
    "#Fields: date time cs-uri-stem cs-uri-query cs-method c-ip cs(User-Agent) sc-status sc-bytes\n"
    "2024-03-18 00:02:09 /catalog/pumps - GET 66.249.66.1 "
    "Mozilla/5.0+(compatible;+Googlebot/2.1) 200 5120\n"
)


# ── Bot detection ────────────────────────────────────────────────────────────


def test_specific_signature_wins_over_generic():
    """Googlebot-Image must match before the generic Googlebot signature."""
    assert detect_bot("Googlebot-Image/1.0")["name"] == "Googlebot Image"
    assert detect_bot("Mozilla/5.0 (compatible; Googlebot/2.1)")["name"] == "Googlebot"


def test_human_is_not_a_bot():
    assert detect_bot("Mozilla/5.0 (Macintosh) Chrome/120 Safari/537.36") is None
    assert detect_bot(None) is None
    assert detect_bot("-") is None


def test_ai_crawlers_are_recognised_and_not_verifiable():
    """AI crawlers without official PTR ranges must not be marked as verifiable."""
    for ua, name in [
        ("GPTBot/1.0", "GPTBot (OpenAI)"),
        ("ClaudeBot/1.0", "ClaudeBot (Anthropic)"),
        ("PerplexityBot/1.0", "PerplexityBot"),
    ]:
        bot = detect_bot(ua)
        assert bot["name"] == name
        assert bot["family"] == "ai"
        assert bot["verifiable"] is False


def test_search_engines_are_verifiable():
    for ua in ("Googlebot/2.1", "bingbot/2.0", "YandexBot/3.0"):
        assert detect_bot(ua)["verifiable"] is True


# ── Timestamps ───────────────────────────────────────────────────────────────


def test_timezone_is_applied_in_the_right_direction():
    """A -0700 offset adds hours to UTC, while +0300 subtracts them."""
    west = parse_apache_timestamp("10/Oct/2000:13:55:36 -0700")
    assert (west.hour, west.tzinfo) == (20, timezone.utc)
    east = parse_apache_timestamp("10/Oct/2000:13:55:36 +0300")
    assert east.hour == 10


def test_broken_timestamp_returns_none_not_crash():
    assert parse_apache_timestamp("not a date") is None
    assert parse_apache_timestamp("32/Xxx/2024:00:00:00 +0000") is None


# ── Log formats ──────────────────────────────────────────────────────────────


def test_format_detection():
    assert detect_format(COMBINED.splitlines()) == "combined"
    assert detect_format(COMMON.splitlines()) == "common"
    assert detect_format(IIS.splitlines()) == "iis"
    assert detect_format(["garbage", "more garbage"]) is None


def test_sections_are_first_path_segment():
    assert _section("/catalog/pumps/cdm") == "/catalog"
    assert _section("/") == "/"
    assert _section("/pricing?utm=1") == "/pricing"


# ── End-to-end parsing ───────────────────────────────────────────────────────


def _write(tmp_path, text, name="access.log"):
    p = tmp_path / name
    p.write_text(text, encoding="utf-8")
    return str(p)


def test_combined_log_is_parsed_and_grouped(tmp_path):
    r = analyze_log(_write(tmp_path, COMBINED))
    assert r["ok"] and r["format"] == "combined"
    assert r["lines"]["parsed"] == 5 and r["lines"]["skipped"] == 0
    assert "googlebot" in r["by_family"] and "ai" in r["by_family"]
    assert "human" in r["by_family"] and "seo-tool" in r["by_family"]
    # Googlebot requested both the /catalog section and /old-page.
    assert "/catalog" in r["sections_by_family"]["googlebot"]
    # Bot response codes are aggregated separately from human requests.
    assert r["status_by_family"]["googlebot"][404] == 1


def test_iis_reads_field_positions_from_directive(tmp_path):
    r = analyze_log(_write(tmp_path, IIS, "u_ex.log"))
    assert r["ok"] and r["format"] == "iis"
    assert r["lines"]["parsed"] == 1
    assert "googlebot" in r["by_family"]


def test_verification_is_off_by_default(tmp_path):
    """Network verification must remain disabled without explicit permission."""
    r = analyze_log(_write(tmp_path, COMBINED))
    assert r["verification"]["checked"] is False


def test_missing_file_is_data_not_a_crash():
    r = analyze_log("/nope/does-not-exist.log")
    assert r["ok"] is False and "error" in r


def test_unparsable_file_says_so(tmp_path):
    r = analyze_log(_write(tmp_path, "definitely not a log\nsecond line\n"))
    assert r["ok"] is False
    assert "Apache Common/Combined" in r["error"]
    assert "IIS W3C" in r["error"]


def test_findings_flag_error_rate_for_bots(tmp_path):
    """The fixture gives AhrefsBot one 503 response, producing a 100% error rate."""
    r = analyze_log(_write(tmp_path, COMBINED))
    assert any(finding.startswith("seo-tool:") and "(100%)" in finding for finding in r["findings"])


def test_findings_mention_ai_crawlers(tmp_path):
    r = analyze_log(_write(tmp_path, COMBINED))
    assert any("GPTBot (OpenAI)" in finding for finding in r["findings"])
