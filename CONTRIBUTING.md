# Contributing

Contributions are welcome when they keep the toolkit headless, evidence-first, and safe to call
from both a terminal and an agent.

## Before opening a pull request

1. Open an issue for substantial product-scope changes.
2. Add behavior to the core layer first.
3. Register a public tool in all shared interfaces: handler, CLI, and MCP.
4. Add offline tests, including failure and missing-data cases.
5. Update documentation, tool counts, side-effect descriptions, and provider costs.
6. Confirm that no credential, private URL, client data, crawl binary, raw log, local path, or
   generated report is included.

Run:

```bash
ruff check .
ruff format --check .
pytest -q
seohead sf run --exports-dir examples/exports --out /tmp/seohead-report --tasks
```

## Design rules

- Core modules do not import the CLI or server layer.
- Missing data is not reported as a clean result.
- Provider production mode and paid operations are explicit.
- New network behavior is bounded, polite, and testable without the network.
- New file mutation is opt-in, atomic where possible, and documented.
- A report renderer formats existing evidence; it does not invent new calculations.
- Public prose, code comments, docstrings, and error messages are English.

By submitting a contribution, you agree that it may be distributed under the repository's MIT
licence and that you have the right to contribute it.
