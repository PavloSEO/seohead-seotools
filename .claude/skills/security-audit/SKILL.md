---
name: security-audit
description: >-
  Audit a site's security headers from an SEO perspective: HSTS, CSP, X-Frame-Options,
  X-Content-Type-Options, Referrer-Policy, and Permissions-Policy, with a numeric score
  and an A–F grade. Also check software-version disclosure (Server, X-Powered-By), cookie
  flags (Secure, HttpOnly, SameSite), the http→https redirect, and, only when explicitly
  requested, whether operational files are publicly exposed (.git, .env, phpinfo). Use
  when asked to "check site security," audit "security headers," determine whether
  "HSTS/CSP is present," check whether ".git is blocked," or investigate "server-version
  disclosure." Triggers: security headers, HSTS, CSP, secure cookie, samesite, .git exposed,
  .env exposed, version disclosure, x-powered-by, site security.
---

# Security Audit — security headers and information disclosure

This is not a penetration test. Everything uses ordinary GET requests for information the site
already serves publicly: response headers, cookie flags, and the HTTPS redirect. Nothing is
modified and no values are guessed. This matters for SEO: HSTS and HTTPS affect trust and
rankings, while an exposed `.git` or `.env` directly enables data leakage and a subsequent
compromise that may damage search visibility.

The tool is `seohead security-check` (CLI + MCP `seo_security_check` + HTTP).

## Trigger
- "check site security," "security headers," "security score";
- "is HSTS / CSP present," "are the headers configured";
- "does the server / PHP version leak";
- "is .git / .env blocked," "is phpinfo publicly exposed";
- before delivering a site to a client or as part of a full audit.
- Triggers from the frontmatter: security headers, HSTS, CSP, secure cookie,
  samesite, .git exposed, .env exposed, version disclosure, x-powered-by,
  site security.

## Anti-trigger
- Anything resembling a penetration test — exploitation, brute forcing, or
  active vulnerability scanning. This skill only reads what the site already
  serves publicly (headers, cookies, an HTTP→HTTPS redirect); it has no
  offensive capability and neither does any other skill in this toolkit —
  point the user to a dedicated security vendor for that.
- The question is about page-speed impact of a CSP or other header, not its
  security posture — use the `web-speed` skill for the performance angle.
- Probing for exposed operational files (`--probe-paths`) when the user
  hasn't asked about information disclosure — that flag fetches paths like
  `/.git/HEAD` and `/.env` beyond plain header inspection, so it must be
  explicitly requested, not run by default.
- The question is about content-level or crawl-level SEO (redirects,
  canonicals, on-page factors) rather than headers/cookies/disclosure — use
  `sf-analyzer` or another on-page skill instead.

## Preconditions
- [ ] A live, reachable URL — the HTTP→HTTPS redirect check needs the plain
  HTTP endpoint to actually respond, not just the HTTPS one.
- [ ] Explicit user request before adding `--probe-paths` (it fetches
  operational file paths, not just headers).
- [ ] If probing is in scope, confirmation the site is the user's own or one
  they are authorized to audit.

## Workflow
**Baseline check (safe and makes no unnecessary requests):**
```bash
seohead security-check --url https://example.com
```
The response contains `score` and `grade` (A–F based on the weighted total),
`headers_present`, `headers_missing` (with the purpose of each header),
`version_disclosure` (what discloses version information), `cookies` (the
Secure/HttpOnly/SameSite flags for each cookie), `https_redirect` (whether HTTP redirects
to HTTPS), and `findings`, a list of issues in plain language.

**Probe operational paths (only when the user explicitly requests it):**
```bash
seohead security-check --url https://example.com --probe-paths
```
This additionally checks whether `/.git/HEAD`, `/.env`, `/.DS_Store`, `/.svn/entries`,
`/phpinfo.php`, `/server-status`, or `/backup.sql` is publicly accessible. The tool uses
content inspection to distinguish a genuinely exposed file from a soft 404. This is still
limited to reading public URLs, but enable the flag only when the user asks to check for
information disclosure, not by default.

## Score (grade)
A ≥ 90, B ≥ 75, C ≥ 60, D ≥ 40, E ≥ 20; otherwise F. HSTS and CSP are weighted at 20 points
each, and the other four headers at 15 points each. `X-Frame-Options` counts as present if its
role is covered by `frame-ancestors` in CSP.

## Decision points
- **Grade sits just under a threshold** (e.g. 88 vs. the 90 needed for A).
  Identify specifically which missing header would close the gap — HSTS and
  CSP are worth 20 points each, the other four headers 15 each — rather than
  giving a vague "improve headers" recommendation.
- **`X-Frame-Options` absent but CSP `frame-ancestors` present.** Per the
  scoring rule this counts as present; do not double-flag it as missing.
- **Version disclosure found (`Server`/`X-Powered-By`).** Judge severity by
  what's disclosed — an exact framework-plus-version string is more
  actionable for an attacker than a generic `nginx` — but report it either
  way, since it is a real trust/technical-SEO signal even at low severity.
- **`--probe-paths` finds a path that returns 200.** The tool distinguishes a
  genuinely exposed file from a soft-404 page via content inspection — trust
  that distinction in the report rather than treating every 200 on a probed
  path as a confirmed leak.

## Definition of done
- [ ] `security-check` baseline run completed and `score`/`grade` reported
  with the specific missing headers that would raise the grade.
- [ ] Cookie flags (Secure/HttpOnly/SameSite) reported per cookie, not just
  in aggregate.
- [ ] http→https redirect status confirmed explicitly (redirects or not).
- [ ] `--probe-paths` run only if the user explicitly asked, and its results
  (or the fact it was not run) stated plainly.
- [ ] Version-disclosure findings listed with which header/value discloses what.

## Cost
The baseline `seohead security-check` run is 1-2 lightweight GET requests
plus the HTTP→HTTPS redirect check. With `--probe-paths` it adds up to
roughly 7 more GETs (`.git/HEAD`, `.env`, `.DS_Store`, `.svn/entries`,
`phpinfo.php`, `server-status`, `backup.sql`). Under 10 requests total,
sub-second each, no paid API, and no destructive or write actions — every
request is a normal public GET.

## What to deliver to the user
- **Grade:** the letter, the points earned, and what is missing for the next grade.
- **Missing controls:** a list of absent headers explaining why each one matters.
- **Disclosure:** which headers reveal software-version information.
- **Cookies:** which ones lack Secure / SameSite.
- **http→https:** whether it redirects.
- **Exposed files** (if the probe was run): what must be blocked immediately.

Headers are part of technical SEO. Related skills: **seo-recon** (infrastructure),
**sf-analyzer** (on-page crawl), and **seo-deep-audit** (full domain audit).
For client sites, also examine CSP headers from a performance perspective with **web-speed**.
