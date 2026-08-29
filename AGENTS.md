# AGENTS.md — public repository contract

SEOHEAD Tools is a headless, local-first Python SEO toolkit. It has exactly two user interfaces:
the `seohead` CLI and one local stdio MCP server. Do not add a GUI, desktop shell, hosted API, or
remote MCP endpoint to this repository.

## Start here

```bash
python -m pip install -e ".[dev,mcp,cluster,reports]"
ruff check .
ruff format --check .
pytest -q
seohead sf run --exports-dir examples/exports --out /tmp/seohead-report --tasks
```

## Architecture

```text
seohead/
  cli.py          CLI registration and argument mapping
  tools/          live page, content, image, log, and structured-data tools
  recon/          domain and infrastructure reconnaissance
  sf/             Screaming Frog export runner and 96-check analyzer
  audit/          whole-site orchestration
  reports/        XLSX, DOCX, CSV, Markdown, and JSON formatting
  data_sources/   optional demand, SERP, and traffic providers
  servers/        shared handlers and MCP registration
  skills/         packaged SEO workflow playbooks
```

The core (`tools`, `recon`, `sf`, `audit`, `data_sources`) does not import `cli` or `servers`.
Public behavior starts in the core, receives a shared handler, and is then registered in both the
CLI and MCP. `tests/test_registration.py` enforces this boundary.

## Invariants

- Missing data is not a clean result. Report skipped or unavailable checks with a reason.
- Network failures are result data at tool boundaries, not process crashes.
- User-controlled URL requests use `seohead.recon.net.http_client`; private networks are blocked
  unless `SEOHEAD_ALLOW_PRIVATE_NETWORKS=1` is set deliberately.
- Side effects are explicit. File mutation, service-path probing, DNS bot verification, provider
  production mode, and paid calls never hide behind defaults.
- Image optimization requires an output directory unless `in_place=true`; backups are enabled for
  in-place rewrites and format conversion never deletes the source.
- DataForSEO defaults to sandbox and its geographic coverage guard must not be bypassed.
- Yandex SERP uses the asynchronous endpoint only.
- Provider secrets come from environment variables or local configuration; never print values.
- Metrika log exports may contain personal identifiers and must not be committed or placed in
  client reports.
- Report renderers format an existing audit document; they do not calculate new findings.
- Screaming Frog export mode must remain usable without live crawl mode. Live crawl mode requires
  a separately installed and licensed Screaming Frog CLI.
- Public comments, docstrings, errors, documentation, examples, and skills are English. Localized
  dictionaries and explicit international-SEO fixtures may contain non-English data when required
  by the feature.

## Public boundary

Never commit credentials, client URLs or exports, access logs, `.seospider` binaries, paid-provider
responses, generated client reports, local absolute paths, internal research journals, or private
development history. Examples must use synthetic data and reserved domains.

The source is MIT-licensed. The bundled Schema.org vocabulary remains CC BY-SA 3.0; preserve its
notice in `THIRD_PARTY_NOTICES.md`.

## Adding a tool

1. Implement the smallest useful core function.
2. Add a handler in `seohead/servers/handlers.py` and its `HANDLERS` entry.
3. Add the CLI command and argument mapping.
4. Add the MCP tool with accurate side-effect annotations.
5. Add offline tests for success, failure, limits, and missing dependencies.
6. Update `docs/TOOLS.md`, the README capability count, and any provider cost or safety notes.
