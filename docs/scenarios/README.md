# Usage scenarios

The rest of the documentation lists what this toolkit *has*: 49 commands, 54 MCP tools, 118
checks, 22 skills, each described on its own. This directory describes what it **does** — the
chains that run several of them in order and end in something a person can act on.

The distinction matters. One command is a measurement. A chain is a deliverable:

> You will save 61% of your image weight. Here are the 82 files, already re-encoded, in an
> archive. Here is the task, with the numbers in it.

Nobody can assemble that from a list of tool names. Every scenario below is written so that an
agent — or a person — can run it start to finish without inventing the sequence.

## How to read one

Each scenario has the same five parts:

| Part | What it answers |
|---|---|
| **The question** | what somebody actually asked, in their words |
| **The chain** | every command in order, with real flags, and what each one adds |
| **What comes out** | the artifact, with a real excerpt |
| **What it costs** | requests, wall time, whether anything is paid |
| **What it cannot answer** | the limits of this chain, named |

That last part is not modesty. A scenario that does not say what it cannot answer is
marketing, and an agent that trusts it will report a confident wrong answer.

Every command shown in these files is executed against a fixture site by
`tests/test_docs_commands_execute.py` on every CI run. A scenario that stops working fails the
build rather than sitting here misleading its next reader.

## The scenarios

| # | Scenario | Start here when |
|---|---|---|
| 1 | [Images](images.md) | "are our images costing us anything?" |
| 2 | [Metadata and thin pages](metadata.md) | "which pages need writing?" |
| 3 | [Structure and internal links](structure.md) | "is anything unreachable, or buried too deep?" |
| 4 | [Rendering](rendering.md) | "does Google see what a visitor sees?" |
| 5 | [Structured data](structured-data.md) | "why don't we get rich results?" |
| 6 | [Content extraction](content.md) | "how much of this page is actually content?" |
| 7 | [Infrastructure](infrastructure.md) | "what is this site running on, and is it safe?" |
| 8 | [AI visibility](ai-visibility.md) | "will an AI assistant cite us?" |
| 9 | [Comparing two crawls](comparison.md) | "what changed since the release?" |
| 10 | [From audit to deliverable](deliverable.md) | "turn this into something I can hand over" |

## The rule underneath all of them

Run the crawl once; run everything else against what it collected. Every scenario here starts
from one `crawl-site` run and reuses its `audit.json` and `pages.jsonl`, because a second crawl
of the same site to answer a second question is a second load on somebody's server for an
answer that is already on disk.

After any chain, `seohead log-scan --run <dir>` reports whether the run contradicts itself
before you act on its numbers. Every defect this toolkit has had on live sites was an impossible
number that nobody checked, so checking is one command.
