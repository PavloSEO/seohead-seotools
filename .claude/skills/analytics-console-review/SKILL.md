---
name: analytics-console-review
description: >-
  Review aggregate search, analytics, tag-management, or UX-console evidence through a
  user-authorized signed-in browser or user-supplied export when no provider API is configured.
  Use for read-only GSC, GA4, Metrika, Yandex Webmaster, Bing Webmaster, GTM, or Clarity review;
  do not use it to collect raw visitor data or perform unconfirmed writes.
---

# Analytics console review

Use this method when the required evidence exists in a provider console but the toolkit has no
configured API client for it. The browser belongs to the agent host, not SEOHEAD Tools: this skill
does not bundle a browser, open a remote service, or make a provider integration appear to exist.

## Preflight

Before navigation, establish a scope ticket with:

- provider and already-authorized account;
- exact property, counter, container, or project;
- report and comparison periods;
- dimensions, metrics, filters, and search type;
- an ignored local output directory, for example
  `_sandbox/analytics-console-review/2026-08-30/`.

If the request says only “search traffic,” ask which evidence source is intended: GSC, Bing
Webmaster, Yandex Webmaster, or a web-analytics platform. Do not assume that GSC access exists.

Ask the user to handle sign-in and account selection. Never type credentials, inspect cookies or
tokens, open developer storage, or switch to another property to bypass missing access.

Report one explicit readiness state before collecting data:

- `browser unavailable`;
- `sign-in required`;
- `property selection required`;
- `access denied`;
- `read view available`;
- `export available`;
- `export unavailable`.

When sign-in, property, or access is missing, stop console work with a concise handoff:

```text
Readiness: sign-in required | property selection required | access denied
Provider: <provider or unresolved>
Needed from the user: sign in, select <property>, approve read-only review
Proposed scope: <report>, <period A> vs <period B>, <dimensions/metrics>
First export: <smallest aggregate table>
No settings, users, tags, sitemaps, or saved reports will be changed.
```

## Read and export boundary

The user may authorize navigation, temporary report filters, aggregate table review, and named file
downloads for the scoped task. A local download is not permission to share, commit, upload, or keep
the data indefinitely.

Do not collect raw session recordings, ClientID or user identifiers, cookies, authentication
material, unrestricted event logs, or browser network archives. Prefer aggregate CSV/XLSX exports
and record when the UI exposes only a truncated or sampled view.

## Workflow

1. Confirm that the visible property and date range match the scope ticket.
2. Capture the smallest aggregate table that answers the question.
3. Export only when the console exposes an explicit export control and the user authorized the
   destination.
4. Write a compact retrieval manifest beside the export:
   - provider and selected property;
   - retrieval time and report periods;
   - dimensions, metrics, filters, and search type;
   - export file name and SHA-256;
   - visible truncation, anonymization, sampling, or UI limitations.
5. Cross-check only supported claims with deterministic evidence. Useful local calls include
   `seohead parse`, `seohead headers-check`, `seohead robots-check`,
   `seohead tech-detect`, `seohead sources-doctor`, and an existing
   `seohead sf run` export audit.
6. Separate observations, candidate explanations, missing evidence, and proposed next checks.

A minimal manifest can use this shape:

```yaml
provider: google-search-console
property: sc-domain:example.com
retrieved_at: 2026-08-30T12:00:00Z
periods: [2026-07-01/2026-07-31, 2026-06-01/2026-06-30]
dimensions: [page]
metrics: [clicks, impressions, ctr, position]
filters: {search_type: web}
file: pages.csv
sha256: <hex digest>
limitations: [top rows only, anonymized queries excluded]
```

When the user asks to “get whatever you can,” a bounded public baseline is allowed before console
access: status, title, canonical, robots, headers, sitemap visibility, and detected public tags.
Keep that baseline in a separate section and say explicitly that it cannot confirm or explain a
traffic decline without affected landing-page evidence.

Missing controls or rows are `unavailable`, never zero. Search-console clicks and analytics
sessions are different measurements; attribution, bot filtering, canonical aggregation, time zones,
privacy thresholds, and reporting delays can all create legitimate deltas.

## Provider writes

Default to no writes. Saving a report or segment, creating a property/counter/container/workspace,
changing access, submitting a sitemap or validation, importing GTM JSON, editing tags/triggers,
publishing a container, and deleting anything are writes.

Before any write, show the exact target, action, and available diff or impact, then wait for a
separate final confirmation. GTM import and publish are outside version 1 of this skill.

## Useful no-key reviews

- **Search loss:** export a page comparison first, then queries only for selected losing pages.
  Rank candidate pages by visible clicks, impressions, CTR, and position deltas; do not claim cause.
- **Landing-page decline:** review aggregate visits/users/conversions for one counter and explicit
  goals. If comparison, goal, or export controls are absent, report them as unavailable.
- **Instrumentation inventory:** read one GTM container/version and compare its tags, triggers,
  variables, consent settings, and metadata with public-page `seohead tech-detect` evidence. This
  cannot prove that a tag fired correctly.

See [the no-key workflow recipes](../../../docs/RECIPES.md) for copy-paste commands and artifact
contracts.

## Boundaries

- A visible console page does not prove API access or complete data coverage.
- UI exports can be capped, anonymized, sampled, or inconsistent with chart totals.
- A detected public tag does not prove that an analytics property receives correct events.
- Browser evidence is a dated observation, not a reproducible provider API response.
- Orphan and decline outputs are candidates for review, not causal conclusions.
- Generic site-audit findings are not loss candidates until they are joined to affected landing
  pages or another scoped evidence set.
- Never commit exports, manifests containing private property names, or client analytics data.
