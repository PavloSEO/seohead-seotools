# Scenario 8 — AI visibility: will an assistant cite this site

## The question

> People ask ChatGPT instead of Google now. Are we even readable to it?

## The chain

**1. Which AI crawlers are allowed in at all.**

```bash
seohead ai-bots-check --url https://example.com
```

GPTBot, ClaudeBot, PerplexityBot, Google-Extended and the rest, read from the site's own
robots.txt. A blanket `Disallow: /` for an unfamiliar user-agent is usually nobody's decision —
it is a default that was never revisited.

**2. Whether there is anything written for a model to read.**

```bash
seohead llms-txt-check --url https://example.com --brand Example
```

Reports whether `/llms.txt` exists, whether it is well-formed, and whether it actually names
the brand and points at pages worth reading — an llms.txt that lists a sitemap and nothing else
is a file, not an answer.

**3. Whether the content is in a shape a model can quote.**

```bash
seohead citability-check --url https://example.com/page
```

A citable page answers a question in a paragraph a model can restate with a link. A page whose
answer is spread across a carousel, a table image and three collapsibles is not quotable, no
matter how correct it is.

**4. Whether the answer survives without JavaScript.** AI crawlers almost never render. What
[scenario 4](rendering.md) reports as "JS-dependent" is, for this audience, "absent".

## What comes out

```json
{
  "ai_bots": {"GPTBot": "allowed", "ClaudeBot": "allowed", "Google-Extended": "disallowed"},
  "llms_txt": {"present": true, "mentions_brand": true, "entries": 14},
  "citability": {"score": "partial", "reason": "answer split across collapsibles"}
}
```

## What it costs

Three requests. Nothing paid.

## What it cannot answer

- **Whether an assistant will actually cite you.** No public API reports that. This measures
  whether you are readable and quotable, which is the part you control.
- **What any model was trained on.** Nothing here can see a training corpus.
- **Whether being crawled is good for you.** Allowing `GPTBot` is a business decision about
  your content, not a technical default this tool should push you toward.
