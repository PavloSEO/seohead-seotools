# Scenario 25 — Image alt text: missing, empty, and the images no crawler sees

## The question

> Accessibility flagged our images. How many are missing alt text, and are we sure that list is
> all of them?

The second half of that question is the interesting one. An alt-text list built from `<img>`
elements omits every image the page loads through CSS, and those are usually the largest ones on
the page.

## Covers

- **Images** — Missing Alt Text · Missing Alt Attribute · Background Images

## The chain

**1. Know what a native crawl will not tell you, before you run it.**

```bash
seohead crawl-site --url https://example.com --out-dir ./run --max-urls 200
```

The image checks name themselves absent in `run.checks_skipped` rather than reporting zero:

```
{"id": "IMG_MISSING_ALT",        "reason": "missing export: images_missing_alt"}
{"id": "IMG_MISSING_DIMENSIONS", "reason": "missing export: images_missing_size"}
```

Per-image attributes are not part of the record a native crawl builds. Reading that skip as "no
problems" is the single most common way this chain gets misreported.

**2. Get the alt-text list from a Screaming Frog export.**

```bash
seohead sf run --exports-dir ./exports --out report --tasks
```

`IMG_MISSING_ALT` activates when the `Images:Missing Alt Text` filter is present in the export
directory — the loader matches it on the filename token `missing_alt`, so any reasonable export
name works.

**3. Understand what that check does *not* separate.** "Missing alt attribute" and "missing alt
text" are reported **together**. An image with no `alt` at all and an image with `alt=""` land in
the same finding — and the second is often correct, because an empty alt is how a decorative
image is properly marked up. Expect to reclassify part of the list by hand; nothing here can do
it for you.

**4. Find the images that are in no `<img>` element at all.**

```bash
seohead parse --input '{"url": "https://example.com/page", "options": {"url_sources": true}}'
```

`url_sources` collects every URL-bearing carrier beyond `a[href]` — `img[src]`, `srcset`,
`source`, `video[poster]` — and the parser separately extracts `url()` references out of CSS
text. It is deliberately not limited to `background-image`: `border-image`, `list-style-image`,
`mask-image` and `content` all fetch a resource the same way, and a checker that knew only one
property would under-report. On a live site this found four images that were invisible to every
`<img>`-based inventory.

A CSS background has **no alt attribute to be missing**. That is the point: it carries no
accessible name at all, and if it conveys meaning the fix is markup, not an attribute.

**5. Put both lists in one task.**

```bash
seohead report-build --audit ./run/audit.json --format docx --out ./image-alt.docx
```

## What comes out

From `parse`, the shape of the carrier list — each URL with the tag and attribute it was found
on, so a developer knows where to look:

```json
{
  "url_sources": [
    {"url": "https://example.com/img/hero.jpg", "tag": "img", "attr": "src"},
    {"url": "https://example.com/img/panel-bg.jpg", "tag": "style", "attr": "css"},
    {"url": "https://example.com/img/tile.png", "tag": "div", "attr": "style"}
  ]
}
```

`attr: "css"` is a `url()` inside a `<style>` block; `attr: "style"` is one in an element's
inline `style` attribute. Those two values are exactly the set that identifies a background
image, because every other carrier is either an `<img>` or not an image at all.

And the deliverable is two lists with two different fixes: `<img>` elements that need alt text
written, and CSS backgrounds that need to become real images before alt text is even possible.

## What it costs

One request per page for `parse`. The alt-text inventory rides along with a Screaming Frog export
you already made. Nothing paid.

## What it cannot answer

- **Whether an empty alt is correct.** A decorative image with `alt=""` is right and is reported
  alongside images that have no attribute at all. This distinction is not made.
- **Whether the alt text that exists is any good.** "image1.jpg" as alt text passes every check
  here. Alt-text length is not thresholded either.
- **Images injected by JavaScript.** The parse reads served HTML and CSS text. A gallery built
  client-side needs [scenario 4](rendering.md) first.
- **Backgrounds declared in a linked stylesheet.** `parse` reads one document and performs no
  I/O of its own, so `url()` inside inline styles and `<style>` blocks is found and a `.css`
  file is reported as a resource whose contents were never opened.
- **Anything about image weight.** That is a separate chain, and it ends in re-encoded files
  rather than a list — see [scenario 1](images.md).
