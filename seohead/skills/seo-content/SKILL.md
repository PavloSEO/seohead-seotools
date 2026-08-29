---
name: seo-content
description: >
  Write SEO articles, optimize content for generative engine answers (GEO), and assess content quality before publication (E-E-A-T).
  Use when asked to write a complete article or landing page, optimize copy for inclusion in AI Overviews / ChatGPT,
  or determine whether content is ready to publish. Works for Google and Yandex across all geographies and languages.
  Triggers: "write an article," "SEO copy," "optimize content," "appear in AI answers," "ready to publish," "review this article."
---

# SEO Content (Writing + GEO + Quality Review)

Three blocks in one workflow:
**Writing → GEO Optimization → Quality Review**

---

## Quick Start

```
Write an SEO article about [topic], targeting [keyword], for [country/language]
```
```
Optimize this content for AI answers (GEO): [text or URL]
```
```
Review this article before publication and assess how ready it is: [text or URL]
```

---

## BLOCK 1 — Writing an SEO Article

### Workflow (9 Steps)

1. **Gather requirements** — primary and secondary keywords, target length, content type (article/landing page/review), audience, intent, tone, CTA, and competitors.
2. **Analyze the SERP** — review the top 10 results for the target keyword: formats, structure, length, and content surfaced in snippets.
3. **Create an optimized headline (H1/Title)** — place the keyword near the beginning, keep it under 60 characters, and match search intent. Provide 3 options.
4. **Write the meta description** — combine the keyword, value proposition, and CTA in 150–160 characters. Provide 3 options.
5. **Structure and write the content** — H1 → introduction (answer immediately) → H2/H3 sections → FAQ → conclusion + CTA.
6. **Apply on-page practices** — use the keyword within the first 100 words and in subheadings, write alt text, and maintain readability (Flesch ≥50 for English; adapt the metric for Russian).
7. **Add internal and external links** — include 2–5 relevant internal links and 1–2 authoritative external sources.
8. **Optimize for snippets and featured blocks** — add an FAQ block, numbered lists for how-to content, and tables for comparisons.
9. **Run a final review** — confirm keyword placement, complete intent coverage, no keyword stuffing, and clear E-E-A-T signals.

### Headline Formulas

| Pattern | Example |
|---------|--------|
| Keyword + Benefit | "SEO Site Audit: How to Find and Fix Errors" |
| Number + Keyword | "12 SEO Mistakes That Kill Organic Traffic" |
| How to + Keyword + Outcome | "How to Run an SEO Audit and Reach the Top 10" |
| Keyword + [Year] | "SEO in 2025: What Works Now" |
| Keyword vs. Keyword | "Yandex vs. Google: How Their Ranking Systems Differ" |

### Content Types and Their Structures

**How-to guide:** Introduction → Requirements → Step 1...N → Common mistakes → FAQ → Conclusion

**Comparison (A vs. B):** Introduction → Comparison table → Details of A → Details of B → Best fit for each audience → Conclusion

**Long-form / pillar page:** Introduction → TL;DR → H2 sections (6–10) → Each H2 is self-contained → Conclusion + CTA

**Landing page:** Offer in H1 → Pain point → Solution → Benefits → Evidence → CTA → FAQ

---

## BLOCK 2 — GEO Optimization (Appearing in AI Answers)

**Use when:** content needs to be cited by ChatGPT, Perplexity, Google AI Overviews, Gemini, or Alice.

### How AI Selects Sources to Cite

- Looks for clear definitions (25–50 words) at the beginning of a section
- Prefers specific data accompanied by sources and dates
- Extracts directly citable claims ("X is Y%, according to Z, 2024")
- Favors Q&A structures, tables, and numbered lists
- Assesses authority through the author, organization, and links to primary sources

### 5 Steps for GEO Optimization

1. **Load the CORE-EEAT GEO targets** — prioritize an immediate clear answer (C02), factual density (C09), structure (O03), schema (O05), and authority (E01).

2. **Analyze the current content** — assess:
   - Does it contain a standalone definition (25–50 words)?
   - Does it contain citable claims with figures and dates?
   - Does it include a Q&A section?
   - Are authority signals visible (author, experience, sources)?
   - How current is the content?

3. **Apply GEO techniques:**

   | Before | After |
   |------|-------|
   | "Email marketing is a useful tool" | "Email marketing is a direct communication channel for reaching subscribers. According to Litmus (2024), the average ROI is $36 for every $1 spent." |
   | General statements without figures | Specific data + source + year |
   | Unbroken prose | Table / list / Q&A |
   | "We believe that..." | "[Author, title, company] states: ..." |

4. **GEO output** — show what changed, the GEO score before and after, and AI-query coverage.

5. **Self-check** — verify: Is the answer in the first 2 paragraphs? Are there ≥3 citable facts? Does the FAQ match the visible content? Has schema been added?

### Engine-Specific Considerations

| Engine | What It Prefers |
|--------|-----------------|
| Google AI Overviews | Structure, FAQ/HowTo schema, E-E-A-T, domain authority |
| ChatGPT / Copilot | Clear definitions, well-structured prose, links to primary sources |
| Perplexity | Freshness, specific data, direct answers to questions, citable sources |
| Yandex / Alice | Structure, speed, mobile friendliness, authoritative Russian-language sources |

---

## BLOCK 3 — Quality Review (E-E-A-T / CORE-EEAT)

**Use when:** the article is written and a publish-or-revise decision is needed.

> Run automatically after writing or optimizing content with block 1 or 2.

### 8 Quality Dimensions

| Dimension | What to Assess | Weight |
|-----------|----------------|-----|
| C — Clarity | Comprehensibility, structure, no filler | High |
| O — Originality | A distinctive angle, no copied content, original data | High |
| R — Reliability | Sources, facts, dates, and absence of errors | Critical |
| E — Expertise | Depth, author expertise, and nuance | High |
| E — Experience | First-hand experience, case studies, and practical examples | Medium |
| A — Authoritativeness | Reputation, backlinks, and mentions | Medium |
| T — Trust | Transparency, no manipulation, and no contradictions | Critical |
| + GEO | AI citability and structure for AI systems | Medium |

### Prepublication Checklist

**Critical (do not publish unless all are satisfied):**
- [ ] Search intent is covered completely
- [ ] There are no factual errors
- [ ] The headline and body do not contradict each other
- [ ] The evaluated content matches what users can see (no hidden text)
- [ ] The main question has a clear answer

**Important:**
- [ ] The H1 contains the primary keyword
- [ ] A meta description is provided
- [ ] Internal links are included (at least 2)
- [ ] Images have alt text
- [ ] An FAQ section is included (for GEO)
- [ ] The author or source of expertise is identified

**Recommended:**
- [ ] Schema markup is included (FAQ, Article, HowTo)
- [ ] Data includes dates and sources
- [ ] Tables/lists present structured information
- [ ] Freshness signals are present (last-updated date)

### Verdict

- **Publish** — all critical items are satisfied ✓ and ≥80% of important items are satisfied
- **Revise** — critical or important items still have issues
- **Rewrite** — search intent is not covered or the content contains serious factual errors

---

## Related Skills

- Schema opportunities identified → **seo-markup**
- Page audit needed → **seo-audit-page**
- After publication → monitor rankings, impressions, clicks, engagement, and conversions against the documented baseline
