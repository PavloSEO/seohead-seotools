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
| `cluster` | `scikit-learn`, `numpy`, `nltk` | `keywords-cluster` |
| `dev` | `pytest`, `pytest-cov`, `ruff`, `respx` | the test suite |

## First run

```bash
seohead --version                     # seohead 3.0.0
seohead --help                        # the command list
pytest -q                             # 458 offline tests; runtime depends on extras
seohead sf run --exports-dir examples/exports --out /tmp/report --tasks
```

The last command runs a real audit (mode B) over the synthetic crawl in
`examples/exports/` and writes `/tmp/report/audit.json` + `audit.md` +
`tasks.json` + `tasks.md`. If that works, the toolkit works.

`seohead sf doctor` prints environment diagnostics: where the SF CLI is (or
is not), which optional dependencies are present.

`sf-analyzer` is also installed as a focused audit-CLI alias (`[project.scripts]` in
`pyproject.toml`). Use `seohead sf ...` when one entry point is preferable.

## Environment variables

Names only — values are secrets and never belong in a repo, a log or a doc.

Tool behaviour:

| Variable | Purpose |
|---|---|
| `SF_CLI`, `SCREAMINGFROG_CLI` | explicit path to the SF CLI executable for audit mode A (`seohead/sf/core/runner.py`) |
| `SEOHEAD_TECH_DB` | path to an external technology-fingerprint database; not shipped for license reasons (`recon/tech_db.py`) |
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
