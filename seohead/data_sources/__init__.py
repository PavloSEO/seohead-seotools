"""External demand, SERP, and analytics sources used by SEOHEAD Tools.

Crawls and live checks describe what a website exposes. Search-volume, ranking, and traffic
evidence comes from external providers, so this package keeps one canonical client per provider.
Layer rules:

* **A client does not know who called it.** CLI, MCP, and project orchestration remain outside
  this layer; a client validates a request and returns provider data.
* **Network and quota failures are not process failures.** HTTP 429 and 503 responses use
  backoff. Exhausted retries are represented as errors at the tool boundary instead of
  terminating the process.
* **Secrets come only from files or environment variables.** They never appear in source or
  logs; see :mod:`credentials`.
* **Every paid call is written to the spend log.** See :mod:`spend`; measured provider units are
  safer than informal cost estimates.
* **This layer does not own project state.** Keyword decisions and longitudinal datasets belong
  to the caller, not to an API transport client.
"""

from seohead.data_sources import credentials, spend

__all__ = ["credentials", "spend"]
