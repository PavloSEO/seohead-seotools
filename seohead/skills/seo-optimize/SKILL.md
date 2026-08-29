---
name: seo-optimize
description: >
  Optimize existing content by refreshing outdated articles and improving internal linking. Use when
  a page is losing traffic, an article is outdated, orphan pages need to be found, a topic cluster
  needs to be built through links, or internal link equity needs to be improved.
  Triggers: "refresh this article," "content is outdated," "traffic dropped," "internal links,"
  "internal linking," "orphan pages," "topic cluster," "update content," "ranking loss."
---

# SEO Content Optimization (Refresh + Internal Linking)

Two modules:
**Content Refresh → Internal Linking**

---

## Quick Start

```
Refresh this article—its traffic has dropped: [URL or text]
```
```
Find the internal links that should be added for this page: [URL]
```
```
Audit the internal linking of [domain] and provide recommendations
```
```
This article is outdated—what should be updated? [URL]
```

---

## MODULE 1 — Content Refresh

**Use when:** an article is losing traffic or rankings, its content is outdated, or a new competitor has emerged.

### Content Decay Signals

| Signal | Action Threshold | Priority |
|--------|------------------|----------|
| MoM traffic decline | >20% over 2 weeks; >40% is urgent | P1–P0 |
| Ranking decline | 3–5 positions: investigate; >5 positions: urgent | P1–P0 |
| CTR decline | >20% from baseline: rewrite title/description | P2 |
| Publication date >12 months ago with no updates | High decay risk | P2 |
| Outdated links (>10% broken) | Medium risk | P2 |
| A competitor moved above the page | Displacement | P1 |
| Featured snippet or AI Overview lost | Displacement | P1 |

### Decay Score (0–100)

| Factor | Weight |
|--------|--------|
| Traffic decline | 30% |
| Ranking decline | 25% |
| CTR decline | 15% |
| Outdated content | 15% |
| Competitive displacement | 15% |

| Score | Status | Action |
|-------|--------|--------|
| 0–20 | Healthy | Monitor |
| 21–40 | Early decay | Add to next month's plan |
| 41–60 | Active decay | Refresh this week |
| 61–80 | Significant decay | Refresh urgently or rewrite |
| 81–100 | Critical | Rewrite, redirect, or remove |

### 9-Step Refresh Workflow

**1. E-E-A-T quick score** — assess eight dimensions (Clarity, Originality, Reliability, Expertise, Experience, Authoritativeness, Trust, GEO) and identify red flags.

**2. Refresh candidates** — identify them by age, outdated data, traffic decline, ranking loss, broken links, and changes in SERP intent.

**3. Decay analysis** — compare performance six months ago with performance now: traffic, rankings, CTR, keyword delta, changes among top-ranking competitors, and the reasons for the decline.

**4. What needs to be updated** — document:
- Outdated facts, figures, and dates
- Gaps relative to competitors and PAA
- SEO updates (new keywords, intent changes)
- GEO updates (missing Q&A and citable facts)
- Broken links (internal and external)
- Outdated images

**5. Refresh plan** — specify the new title, structural changes, new sections, updated statistics, links, images, and validation requirements.

**6. Write the refreshed content** — draft a new introduction, replacement sections, updated facts, FAQ answers, and a "What Changed" section.

**7. GEO optimization** — add standalone definitions (40–60 words), citable claims with dates and sources, Q&A, tables, and lists.

**8. Republishing strategy**

| Scope of Changes | Date | Action |
|------------------|------|--------|
| >50% new content | Update datePublished | Republish with a new date |
| 20–50% changed | Update dateModified | Show the updated date |
| <20% changed | Keep the original date | Silent update |

After the refresh: update Schema (`dateModified`), update `lastmod` in the sitemap, request recrawling in GSC and Yandex Webmaster, and monitor performance for 4–6 weeks.

**9. Refresh report** — state what was done, the expected outcome, the owner, and the date of the next review.

### Refresh vs. Rewrite vs. Remove

| Situation | Decision |
|-----------|----------|
| Strong potential, outdated content | Refresh |
| Search intent has changed fundamentally | Rewrite |
| Several weak articles cover the same topic | Consolidate them into one strong article |
| No traffic and no value | Redirect or noindex |
| Strong traffic but poor content | Rewrite urgently |

---

## MODULE 2 — Internal Linking

**Use when:** internal link equity needs improvement, orphan pages need to be found, or a topic cluster needs to be built.

### 7-Step Optimization Workflow

**1. Analyze the current structure**
- Domain, page count, and total number of internal links
- Average number of links per page
- Most-linked pages
- Important pages with few links (a problem)
- Crawl depth (pages more than three clicks from the homepage are a problem)
- Structure score out of 10

**2. Orphan pages (pages with no internal links)**

Priorities:
- 🔴 High value + no links → add a link from a hub or category page immediately
- 🟡 Medium value → add a link from a tag or category page
- ⚪ Low value → delete, noindex, or redirect

**3. Anchor text**
- Which patterns are currently used?
- Is there over-optimization from too many identical anchors?
- Are there too many "click here" or "read more" anchors?
- Anchor diversity is required

**4. Topic Cluster Strategy**

```
Pillar (main topic page)
  └── Cluster 1 → links to the pillar
  └── Cluster 2 → links to the pillar
  └── Cluster 3 → links to the pillar
  └── Pillar ←→ all clusters bidirectionally
```

Steps:
1. Identify pillar pages (main topics)
2. Map cluster pages to each pillar
3. Check whether each pillar links to all its clusters and every cluster links back to its pillar
4. Add the missing links

**5. Contextual links**

For each page, identify:
- Source page (where the link will be placed)
- Target page (where the link points)
- Recommended anchor text
- Paragraph or placement for insertion
- Priority (P0/P1/P2)

**6. Navigation and footer**
- Main menu: are the correct pages included in the navigation?
- Footer: are important pages included without overloading it?
- Breadcrumbs: are they configured and do they help crawling?
- Sidebar, if present: are the links relevant?

**7. Implementation plan**
- Phase 1 (urgent): orphan pages + pillar-to-cluster relationships
- Phase 2 (this month): contextual links on top-performing pages
- Phase 3 (next month): navigation optimization
- Tracking metrics: crawl depth, indexed pages, organic traffic

### Anchor Text Rules

| Anchor Type | Share | Example |
|-------------|-------|---------|
| Descriptive (link topic) | 40–50% | "SEO audit guide" |
| Branded | 5–10% | "WebAgency" |
| Partial keyword match | 20–30% | "how to audit a website" |
| Naked URL | 5–10% | `example.com/seo-audit` |
| Generic ("here," "read") | <10% | Minimize |

**Stop patterns:**
- The same anchor from 5+ pages to one target → anchor-text spam
- Every link uses "click here" or "read more" → poor anchor quality
- No links point to an important page → orphan page

### Architecture Patterns

| Site Type | Recommended Structure |
|-----------|-----------------------|
| Blog/media | Pillar + clusters, category hubs |
| E-commerce | Category → subcategory → product, breadcrumbs |
| Corporate | Services → case studies → team → contact |
| SaaS | Features → How-to → Integrations → Pricing |

---

## Related Skills

- After refreshing content → **seo-content** (module 3, quality review)
- After the refresh → monitor rankings, impressions, clicks, and conversions in GSC, Yandex Webmaster, and analytics over the stated comparison window
- Technical issues found → **seo-audit-page** (technical module)
