---
name: schema-graph
description: >-
  Analyzes and recommends Schema.org structured data for a page: which type
  describes the content (Article/Product/Service/LocalBusiness/Event/Recipe/FAQPage/...),
  which connected @graph to build (Organization ← WebSite ← WebPage ← type), and what
  the current JSON-LD is missing for a rich result. Use when asked to check
  markup, schema.org, JSON-LD, structured data, or rich results/snippets, or when
  a general audit reaches the structured-data section. Two layers: vocabulary
  validation (1,010 types, inheritance, deprecated/pending terms) and rich-result
  eligibility. English triggers: check markup, schema org, json-ld, structured data,
  rich results, snippet, schema graph, validate jsonld. Localized Russian trigger
  examples: check structured data, validate JSON-LD, review rich-result eligibility.
---

# Schema Graph — Check Page Structured Data and Recommend a Graph

Two tools work as a pair: **`schema-build`** identifies the page type and recommends
a connected `@graph` (what to add), while **`schema-check`** validates the markup that
is already present. The first builds; the second checks—not the other way around.

## When to use it
- The user asks to check or create markup, JSON-LD, Schema.org, or rich results.
- A general audit (`seo-deep-audit`) has reached the structured-data section.
- A page does not produce a rich result even though it contains qualifying content—find
  out what is missing.

## Workflow (default: build → check → compare)
**Step 1. Recommend a graph.** One command provides the type classifier, a ready-to-use
`@graph`, and a diff:
```bash
seohead schema-build --url https://example.com/page
```
Read these fields carefully: `inferred_type`, `confidence`, `signals[]` (the basis for
the decision), `alternatives[]`, and `note`. If `confidence: low` and a `note` is
present, the classifier is **uncertain**; do not present the type as a fact. Either
inspect the page visually or have a person specify the type with `--type Product` (or
`Service`, `Article`, `LocalBusiness`, and so on).

**Step 2. Validate what is already on the page.**
```bash
seohead schema-check --url https://example.com/page
```
These are two different layers: `entities[].errors/warnings` covers the Schema.org
vocabulary (inheritance, deprecated/pending terms, and dangling `@id` references),
while `rich_results[]` covers rich-result eligibility and `missing_required`. `graph`
covers connectivity: islands and `is_graph`.

**Step 3. Compare what the site promises with what its markup declares.** Compare page
facts (`facts`: price, rating, article date, H1, OG, and `sameAs`) with
`existing_jsonld`. Any mismatch is a finding: for example, a price is visible but
`offers` is absent from the JSON-LD, or `datePublished` in the markup does not match
`article:published_time`. `diff_vs_existing.addable_now` lists fields that can be
populated immediately from visible facts.

## What to deliver to the user
1. **Page type**, including confidence and the decision signals (`signals`). When
   confidence is `low`, say honestly: "Uncertain; the closest candidates are X/Y.
   Specify the type manually or verify it."
2. **Verdict on the current markup**: vocabulary errors, deprecated terms, dangling
   `@id` references, graph islands, rich-result eligibility, and `missing_required`.
3. **Recommended `@graph`**—connected and based only on visible facts. Do not add
   properties for information that is absent from the page.
4. **What to add** (`diff_vs_existing.addable_now`) and what is already marked up well.
5. An honest note about **FAQPage/HowTo**: Google no longer provides rich results for
   them, but the markup remains useful for AI content extraction (GEO/AEO).

## Graceful degradation
No network access or the page is unavailable → request the HTML and check it offline:
`--input '{"html": "..."}'`. No JSON-LD blocks → `schema-check.findings` will report
that no blocks were found and show whether other markup is present (`other_markup`).
The classifier found nothing → `inferred_type: WebPage, confidence: low`; this is an
honest result, so do not invent a type.

## Related workflows
Validation core: `schema-check`. Full-audit orchestrator: `seo-deep-audit` (this skill
is its structured-data phase). Decision map for Screaming Frog versus the toolkit:
`sf-boundaries`.

References (load them as needed, not all at once): `reference/page-type-signals.md`
(how the classifier decides) · `reference/graph-templates.md` (`@graph` templates by
type).
