# Silo Architecture — Reference for Evaluating Website Structure

Condensed theory for the `silo-audit` skill. The source is the seohead.tech article on
silo structure. Use it as the basis for a verdict of “chaos / basic silo / extended silo.”

## Semantic Coverage (Working Metric)
The share of actual search demand on a topic that the website addresses with pages. This
is not the number of pages or their rankings; it is **intent coverage**. Use these
benchmarks when designing a structure:

| Level | Coverage | Description |
|---|---|---|
| Typical chaos (“brochure site”) | **5–15%** | catalog + shipping/payment + about, with no hubs |
| Basic silo | **20–30%** | section hubs and a URL hierarchy, without SEO filters or cross-links |
| Extended silo | **70–90%** | filters, industries, glossary, cases, resources, internal linking, and E-E-A-T |
| Full coverage (target) | **100%** | intents across the entire funnel and long tail are covered |

This is an estimate of topical completeness during architecture design, not a Search
Console KPI.

## Three Structures for the Same Website
1. **Chaos / “the usual approach.”** A flat catalog; `/delivery/` and `/payment/` are
   isolated L1 URLs without a parent hub; there is no hierarchy, no breadcrumbs, and no
   internal linking. A crawler sees a collection of pages, not a structure. Coverage is
   5–15%.
2. **Basic silo.** Every section has a hub page: `/catalog/`, `/services/`, and
   `/clients/` as the parent of shipping/payment/warranty pages. URLs reflect the
   structure, and breadcrumbs are logical. The website does not yet have SEO filters,
   industry landing pages, a glossary or cases, cross-links, or an author/E-E-A-T layer.
   Coverage is 20–30%.
3. **Extended silo.** L2–L3 depth, a filter matrix, industries (`/industries/`),
   materials (`/materials/`), a glossary (`/glossary/`), cases (`/cases/`), calculators,
   and an author/expert. Coverage is 70–90%.

## URL Nesting Rule
Depth is not an aesthetic choice. `/catalog/workwear/winter/for-welders/` is understood
as a document within a topical cluster, while the flat
`/winter-workwear-for-welders/` is merely a page. **Every URL level must be a real page
with its own content**, not a technical segment. An important page must be reachable in
≤3 clicks from the home page. The CMS, language, and hosting do not affect the
architecture. Sitemap structure: an index file plus separate sitemaps for each section.

## An SEO Filter Matrix Instead of an Infinite Catalog
Categories provide the basic branching structure; filters address demand at a finer
level: **category × attribute**. A populated cell is a separate SEO page with a unique
URL, H1, metadata, and content. An empty cell means **there is no page**: without demand,
do not create thin URLs. This yields 40–60 targeted pages instead of 5 categories; a dash
is an honest “no demand” signal.

## Cross-Links: A Silo Is Not a Prison
**Navigation flows** are isolated, while contextual internal links between sections
create semantic connectedness. In a silo + link-pyramid hybrid, the silo defines
clusters and the pyramid circulates authority within a cluster: hub → leaves → hub.
Cross-links between clusters must be **meaningful and selective**, neither “everything
to everything” nor zero. If links have to be “invented,” the structure is immature and
the content was not written for people.

## A Case Study as a Landing Page, Not a Gallery
Every case study has its own URL with text, stages (before / in progress / result), and
links to products, materials, and services. It ranks for queries such as “equipping a …
facility” and passes authority.

## Author and E-E-A-T
Google filters out impersonal templates. The website needs an expert author such as a
director or specialist, the author's photo on pages, an author page with a biography and
experience, `author` in Schema.org, and personal commentary in the text. One detailed
case study is worth more than ten bare galleries.

## Universal Sections (Coverage Checklist)
Author/expert · Glossary · Services · Industry solutions · Product capabilities/filters ·
Materials/technologies · “For Customers” hub (shipping/payment/warranty) · “About” hub
(team/production/certificates) · Cases · Calculators · Geographic pages · Blog.
Every section addresses its own intent type and connects to other sections with
meaningful links.

## Advantages and Disadvantages of an Extended Silo
**+** Full-funnel coverage, topical authority, faster indexing, scalability, and clarity
for users. **−** Complex design, including the risk of cannibalization or tautological
URLs; the risk of thin content; resource-intensive content production; and time to
results: 3–4 months for the structure and at least 6 months for visible traffic.

## Hierarchy: Number of Levels
The optimum is 2–3 levels: home page → category → resource. Use L4 only for very large
websites. Pages more than 3 clicks from the home page are indexed less effectively.
