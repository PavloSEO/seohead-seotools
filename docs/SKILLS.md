# Skill map

20 skills in `.claude/skills/`. A skill is not tool documentation — it is a
**method**: when to apply, in what order, how to read the result, and where
the boundary is beyond which the tool starts to lie.

## How to choose

```
given a domain, what to do?
   └─ seo-deep-audit ─── the single entry point, orchestrates the rest
        └─ audit-roadmap ─ when the domain is new: scout the minimum first
                           and decide what to collect
```

Then by the layer of the task.

## Orchestrators

| Skill | When |
|---|---|
| **seo-deep-audit** | Given a site and asked "look what's there". Single entry, distributes the work |
| **audit-roadmap** | Unfamiliar domain: 5 minutes of recon to decide what to collect next |
| **sf-boundaries** | The fork "does Screaming Frog cover this, or does it need an agent?" — a router |

## Screaming Frog crawl audit

| Skill | When | Tool |
|---|---|---|
| **sf-analyzer** | There is a crawl or exports — produce a machine-readable audit | `sf run` |
| **sf-config** | Configure SF once so mode A can feed all 96 checks | — |
| **sf-report** | Turn the export into a human-readable report | `sf run --out` |
| **sf-tasks** | Build a prioritized backlog from `audit.json` | `sf tasks` |

## Recon and technical hygiene

| Skill | When | Tools |
|---|---|---|
| **seo-recon** | Domain age, hosting, CDN, caching — everything SF does not give | `domain-profile`, `cdn-check` |
| **tech-audit** | What the site is made of: CMS, framework, analytics, pixels | `tech-detect` |
| **security-audit** | Security headers through an SEO lens | `security-check` |
| **robots-audit** | robots.txt dissected for harmful directives | `robots-check` |
| **js-render-check** | What appears only after JavaScript + lab metrics | `render-check` |
| **regional-audit** | Regions: subdomains, folders, satellites, branches across Russia | `regions-check` |

## Content and structure

| Skill | When | Tools |
|---|---|---|
| **schema-graph** | Structured data: dissect, validate, build a `@graph` | `schema-check`, `schema-build` |
| **duplicate-audit** | Near-duplicates and thin pages | `duplicate-check` |
| **heading-outline** | The H1–H6 structure and its hierarchy | `parse` |
| **silo-audit** | Is the structure silo-like, hubs, interlinking, orphans | `links-check`, `sitemap-crawl` |
| **backlinks-check** | Verify links against your own donor list | `backlinks-check` |
| **geo-aeo-audit** | Visibility in AI answers: crawlers, llms.txt, citability | `ai-bots-check`, `llms-txt-check`, `citability-check` |

## The audit as a whole and reports

| Skill | When | Tools |
|---|---|---|
| **site-report** | The whole site dissected and a ready file — Excel, Word, CSV | `site-audit`, `report-build` |

## Tools without a skill of their own

Twenty-one of the 42 commands are used inside other skills or are plumbing,
and have no skill of their own — deliberately: a skill per single command
is noise.

Page-level utilities: `headers-check` · `hreflang-check` · `links-check` ·
`redirects-check` · `redirects-generate` · `soft404-check` ·
`social-meta-check` · `log-analyze` · `keywords-cluster` ·
`images-download` · `images-optimize`

External data sources (`data_sources/` layer): `keywords-expand` ·
`keywords-seasonality` · `keywords-exact` · `serp-fetch` ·
`google-keywords` · `google-serp` · `metrika-counters` · `metrika-setup` ·
`metrika-report` · `spend-report` · `sources-doctor` · `regions-tree`

Two of them are candidates for a skill if the work becomes regular:
`log-analyze` (log parsing is its own genre with its own method) and
`redirects-generate` (site migrations).

## Skill rules

**Where a skill lives.** A general method applicable to any project ->
`~/.claude/skills/`. Knowledge about this repository -> `.claude/skills/`
here.

**Skills must age together with the code.** A new tool appears — the skill
that used to teach doing the same by hand gets rewritten. That is how
`js-render-check` stopped explaining `curl` and headless Chrome and started
documenting `render-check`.

**Every skill has a "Boundaries" section.** What the tool does not do and
what cannot be claimed from its output. Without it a skill turns into an
ad for the tool.

**Consistency check** — `tests/test_docs_drift.py`: every `seohead` command
mentioned in any skill must exist in the CLI. A skill referencing a
non-existent command fails the suite.
