"""Selective JavaScript-rendering escalation over an already-completed static
crawl, and the pre-flight gate that stops an empty shell or a link-less start
page from reaching a health score.

Rendering costs roughly an order of magnitude more per URL than a static
fetch (#18), so this module never renders the whole crawl. It samples a
handful of URLs per detected *template pattern* rather than per URL, decides
per pattern whether the static and rendered document diverge enough to
matter, and only then re-fetches the fuller representation for pages that
share an escalated pattern -- inside its own, separate budget.

Both the sampling probe and the full re-fetch are injected callables. That
is what keeps this module testable without a browser or the network: the
production caller (``seohead.servers.handlers.crawl_site``) binds them to
``seohead.tools.render``'s Playwright-backed functions; a test binds them to
plain functions returning canned data.

Which fuller representation is fetched -- executing JavaScript, or honouring
the legacy ``_escaped_fragment_`` scheme -- is the caller's business, not
this module's: ``escalate()`` only asks "does this pattern need a fuller
fetch" and "go get it", and records whatever label the caller passes as the
representation that produced each page's evidence going forward. That
recording is the point of #18's central rule: raw and rendered numbers are
not comparable, so every finding must say which one produced it.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field, fields
from typing import Any, Protocol
from urllib.parse import urlsplit, urlunsplit


class _HasUrl(Protocol):
    url: str


# A path segment shaped like this is almost certainly a per-item identifier
# (numeric id, slug, UUID) rather than part of the template. Collapsing it is
# what lets two pages of one template share a single pattern key, so a
# hundred product pages are sampled as one pattern instead of a hundred --
# over-grouping only costs one extra sample, never a missed escalation, since
# every page under an escalated pattern is still re-fetched.
_ID_SEGMENT_RE = re.compile(
    r"^(?:\d+"
    r"|[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
    r"|[\w-]{9,})$"
)


def url_pattern(url: str) -> str:
    """Collapse a URL's identifier-shaped path segments into a template key.

    A heuristic, not a template engine. Query string and fragment are
    dropped entirely: they vary per item at least as often as path segments
    do, and keeping them would turn "one pattern per template" back into
    "one pattern per URL".
    """
    parts = urlsplit(url)
    segments = ["*" if seg and _ID_SEGMENT_RE.match(seg) else seg for seg in parts.path.split("/")]
    return urlunsplit((parts.scheme, parts.netloc, "/".join(segments), "", ""))


def select_samples(urls: Iterable[str], sample_per_pattern: int) -> dict[str, list[str]]:
    """Group URLs by pattern and keep only the first N of each for probing."""
    n = max(1, int(sample_per_pattern))
    groups: dict[str, list[str]] = {}
    for u in urls:
        groups.setdefault(url_pattern(u), []).append(u)
    return {pattern: members[:n] for pattern, members in groups.items()}


@dataclass
class GateResult:
    """Whether a run is a false-green that must not reach a health score."""

    requires_rendering: bool = False
    reason: str = ""


def start_page_gate(start_url: str, internal_outlinks: int, start_html: str) -> GateResult:
    """Catch the two shapes of "fetched fine, proved nothing" before scoring.

    An empty shell fetches cleanly, yields one URL, and produces a
    clean-looking audit -- exactly the false-green #18 asks this gate to
    stop. Both checks here are static-only: an empty SPA shell is a raw-HTML
    regex match, and the outlink count comes from the ordinary parse of the
    start page. Neither needs a browser, so this gate applies even to a
    ``rendering.mode: "raw"`` run -- the one that most needs it, since raw
    mode has no render to fall back on.
    """
    if internal_outlinks <= 0:
        return GateResult(True, f"the start URL yielded zero internal links: {start_url}")
    if start_html:
        from seohead.tools.render import detect_empty_shell

        shell = detect_empty_shell(start_html)
        if shell:
            return GateResult(
                True,
                f'the start URL is a detected empty SPA shell (<div id="{shell}">): {start_url}',
            )
    return GateResult(False, "")


@dataclass
class EscalationResult:
    schema_version: str = "render_escalation.v1"
    mode: str = "raw"
    patterns_sampled: int = 0
    patterns_escalated: list[str] = field(default_factory=list)
    # Request counts are how "selective" is proven rather than asserted: a
    # crawl of 500 URLs across 12 patterns should show on the order of 24
    # probe requests, not 500 -- see the acceptance criterion in #18.
    probe_requests: int = 0
    render_requests: int = 0
    render_budget_exhausted: bool = False
    empty_shell_urls: list[str] = field(default_factory=list)
    # url -> the representation that produced its evidence going forward.
    representations: dict[str, str] = field(default_factory=dict)
    # url -> whatever render_fetch() returned for it (html, final_url, ...).
    rendered: dict[str, dict[str, Any]] = field(default_factory=dict)
    # URLs where render_fetch() returned ok:True but the parsed body cleared
    # none of apply_rendered_evidence()'s floor -- a client-side crash after
    # load, a cookie wall, a script blocked by an extension, an app that
    # never hydrates. The raw record is kept for these (#143); this list is
    # what makes the downgrade-that-didn't-happen auditable instead of silent.
    degenerate_render_urls: list[str] = field(default_factory=list)


def escalate(
    pages: Iterable[_HasUrl],
    rendering_config: dict[str, Any],
    *,
    probe: Callable[[str], dict[str, Any]],
    render_fetch: Callable[[str], dict[str, Any]],
    representation_label: str,
) -> EscalationResult:
    """Sample, decide, and selectively re-fetch -- see the module docstring.

    ``probe(url)`` answers "does this URL's pattern need a fuller fetch": it
    must return a dict with ``ok`` and ``needs_escalation``, and may include
    ``empty_shell`` (an SPA mount-point id, or a falsy value). ``render_fetch
    (url)`` performs the fuller fetch for one page and must return a dict
    with ``ok`` and, when ``ok``, ``html``. Both are entirely the caller's
    business -- this function only counts requests and applies the two
    budgets (patterns sampled, then URLs rendered).
    """
    urls = [p.url for p in pages]
    result = EscalationResult(mode=rendering_config.get("mode", "raw"))
    for u in urls:
        result.representations[u] = "static"

    escalation_cfg = rendering_config.get("escalation", {})
    samples = select_samples(urls, escalation_cfg.get("sample_per_pattern", 1))
    result.patterns_sampled = len(samples)

    escalated: set[str] = set()
    for pattern, sample_urls in samples.items():
        needs_it = False
        for sample_url in sample_urls:
            probed = probe(sample_url)
            result.probe_requests += 1
            if not probed.get("ok"):
                continue
            if probed.get("empty_shell"):
                result.empty_shell_urls.append(sample_url)
            if probed.get("needs_escalation"):
                needs_it = True
        if needs_it:
            escalated.add(pattern)
    result.patterns_escalated = sorted(escalated)
    if not escalated:
        return result

    by_pattern: dict[str, list[str]] = {}
    for u in urls:
        by_pattern.setdefault(url_pattern(u), []).append(u)

    budget = int(escalation_cfg.get("max_render_urls", 0))
    for pattern in result.patterns_escalated:
        if budget <= 0:
            result.render_budget_exhausted = True
            break
        for target_url in by_pattern.get(pattern, []):
            if budget <= 0:
                result.render_budget_exhausted = True
                break
            fetched = render_fetch(target_url)
            result.render_requests += 1
            budget -= 1
            if fetched.get("ok"):
                result.representations[target_url] = representation_label
                result.rendered[target_url] = fetched
    return result


def _clears_content_floor(record: Any) -> bool:
    """A non-trivial word count, or at least one of title/h1/canonical present.

    The same ``EMPTY_BODY_WORDS``-style reasoning
    ``seohead.tools.render.detect_empty_shell`` already applies to an empty
    SPA shell, reused here as the minimum signal that a ``PageRecord`` (raw
    or freshly re-derived from a render) describes a real page rather than a
    blank one -- see ``apply_rendered_evidence``.
    """
    from seohead.tools.render import EMPTY_BODY_WORDS

    return bool(
        record.word_count >= EMPTY_BODY_WORDS or record.title or record.h1 or record.canonical
    )


# PageRecord fields apply_rendered_evidence must never touch: identity/transport
# facts of the *static* fetch (url, status_code, ...), the two outlink counts
# (recomputed below as the raw/rendered union, never a plain overwrite), and
# the bookkeeping fields this function itself decides (error, cache_status,
# representation). Every other field is body-derived and belongs to whichever
# body last produced it -- see _apply_body.
_RENDER_UNTOUCHED_FIELDS = frozenset(
    {
        "url",
        "status_code",
        "content_type",
        "response_time",
        "redirect_url",
        "x_robots",
        "content_encoding",
        "crawl_depth",
        "outlinks",
        "external_outlinks",
        "error",
        "cache_status",
        "representation",
    }
)


def apply_rendered_evidence(
    pages: list[Any],
    raw_links: Iterable[Any],
    escalation: EscalationResult,
) -> None:
    """Fold each re-fetched page's fuller HTML back into its ``PageRecord``.

    Every body-derived field is filled in by ``_apply_body`` -- the same
    function a live fetch and a cache hit already share (#99) -- instead of
    a second, hand-rolled copy of what it does. That is what #139 found
    missing: calling ``_record_from_parsed`` directly here left `size_bytes`,
    `text_ratio`, `jsonld_blocks_found` and `jsonld_blocks_parsed` at the
    static fetch's values while `title` and `word_count` moved on.

    ``size_bytes`` for a rendered page is the length of the DOM Playwright
    serialized back to us, not "bytes on the wire" (#99's original sense) --
    a rendered document was never transferred as this string, so there is no
    wire size to report for it. The serialized length is the only honest
    stand-in, and it is exactly what ``_apply_body`` already falls back to
    whenever no real byte count is supplied, so no ``size_bytes`` argument is
    passed through here on purpose.

    A render is only rejected as failed when it takes a record that already
    showed a real page -- a non-trivial word count, or at least one of
    title/h1/canonical present, the same ``EMPTY_BODY_WORDS``-style
    reasoning ``seohead.tools.render.detect_empty_shell`` already applies to
    an empty SPA shell -- and produces a body that clears none of those
    signals. That comparison is deliberately one-sided: a raw record that
    was already an empty shell has nothing left to lose, so its rendered
    replacement is applied even when it too is thin (that is exactly #139's
    case -- rendering an empty static shell into a real, if imperfect,
    document). What must never happen is the other direction: a raw record
    that already carried real content being overwritten by an emptier
    rendered one (#143). A page that is merely thinner after rendering while
    still clearing the floor is not failed -- it is a real finding (JS
    hydration removing content a non-rendering crawler cannot see), and it
    must still reach the report as the rendered numbers, not be silently
    kept as the raw ones. A render that fails this test, or whose body fails
    to parse at all (``_apply_body`` returns ``None``), is treated as
    failed: `representation` and every raw field are left exactly as the
    static fetch produced them, and the URL is recorded in
    ``degenerate_render_urls`` so the downgrade-that-didn't-happen is
    auditable instead of silent.

    Outlinks are the union of what the raw HTML and the fuller fetch each
    found, never the fuller fetch alone: a link hydration removes is a real
    finding (#18), not a link that never existed, and dropping it here would
    make that finding invisible to every check built on outlink counts.
    """
    from dataclasses import replace
    from urllib.parse import urlsplit

    from seohead.crawl.collect import _apply_body

    raw_links_by_page: dict[str, set[str]] = {}
    for edge in raw_links:
        raw_links_by_page.setdefault(edge.source, set()).add(edge.destination)

    by_url = {p.url: p for p in pages}
    for target_url, fetched in escalation.rendered.items():
        record = by_url.get(target_url)
        html = fetched.get("html")
        if record is None or not html:
            continue
        final_url = fetched.get("final_url") or target_url

        # Judge the render on a scratch copy first -- _apply_body mutates in
        # place, and whether a render clears the floor can only be known
        # after deriving it. The real record is touched only once accepted.
        scratch = replace(record)
        # render_fetch always hands back a rendered DOM, HTML by definition;
        # a fresh PageRecord (as in a test fixture, or a page never given a
        # content-type by its raw fetch) may still have content_type == "",
        # which would make _apply_body's is_html guard reject it wrongly.
        scratch.content_type = scratch.content_type or "text/html"

        raw_had_content = _clears_content_floor(record)
        parsed = _apply_body(scratch, final_url, html)
        rendered_has_content = parsed is not None and _clears_content_floor(scratch)
        if raw_had_content and not rendered_has_content:
            escalation.degenerate_render_urls.append(target_url)
            continue

        record.representation = escalation.representations.get(target_url, "static")
        for f in fields(record):
            if f.name not in _RENDER_UNTOUCHED_FIELDS:
                setattr(record, f.name, getattr(scratch, f.name))

        rendered_hrefs = {link["href"] for link in parsed.get("links") or []}
        merged = raw_links_by_page.get(target_url, set()) | rendered_hrefs
        host = (urlsplit(final_url).hostname or "").lower()
        record.outlinks = len(merged)
        record.external_outlinks = sum(
            1 for href in merged if (urlsplit(href).hostname or "").lower() != host
        )
