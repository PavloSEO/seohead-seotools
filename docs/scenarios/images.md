# Scenario 24 — Images: from "the site feels slow" to an archive a developer can deploy

## The question

> Are our images costing us anything? And if they are, don't just tell me — give me the fixed
> files.

This is the scenario that separates an analysis from a result. Anyone can report that images
are heavy. The chain below downloads them, re-encodes them, measures the saving per file, and
ends with an archive plus a task that has the real numbers in it.

## Covers

- **Images** — Over 100 kb
- **PageSpeed** — Improve Image Delivery

## The chain

**1. Find every image the site actually serves.** Not the ones in the sitemap — the ones pages
reference, including CSS backgrounds.

```bash
seohead crawl-site --url https://example.com --out-dir ./run --max-urls 200
```

`pages.jsonl` now holds every fetched URL with its content type and its **size in bytes on the
wire**, and `audit.json` holds the findings. The size is measured before the body is decoded;
that is not a detail, it was wrong by 1.72× until recently and made every weight-based
conclusion unusable.

**2. Check the run before trusting it.**

```bash
seohead log-scan --run ./run
```

Exits 0 when the run's numbers agree with each other and 2 when they do not. Twenty seconds
here is cheaper than a client asking why a 700 KB file is listed as 1.3 MB.

**3. Download the images themselves.** A recorded size is a claim; a file on disk is a fact.

```bash
seohead images-download --urls https://example.com/image.png --output-dir ./images
```

In practice the URL list comes from the crawl rather than being typed:

```bash
seohead images-download --input '{"urls": ["https://example.com/image.png"], "output_dir": "./images"}'
```

**4. Re-encode them, and measure what that saved.**

```bash
seohead images-optimize --files ./images --output-dir ./images-optimized --format webp --quality 82
```

The result reports per file: original bytes, new bytes, the saving, and what was done to it.
Sources are never touched unless `--in-place` is passed explicitly, and even then backups are
made — an optimizer that overwrites originals by default is a data-loss bug waiting for its
first bad quality setting.

**5. Turn it into a task somebody can act on.**

```bash
seohead report-build --audit ./run/audit.json --format docx --out ./images-task.docx
```

Then hand over the archive beside it:

```bash
tar -czf images-optimized.tgz -C ./images-optimized .
```

## What comes out

Three artifacts, from a real run of this chain against a live construction-company site:

```
images/                    82 files, 69.7 MB   the originals, as served
images-optimized/          82 files, 27.4 MB   re-encoded, -61%
images-task.docx                               the task, with those numbers in it
```

And a per-file table inside the optimize result:

```json
{
  "file": "gallery-kvarc-vinil-23.webp",
  "original_bytes": 738968,
  "optimized_bytes": 291204,
  "saved_pct": 60.6,
  "action": "re-encoded webp q82"
}
```

That is the whole point of the chain. "Your images are heavy" is an opinion. "These 82 files,
which you can deploy right now, are 42.3 MB lighter" is a job that is already done.

## What it costs

- One request per crawled page, plus one per image downloaded. At the default 200-URL budget
  and a polite rate, minutes rather than hours.
- Re-encoding is CPU-bound and local. Nothing is sent anywhere.
- No paid API is involved at any step.

Set the rate deliberately for the host: a shared-hosting site that answers in 1.2 s will start
refusing TLS handshakes long before it returns an error status, and a crawler that only widens
on non-200 responses will keep pushing. `crawl-site` adapts to latency for this reason, and
`speed.min_delay_seconds` is the floor you choose yourself.

## What it cannot answer

- **Whether the server is configured to serve them well.** This chain finds oversized files and
  fixes the files. It does not fix a missing `Cache-Control`, an absent CDN, or a server that
  never enables compression — use [scenario 7](infrastructure.md) for that.
- **Whether the image is the right image.** Nothing here judges whether a 3000px hero photo
  should exist at all, or whether it is the wrong crop. That is a person's call.
- **Images injected by JavaScript after load.** The crawl reads what the HTML and CSS reference.
  A gallery assembled client-side needs [scenario 4](rendering.md) first.
- **Whether the saving survives deployment.** An archive is not a deploy. If the CMS regenerates
  derivatives on upload, the numbers above describe files the site may never serve.
