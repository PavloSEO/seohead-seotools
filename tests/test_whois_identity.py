"""A whois record must be about the domain that was asked about.

Answering with the zone record produced a normal-looking registration for a
different object: every .ru domain came back aged 32.4 years, the .RU
delegation date. A confident wrong age silently changes an audit's conclusion.
"""

from seohead.recon import net
from seohead.recon.domain import whois_record_is_about

ZONE_RECORD = """
% By submitting a query you agree not to use the information
domain:      RU
nserver:     a.dns.ripn.net
created:     1994-04-07T00:00:00Z
"""

DOMAIN_RECORD = """
domain:      EXAMPLE.RU
registrar:   REGRU-RU
created:     2013-09-25T20:41:47Z
nserver:     ns1.example.ru
"""


def test_zone_record_is_rejected_for_a_domain_query():
    assert whois_record_is_about(ZONE_RECORD, "example.ru") is False


def test_matching_record_is_accepted_case_insensitively():
    assert whois_record_is_about(DOMAIN_RECORD, "example.ru") is True


def test_trailing_dot_does_not_break_the_match():
    assert whois_record_is_about("domain: example.ru.\n", "example.ru") is True


def test_record_without_an_identity_field_is_rejected():
    assert (
        whois_record_is_about("created: 2013-09-25\nnserver: ns1.example.ru\n", "example.ru")
        is False
    )


def test_gtld_style_domain_name_key_is_understood():
    assert whois_record_is_about("Domain Name: EXAMPLE.COM\n", "example.com") is True


def test_a_different_domain_is_rejected():
    assert whois_record_is_about("domain: other.ru\n", "example.ru") is False


# ── referral and server selection ────────────────────────────────────────────


def test_referral_field_is_extracted():
    text = "domain: RU\nwhois: whois.tcinet.ru\n"
    assert net._whois_field(text, net._WHOIS_REFERRAL_KEYS) == "whois.tcinet.ru"


def test_comment_lines_are_not_parsed_as_fields():
    text = "% whois: evil.example\ndomain: EXAMPLE.RU\n"
    assert net._whois_field(text, net._WHOIS_REFERRAL_KEYS) is None


def test_ru_is_mapped_to_the_registry_server():
    assert net.WHOIS_SERVERS_BY_TLD["ru"] == "whois.tcinet.ru"
    assert net.WHOIS_SERVERS_BY_TLD["xn--p1ai"] == "whois.tcinet.ru"


def test_a_referral_that_is_not_a_hostname_is_never_executed(monkeypatch):
    """The server comes from a registry response, so it is untrusted input."""
    calls: list[list[str]] = []

    class _Result:
        stdout = "domain: EXAMPLE.RU\n"

    def fake_run(argv, **kwargs):
        calls.append(argv)
        return _Result()

    monkeypatch.setattr(net.shutil, "which", lambda _: "/usr/bin/whois")
    monkeypatch.setattr(net.subprocess, "run", fake_run)
    assert net.whois_text("example.ru", server="evil.example; rm -rf /") is None
    assert calls == []


def test_a_valid_server_is_passed_as_arguments_not_through_a_shell(monkeypatch):
    calls: list[list[str]] = []

    class _Result:
        stdout = "domain: EXAMPLE.RU\n"

    monkeypatch.setattr(net.shutil, "which", lambda _: "/usr/bin/whois")
    monkeypatch.setattr(
        net.subprocess, "run", lambda argv, **kw: (calls.append(argv), _Result())[1]
    )
    net.whois_text("example.ru", server="whois.tcinet.ru")
    assert calls[0] == ["/usr/bin/whois", "-h", "whois.tcinet.ru", "example.ru"]
