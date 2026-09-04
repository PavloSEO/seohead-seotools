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

## Trigger

- The evidence needed lives inside a provider console — GSC, GA4, Metrika, Yandex Webmaster, Bing
  Webmaster, GTM, or Clarity — and the toolkit has no configured API client for that provider.
- The user has already authorized, or is willing to authorize, a signed-in browser session, or has
  supplied an export file from one of those consoles.
- A read-only review of aggregate reports, period comparisons, or an instrumentation inventory is
  requested — for example "why did search traffic drop," "check the GA4 landing-page numbers," or
  "what tags fire on this site."

## Anti-trigger

- A provider API client IS already configured in the toolkit for the data in question (for example
  Yandex Metrika via `seohead metrika-report`/`metrika-counters`/`metrika-setup`) — use that
  deterministic CLI path instead of a browser session.
- The request needs raw, row-level, or per-visitor data (session recordings, ClientIDs, cookies,
  unrestricted event logs) — this skill explicitly refuses that; there is no lower-privacy fallback
  inside it.
- The task requires changing settings, saving a report/segment, creating a property/counter/
  container, submitting a sitemap, or publishing a GTM container, without a separately confirmed
  write step — treat that as out of scope until confirmed (see Provider writes below).
- The question can be answered from public, unauthenticated page evidence alone (status, canonical,
  robots, headers, schema, detected tags) — use `seohead parse`, `headers-check`, `robots-check`,
  `tech-detect`, or `sources-doctor` directly and skip the console/browser entirely.

## Preconditions

- [ ] A scope ticket has been drafted: provider, authorized account, exact property/counter/
  container, report/comparison periods, dimensions/metrics/filters, and search type.
- [ ] The user will handle sign-in and property selection themselves — the skill never handles
  credentials or switches properties to route around missing access.
- [ ] An ignored local output directory exists or is agreed for exports (for example
  `_sandbox/analytics-console-review/<date>/`).
- [ ] If the ask is ambiguous ("search traffic"), the specific evidence source (GSC / Bing
  Webmaster / Yandex Webmaster / a web-analytics platform) has been confirmed with the user rather
  than assumed.

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

## Decision points

- **Ambiguous evidence source ("search traffic").** This could mean GSC, Bing Webmaster, Yandex
  Webmaster, or a web-analytics platform — ask the user rather than assuming GSC access exists.
- **Readiness gate.** Before pulling any data, classify the state (browser unavailable / sign-in
  required / property selection required / access denied / read view available / export available /
  export unavailable). Anything short of "read view available" or "export available" means stop and
  hand off — do not partially collect data while hoping access appears.
- **"Get whatever you can" requests.** Decide between running the bounded public baseline
  (status/title/canonical/robots/headers/sitemap/tags) now or waiting for console access; if the
  baseline is run, keep it in its own section and state explicitly that it cannot confirm or explain
  a traffic decline without affected landing-page evidence.
- **Any save/create/publish/delete action surfaces inside the console.** That is a write, not a
  read — stop, show the exact target, action, and available diff or impact, and wait for a separate
  final confirmation instead of folding it into the read-only review.

## Definition of done

- [ ] A readiness state was reported before any data collection; if it was below "read view
  available"/"export available," the skill stopped with the concise handoff instead of guessing.
- [ ] The visible property and date range were confirmed against the scope ticket before capturing
  data.
- [ ] Every export, if any, has a retrieval manifest beside it (provider, property, retrieval time,
  periods, dimensions/metrics/filters/search type, file name, SHA-256, visible limitations).
- [ ] No raw session-level data, credential, or write action was taken without a separate explicit
  confirmation.
- [ ] Findings are separated into observations, candidate explanations, missing evidence, and
  proposed next checks; any public-baseline section is clearly marked as not proving a console-level
  claim.

## Cost

This skill drives a human-authorized browser session, not a paid API — the cost is mostly the
user's time (sign-in plus a few minutes per report) and there is no per-call charge for the console
itself. When cross-checks are run, they call local read-only toolkit commands (`seohead parse`,
`headers-check`, `robots-check`, `tech-detect`, `sources-doctor`, or reading an existing
`seohead sf run` export) — each a single lightweight request, no paid API, sub-second to a few
seconds, typically well under 10 requests for a baseline pass.

## Boundaries

- A visible console page does not prove API access or complete data coverage.
- UI exports can be capped, anonymized, sampled, or inconsistent with chart totals.
- A detected public tag does not prove that an analytics property receives correct events.
- Browser evidence is a dated observation, not a reproducible provider API response.
- Orphan and decline outputs are candidates for review, not causal conclusions.
- Generic site-audit findings are not loss candidates until they are joined to affected landing
  pages or another scoped evidence set.
- Never commit exports, manifests containing private property names, or client analytics data.
