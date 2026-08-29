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

## When to use it
- "check site security," "security headers," "security score";
- "is HSTS / CSP present," "are the headers configured";
- "does the server / PHP version leak";
- "is .git / .env blocked," "is phpinfo publicly exposed";
- before delivering a site to a client or as part of a full audit.

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
