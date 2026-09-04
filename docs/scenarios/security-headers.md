# Scenario 16 — Security headers, read as a crawling problem

## The question

> Security sent us a scan full of missing headers. Is any of it ours, and does it affect
> search at all?

Most of that list belongs to the security team. A smaller part of it belongs here, for one
reason: a browser that refuses to load a resource, and a crawler that never received it, are
the same outcome for what a page is understood to contain.

## Covers

- **Security** — Missing HSTS Header · Missing Content-Security-Policy Header · Missing X-Content-Type-Options Header · Missing X-Frames-Options Header · Missing Secure Referrer-Policy Header · Bad Content Type

## The chain

**1. Ask one origin what it sends.**

```bash
seohead security-check --url https://example.com
```

```json
{
  "score": 0,
  "grade": "F",
  "headers_present": {},
  "headers_missing": [
    {"header": "strict-transport-security", "purpose": "forces browsers to use HTTPS"},
    {"header": "content-security-policy",
     "purpose": "controls allowed script and style sources"},
    {"header": "x-content-type-options", "purpose": "prevents MIME type sniffing"},
    {"header": "x-frame-options",
     "purpose": "prevents clickjacking, or use frame-ancestors in CSP"},
    {"header": "referrer-policy", "purpose": "limits URL information sent to other sites"}
  ]
}
```

Alongside them: version disclosure from `Server` and `X-Powered-By`, cookie flags, and whether
`http://` upgrades to HTTPS at all.

**2. Read the delivery headers next to the security ones.**

```bash
seohead headers-check --url https://example.com
```

This is where `Content-Type`, compression, cache lifetimes and the HTTP version come from. The
declared content type is the header that decides whether a response is parsed as a document at
all, which makes it the one on this list with a direct crawling consequence.

**3. Check more than the home page.**

```bash
seohead security-check --url https://example.com/page
```

Headers are usually set at the edge, and edge rules are per path. One measurement of one URL is
one URL, and an origin that is fronted by a CDN may answer differently for an asset path than
for a document.

**4. Put it beside the rest of the delivery picture.**

```bash
seohead cdn-check --url https://example.com
```

**5. Carry it into a report with everything else the run found.**

```bash
seohead report-build --audit ./run/audit.json --format docx --out ./security.docx
```

## What comes out

A per-header verdict with the reason each header exists, a letter grade, and a short findings
list in plain sentences. The grade is a summary of the same facts, not an extra measurement,
and it is the least useful part of the output — the header list is what somebody configures.

Across a crawl, `MISSING_HSTS` is available as a site-wide finding when a Screaming Frog
security export supplies it; from a native crawl, treat `security-check` per URL as the source
of truth for headers and do not read the absence of the finding as the presence of the header.

## What it costs

One request per URL checked. `--probe-paths` adds a handful of extra requests probing for
exposed service paths such as `.git` and `.env`; it is opt-in because probing somebody's server
for files is a different act from reading its headers, and should be a decision.

Nothing paid.

## What it cannot answer

- **Whether a missing header is a mistake.** No CSP on a static brochure site is not the
  problem it is on a checkout. The check reports absence; the risk is contextual.
- **Whether the declared content type is true.** The type is recorded and drives document
  detection, but a response that declares one type and carries another is not asserted here.
  A file served as `text/html` that is really something else passes this chain.
- **Whether a CSP actually works.** A policy that is present may still be permissive enough to
  be decorative. Nothing here evaluates its contents.
- **Anything from inside the server.** No configuration, no filesystem, no logs.
- **Whether the site is secure.** This is a header check, not a penetration test, and reporting
  it as one is how a real finding gets ignored later.
