---
name: geo-aeo-audit
description: >-
  Audits website visibility in the age of AI-generated answers (GEO/AEO): which AI
  crawlers robots.txt allows (GPTBot, ClaudeBot, Perplexity, Google-Extended…), whether
  /llms.txt exists and how useful it is to models, and how citable the content is
  (answers that an AI is ready to restate with a link). Triggers on: “AI search,”
  “visibility in ChatGPT,” “GEO audit,” “AEO,” “llms.txt,” “AI crawlers,” “GPTBot
  blocking,” “citability,” “answer engine optimization,” “AI visibility,” “LLM SEO,”
  and “will the website appear in an AI answer.”
---

# GEO / AEO Audit — Website Visibility in AI Answers

Classic SEO concerns search results. GEO/AEO concerns whether a website appears in an
answer when a user asks ChatGPT, Perplexity, or Gemini, and whether the AI provides a link.
There are three levers:

1. **AI crawler access** — which crawlers robots.txt allows or blocks, intentionally or accidentally.
2. **llms.txt** — whether the website has a manifest for models and how useful it is.
3. **Content citability** — whether the content is written so that an AI can answer with a link.

## When to Use It
- A website is losing traffic from conventional search and wants a channel from AI answers.
- To check whether GPTBot was blocked accidentally.
- To launch llms.txt as a new entry point for models.

## Workflow

**Step 1. AI crawler access.** One command reports the status of 18+ known bots:
```bash
seohead ai-bots-check --url https://example.com
```
Read ``summary.by_type``: ``training`` (model training — Google-Extended, CCBot,
Bytespider), ``retrieval`` (answer retrieval — PerplexityBot, Claude-Web), and ``user``
(a request on behalf of a user — ChatGPT-User). The usual decision is to **allow
retrieval** for visibility in answers and make a considered choice about **training**
because providing data for training may be undesirable. Bots with ``status:
allowed_default`` were neither explicitly allowed nor explicitly blocked by the website;
they are allowed by default unless a general ``Disallow`` rule applies.

**Step 2. llms.txt.**
```bash
seohead llms-txt-check --url https://example.com --brand "SiteName"
```
There are 9 checkpoints: an H1, ≥3 sections, ≥3 links, a brand/category mention,
product/proof/docs pages, and a size of ≤60 KB. The result is a 0–10 score plus a letter
grade. A missing file produces ``ok: False`` and the finding “the website does not provide
AI with ready-to-use context.” ``--brand`` checks whether the brand name is mentioned.

**Step 3. Content citability.** The formal scorer uses 4 dimensions worth 25 points each:
```bash
seohead citability-check --url https://example.com/page       # use the page text
seohead citability-check --input '{"text":"...excerpt..."}'   # analyze an excerpt offline
```
The dimensions are **answer blocks** (self-contained paragraphs of 20–200 words that do
not begin with context-dependent language), **self-containment** (no phrases such as “as
mentioned above” that make an extracted passage meaningless), **statistical density**
(numbers, percentages, and dates plus evidence markers per 100 words), and **structure
quality** (headings, lists, TL;DR, and paragraph length). The result is a 0–100 score plus
a letter grade.

## What to Deliver to the User
1. **Access by type**: which retrieval bots are blocked, causing a loss of visibility in
   their answers, and which training bots are allowed, which may be undesirable.
2. **llms.txt**: the score and checkpoints, specific gaps such as “no proof section” or
   “no link to docs,” and an example of a better structure.
3. **Citability**: 2–3 page templates, scored by characteristic and accompanied by
   recommendations.
4. **Competitor delta**, if requested: which competitors already have llms.txt and which
   allow retrieval bots.

## Graceful Degradation
If robots.txt cannot be retrieved, ``ai-bots-check`` returns an error; do not crash. A
missing llms.txt is a finding (``ok: False``), not a failure. ``robots_text`` can be
provided offline through ``--input``.

## Integrations
`robots-check` is the source of robots rules. `schema-graph` covers the content side,
including FAQ/HowTo markup for AI. In a full audit, this skill is a separate block in the
`seo-deep-audit` orchestrator.
