<div align="center">

![SEOHEAD Tools](https://raw.githubusercontent.com/PavloSEO/seohead-seotools/main/.github/assets/social-preview.jpg)

# SEOHEAD Tools

**A local-first SEO workstation for people and AI agents.**

47 callable tools · 96 Screaming Frog crawl checks · 27 workflow skills · CLI · local MCP · Docker

[Website](https://seohead.tech) · [Product page](https://seohead.tech/seotools) · [Portfolio](https://seohead.tech/about/results) · [Documentation](docs/README.md)

[![CI](https://github.com/PavloSEO/seohead-seotools/actions/workflows/ci.yml/badge.svg)](https://github.com/PavloSEO/seohead-seotools/actions/workflows/ci.yml)
![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-1565C0)
![Tests](https://img.shields.io/badge/tests-458%20offline-BDDDF5)
![MCP](https://img.shields.io/badge/MCP-local%20stdio-151A25)
[![MIT License](https://img.shields.io/badge/code-MIT-1565C0)](LICENSE)

</div>

SEOHEAD Tools brings technical audits, live URL checks, infrastructure reconnaissance,
structured-data work, keyword and SERP sources, traffic data, report generation, and agent
playbooks into one Python package. It is the SEO specialist's Swiss Army knife: one command and
one local MCP server instead of a folder of unrelated scripts.

The toolkit does not write strategy or client copy by itself. It collects evidence, applies
deterministic checks, and returns structured data. A capable tool-calling agent can then combine
those results into a site review, competitor brief, migration plan, prioritized backlog, or
commercial-proposal draft while a specialist keeps control of interpretation.

## Why it is useful

A serious review repeatedly asks the same questions: what is indexable, what redirects, where
canonicals point, whether hreflang is reciprocal, what Schema.org declares, which technologies
and CDN are present, what bots can crawl, what the logs show, and how all of that becomes a
deliverable. SEOHEAD turns this collection layer into reusable tool calls.

In the author's workflow, evidence collection and report scaffolding are often several times
faster because one agent can run the same bounded checks, preserve their structured output, and
assemble the first report pass. This is an experience statement, not a universal benchmark.
Network conditions, crawl scope, provider quotas, and expert review still determine total time.

## What is included

### 42 core CLI commands and MCP tools

| Layer | Tools | What it covers |
|---|---:|---|
| Live page and URL evidence | 11 | parsing, robots.txt, headers, links, hreflang, redirects, sitemaps, image download and optimization, keyword clustering |
| Domain and infrastructure reconnaissance | 8 | domain/DNS/TLS, CDN cache behavior, technology detection, security headers, mirrors, regional structure, donor backlink verification, AI crawler access |
| Structured data, content, rendering, and logs | 10 | Schema.org validation and graph generation, near-duplicates, llms.txt, citability, social previews, soft 404s, raw-vs-rendered DOM, access-log analysis |
| Audit orchestration and reporting | 2 | whole-site orchestration and XLSX/DOCX/CSV/Markdown/JSON output |
| Demand, SERP, and traffic sources | 11 | Yandex Wordstat and async SERP, Arsenkin exact frequency, Yandex Metrika, DataForSEO Google data, region tree, credential and spend diagnostics |

Run `seohead --help` for the authoritative command list. Every core command goes through the
same handler used by its `seo_*` MCP counterpart; a test gate fails if the interfaces drift.

### Screaming Frog audit layer

Five additional `sf_*` MCP tools turn a Screaming Frog crawl into machine-readable evidence,
compact summaries, filtered findings, an export inventory, and a prioritized task backlog.

The analyzer applies **96 checks** across metadata, indexability, canonicals, redirects, internal
links, sitemaps, hreflang, structured data, page depth, HTML weight, performance signals, and
other crawl-derived evidence. Missing input is reported as skipped with a reason; it is never
silently converted into “zero issues.”

Two modes are intentionally supported:

- **Export mode** analyzes existing CSV/XLSX exports and does not require SEOHEAD to run
  Screaming Frog.
- **Live crawl mode** launches the local Screaming Frog CLI and therefore requires an installed,
  active paid Screaming Frog SEO Spider licence. SEOHEAD does not bundle or replace that licence.

### 27 agent workflow skills

The repository ships 20 technical-audit playbooks in `.claude/skills/` and seven broader SEO
content/research playbooks in `seohead/skills/`. They teach an agent when to call tools, how to
separate evidence from inference, and how to assemble outputs without pretending that an
unmeasured signal is clean.

### A reproducible self-test

The social preview at the top of this README was processed by the public `images-optimize`
command. The generated 1774×887 source was resized to 1280×640 and reduced from **1,056,172 bytes
to 33,173 bytes** (**96.9% smaller**) while the source remained untouched. This is a concrete
product result, not a mock dashboard; the command and safety behavior are covered by the test
suite.

## Quick start

Clone the repository and let one install command resolve the Python dependencies:

```bash
git clone https://github.com/PavloSEO/seohead-seotools.git
cd seohead-seotools
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[all]"
```

On Windows PowerShell, activate with `.venv\Scripts\Activate.ps1`.

Optional components stay optional:

- `render` adds Playwright-based raw/rendered comparison; install its Chromium separately;
- `mcp` adds the local stdio server;
- `cluster` adds scikit-learn clustering;
- `reports` adds DOCX/XLSX output;
- `sitemap` adds optional sitemap helpers;
- external providers require your own credentials and may charge their own fees.

## One-command examples

```bash
# Full live evidence pass over a site, then write an Excel deliverable
seohead site-audit \
  --url https://example.com \
  --limit 25 \
  --report xlsx \
  --out report.xlsx

# Audit existing Screaming Frog exports without crawling again
seohead sf run \
  --exports-dir ./exports \
  --out ./report \
  --tasks

# Inspect one page and its infrastructure
seohead parse --url https://example.com
seohead headers-check --url https://example.com
seohead schema-check --url https://example.com
seohead domain-profile --domain example.com

# Build a connected Schema.org graph from facts visible on the page
seohead schema-build --url https://example.com/product/example

# Optimize images into a separate directory; source files stay untouched
seohead images-optimize \
  --files ./images \
  --output-dir ./optimized \
  --format webp \
  --quality 82
```

All commands also accept a JSON object through `--input`; without explicit flags, that object may
come from stdin. See [usage examples](docs/USAGE.md) and the [tool reference](docs/TOOLS.md).

## Local MCP server

Install the `mcp` extra, then register one stdio process in any compatible client:

```json
{
  "mcpServers": {
    "seohead": {
      "command": "/absolute/path/to/.venv/bin/seohead",
      "args": ["mcp"]
    }
  }
}
```

The server exposes **42 `seo_*` tools plus five `sf_*` tools**. It opens no port, hosts no
dashboard, stores no account, sends no telemetry, and shares the same tested handler layer as the
CLI. File-producing tools return paths instead of dumping large reports into an agent context.

## Docker and VPS use

The image is headless and exposes no network service:

```bash
docker build -t seohead-tools:local .
docker run --rm seohead-tools:local --version
docker run --rm seohead-tools:local parse --url https://example.com
```

For MCP, keep stdin attached and mount only the workspace the agent may read or write:

```json
{
  "mcpServers": {
    "seohead": {
      "command": "docker",
      "args": [
        "run", "--rm", "-i",
        "-v", "/absolute/authorized/workspace:/data",
        "seohead-tools:local", "mcp"
      ]
    }
  }
}
```

On a VPS, the same container is launched by the local agent host. There is deliberately no public
MCP endpoint in this repository. The image does not bundle Screaming Frog or a Playwright browser;
export-mode SF analysis works, while live SF crawls and rendered checks use authorized host tools.

## External data sources

Provider integrations are optional and explicit:

- Yandex Cloud supplies Wordstat expansion, seasonality, the region tree, and async Yandex SERP;
- Arsenkin supplies exact frequency where the Wordstat API does not;
- Yandex Metrika supplies counter configuration and traffic reports;
- DataForSEO supplies Google keyword and SERP data and defaults to its sandbox environment.

Secrets are read from environment variables or local configuration files and are never shipped.
Paid calls are journalled before response parsing so a parser failure cannot make spend invisible.
Read [provider gotchas](docs/GOTCHAS.md) before enabling production credentials.

## Safety and honest limits

- Network tools reject non-HTTP schemes and block private/non-public targets by default.
- File-changing operations require explicit intent; image optimization is non-destructive by
  default and validates output before reporting success.
- Security path probes, bot DNS verification, and sitemap live rechecks are opt-in.
- DataForSEO production mode is opt-in; its default is sandbox.
- Yandex SERP uses only the asynchronous endpoint.
- The toolkit does not discover the web-scale backlink profile of a domain.
- Lab browser timings are labelled as lab data, not field Core Web Vitals.
- `backlinks-check` verifies a donor list; it does not replace Ahrefs, Majestic, GSC, or another
  backlink index.
- International tools validate hreflang and regional structure; the package does not claim a
  machine-translation engine. Translation belongs to a reviewed model or localization workflow.
- SEOHEAD does not include its own general-purpose crawler. Whole-site crawling is delegated to
  Screaming Frog; export analysis remains available without live crawl mode.

Read [SECURITY.md](SECURITY.md), [architecture](docs/ARCHITECTURE.md), and
[limitations](docs/COMPARISON.md) before using outputs in a client deliverable.

## Development

```bash
python -m pip install -e ".[dev,mcp,cluster,reports]"
ruff check .
ruff format --check .
pytest -q
seohead sf run --exports-dir examples/exports --out /tmp/seohead-report --tasks
python -m build
```

The suite contains **458 offline tests**. CI also checks interface registration, layer boundaries,
the synthetic crawl audit, package metadata, and English-only public documentation.

## Provenance and licence

The Python implementation and documentation are released under the [MIT License](LICENSE).
The bundled Schema.org vocabulary retains its original CC BY-SA 3.0 terms. Compatible upstream
projects that informed individual algorithms are credited in
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md); no GPL or unlicensed source code is included.
See [PROVENANCE.md](PROVENANCE.md) for the clean-snapshot policy and
[TRADEMARKS.md](TRADEMARKS.md) for the SEOHEAD name and terminal mark.
