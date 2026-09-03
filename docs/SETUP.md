# Setup from zero

Everything below was verified on macOS (darwin, arm64) with the repo's own
venv; the same steps work on Linux. Windows paths for the SF CLI are
supported by `config.json` search paths.

## Requirements

- **Python 3.10+** (`requires-python` in `pyproject.toml`).
- pip, git. That is all — every other dependency is a Python package.
- Optional, improves results if present on the system:
  - **Screaming Frog SEO Spider CLI** — for audit mode A (the toolkit
    drives the crawler itself). Without it, mode B works from ready exports.
  - **system `whois`** — fallback for ccTLDs without RDAP. Without RDAP and
    without `whois`, domain registration data is honestly reported as
    `source: none`.

## Install

```bash
git clone https://github.com/PavloSEO/seohead-seotools.git
cd seohead-seotools

python3 -m venv .venv
source .venv/bin/activate

pip install -e ".[all,dev]"            # everything incl. reports, render, tests
python -m playwright install chromium  # browser for render-check (~150 MB)
```

Why `-e`: the `seohead` entry point must see the working tree while you edit
it. The install is not global — everything lives inside `.venv/` (which is
gitignored).

The toolkit is deliberately split into dependency groups (`pyproject.toml`,
`[project.optional-dependencies]`); with any group missing, the rest still
works, and the affected tool answers `{"ok": false, "error": ...,
"install": "..."}` with the exact install command instead of crashing:

| Group | Installs | What stops working without it |
|---|---|---|
| base (always) | `httpx`, `beautifulsoup4`, `lxml`, `defusedxml`, `pandas`, `h2`, `pydantic`, `jsonschema`, `openpyxl`, `Pillow` | nothing, this is the minimum |
| `reports` | `python-docx` (+ openpyxl already in base) | `docx` output of `report-build` (xlsx/csv/md/json stay) |
| `render` | `playwright` | `render-check`, `regions-check --render` |
| `sitemap` | `advertools`, `python-dateutil` | deep parsing of very large sitemaps |
| `mcp` | `mcp` | the MCP server (the CLI stays) |
| `cluster` | `scikit-learn`, `numpy`, `snowballstemmer` | `keywords-cluster` |
| `dev` | `pytest`, `pytest-cov`, `ruff`, `respx` | the test suite |

## First run

```bash
seohead --version                     # seohead 3.0.0
seohead --help                        # the command list
pytest -q                             # 610 offline tests; runtime depends on extras
seohead sf run --exports-dir examples/exports --out /tmp/report --tasks
```

The last command runs a real audit (mode B) over the synthetic crawl in
`examples/exports/` and writes `/tmp/report/audit.json` + `audit.md` +
`tasks.json` + `tasks.md`. If that works, the toolkit works.

## Crawling without a Screaming Frog licence

```bash
seohead crawl-site --url https://example.com/ --max-urls 200 --out-dir ./report
```

Follows links from the start URL on the same host, respects `robots.txt`, and audits the result
through the same checks used for Screaming Frog exports. `--min-delay` is the floor beneath an
adaptive back-off: latency widens the delay, a timeout widens it hard, and repeated timeouts stop
the run rather than pushing a failing origin. Rows land in `pages.jsonl` as they are collected, so
an interrupted crawl still leaves evidence behind.

This is not Screaming Frog parity. Checks whose evidence a native crawl cannot produce —
redirect chains, near-duplicates, readability, pixel widths, link score — are reported as
**skipped**, never as clean, and `summary.check_coverage` states how much of the registry ran.

`seohead sf doctor` prints environment diagnostics: where the SF CLI is (or
is not), which optional dependencies are present, which base Screaming Frog
config a crawl would use, and which module switches that config turns on. A
module the reader cannot decode is printed as `unknown`, never as `off`.

Module switches decide whether the module-dependent checks can run at all.
Without a base config SF crawls with its own defaults and those checks come
back `skipped` — which you would otherwise only discover after the crawl. Two
things make that visible up front:

```bash
seohead sf save-config                # copy the latest SF crawl config to audit.seospiderconfig
seohead sf save-config --out base.seospiderconfig --force
```

`sf run` prints a `[preflight]` line before a fresh crawl for every check that
the configuration in force cannot satisfy, so the config can be fixed first.
Mode B (`--exports-dir`) already has the exports and is not affected.

`sf-analyzer` is also installed as a focused audit-CLI alias (`[project.scripts]` in
`pyproject.toml`). Use `seohead sf ...` when one entry point is preferable.

## Crawler configuration

```bash
seohead crawl-site --url https://example.com/ --config crawl.json --out-dir ./report
```

```json
{
  "limits": {"max_urls": 500, "max_depth": 4},
  "speed": {"min_delay_seconds": 1.0},
  "robots": {"policy": "report_only"},
  "discovery": {"external": {"store": true, "crawl": false}}
}
```

Resolution order is defaults, then the file, then environment variables, then explicit command-line
arguments — the most local statement of intent wins.

Three properties are deliberate:

**An unknown key is an error, not a no-op.** A setting the crawler does not read would promise
behaviour that does not exist, and a typo in a scope pattern would silently widen a crawl.

**`store` and `crawl` are separate flags** for every link type: keep it in the report, versus
request it for a status code. These are different questions, and one flag for both is why a crawler
either misses broken images or triples its request count.

**Settings that change what the audit finds are written into `audit.json`** as
`run.crawl_config`, with their resolved values. Two reports on the same site are otherwise not
comparable, and nobody can tell why they differ. `run.effective_max_requests_per_second` records the
politeness the run actually permitted, because politeness is a combination of settings rather than
any single one.

`robots.policy` accepts `respect` (obey), `report_only` (fetch it, report what it would block, crawl
anyway — the honest audit setting), and `ignore` (do not fetch it at all).

Environment overrides: `SEOHEAD_CRAWL_MAX_URLS`, `SEOHEAD_CRAWL_MAX_DEPTH`,
`SEOHEAD_CRAWL_MIN_DELAY`, `SEOHEAD_CRAWL_ROBOTS`, `SEOHEAD_CRAWL_USER_AGENT`.

## Run journal

Every CLI command and MCP call is appended to one JSONL journal, so a session can be
reconstructed after the process exits: which tools ran, against what, how long they took, and
whether they failed.

```bash
SEOHEAD_RUN_LOG=./runs.jsonl seohead crawl-site --url https://example.com/
SEOHEAD_RUN_LOG=off seohead parse --url https://example.com/    # disable
```

Default path is `~/.config/seohead/runs.jsonl`. Journaling wraps the shared handler registry
rather than each interface, so both faces of the toolkit record exactly once and a new tool
cannot be added without being recorded.

Arguments whose names look like credentials — token, key, secret, password, auth — are stored as
`[redacted]`, and long values and lists are shortened rather than dropped. A journal that leaks an
API key would leak it silently, since nothing about a log file suggests it holds secrets.

Each entry carries a `fingerprint` of the call: the same tool with the same arguments produces the
same value regardless of argument order. Nothing currently reuses it — reuse is a decision for a
caller who knows whether a stale answer is acceptable, and that decision is deliberately not made
inside the journal.

An unwritable journal never fails a run: a degraded observation is not a failed audit.

## Environment variables

Names only — values are secrets and never belong in a repo, a log or a doc.

Tool behaviour:

| Variable | Purpose |
|---|---|
| `SF_CLI`, `SCREAMINGFROG_CLI` | explicit path to the SF CLI executable for audit mode A (`seohead/sf/core/runner.py`) |
| `SEOHEAD_TECH_DB` | path to an external technology-fingerprint database; not shipped for license reasons (`recon/tech_db.py`) |
| `SEOHEAD_RUN_LOG` | where the run journal is written (default `~/.config/seohead/runs.jsonl`); `off` disables it |
| `SEOHEAD_SPEND_LOG` | override for the paid-call journal (default `~/.config/seohead/spend.jsonl`) |
| `DATAFORSEO_ENV` | `sandbox` (default) or `prod` for the DataForSEO tools |

Credentials (each wins over its file under `~/.config/`; see
`seohead/data_sources/credentials.py`):

| Variable | File fallback | Used by |
|---|---|---|
| `ARSENKIN_TOKEN` | `~/.config/arsenkin/token` | `keywords-exact` |
| `YANDEX_CLOUD_API_KEY` | `~/.config/yandex-wordstat/api_key` | `keywords-expand`, `keywords-seasonality`, `serp-fetch` |
| `YANDEX_CLOUD_FOLDER_ID` | `~/.config/yandex-wordstat/folder_id` | same |
| `YANDEX_METRIKA_TOKEN` | `~/.config/yandex-metrika/token` | `metrika-*` |
| `DATAFORSEO_LOGIN` | `~/.config/dataforseo/login` | `google-keywords`, `google-serp` |
| `DATAFORSEO_PASSWORD` | `~/.config/dataforseo/password` | same |

`seohead sources-doctor` reports which of these are present and where they
are read from — run it before planning any paid collection.

## Docker alternative

No local Python needed:

```bash
docker compose run --rm seohead sf run --exports-dir /data/exports --out /data/report --tasks
docker compose run --rm seohead headers-check --url https://example.com
```

The image is a multi-stage build on `python:3.12-slim`, runs as non-root user `seohead`, and mounts
`./workspace` as `/data`. It does not bundle Screaming Frog or Chromium. See
[USAGE.md](USAGE.md).

## What is intentionally absent

- **No GUI, no web service, no HTTP API.** The two interfaces are the CLI and the local stdio MCP
  server. Reports are files.
- **No push deploy.** `git push` deploys nothing — there are no deploy
  workflows, hooks or scripts in this repo.
