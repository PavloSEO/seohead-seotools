# Audit Tasks — example.com

- Source: audit generated at 2026-06-21T17:39:00Z (health 25)
- Tasks: **15** (P1: 3, P2: 8, P3: 4)

## P1 (3)

- [ ] **Internal link points to a 4xx URL — 1 page** `BROKEN_INTERNAL_LINK` · critical · effort: high · `TASK-92174247`
    - _How to fix:_ Replace the link with the current URL or add a 301 redirect. If the link appears in the footer or navigation, update the shared template.
    - Broken links (destination ← source · position · XPath):
        - https://example.com/old-page (404) ← https://example.com/ · Content · `/html/body/main/article/p[3]/a`
        - https://example.com/old-page (404) ← https://example.com/page-a · Footer · `/html/body/footer/nav/a[2]`

- [ ] **Page returns a 4xx status — 1 page** `BROKEN_PAGE_4XX` · critical · effort: high · `TASK-54ad8503`
    - _How to fix:_ Restore the page or redirect it to a relevant URL with a 301 response; remove links that still point to the broken URL.
        - https://example.com/old-page

- [ ] **Title is missing — 1 page** `TITLE_MISSING` · critical · effort: high · `TASK-c5d3ee4f`
    - _How to fix:_ Add a unique, descriptive title.
        - https://example.com/no-title

## P2 (8)

- [ ] **Duplicate meta description — 2 pages** `DESC_DUPLICATE` · warning · effort: medium · `TASK-45424e37`
    - _How to fix:_ Write a unique description for each page.
        - https://example.com/
        - https://example.com/page-b

- [ ] **Duplicate title — 2 pages** `TITLE_DUPLICATE` · warning · effort: medium · `TASK-54b0732a`
    - _How to fix:_ Write a unique title for each page.
        - https://example.com/page-a
        - https://example.com/page-b

- [ ] **Indexable page has no canonical URL — 1 page** `CANONICAL_MISSING` · warning · effort: medium · `TASK-64efab10`
    - _How to fix:_ Add a `<link rel="canonical">` element.
        - https://example.com/no-title

- [ ] **Meta description is missing — 1 page** `DESC_MISSING` · warning · effort: medium · `TASK-aa336983`
    - _How to fix:_ Add a description of up to approximately 160 characters.
        - https://example.com/no-title

- [ ] **Multiple H1 elements on one page — 1 page** `H1_MULTIPLE` · warning · effort: medium · `TASK-d54d97a7`
    - _How to fix:_ Keep one H1 and change the remaining top-level headings to H2 or H3.
        - https://example.com/page-a

- [ ] **Oversized HTML in absolute or relative terms — 1 page** `LARGE_HTML` · warning · effort: medium · `TASK-9e27800e`
    - _How to fix:_ Reduce HTML size by moving inline styles and scripts, removing base64 payloads, and simplifying redundant markup.
        - https://example.com/no-title

- [ ] **Slow server response — 1 page** `SLOW_RESPONSE` · warning · effort: medium · `TASK-9bda9060`
    - _How to fix:_ Improve TTFB by optimizing the server and cache configuration.
        - https://example.com/no-title

- [ ] **Thin content (low word count) — 1 page** `THIN_CONTENT` · warning · effort: medium · `TASK-5c3d9251`
    - _How to fix:_ Expand the content or exclude the page from indexing.
        - https://example.com/page-b

## P3 (4)

- [ ] **Title is below the length threshold — 2 pages** `TITLE_TOO_SHORT` · notice · effort: low · `TASK-f4d7444c`
    - _How to fix:_ Expand the title to an informative length.
        - https://example.com/page-a
        - https://example.com/page-b

- [ ] **Meta description is below the length threshold — 1 page** `DESC_TOO_SHORT` · notice · effort: low · `TASK-6c37199b`
    - _How to fix:_ Expand the description.
        - https://example.com/page-a

- [ ] **Bloated HTML: high byte count with little text — 1 page** `HTML_BLOAT` · notice · effort: low · `TASK-69aebead`
    - _How to fix:_ Reduce bytes per word by moving styles and scripts out of the HTML and removing base64 payloads.
        - https://example.com/page-b

- [ ] **Low text-to-HTML ratio — 1 page** `LOW_TEXT_RATIO` · notice · effort: low · `TASK-b37fa823`
    - _How to fix:_ Increase the proportion of meaningful text content.
        - https://example.com/page-b
