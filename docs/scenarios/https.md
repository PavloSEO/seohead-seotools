# Scenario 49 — HTTPS: the leftover HTTP URLs and the resources that undo the padlock

## The question

> We moved to HTTPS three years ago. Why does the browser still complain on some pages?

A migration that was declared finished usually has two residues: URLs the site still emits over
`http://`, and pages served over HTTPS that pull an image, a script or a stylesheet over plain
HTTP. The first is a link problem, the second is a browser one, and both survive because
neither breaks anything loudly.

## Covers

- **Security** — HTTP URLs · Mixed Content

## The chain

**1. Crawl, and let every URL be judged by its own scheme.**

```bash
seohead crawl-site --url https://example.com --config ./crawl.json --out-dir ./run
```

`HTTP_URL` fires on any crawled URL that starts with `http://` — not on the site, on the URL.
That is what turns "we migrated" into a list of the places that did not.

**2. Scan the run.**

```bash
seohead log-scan --run ./run
```

**3. Ask what the origin does with an insecure request.**

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

**4. Look at what the pages themselves load.**

```bash
seohead asset-weight-check --url https://example.com/page
```

Each subresource is listed with its own URL, so an `http://` entry on an HTTPS page is visible
directly. In the audit the same thing appears as `MIXED_CONTENT` and `INSECURE_SUBRESOURCE`.

**5. Confirm one page's markup by hand.**

```bash
seohead parse --url https://example.com/page
```

**6. Report both lists together.**

```bash
seohead report-build --audit ./run/audit.json --format xlsx --out ./https.xlsx
```

## What comes out

Two lists that go to two different places. The HTTP URLs are a redirect rule and a pass over
the templates that still hardcode a scheme. The mixed content is an editorial and template fix:
old post bodies with absolute `http://` image URLs, and a widget embedded years ago.

## What it costs

The crawl, plus one request each for `security-check`, `asset-weight-check` and `parse` on the
pages you inspect by hand. Nothing paid.

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
