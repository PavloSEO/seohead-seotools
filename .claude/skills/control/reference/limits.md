# What this toolkit cannot answer at all

Say these out loud in the deliverable. A limit nobody states is a limit the reader assumes away.

## It measures the site as served, not as ranked

There is no search-engine data in this loop. It cannot tell you what a page ranks for, how much
traffic it gets, whether it is indexed, what a competitor does, or whether a change helped.
Reachability is not indexation; eligibility is not a rich result.

## It measures structure, not quality

Every check is structural. "This page has 800 words in its content region" is measurable;
"this page is worth reading" is not, and nothing here should be read as claiming it. E-E-A-T,
usefulness, tone and accuracy are a person's judgement.

## Lab numbers, not field data

`render-check` reports timings from one headless browser on one machine and one connection.
They are useful for comparing two pages measured the same way. They are not Core Web Vitals as
Google collects them.

## One host, unless told otherwise

Off-host links are recorded and never fetched; a redirect that leaves the host is recorded and
never followed. That is deliberate — a crawler that wanders onto other people's servers is a
crawler nobody should run — but it means nothing here describes a second hostname, a CDN
domain, or a satellite site unless you point it there explicitly.

## Static markup, unless rendering ran

A crawl reports what the HTML and CSS contain. Content, links and directives that exist only
after JavaScript are absent unless rendering was escalated for that pattern, and
`pages_by_representation` says which pages were measured which way.

## It cannot fix a server

An archive of optimized images is not a deploy. A security grade is not a hardened server. A
redirect map is not a redirect. Every deliverable here ends at the point where somebody with
access has to act.

## It does not know what matters

Severity is not priority. The tool has no traffic data, no revenue data and no knowledge of
which page the business cares about. Ordering findings by importance is the one part of this
that has to stay human.
