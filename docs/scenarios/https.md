# Scenario 49 — HTTPS: the leftover HTTP URLs and the resources that undo the padlock

## The question

> We moved to HTTPS three years ago. Why does the browser still complain on some pages?

A migration that was declared finished usually has two residues: URLs the site still emits over
`http://`, and pages served over HTTPS that pull an image, a script or a stylesheet over plain
HTTP. The first is a link problem, the second is a browser one, and both survive because
neither breaks anything loudly.

## Covers

- **Security** — HTTP URLs · Mixed Content · Form URL Insecure · Form On HTTP URL · Unsafe Cross Origin Links · Protocol-Relative Resource Links

## The chain

**1. Crawl with link attributes captured, and let every URL be judged by its own scheme.**

```json
{"link_attributes": {"capture": true}}
```

```bash
seohead crawl-site --url https://example.com --config ./crawl.json --out-dir ./run
```

`HTTP_URL` fires on any crawled URL that starts with `http://` — not on the site, on the URL.
That is what turns "we migrated" into a list of the places that did not. `link_attributes.capture`
is a second, unrelated cost (see step 2) worth paying in the same crawl rather than a second one.

**2. Read the link- and form-shaped residues of a migration nobody re-audits.**

Four checks fire straight from that one crawl, no extra request:

| Finding | The question it answers |
|---|---|
| `FORM_URL_INSECURE` | does a `<form>` submit to `action="http://…"`, critical regardless of the page's own scheme? |
| `FORM_ON_HTTP_URL` | does a password field sit on a plain-HTTP page — credentials leaked before the action URL is even reached? |
| `UNSAFE_CROSS_ORIGIN_LINK` | does a `target="_blank"` link omit `rel="noopener"`/`"noreferrer"`, handing the opened page a live handle back? |
| `PROTOCOL_RELATIVE_LINK` | was an href written as `//host/path`, silently following whatever scheme served the current page? |

The first two need only what every crawl already records (a form's action and whether it holds
a password field); the last two need `link_attributes.capture` from step 1 — off by default
because the extra per-link data has a real memory cost on a large crawl (see that setting's
own docstring in `seohead/crawl/settings.py`).

**3. Scan the run.**

```bash
seohead log-scan --run ./run
```

**4. Ask what the origin does with an insecure request.**

```bash
seohead security-check --url https://example.com
```

```json
"https_redirect": {
  "checked": true,
  "final_url": "https://example.com/",
  "upgrades": true,
  "status_code": 200
}
```

`upgrades: false` is the finding that explains the rest: if `http://` is served rather than
redirected, every old link, bookmark and printed URL keeps arriving unencrypted, and the HTTP
copies of your pages keep existing.

**5. Look at what the pages themselves load.**

```bash
seohead asset-weight-check --url https://example.com/page
```

Each subresource is listed with its own URL, so an `http://` entry on an HTTPS page is visible
directly. In the audit the same thing appears as `MIXED_CONTENT` and `INSECURE_SUBRESOURCE`.

**6. Confirm one page's markup by hand.**

```bash
seohead parse --url https://example.com/page
```

**7. Report the lists together.**

```bash
seohead report-build --audit ./run/audit.json --format xlsx --out ./https.xlsx
```

## What comes out

Four lists that go to four different places. The HTTP URLs are a redirect rule and a pass over
the templates that still hardcode a scheme. The mixed content is an editorial and template fix:
old post bodies with absolute `http://` image URLs, and a widget embedded years ago. The forms
list is two different repairs (an action to point at `https://`, a page that must move to HTTPS
before its own login form is trustworthy at all). The link list is a template fix in the
component that opens external links in a new tab, or a copyeditor's habit of pasting a CDN URL
without a scheme.

## What it costs

The crawl (`link_attributes.capture` adds memory, not requests), plus one request each for
`security-check`, `asset-weight-check` and `parse` on the pages you inspect by hand. Nothing
paid.

## What it cannot answer

- **Whether the certificate is any good.** Nothing here inspects the certificate, its chain or
  its expiry date. That is one `openssl s_client` away and is not part of this chain.
- **Mixed content introduced after load.** A script that injects an `http://` image at runtime
  is invisible to a static parse — see [scenario 4](rendering.md).
- **Whether HSTS is safe to add.** Committing a domain to HTTPS-only is a decision with a
  rollback cost; see [security headers](security-headers.md) for what is measured and what is
  still a judgement.
- **Which HTTP URLs still receive traffic.** The crawl finds the URLs, not their visitors. That
  needs analytics or logs, and `log-analyze` if you have the logs.
- **Whether an insecure subresource is load-bearing.** A blocked tracking pixel and a blocked
  stylesheet look identical in the list and are not the same emergency.
- **A form or link written by JavaScript.** The edge and form lists are built from served HTML;
  see [scenario 4](rendering.md).
