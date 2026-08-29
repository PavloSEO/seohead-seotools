---
name: sf-config
description: >-
  Configure Screaming Frog ONCE so mode A can obtain all 96 checks for any site.
  Explains how to create audit.seospiderconfig (enable Spelling & Grammar,
  Structured Data, Security, Store HTML/Rendered HTML, JS Rendering, Crawl Linked
  XML Sitemaps, and Crawl Analysis), where to place it, and which checks it
  unlocks. Use when asked: "configure SF for a complete audit," "why is
  MIXED_CONTENT / STRUCTURED_DATA / SPELLING skipped?", "obtain every check from
  SF," or "create one SF config for all sites." Triggers: seospiderconfig,
  Screaming Frog config, audit config, SF structured data, SF security, SF spelling
  and grammar, complete SF audit.
---

# SF Config — Configure Screaming Frog Once for Every Site

SF calculates some checks **only when the corresponding modules are enabled**.
They are disabled by default -> the report honestly marks those checks as
`skipped` (instead of falsely reporting zero). To obtain **all 96 checks** for any
site in a single `--crawl` run, create an `audit.seospiderconfig` profile once;
the tool will then load it automatically.

> The `.seospiderconfig` format is binary and can be created **only by SF itself**
> (it cannot be generated programmatically). Therefore, the step below must be
> completed manually once in the SF GUI (~1 minute).

## Step 1 — Enable the Modules in SF (Once)
Open Screaming Frog, go to the **Configuration** menu, and enable:

- **Spelling & Grammar** -> `Configuration → Content → Spelling & Grammar` ->
  Enable (+ select a language) -> unlocks `SPELLING_ERRORS`, `GRAMMAR_ERRORS`,
  `LONG_SENTENCES`, `READABILITY_DIFFICULT` (the columns appear in Internal:All).
- **Structured Data** -> `Configuration → Spider → Extraction → Structured Data`
  -> enable JSON-LD + Microdata + RDFa + Schema.org Validation + Google Rich
  Results -> unlocks `SCHEMA_VALIDATION_ERROR`, `STRUCTURED_DATA_MISSING`.
- **Security** -> the Security tab is populated during a normal crawl, but for
  resources, enable `Configuration → Spider → Crawl → Check Links Outside of Start
  Folder` and rendering (below) -> unlocks `MIXED_CONTENT`, `MISSING_HSTS`.
- **Store HTML + Rendered HTML** -> `Configuration → Spider → Extraction → Store
  HTML` and `Store Rendered HTML` -> unlocks `DOM_TOO_DEEP`,
  `DOM_TOO_MANY_NODES` (pass the directory through `--config` during the crawl +
  `input.html_store_dir`).
- **JavaScript Rendering** -> `Configuration → Spider → Rendering → JavaScript` ->
  for SPA/Next.js sites; otherwise, the raw HTML contains less content.
- **Crawl Linked XML Sitemaps** -> `Configuration → Spider → Crawl → XML Sitemaps`
  -> Crawl Linked XML Sitemaps -> populates the `Sitemaps:*` tabs (Orphan, Non-200
  URLs in the sitemap).
- **Crawl Analysis (automatic)** -> `Crawl Analysis → Configure → Auto Analyse At
  End of Crawl` -> without it, Near Duplicates, Orphan URLs, and Link Score are
  empty.

The exact checkbox checklist is in `reference/sf_config_checklist.md`.

## Step 2 — Save the Profile in the Repository
`File → Configuration → Save Configuration As…` -> save it as
**`audit.seospiderconfig`** in the repository root (next to `config.json`).

## Step 3 — Done; It Is Automatic from This Point On
The tool passes `--config audit.seospiderconfig` to SF automatically **if the file
exists** (see `sf_cli.seospiderconfig` in `config.json`). Use the same config for
every site:
```bash
seohead sf run --crawl https://example.com --out report --tasks
```
Check that SF and the config are available with `seohead sf doctor`. If the config
is absent, the tool simply runs SF with its defaults (without errors), while the
module-dependent checks remain `skipped`.

## Table of Which Checks Each Module Unlocks
See `reference/sf_config_checklist.md` (module -> checks -> how to verify that it
works).
