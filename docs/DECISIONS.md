# Public design decisions

This document records stable product choices that contributors should not have to rediscover.

## Exactly two interfaces

SEOHEAD Tools exposes a CLI and one local stdio MCP server. Both use the same handler registry.
There is no GUI, desktop shell, HTTP API, hosted account, or public MCP endpoint.

Reports are output formats, not interfaces. XLSX and DOCX are allowed because they are useful work
products; report renderers still contain no network or finding logic.

## Evidence before interpretation

Every output distinguishes observed data, derived findings, missing inputs, and failures. A tool
that cannot measure a signal must not report that signal as healthy. This is why outputs include
fields such as `http_version_measurable`, skipped-check reasons, and `tools_failed`.

## Safe defaults

- User-controlled URL requests block private and non-public networks unless explicitly enabled.
- Potentially intrusive path probes and bot DNS verification are opt-in.
- Image optimization needs a separate output directory unless `in_place=true`; in-place rewrites
  create backups by default.
- DataForSEO uses sandbox unless production is selected explicitly.
- Paid operations are journalled before response parsing.
- Yandex SERP uses the asynchronous endpoint only.

## Two Screaming Frog modes

Export mode is self-contained and tested offline. Live crawl mode is an optional adapter around a
separately installed and licensed Screaming Frog CLI. Convenience in live mode must not break
export mode.

## Lab metrics stay lab metrics

Playwright timing data lives under `metrics_lab`. One browser run is not field Core Web Vitals;
field conclusions require CrUX, Search Console, or another real-user dataset.

## Rendering waits for `load` by default

Long-lived analytics, chat, ad, and websocket connections can prevent `networkidle` indefinitely.
`load` provides a bounded default; callers may select another wait strategy when a site's behavior
requires it.

## Optional heavy dependencies

Playwright, clustering, report formats, sitemap helpers, and MCP support live in extras. A missing
optional dependency returns an actionable install instruction instead of crashing unrelated tools.

## Report generators compute nothing

Audit and aggregation layers own calculations. Renderers only lay out the finished document. This
prevents XLSX, DOCX, CSV, Markdown, and JSON outputs from disagreeing about the same run.

## No bundled GPL fingerprint database

An external technology fingerprint database can be loaded through configuration, but is not
distributed in the MIT package. Built-in signatures are curated in-repository, and compatible
sources are credited in `THIRD_PARTY_NOTICES.md`.

## Offline tests

The test suite does not depend on live sites or provider availability. Network boundaries are
tested with fakes and pure verdict functions; live verification is a separate release step.

## Public history is intentionally clean

The public repository starts from a reviewed snapshot. Internal experiments, research journals,
client artifacts, discarded implementations, and private commit history are outside the public
source boundary described in `PROVENANCE.md`.
