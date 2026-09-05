# Scenario 17 — Title length: characters we count, pixels we only carry

## The question

> Our titles get cut off in Google. Can you give me the list of the ones that are too long —
> and the stubby ones too, while you are at it?

Length has two units. Characters are cheap and this toolkit counts them itself. Pixel width is
what actually decides truncation, and it needs font metrics this toolkit does not have.

## Covers

- **Page Titles** — Over 60 Characters · Below 30 Characters · Over 561 Pixels · Below 200 Pixels

## The chain

**1. Crawl, and get the character lengths for free.**

```bash
seohead crawl-site --url https://example.com --out-dir ./run --max-urls 200
```

`TITLE_TOO_LONG` fires above 60 characters and `TITLE_TOO_SHORT` below 30. Both thresholds are
configuration, not law — the catalogue's numbers happen to be this toolkit's defaults, and a
brand with a long suffix may want its own.

**2. Check the run's arithmetic.**

```bash
seohead log-scan --run ./run
```

**3. Look at one title in full before you trust the count.**

```bash
seohead parse --url https://example.com/page
```

A length is a number; the title is the thing being edited. `parse` returns it whole, beside the
H1, so you can see whether the 74 characters are a useful subtitle or a repeated brand name.

**4. Bring in pixel width — which only a Screaming Frog export can supply.**

```bash
seohead sf run --exports-dir ./exports --out report --tasks
```

`Title 1 Pixel Width` is read from the export and carried into the finding's details. It is
**never computed here**: measuring it needs the font, the weight and the rendering stack Google
uses, and a number invented without those is worse than no number.

Two consequences worth stating out loud in any report built from this chain:

- **Over 561 pixels** participates in `TITLE_TOO_LONG` — the check fires when the character
  count is over its threshold **or** the pixel width is over 561, when a width is present.
- **Below 200 pixels** has no counterpart. There is no minimum-pixel threshold in the
  configuration at all; a short title is caught by its character count, and the pixel column is
  reported as evidence rather than judged.

A native crawl declares that column unmeasured rather than defaulting it to zero, which is why
a pixel-based finding never appears silently:

```
"unmeasured_columns": ["Title 1 Pixel Width", "Meta Description 1 Pixel Width", ...]
```

**5. Hand over the list.**

```bash
seohead report-build --audit ./run/audit.json --format xlsx --out ./title-length.xlsx
```

## What comes out

The shape of a finding, which says which unit tripped it so nobody re-measures by hand:

```json
{
  "check": "TITLE_TOO_LONG",
  "target_url": "https://example.com/services/foundation-repair",
  "details": {"length": 74, "pixel_width": 604, "max_chars": 60}
}
```

`pixel_width` is `null` on any run without an export behind it. That null is the honest answer
and should survive into the deliverable rather than being read as "fine".

## What it costs

One request per page, plus one for the live read in step 3. Pixel width costs a Screaming Frog
licence and an export you already had to make — nothing extra is fetched for it.

## What it cannot answer

- **Whether a title will actually be truncated.** Google rewrites titles, varies the width by
  device, and truncates its own way. 604 pixels is a strong hint, not a verdict.
- **Whether the title is too long for a reason.** A 74-character title carrying a model number
  may be exactly right for the query it serves.
- **Pixel width without an export.** Nothing in a native crawl produces it, and "Below 200
  Pixels" is not evaluated even when the column is present.
- **Whether shortening it helps anything.** No ranking or click-through data is in this loop.
  See the [metadata scenario](metadata.md) for where demand data would have to come from.
