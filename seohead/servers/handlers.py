"""Shared handler layer over the core, used by both the CLI and local stdio MCP server.

Each function takes/returns plain JSON-serializable objects (headless). Add new
behavior to the core + a handler here, then surface it in each face.
"""

from __future__ import annotations

from typing import Any

from seohead import runlog
from seohead.tools import (
    clusterer,
    downloader,
    optimizer,
    parser,
    sitemap,
)
from seohead.tools import (
    headers as headers_core,
)
from seohead.tools import (
    hreflang as hreflang_core,
)
from seohead.tools import (
    links as links_core,
)
from seohead.tools import (
    robots as robots_core,
)

# SEO core is extracted BY DEFAULT (the caller can turn any field off with False).
DEFAULT_PARSE_OPTIONS: dict[str, bool] = {
    "meta": True,
    "canonical": True,
    "og": True,
    "headings": True,
    "jsonld": True,
    "links": True,
    "text": True,
}


def parse(
    url: str | None = None, urls: list[str] | None = None, options: dict[str, Any] | None = None
) -> dict[str, Any]:
    targets = urls if isinstance(urls, list) else ([url] if url else [])
    if not targets:
        raise ValueError("url or urls[] required")
    opts = {**DEFAULT_PARSE_OPTIONS, **(options or {})}
    results = [parser.parse_url(str(u), opts) for u in targets]
    return {"count": len(results), "results": results}


def redirects_generate(
    redirects: list[dict] | None = None,
    fmt: str = "apache-rewrite-rule",
    default_url: str = "/",
    custom_template: str = "",
) -> dict[str, Any]:
    from seohead.tools import redirects as redirects_core

    items = redirects if isinstance(redirects, list) else []
    return {"rules": redirects_core.generate_rules(items, fmt, default_url, custom_template)}


def redirects_check(
    url: str | None = None, options: dict[str, Any] | None = None
) -> dict[str, Any]:
    if not url:
        raise ValueError("url required")
    from seohead.tools import redirects as redirects_core

    return {"chain": redirects_core.check_chain(url, options or {})}


def sitemap_crawl(url: str | None = None, concurrency: int = 3) -> dict[str, Any]:
    if not url:
        raise ValueError("url required")
    return sitemap.crawl(url, concurrency)


def crawl_site(
    url: str | None = None,
    urls: list[str] | None = None,
    config: str | None = None,
    max_urls: int | None = None,
    max_depth: int | None = None,
    min_delay: float | None = None,
    robots: str | None = None,
    out_dir: str | None = None,
) -> dict[str, Any]:
    """Crawl a site from a start URL, or fetch an explicit list, then audit it.

    The interface layer is where collector and analyzer are allowed to meet:
    ``seohead.crawl`` gathers evidence and never imports the analyzer,
    ``seohead.sf`` judges it and never imports the collector, and this function
    hands the projection from one to the other.

    ``min_delay`` defaults to half a second because the target is somebody's
    production site: polite by accident beats fast by accident.
    """
    import json
    import os
    from datetime import datetime, timezone

    from seohead.crawl import config as crawl_config
    from seohead.crawl.collect import collect_urls
    from seohead.crawl.evidence import build_evidence
    from seohead.crawl.spider import crawl_site as _spider
    from seohead.sf.config import load_config
    from seohead.sf.core.aggregate import aggregate
    from seohead.sf.core.context import AuditContext
    from seohead.sf.core.loader import LoadedExports
    from seohead.sf.core.rules import run_rules

    if not url and not urls:
        raise ValueError("url or urls required")

    # Defaults, then file, then environment, then these explicit arguments.
    settings = crawl_config.load(
        config,
        overrides={
            "limits.max_urls": max_urls,
            "limits.max_depth": max_depth,
            "speed.min_delay_seconds": min_delay,
            "robots.policy": robots,
            "output.dir": out_dir,
        },
    )
    out_dir = settings["output"]["dir"] or None
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    pages_path = (
        os.path.join(out_dir, "pages.jsonl")
        if out_dir and settings["output"]["write_pages_jsonl"]
        else None
    )

    if url:
        result = _spider(
            url,
            max_urls=settings["limits"]["max_urls"],
            max_depth=settings["limits"]["max_depth"],
            min_delay=settings["speed"]["min_delay_seconds"],
            timeout=settings["http"]["timeout_seconds"],
            respect_robots=settings["robots"]["policy"] != "ignore",
            out_path=pages_path,
        )
        discovery = {
            "mode": "spider",
            "max_depth_reached": result.max_depth_reached,
            "links_seen": len(result.links),
            "excluded": result.excluded,
            "robots_note": result.robots_note,
        }
    else:
        result = collect_urls(
            urls or [],
            max_urls=settings["limits"]["max_urls"],
            min_delay=settings["speed"]["min_delay_seconds"],
            timeout=settings["http"]["timeout_seconds"],
            out_path=pages_path,
        )
        discovery = {"mode": "list"}

    evidence = build_evidence(result)
    exports = LoadedExports()
    exports.frames.update(evidence["frames"])
    exports.found = list(evidence["found"])
    exports.missing = list(evidence["missing"])

    ctx = AuditContext(exports, load_config(None))
    ctx.skip_unsupported(set(exports.frames))
    run_rules(ctx)
    audit = aggregate(
        ctx,
        {
            "input_mode": "crawl" if url else "crawl-list",
            "source": url or "url-list",
            "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "collector": "seohead.crawl",
            "crawl_partial": result.partial,
            "crawl_stopped_reason": result.stopped_reason,
            # Resolved values of every setting that can change what was found.
            # Without these two reports on the same site are not comparable.
            "crawl_config": crawl_config.manifest(settings),
            "effective_max_requests_per_second": crawl_config.effective_request_rate(settings),
        },
        {},
        {},
    ).to_json()

    if out_dir:
        with open(os.path.join(out_dir, "audit.json"), "w", encoding="utf-8") as fh:
            json.dump(audit, fh, ensure_ascii=False, indent=2)

    return {
        "urls_collected": len(result.pages),
        "partial": result.partial,
        "stopped_reason": result.stopped_reason,
        "discovery": discovery,
        "limitations": result.limitations,
        "summary": audit["summary"],
        "checks_skipped": len(audit["run"].get("checks_skipped", [])),
        "out_dir": out_dir,
    }


def images_download(
    urls: list[str] | None = None,
    output_dir: str | None = None,
    options: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not output_dir:
        raise ValueError("output_dir required")
    results = downloader.download_images(urls or [], output_dir, options or {})
    return {"count": len(results), "results": results}


def images_optimize(
    files: list[str] | None = None, settings: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Optimize image files with explicit output semantics.

    Provide ``settings.out_dir`` for non-destructive output. Rewriting source files requires the
    caller to opt in with ``settings.in_place=true``; the optimizer's backup safeguards still apply.
    """
    if not files:
        raise ValueError("files[] required")
    return optimizer.optimize_files(files, settings or {})


def keywords_cluster(**params: Any) -> dict[str, Any]:
    return clusterer.run_clusterer(params)


def robots_check(
    url: str | None = None, user_agent: str = "*", paths: list[str] | None = None
) -> dict[str, Any]:
    if not url:
        raise ValueError("url required")
    return robots_core.check_robots(url, user_agent=user_agent, paths=paths)


def headers_check(url: str | None = None, method: str = "GET") -> dict[str, Any]:
    if not url:
        raise ValueError("url required")
    return headers_core.check_headers(url, method=method)


def links_check(
    url: str | None = None, internal_only: bool = False, limit: int = 200
) -> dict[str, Any]:
    if not url:
        raise ValueError("url required")
    return links_core.check_links(url, internal_only=internal_only, limit=limit)


def hreflang_check(url: str | None = None) -> dict[str, Any]:
    if not url:
        raise ValueError("url required")
    return hreflang_core.check_hreflang(url)


def domain_profile(domain: str | None = None, with_tls: bool = True) -> dict[str, Any]:
    if not domain:
        raise ValueError("domain required")
    from seohead.recon import domain as domain_core

    return domain_core.profile_domain(domain, with_tls=with_tls)


def cdn_check(url: str | None = None) -> dict[str, Any]:
    if not url:
        raise ValueError("url required")
    from seohead.recon import cdn as cdn_core

    return cdn_core.check_cdn(url)


def tech_detect(url: str | None = None) -> dict[str, Any]:
    if not url:
        raise ValueError("url required")
    from seohead.recon import tech as tech_core

    return tech_core.detect_tech(url)


def security_check(url: str | None = None, probe_paths: bool = False) -> dict[str, Any]:
    if not url:
        raise ValueError("url required")
    from seohead.recon import security as security_core

    return security_core.check_security(url, probe_paths=bool(probe_paths))


def schema_check(url: str | None = None, html: str | None = None) -> dict[str, Any]:
    if not url and not html:
        raise ValueError("url or html required")
    from seohead.tools import schema as schema_core

    return schema_core.check_schema(url=url, html=html)


def schema_build(
    url: str | None = None, html: str | None = None, override_type: str | None = None
) -> dict[str, Any]:
    if not url and not html:
        raise ValueError("url or html required")
    from seohead.tools import schema_build as builder

    return builder.build_schema(url=url, html=html, override_type=override_type)


def log_analyze(path: str | None = None, verify_bots: bool = False) -> dict[str, Any]:
    if not path:
        raise ValueError("path required (web server access-log file)")
    from seohead.tools import logs as logs_core

    return logs_core.analyze_log(path, verify_bots=bool(verify_bots))


def regions_check(
    url: str | None = None, extra: list[str] | None = None, limit: int = 12, render: bool = False
) -> dict[str, Any]:
    if not url:
        raise ValueError("url required (any site page, usually the home page)")
    from seohead.recon import regions as regions_core

    return regions_core.analyze_regions(url, extra=extra or [], limit=limit, render=bool(render))


def site_audit(
    url: str | None = None,
    urls: list[str] | None = None,
    limit: int = 25,
    concurrency: int = 5,
    render: bool = False,
    skip: list[str] | None = None,
) -> dict[str, Any]:
    if not url:
        raise ValueError("url required (site home page)")
    from seohead.audit.site import audit_site

    return audit_site(
        url, urls=urls, limit=limit, concurrency=concurrency, render=bool(render), skip=skip
    )


def report_build(audit: Any = None, fmt: str = "xlsx", out: str | None = None) -> dict[str, Any]:
    if audit is None:
        raise ValueError("audit required: audit document or path to its JSON representation")
    from seohead.reports import build_report

    return build_report(audit, fmt=fmt, path=out)


def render_check(
    url: str | None = None, viewport: str = "desktop", wait: str = "load"
) -> dict[str, Any]:
    if not url:
        raise ValueError("url required")
    from seohead.tools import render as render_core

    return render_core.render_check(url, viewport=viewport, wait=wait)


def backlinks_check(
    target: str | None = None, donors: list[str] | None = None, concurrency: int = 3
) -> dict[str, Any]:
    if not target:
        raise ValueError("target required")
    if not donors:
        raise ValueError("donors[] required")
    from seohead.recon import backlinks as backlinks_core

    return backlinks_core.check_backlinks(target, donors, concurrency=concurrency)


def duplicate_check(
    items: list[dict] | None = None, threshold: float = 0.92, with_fingerprints: bool = False
) -> dict[str, Any]:
    if not items:
        raise ValueError("items[] required (list of {id, text})")
    from seohead.tools import duplicate as dup_core

    return dup_core.find_duplicates(items, threshold=threshold, with_fingerprints=with_fingerprints)


def mirror_check(url: str | None = None, timeout: float = 12.0) -> dict[str, Any]:
    """Verify canonical host consolidation across scheme, ``www``, index-file, case, and slash variants."""
    if not url:
        raise ValueError("url required")
    from seohead.recon import mirrors as mirrors_core

    return mirrors_core.check_mirrors(url, timeout=timeout)


def ai_bots_check(url: str | None = None, robots_text: str | None = None) -> dict[str, Any]:
    """Evaluate AI-crawler access from supplied robots.txt content or a site URL."""
    if not url and not robots_text:
        raise ValueError("url or robots_text required")
    from seohead.recon import ai_bots as ai_bots_core

    if robots_text is None:
        from seohead.recon.net import http_client, normalize_url

        target = normalize_url(url or "")
        if not target:
            return {"ok": False, "error": f"not a recognizable URL: {url!r}"}
        from urllib.parse import urlsplit, urlunsplit

        parts = urlsplit(target)
        robots_url = urlunsplit((parts.scheme, parts.netloc, "/robots.txt", "", ""))
        try:
            client, _ = http_client(20.0)
            with client:
                resp = client.get(robots_url)
            robots_text = resp.text
            fetched = {"robots_url": robots_url, "status_code": resp.status_code}
        except Exception as exc:  # Tool boundary: network failures are result data, not crashes.
            return {"ok": False, "url": robots_url, "error": str(exc)}
    else:
        fetched = {}
    result = ai_bots_core.check_ai_access(robots_text)
    return {**result, "url": url, **fetched}


def llms_txt_check(url: str | None = None, brand: str | None = None) -> dict[str, Any]:
    if not url:
        raise ValueError("url required")
    from seohead.tools import llms_txt as llms_core

    return llms_core.check_llms_txt(url, brand=brand)


def citability_check(url: str | None = None, text: str | None = None) -> dict[str, Any]:
    """Score whether content is self-contained and evidence-rich enough to support a cited AI answer."""
    if not url and not text:
        raise ValueError("url or text required")
    from seohead.tools import citability as cit_core

    if text is not None:
        return cit_core.score_citability(text)
    # Fetch only visible text through the shared parser; other extraction fields are unnecessary.
    from seohead.tools import parser as _parser

    page = _parser.parse_url(
        url,
        {
            "meta": False,
            "canonical": False,
            "og": False,
            "headings": False,
            "jsonld": False,
            "links": False,
            "text": True,
        },
    )
    if not page.get("ok"):
        return {"ok": False, "url": url, "error": page.get("error", "parse failed")}
    return {"url": url, **cit_core.score_citability(page.get("text") or "")}


def social_meta_check(
    url: str | None = None, og: dict[str, str] | None = None, twitter: dict[str, str] | None = None
) -> dict[str, Any]:
    """Identify missing Open Graph and Twitter Card fields required for a stable link preview."""
    if not url and og is None and twitter is None:
        raise ValueError("url or og/twitter required")
    from seohead.tools import social_meta as sm_core

    if og is None and twitter is None:
        from seohead.tools import parser as _parser

        page = _parser.parse_url(
            url,
            {
                "meta": False,
                "canonical": False,
                "og": True,
                "headings": False,
                "jsonld": False,
                "links": False,
                "text": False,
            },
        )
        if not page.get("ok"):
            return {"ok": False, "url": url, "error": page.get("error", "parse failed")}
        og, twitter = page.get("og") or {}, page.get("twitter") or {}
        fetched = {"url": url}
    else:
        fetched = {}
    return {**sm_core.check_social_meta(og=og, twitter=twitter), **fetched}


def soft404_check(url: str | None = None) -> dict[str, Any]:
    """Probe two deterministic nonexistent URLs to distinguish honest 404s from soft-404 responses."""
    if not url:
        raise ValueError("url required")
    from seohead.tools import soft404 as s4_core

    return s4_core.check_soft404(url)


# Registry consumed by the CLI and MCP server: one source of truth for public behavior.

# --- External data providers: demand, search results, and spend -------------------------


def keywords_expand(
    phrase: str | None = None, limit: int = 300, regions: list[str] | None = None
) -> dict[str, Any]:
    """Expand a seed phrase with Yandex Wordstat refinements and related queries.

    Returned frequency is **base frequency**, not exact frequency: the API does not expose
    ``!``, ``+``, or ``[]`` operators, and base counts are typically about nine times higher than
    exact counts. They are suitable for initial filtering; use Arsenkin for exact ``!W`` values.
    A multi-region request sums demand across its regions, so request regions separately when
    regional comparison matters. This method is paid and subject to Wordstat's hourly quota.
    """
    if not phrase:
        raise ValueError("phrase required")
    from seohead.data_sources.credentials import MissingCredential
    from seohead.data_sources.yandex_cloud import Wordstat

    try:
        pool, meta = Wordstat().expand(phrase, limit=limit, regions=tuple(regions or ["225"]))
    except MissingCredential as exc:
        return {"ok": False, "error": str(exc)}
    except RuntimeError as exc:
        return {"ok": False, "error": str(exc)}
    ranked = sorted(pool.items(), key=lambda kv: -kv[1])
    return {
        "ok": True,
        "phrase": phrase,
        "found": len(ranked),
        "total_count": meta.get("totalCount"),
        "from_results": meta.get("results"),
        "from_associations": meta.get("associations"),
        "keywords": [
            {"phrase": p, "base_frequency": c, "origin": meta["origin"].get(p)} for p, c in ranked
        ],
    }


def keywords_seasonality(
    phrase: str | None = None,
    from_date: str | None = None,
    to_date: str | None = None,
    period: str = "PERIOD_MONTHLY",
    regions: list[str] | None = None,
) -> dict[str, Any]:
    """Return Yandex Wordstat demand dynamics; dates use RFC3339, e.g. ``2026-01-01T00:00:00Z``."""
    if not phrase or not from_date or not to_date:
        raise ValueError("phrase, from_date and to_date required")
    from seohead.data_sources.credentials import MissingCredential
    from seohead.data_sources.yandex_cloud import Wordstat

    try:
        body = Wordstat().dynamics(
            phrase, from_date, to_date, period=period, regions=tuple(regions or ["225"])
        )
    except MissingCredential as exc:
        return {"ok": False, "error": str(exc)}
    except RuntimeError as exc:
        return {"ok": False, "error": str(exc)}
    return {"ok": True, "phrase": phrase, "period": period, "dynamics": body}


def serp_fetch(
    query: str | None = None, queries: list[str] | None = None, region: str = "225", top: int = 10
) -> dict[str, Any]:
    """Fetch Yandex results for one query or a batch through the asynchronous API only.

    The synchronous endpoint is deliberately excluded because it costs roughly sixteen times more.
    Batch operations are launched together and polled as a group, so N queries take approximately
    one batch duration rather than N sequential request durations. Submitted operations are billed
    even if polling times out; their operation records remain in the local spend journal.
    """
    targets = [q for q in ([query] if query else []) + list(queries or []) if q]
    if not targets:
        raise ValueError("query or queries required")
    from seohead.data_sources.credentials import MissingCredential
    from seohead.data_sources.yandex_cloud import WebSearch

    try:
        client = WebSearch()
        raw = client.search_batch(targets, region=region, groups=top)
    except MissingCredential as exc:
        return {"ok": False, "error": str(exc)}
    except RuntimeError as exc:
        return {"ok": False, "error": str(exc)}
    results = {q: {"docs": v.get("docs", []), "error": v.get("error")} for q, v in raw.items()}
    missing = [q for q in targets if q not in results]
    return {
        "ok": True,
        "region": region,
        "requested": len(targets),
        "returned": len(results),
        "results": results,
        "not_returned": missing,
        "note": (
            "queries not returned before timeout were already billed; their operations "
            "are recorded in the spend journal"
            if missing
            else None
        ),
    }


def keywords_exact(
    keywords: list[str] | None = None, region: int = 225, wait: bool = True
) -> dict[str, Any]:
    """Fetch exact ``!W`` frequency through Arsenkin, which Wordstat's API does not expose.

    This operation is paid and consumes account limits. The charge and ``task_id`` are journaled as
    soon as the task is created, allowing a result whose polling or parsing failed to be retrieved
    later without paying for a duplicate task.
    """
    if not keywords:
        raise ValueError("keywords required")
    from seohead.data_sources.arsenkin import ArsenkinClient, ArsenkinError
    from seohead.data_sources.credentials import MissingCredential

    try:
        client = ArsenkinClient()
        task = client.set_task(
            "keywords_frequency", {"keywords": list(keywords), "region": int(region)}
        )
        if not wait:
            return {
                "ok": True,
                "task_id": task["task_id"],
                "cost": task["cost"],
                "note": "task created and billed; retrieve the result later by task_id",
            }
        result = client.wait(task["task_id"])
        return {
            "ok": True,
            "task_id": task["task_id"],
            "cost": task["cost"],
            "result": result.get("result", result),
        }
    except MissingCredential as exc:
        return {"ok": False, "error": str(exc)}
    except ArsenkinError as exc:
        return {"ok": False, "error": str(exc), "code": exc.code}


def google_keywords(
    keywords: list[str] | None = None,
    seed: str | None = None,
    location_code: int = 2840,
    language: str = "en",
    country: str | None = None,
    limit: int = 100,
    difficulty: bool = False,
) -> dict[str, Any]:
    """Query Google demand through DataForSEO by keyword list or seed phrase.

    ``keywords`` returns search volume and competition for an existing list. ``seed`` expands one
    phrase into keyword ideas, analogous to Wordstat refinements but for Google. Set
    ``difficulty=true`` to return keyword difficulty instead of search volume.

    DataForSEO does not support locations in Russia or Belarus. The geographic
    guard blocks such requests before they reach the paid provider and directs callers to Wordstat
    or Arsenkin. The default ``sandbox`` environment returns realistic response shapes with fake
    data and incurs no charge; production requires explicit provider configuration.
    """
    from seohead.data_sources import dataforseo as core

    if seed:
        return core.keyword_ideas(
            seed, location_code=location_code, language=language, limit=limit, country=country
        )
    if not keywords:
        raise ValueError("keywords or seed required")
    if difficulty:
        return core.keyword_difficulty(
            keywords, location_code=location_code, language=language, country=country
        )
    return core.search_volume(
        keywords, location_code=location_code, language=language, country=country
    )


def google_serp(
    query: str | None = None,
    location_code: int = 2840,
    language: str = "en",
    depth: int = 10,
    country: str | None = None,
) -> dict[str, Any]:
    """Return the Google organic results that actually rank for a query in the selected market."""
    if not query:
        raise ValueError("query required")
    from seohead.data_sources import dataforseo as core

    return core.serp(
        query, location_code=location_code, language=language, depth=depth, country=country
    )


def metrika_counters() -> dict[str, Any]:
    """List Metrika counters visible to the token and expose the ``counter_id`` required by reports."""
    from seohead.data_sources.credentials import MissingCredential
    from seohead.data_sources.metrika import MetrikaClient, MetrikaError

    try:
        counters = MetrikaClient().counters()
    except MissingCredential as exc:
        return {"ok": False, "error": str(exc)}
    except MetrikaError as exc:
        return {"ok": False, "error": exc.message, "status": exc.status}
    return {
        "ok": True,
        "count": len(counters),
        "counters": [
            {
                "id": c.get("id"),
                "name": c.get("name"),
                "site": c.get("site"),
                "status": c.get("status"),
            }
            for c in counters
        ],
    }


def metrika_setup(counter_id: str | None = None) -> dict[str, Any]:
    """Inspect a Metrika counter's goals, filters, and data-processing operations.

    Run this before drawing conclusions from traffic. Counter operations can silently reshape
    reports—for example by removing URL parameters. If no goals are configured, the dataset cannot
    contain conversions; reporting a "zero conversion rate" would describe instrumentation, not
    observed user behavior.
    """
    if not counter_id:
        raise ValueError("counter_id required")
    from seohead.data_sources.credentials import MissingCredential
    from seohead.data_sources.metrika import MetrikaClient, MetrikaError

    try:
        client = MetrikaClient()
        goals = client.goals(counter_id)
        filters = client.filters(counter_id)
        operations = client.operations(counter_id)
    except MissingCredential as exc:
        return {"ok": False, "error": str(exc)}
    except MetrikaError as exc:
        return {"ok": False, "error": exc.message, "status": exc.status}
    return {
        "ok": True,
        "counter_id": counter_id,
        "goals": [{"id": g.get("id"), "name": g.get("name"), "type": g.get("type")} for g in goals],
        "goals_count": len(goals),
        "filters": (filters or {}).get("filters", []),
        "operations": (operations or {}).get("operations", []),
        "note": (
            "no goals are configured, so conversions cannot appear in the data; "
            "a zero conversion rate would reflect instrumentation, not observed behavior"
        )
        if not goals
        else None,
    }


def metrika_report(
    counter_id: str | None = None,
    metrics: str | None = None,
    dimensions: str | None = None,
    date1: str = "30daysAgo",
    date2: str = "today",
    filters: str | None = None,
    sort: str | None = None,
    limit: int = 100,
    paginate: bool = False,
) -> dict[str, Any]:
    """Return a Metrika report as flat JSON-serializable records.

    ``metrics`` and ``dimensions`` are comma-separated API identifiers such as ``ym:s:visits`` and
    ``ym:s:startURL``. Dates also accept relative forms such as ``30daysAgo``. With
    ``paginate=true`` the client collects successive pages but stops at 100,000 rows and marks the
    result as capped rather than implying that the dataset is complete.
    """
    if not counter_id or not metrics:
        raise ValueError("counter_id and metrics required")
    from seohead.data_sources.credentials import MissingCredential
    from seohead.data_sources.metrika import MetrikaClient, MetrikaError, rows_to_records

    params = {"ids": counter_id, "metrics": metrics, "date1": date1, "date2": date2}
    if dimensions:
        params["dimensions"] = dimensions
    if filters:
        params["filters"] = filters
    if sort:
        params["sort"] = sort
    try:
        body = MetrikaClient().report(params, paginate=paginate, limit=limit)
    except MissingCredential as exc:
        return {"ok": False, "error": str(exc)}
    except MetrikaError as exc:
        return {"ok": False, "error": exc.message, "status": exc.status}
    return {
        "ok": True,
        "counter_id": counter_id,
        "period": f"{date1}..{date2}",
        "total_rows": body.get("total_rows"),
        "returned": len(body.get("data") or []),
        "capped": body.get("capped", False),
        "totals": body.get("totals"),
        "rows": rows_to_records(body),
    }


def regions_tree(save_to: str | None = None) -> dict[str, Any]:
    """Fetch the authoritative Yandex region tree used by the ``regions[]`` parameter.

    This is Wordstat's only free method. Static mappings in ``data_sources/regions.py`` are faster,
    but some entries are documentation-derived rather than verified against the current API; use
    this live tree to validate an unfamiliar region before issuing a paid request.
    """
    from seohead.data_sources import regions as regions_core

    return regions_core.fetch_tree(save_to=save_to)


def spend_report(since: str | None = None) -> dict[str, Any]:
    """Summarize recorded provider charges by source, operation, and day."""
    from seohead.data_sources import spend as spend_core

    return spend_core.report(since=since)


def sources_doctor() -> dict[str, Any]:
    """Report provider readiness and credential locations without exposing secret values."""
    from seohead.data_sources import credentials as creds

    checks = {
        "arsenkin": ("arsenkin/token", "ARSENKIN_TOKEN"),
        "yandex_cloud_api_key": ("yandex-wordstat/api_key", "YANDEX_CLOUD_API_KEY"),
        "yandex_cloud_folder": ("yandex-wordstat/folder_id", "YANDEX_CLOUD_FOLDER_ID"),
        "yandex_metrika": ("yandex-metrika/token", "YANDEX_METRIKA_TOKEN"),
        "dataforseo": ("dataforseo/login", "DATAFORSEO_LOGIN"),
    }
    sources = {
        name: {
            "ready": creds.available(path, env),
            "file": str(creds.CONFIG_ROOT / path),
            "env": env,
        }
        for name, (path, env) in checks.items()
    }
    from seohead.data_sources import spend as spend_core

    return {"ok": True, "sources": sources, "spend_log": str(spend_core.log_path())}


_RAW_HANDLERS = {
    "parse": parse,
    "redirects_generate": redirects_generate,
    "redirects_check": redirects_check,
    "sitemap_crawl": sitemap_crawl,
    "crawl_site": crawl_site,
    "images_download": images_download,
    "images_optimize": images_optimize,
    "keywords_cluster": keywords_cluster,
    "robots_check": robots_check,
    "headers_check": headers_check,
    "links_check": links_check,
    "hreflang_check": hreflang_check,
    "domain_profile": domain_profile,
    "cdn_check": cdn_check,
    "tech_detect": tech_detect,
    "security_check": security_check,
    "backlinks_check": backlinks_check,
    "schema_check": schema_check,
    "schema_build": schema_build,
    "duplicate_check": duplicate_check,
    "ai_bots_check": ai_bots_check,
    "mirror_check": mirror_check,
    "llms_txt_check": llms_txt_check,
    "citability_check": citability_check,
    "social_meta_check": social_meta_check,
    "soft404_check": soft404_check,
    "log_analyze": log_analyze,
    "regions_check": regions_check,
    "render_check": render_check,
    "site_audit": site_audit,
    "report_build": report_build,
    "keywords_expand": keywords_expand,
    "keywords_seasonality": keywords_seasonality,
    "keywords_exact": keywords_exact,
    "serp_fetch": serp_fetch,
    "spend_report": spend_report,
    "sources_doctor": sources_doctor,
    "regions_tree": regions_tree,
    "metrika_counters": metrika_counters,
    "metrika_setup": metrika_setup,
    "metrika_report": metrika_report,
    "google_keywords": google_keywords,
    "google_serp": google_serp,
}

# Journaling sits here rather than in each interface: the CLI and the MCP server
# both dispatch through this mapping, so one wrapper records every call exactly
# once and no future tool can be added without being recorded.
HANDLERS = {name: runlog.journaled(name, fn) for name, fn in _RAW_HANDLERS.items()}
