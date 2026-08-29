---
name: tech-audit
description: >-
  Analyze what a site is built with: CMS/site builder, server-side framework and
  runtime, analytics and advertising pixels, widgets and chats, consent management,
  payment systems, fonts and libraries from third-party CDNs, protection, and CDN
  hosting. Make one HTTP request, then inspect the HTML, headers, cookies, and script
  src attributes using signatures; optionally load an external
  fingerprint database (the SEOHEAD_TECH_DB environment variable). Use when asked
  "what is the site built with," "which technologies," "site stack," "what does the
  site use," "detect technologies," "tech stack," "wappalyzer," "is it WordPress,"
  or "site CMS." Triggers: tech stack, detect technologies, wappalyzer, CMS,
  WordPress, Bitrix, Tilda, Shopify, Next.js, Nuxt, Vue, React, Angular, Laravel,
  Django, analytics, Google Analytics, Yandex Metrica, pixels, Meta Pixel, TikTok
  Pixel, widgets, Intercom, chats, Stripe, Cloudflare, consent, cookie banner,
  headless, what is it built with, site engine, and how traffic is measured.
---

# Tech Audit — What a Site Is Built With: Stack, Analytics, Pixels, and Widgets

Detect the technologies on a single page: which CMS or site builder it uses, which
framework renders the HTML, what runs on the backend, how traffic is measured, which
advertising pixels and chats are installed, who processes payments, and who protects
the site. For SEO, this answers "what can actually be changed on this site," "how is
traffic measured," and "how many third-party scripts weigh down the page."

This is not a manual source-code review, but a tool in the `seohead` toolkit
(CLI + MCP + HTTP). In MCP, it is `seo_tech_detect`. After one request to the page,
all further analysis is static signature matching against `header`, `value`, `cookie`,
`html`, and `script`. Every match includes the marker (`evidence`) that triggered it,
making the conclusion verifiable.

## When to Use It
- "what is the site built with," "which site engine," "which CMS," "is it WordPress," "site stack";
- "which technologies," "what does the site use," "how is traffic measured," "which pixels are installed";
- "which widgets / chats / support tools," "which consent banner," "which payment systems";
- "does it use Cloudflare / protection," "who hosts the frontend (Vercel / Netlify / CloudFront)";
- checking a headless combination (CMS + Next.js/Nuxt) before a rendering audit;
- a quick competitor profile before an audit — what it uses and how it differs.

## Workflow

**1. Technologies on a single page — the only command:**
```bash
seohead tech-detect --url https://example.com
```
After one request, the tool inspects the HTML, headers, cookies, and script `src`
attributes using ~200 built-in signatures. The response contains:
- `generator` — the complete contents of `<meta name=generator>` (often includes the CMS version);
- `technologies` — each entry with `category`, `evidence` (the marker that identified it),
  and `version` when exposed in `generator` or `x-powered-by`;
- `by_category` — the same technologies grouped by category;
- `scripts_total` — the total number of external scripts on the page;
- `third_party_hosts` — third-party domains from which scripts are loaded;
- `external_db` — the status of the external fingerprint database (see below);
- `findings` — plain-language conclusions assembled from the signatures.

**2. Interpret the response by category** (`by_category`):
- **cms** — WordPress, 1C-Bitrix, OpenCart, Drupal, Joomla, MODX, Tilda, Wix,
  Squarespace, Ghost, Webflow, HubSpot CMS, Craft, Statamic, Sanity, Contentful,
  Payload, Wagtail, October, Umbraco, uCoz, Moguta, Hugo, Jekyll, Eleventy,
  Docusaurus, VitePress, MkDocs, Sphinx;
- **ecommerce** — Shopify, WooCommerce, Magento, PrestaShop, InSales, BigCommerce,
  CS-Cart, Saleor, Spree, VirtueMart;
- **framework** — Next.js, Nuxt, SvelteKit, Astro, Gatsby, Remix, Angular, Vue.js,
  React, Preact, Qwik, Alpine.js, htmx, Turbo, Stimulus, Laravel, Django, Rails,
  Flask, Symfony, CodeIgniter, Yii, Spring;
- **library** — jQuery, Tailwind, Bootstrap, Bulma, Material-UI, Ant Design,
  shadcn/ui, Lodash, Moment/Day.js, D3, Three.js, GSAP, Swiper, Slick, AOS, Lottie,
  webpack, Vite, esbuild, Parcel, Rollup, Babel;
- **server** — nginx, Apache, LiteSpeed, Microsoft IIS, Caddy;
- **runtime** — PHP, Express, ASP.NET, Passenger, Deno, Gunicorn, uWSGI, Puma, Tomcat;
- **analytics** — Google Analytics 4, GTM, Yandex Metrica, Matomo, Plausible,
  Fathom, Hotjar, Clarity, Vercel Analytics, Amplitude, Mixpanel, PostHog, Heap,
  FullStory, Adobe Analytics, Statcounter, Openstat, LiveInternet, Clicky,
  GoatCounter, Chartbeat;
- **pixel** — Meta Pixel, TikTok, LinkedIn Insight, Google Ads, VK Pixel,
  Top.Mail.Ru, Reddit, Pinterest Tag, Quora, Bing UET, Yandex.Direct, Outbrain, Taboola;
- **widget** — Intercom, Crisp, Tawk.to, Jivo, Zendesk, Bitrix24 CRM, Calendly,
  Drift, LiveChat, Userlike, HelpCrunch, Verbox, Typeform, Youtube subscribe;
- **consent** — Cookiebot, OneTrust, Osano, iubenda, Didomi, Usercentrics, Termly, Klaro;
- **payment** — Stripe, PayPal, YooKassa, CloudPayments, Tinkoff Pay, Sber Pay,
  Robokassa, LiqPay, Braintree;
- **fonts** — Google Fonts, Adobe Fonts;
- **cdn-lib** — jsDelivr, cdnjs, unpkg, Bunny CDN, Fastly, AWS CloudFront, Vercel,
  Netlify, GitHub Pages, Amazon S3;
- **protection** — Cloudflare, DDoS-Guard, Qrator, Sucuri, Imperva Incapsula,
  ModSecurity, Cloudflare Turnstile, Google reCAPTCHA, hCaptcha;
- **marketing** — Mailchimp, HubSpot, Unisender, Mindbox, SendGrid.

**3. The `external_db` field — whether an external fingerprint database is connected:**
- `loaded: false` — the ~200 built-in MIT-licensed signatures are active; no external
  database is connected;
- `loaded: true` — the user supplied an external database and set its path in the
  `SEOHEAD_TECH_DB` environment variable; `technologies_in_db` (thousands of signatures)
  and `path` are shown. Built-in signatures take priority, while external signatures add
  technologies not covered internally. The tool reads the database as an external
  user-provided resource (like MaxMind GeoIP); the binary itself does not distribute it.

**4. `findings` and `third_party_hosts` — conclusions and context:**
- `findings` already includes flags for an unidentified site engine (probably custom-built
  or entirely JavaScript-driven), missing analytics, ≥3 advertising pixels, ≥10 third-party
  domains, and a headless combination (CMS + rendering framework —
  Next.js/Nuxt/SvelteKit/Astro/Gatsby/Remix);
- `third_party_hosts` shows the domains from which scripts are actually loaded. This provides
  performance and privacy context, revealing a "double" analytics stack, pixel overload,
  and hidden redirects to the CMS backend.

## What to Deliver to the User
A concise stack analysis in a single block, assembled from `by_category`, `findings`,
and `third_party_hosts`:
- **Stack by category:** CMS/site builder + framework + runtime/server (with the version
  from `generator`/`x-powered-by`, when exposed).
- **Analytics and pixels:** how traffic is measured (GA4/Yandex Metrica/Plausible/…),
  which advertising pixels are installed (Meta, TikTok, VK, …) — this shows "what they
  invest in."
- **Widgets and chats:** support tools (Intercom/Jivo/Crisp/…), session recording
  (Hotjar/Clarity).
- **Consent / payment:** which consent banner and payment systems are used — an indicator
  of store maturity and compliance.
- **Protection and CDN:** Cloudflare/DDoS-Guard/Qrator/Imperva; Vercel/Netlify/CloudFront
  as frontend hosting.
- **Third-party domains:** the `third_party_hosts` list — who actually serves the page.
- **Flags:** missing analytics, headless combination (check rendering), ≥3 pixels,
  ≥10 third-party domains, or an unidentified site engine.

## Degraded Mode
If `seohead` is not installed and cannot be installed, identify the basic site engine manually:
`curl -sL "https://$URL"` → `<meta name=generator>` (WordPress/Bitrix/Tilda with
version), characteristic HTML paths (`/wp-content/`, `/bitrix/`, `tildacdn.com`,
`/_next/static`, `/_nuxt/`), `curl -sIL` headers (`server`, `x-powered-by`,
`cf-ray`, `x-vercel-id`, `x-shopify-stage`), and cookie names (`BITRIX_SM_*`,
`laravel_session`, `csrftoken`). The logic is the same as the signatures, but performed
manually, without `evidence` and without the external database's thousands of entries.

## Integrations
- **seo-recon** — domain and infrastructure: whois, DNS, hosting/ASN, TLS, CDN, and
  actual cache behavior. `tech-detect` answers "what is the frontend built with,"
  while `seo-recon` answers "where does the server run, and does the cache work."
- **audit-roadmap** / **seo-deep-audit** — a complete domain audit: technologies from
  this tool feed into the site profile as one roadmap input, alongside the crawl
  (`sf-analyzer`), rendering (`js-render-check`), and security (`security-audit`).
