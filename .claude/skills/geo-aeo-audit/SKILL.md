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

## Trigger
- A website is losing traffic from conventional search and wants a channel from AI answers.
- To check whether GPTBot was blocked accidentally.
- To launch llms.txt as a new entry point for models.
- The request is phrased as: "AI search," "visibility in ChatGPT," "GEO audit," "AEO," "llms.txt,"
  "AI crawlers," "GPTBot blocking," "citability," "answer engine optimization," "AI visibility,"
  "LLM SEO," or "will the website appear in an AI answer."

## Anti-trigger
- The ask is about classic Google/Yandex organic ranking rather than AI-answer visibility — use
  the standard `seo-audit-page`/`sf-analyzer` path; GEO/AEO signals (llms.txt, citability) do not
  substitute for on-page/technical SEO.
- The ask is to actually author or rewrite content for citability rather than audit existing
  content — this skill scores and flags gaps, it does not generate the answer-block copy itself.
- `robots.txt` is unreachable or absent and no offline `robots_text` can be supplied —
  `ai-bots-check` needs at least one of those; note the gap rather than guessing bot access.
- The question is about schema-markup coverage in general, not the FAQ/HowTo-for-AI angle — that
  is `schema-graph`/`schema-check`'s job; this skill only touches the AI-citability side of content.

## Preconditions
- [ ] A live, reachable `robots.txt` for the domain, or an offline `robots_text`/`--input` payload
  to feed `ai-bots-check`.
- [ ] For `llms-txt-check`, the brand name to check for (`--brand`) is known.
- [ ] For `citability-check`, either a live page URL or a text excerpt is available for each of
  2–3 representative page templates chosen in advance, not just the homepage.

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
There are 9 checkpoints: a non-empty H1, ≥3 sections, ≥3 links, a brand/category mention,
product/proof/docs pages, and a size of ≤60 KB. The result is a 0–10 score plus a letter
grade. A missing file produces ``ok: True, exists: False`` and the finding “the website does
not provide AI with ready-to-use context.” ``--brand`` checks whether the brand name is mentioned.

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

## Decision points
- **A bot has `status: allowed_default`.** This means it was never explicitly mentioned in
  robots.txt, not that it was deliberately allowed — check whether that is the intended posture
  (usually fine) or an oversight (a blanket `Disallow: /` above it would make it blocked anyway)
  before reporting it as "allowed."
- **Retrieval vs training bot classification.** The default recommendation is allow-retrieval,
  weigh-training-carefully — but confirm the user's actual stance (some sites want zero AI-training
  exposure even at the cost of retrieval visibility) rather than applying the default silently.
- **llms.txt scores well but citability scores poorly, or vice versa.** These measure different
  things (a manifest for models vs the actual page prose) — do not let a good llms.txt score mask
  pages that are not self-contained/citable, and do not let poor citability imply llms.txt is
  useless.
- **Missing llms.txt.** This is a measured finding (`ok: True, exists: False`), not a hard failure — weigh whether it is
  worth recommending given the site's actual GEO ambitions (a small local-business site may not
  need one) rather than treating it as universally mandatory.

## Definition of done
- [ ] `ai-bots-check` results are broken out `by_type` (training/retrieval/user), not reported as
  one flat allow/block list.
- [ ] `llms-txt-check` results state `exists`, score and grade; an existing manifest also names
  each failed checkpoint.
- [ ] `citability-check` was run on 2–3 representative templates, each with its own score and
  per-dimension breakdown.
- [ ] Every recommendation states which of the three levers (crawler access / llms.txt /
  citability) it addresses.
- [ ] If a competitor delta was requested, it is included; if not requested, its absence is not
  treated as incomplete.

## Cost
Three lightweight local-tool calls per target: one `ai-bots-check` (single robots.txt fetch), one
`llms-txt-check` (single file fetch), and one `citability-check` per page template (2–3 calls,
live fetch or offline text) — roughly 4–6 requests total for a single-domain pass, sub-second to a
few seconds each, no paid API involved.

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
missing llms.txt is a measured finding (``ok: True, exists: False``), not a failure.
An HTTP error means it was not measured. ``robots_text`` can be
provided offline through ``--input``.

## Integrations
`robots-check` is the source of robots rules. `schema-graph` covers the content side,
including FAQ/HowTo markup for AI. In a full audit, this skill is a separate block in the
`seo-deep-audit` orchestrator.
