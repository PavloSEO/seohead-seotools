"""Network-free tests for AI crawler access checks."""

from seohead.recon import ai_bots


def test_gptbot_blocked_by_disallow_root():
    robots = "User-agent: GPTBot\nDisallow: /\n"
    r = ai_bots.check_ai_access(robots)
    gpt = next(b for b in r["bots"] if b["token"] == "GPTBot")
    assert gpt["status"] == "blocked"
    assert gpt["blocked_root"] is True
    assert gpt["declared_in_robots"] is True
    assert r["summary"]["blocked"] >= 1


def test_bot_allowed_by_default_when_not_declared():
    robots = "User-agent: *\nAllow: /\n"
    r = ai_bots.check_ai_access(robots)
    gpt = next(b for b in r["bots"] if b["token"] == "GPTBot")
    assert gpt["status"] == "allowed_default"
    assert gpt["declared_in_robots"] is False
    assert gpt["blocked_root"] is False


def test_bot_explicitly_allowed():
    robots = "User-agent: PerplexityBot\nAllow: /\n"
    r = ai_bots.check_ai_access(robots)
    perp = next(b for b in r["bots"] if b["token"] == "PerplexityBot")
    assert perp["status"] == "allowed_explicit"
    assert perp["declared_in_robots"] is True


def test_summary_counts_match():
    robots = (
        "User-agent: GPTBot\nDisallow: /\n"
        "User-agent: CCBot\nDisallow: /\n"
        "User-agent: PerplexityBot\nAllow: /\n"
    )
    r = ai_bots.check_ai_access(robots)
    s = r["summary"]
    assert s["blocked"] == 2
    assert s["allowed_explicit"] == 1
    assert s["allowed_default"] == len(ai_bots.AI_BOTS) - 3
    # The GPTBot and CCBot training crawlers are blocked.
    assert s["by_type"]["training"]["blocked"] == 2


def test_all_bots_cover_training_retrieval_user():
    r = ai_bots.check_ai_access("")
    types = {b["type"] for b in r["bots"]}
    assert {"training", "retrieval", "user"} <= types
