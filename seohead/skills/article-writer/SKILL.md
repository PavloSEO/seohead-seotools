---
name: article-writer
description: >
  Write expert bilingual articles (RU+EN) in JSON format for a blog.
  Always use this skill when asked to write an article, create expert material,
  write a guide or review, prepare a blog post, generate researched content
  with sources, write an article with code examples or case studies,
  generate bilingual article JSON, or conduct research before writing.
  The skill covers the complete workflow: research → plan → write RU+EN → valid JSON.
  The final output is always JSON. It works for any topic or industry.
  Triggers: "write an article," "create a post," "write a guide," "prepare a piece,"
  "article JSON," "blog article," "bilingual article," and "write with examples."
---

# Article Writer — Expert Bilingual Articles

**Workflow:** Research → Plan (optional) → Write RU+EN → JSON output

---

## Step 0 — Gather Context

If the request lacks essential information, ask **one clarifying question** before starting, and no more than one:

| Information needed | How to obtain it |
|---|---|
| Article topic | Extract it from the request or ask |
| Author | Use author details supplied by the user or project; otherwise keep the neutral configurable author placeholders |
| Starting format | Ask: "Would you like to review the outline first, or should I start writing immediately?" |
| Tag/category | Infer it from the topic or ask |
| relatedSlugs | Suggest relevant entries and let the user revise them |

---

## Step 1 — Research (Required)

**Always** conduct research before writing. Use **every available source of evidence**:

### 1A — Web Search
- Find 3–5 authoritative sources on the topic, such as official documentation, MDN, Google, W3C, research papers, or industry reports
- Find current statistics with dates and sources
- Verify that technical details are current, including APIs, versions, and changes
- Find real case studies and examples

### 1B — Model Knowledge
- Apply relevant subject-matter knowledge
- Apply best practices and established patterns
- Account for technical details and nuances

### 1C — Operator/Author Knowledge
- Use all context provided about the author's experience, case studies, and opinions
- Highlight the author's position when one is available

### Research Output (Internal; Do Not Show the User)
```
- Topic: [topic]
- Key sources: [list with URLs]
- Key facts: [3–7 verifiable claims with sources]
- Statistics: [specific figures + year + source]
- Examples: [real case studies]
- SEO angle: [keyword and intent]
```

---

## Step 2 — Outline (If the User Selected It)

If the user wants to review an outline first, show it and **wait for confirmation** before writing.

Outline format:
```
## [Article title]

**Tag:** [tag]  **readTime:** ~N min  **Keyword:** [keyword]

### Structure:
1. Intro — [what it resolves]
2. H2: [section] — [what it contains and which blocks it uses]
3. H2: [section] — ...
...
N. Outro + CTA

### Sources to include:
- [URL 1] — for section N
- [URL 2] — for section M

Proceed with writing? (yes / revisions: ...)
```

---

## Step 3 — Write

### Quality Principles

**Expertise:**
- Support every factual claim with a source, either through a link or source attribution
- Use specific figures instead of vague claims such as "many companies"
- Include the author's position where appropriate
- Cover nuances and edge cases that demonstrate genuine expertise

**Structure:**
- H1 = primary keyword + value proposition, generated in `titleRu`/`titleEn`
- The first paragraph answers the question immediately; do not open with "In this article, we will discuss..."
- Make every H2 section self-contained
- Include an FAQ section at the end; this is useful for GEO and AI-generated answers
- End with a CTA

**Links:**
- External links: add them in a `p` block using Markdown syntax: `[text](URL)`
- Documentation: always use current official documentation found during research
- Internal links: provide them through `relatedSlugs` in `meta`

**Examples:**
- Code must be real, functional, and commented
- Case studies must be specific: company / product / result
- Use analogies for complex concepts

---

## Step 4 — Generate JSON

### Complete Schema

```json
{
  "slug": "kebab-case-slug",
  "meta": {
    "tag": "Russian-language tag",
    "tagEn": "English-language tag",
    "date": "DD.MM.YYYY",
    "readTime": "N минут чтения",
    "readTimeEn": "N min read",
    "rating": 4.8,
    "titleRu": "Russian title — keyword first, under 60 characters",
    "titleEn": "English title — keyword first, under 60 characters",
    "leadRu": "Russian meta description — keyword + value + CTA, 150–160 characters.",
    "leadEn": "English meta description — keyword + value + CTA, 150–160 characters.",
    "authorInitials": "<AUTHOR_INITIALS>",
    "authorNameRu": "<AUTHOR_NAME_RU>",
    "authorNameEn": "<AUTHOR_NAME_EN>",
    "authorRole": "<AUTHOR_ROLE>",
    "authorBioRu": "<AUTHOR_BIO_RU>",
    "authorBioEn": "<AUTHOR_BIO_EN>",
    "relatedSlugs": ["slug-1", "slug-2"]
  },
  "ru": {
    "toc": [
      { "id": "anchor-id", "label": "Russian-language section name" }
    ],
    "blocks": []
  },
  "en": {
    "toc": [
      { "id": "anchor-id", "label": "English-language section name" }
    ],
    "blocks": []
  }
}
```

### Calculate readTime
- Count the words in `blocks` for each locale
- RU: words ÷ 180, rounded up to whole minutes
- EN: words ÷ 200, rounded up to whole minutes
- Format: `"5 минут чтения"` / `"5 min read"`

### rating
- Do not generate it independently
- Default to `4.8` from the guide unless otherwise specified

---

## Block Types

### Text

```json
{ "type": "h2", "id": "section-id", "text": "Section heading" }
{ "type": "h3", "id": "subsection-id", "text": "Subheading" }
{ "type": "p", "text": "Text. Supports **bold** and [links](https://example.com)." }
{ "type": "blockquote", "text": "Quotation from an expert or source." }
```

### Lists

```json
{ "type": "ul", "items": ["Item 1", "Item 2", "Item 3"] }
{ "type": "ol", "items": ["Step 1", "Step 2", "Step 3"] }
```

### Callout

```json
{
  "type": "callout",
  "variant": "info",
  "text": "An important note for the reader."
}
```

Supported `variant` values: `info` | `warning` | `success` | `error`

### Code

```json
{
  "type": "code",
  "language": "javascript",
  "code": "// app.ts\nconst result = await fetch(url);\nconsole.log(result);"
}
```

- `language` is optional (js, ts, python, bash, json, css, html, sql, ...)
- Put the file name on the first line as a comment (`// filename.ts`, `# filename.py`)

### Table (Extended Type)

```json
{
  "type": "table",
  "headers": ["Parameter", "Value", "Description"],
  "rows": [
    ["param_1", "string", "Object name"],
    ["param_2", "number", "Size in bytes"]
  ]
}
```

> ⚠️ If the renderer does not support `table`, replace it with `h3` + `ul` using the format "Parameter — Value: Description."

### Timeline (Extended Type)

```json
{
  "type": "timeline",
  "items": [
    { "label": "2020", "text": "First release. Description of the event." },
    { "label": "2022", "text": "Major upgrade. Summary of what changed." },
    { "label": "2024", "text": "Current state." }
  ]
}
```

> ⚠️ If the renderer does not support `timeline`, replace it with `ol` whose items use the format `"**2020** — First release. Description."`.

### FAQ

```json
{
  "type": "faq",
  "items": [
    { "q": "Question?", "a": "Clear answer." },
    { "q": "Another question?", "a": "Another answer." }
  ]
}
```

> Always include an FAQ at the end of the article; it is important for GEO and AI-generated answers.

---

## JSON Quality Rules

1. **slug** — use concise kebab-case with no Cyrillic characters, ideally 3–5 words
2. **id** in h2/h3 blocks — use the same kebab-case style; the value is used in the TOC
3. **TOC** — include only h2 blocks; omit h3 blocks unless otherwise specified
4. **p blocks** — avoid unnecessary line breaks; one `p` equals one semantic paragraph
5. **Links** — include only links that actually exist and were verified during research
6. **RU and EN** — generate them together; adapt each version to its audience instead of translating literally
7. **Do not invent** slugs for `relatedSlugs`; use only real slugs, or explicitly mark uncertain ones with `"?"`
8. **callout** — use no more than 1–2 per section and do not overuse them
9. **Code** — include only functional, verified, commented code

---

## Example of a Minimal Article Structure

```
intro (p, p)
├── h2: What it is and why it matters (p, callout:info, ul)
├── h2: How it works (p, h3, p, code, p)
├── h2: Real example (p, code, callout:success, p)
├── h2: Common mistakes (p, ol, callout:warning)
├── h2: Comparison of options (table or ul)
├── h2: FAQ (faq)
└── outro (p, callout:info with links/CTA)
```

---

## Related Skills

- Need SEO keyword research → **seo-research**
- Need Schema or metadata markup → **seo-markup**
- Need to audit a completed page → **seo-audit-page**
- Need a content quality review → **seo-content** (Section 3 — E-E-A-T)

> This skill is self-contained. Use a related skill only when the request requires deeper work in that specific area.
