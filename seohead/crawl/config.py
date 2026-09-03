"""Crawler configuration: defaults, precedence, validation, and the run manifest.

Three properties matter more than the field list.

**A setting that nothing reads is a lie.** Every key here is wired to behaviour.
Unknown keys are rejected with their path rather than ignored, so a typo in a
scope pattern cannot silently widen a crawl and a setting cannot be added to the
file before it is added to the code.

**Store and crawl are different questions.** For each link type, "keep it in the
report" and "request it for a status code" are independent. Collapsing them into
one flag is why a crawler either misses broken images or triples its requests.

**Two thirds of these settings change what the audit finds.** Those are recorded
in the run manifest, because otherwise two reports on the same site are not
comparable and nobody can tell why they differ. The rest change only how long the
run takes. ``RESULTS_AFFECTING`` is that classification, and a test fails when a
new setting is added without being placed in one group or the other.
"""

from __future__ import annotations

import copy
import json
import os
from typing import Any

DEFAULTS: dict[str, Any] = {
    "scope": {
        # Which discovered URLs count as internal. "host" is the conservative
        # reading; "registrable_domain" also accepts subdomains.
        "internal": "host",  # host | registrable_domain
        "include_patterns": [],
        "exclude_patterns": [],
        # Never fetched regardless of what links to them.
        "exclude_hosts": [],
    },
    "discovery": {
        # Each link type is a pair: store it in the report, and/or request it.
        "hyperlinks": {"store": True, "crawl": True},
        "canonicals": {"store": True, "crawl": False},
        "redirects": {"store": True, "crawl": True},
        "external": {"store": True, "crawl": False},
        "follow_nofollow": False,
    },
    "limits": {
        "max_urls": 200,
        "max_depth": 5,
        "max_query_variants_per_path": 5,
        "max_response_bytes": 5 * 1024 * 1024,
        "max_url_length": 2000,
        "max_crawl_seconds": 0,  # 0 = no wall-clock limit
    },
    "http": {
        "timeout_seconds": 15.0,
        "user_agent": "",  # empty = the toolkit's identifiable default
        "headers": {},
        "retry_on_timeout": 0,
    },
    "robots": {
        # respect: obey. report_only: fetch, report what would be blocked, crawl
        # anyway — the honest audit setting. ignore: do not fetch it at all.
        "policy": "respect",  # respect | report_only | ignore
        "user_agent_token": "SEOHEAD-Tools",
        "unavailable_means_stop": True,
    },
    "speed": {
        "min_delay_seconds": 0.5,
        "max_delay_seconds": 60.0,
        "adaptive": True,
        "stop_after_consecutive_timeouts": 5,
    },
    "output": {
        "dir": "",
        "write_pages_jsonl": True,
    },
}

# Settings that can change what the audit finds. These go into the manifest.
# Everything else changes only duration or resource use.
RESULTS_AFFECTING: frozenset[str] = frozenset(
    {
        "scope.internal",
        "scope.include_patterns",
        "scope.exclude_patterns",
        "scope.exclude_hosts",
        "discovery.hyperlinks.store",
        "discovery.hyperlinks.crawl",
        "discovery.canonicals.store",
        "discovery.canonicals.crawl",
        "discovery.redirects.store",
        "discovery.redirects.crawl",
        "discovery.external.store",
        "discovery.external.crawl",
        "discovery.follow_nofollow",
        # Every limit truncates the corpus, and a truncated crawl produces false
        # "not linked from anywhere" conclusions.
        "limits.max_urls",
        "limits.max_depth",
        "limits.max_query_variants_per_path",
        "limits.max_response_bytes",
        "limits.max_url_length",
        "limits.max_crawl_seconds",
        # A short timeout turns slow pages into "no response"; the user agent and
        # headers change what a UA- or locale-adaptive site serves.
        "http.timeout_seconds",
        "http.user_agent",
        "http.headers",
        "http.retry_on_timeout",
        "robots.policy",
        "robots.user_agent_token",
        "robots.unavailable_means_stop",
        # Politeness is normally cost-only, but a delay low enough to degrade a
        # server turns healthy pages into timeouts, and the audit then measures
        # the crawler rather than the site.
        "speed.min_delay_seconds",
        "speed.adaptive",
        "speed.stop_after_consecutive_timeouts",
    }
)

# Environment overrides, applied between the file and explicit arguments.
ENV_OVERRIDES: dict[str, str] = {
    "SEOHEAD_CRAWL_MAX_URLS": "limits.max_urls",
    "SEOHEAD_CRAWL_MAX_DEPTH": "limits.max_depth",
    "SEOHEAD_CRAWL_MIN_DELAY": "speed.min_delay_seconds",
    "SEOHEAD_CRAWL_ROBOTS": "robots.policy",
    "SEOHEAD_CRAWL_USER_AGENT": "http.user_agent",
}

ROBOTS_POLICIES = ("respect", "report_only", "ignore")
INTERNAL_SCOPES = ("host", "registrable_domain")


class ConfigError(ValueError):
    """A configuration that cannot be trusted to mean what it says."""


def _flatten(mapping: dict[str, Any], prefix: str = "") -> dict[str, Any]:
    """Dotted paths to leaf values. Free-form maps are leaves, not branches."""
    out: dict[str, Any] = {}
    for key, value in mapping.items():
        path = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict) and path not in ("http.headers",):
            out.update(_flatten(value, path))
        else:
            out[path] = value
    return out


def _set_path(mapping: dict[str, Any], path: str, value: Any) -> None:
    parts = path.split(".")
    node = mapping
    for part in parts[:-1]:
        node = node.setdefault(part, {})
    node[parts[-1]] = value


def _coerce(path: str, raw: str) -> Any:
    """Environment values arrive as strings; give them the default's type."""
    current = _flatten(DEFAULTS).get(path)
    if isinstance(current, bool):
        return raw.strip().lower() in ("1", "true", "yes", "on")
    if isinstance(current, int) and not isinstance(current, bool):
        return int(raw)
    if isinstance(current, float):
        return float(raw)
    return raw


def _merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    out = copy.deepcopy(base)
    for key, value in overlay.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _merge(out[key], value)
        else:
            out[key] = value
    return out


def validate(config: dict[str, Any]) -> None:
    """Reject anything that cannot be honoured, naming the offending path."""
    known = set(_flatten(DEFAULTS))
    for path in _flatten(config):
        if path not in known:
            raise ConfigError(
                f"unknown setting {path!r}. A setting the crawler does not read would "
                "promise behaviour that does not exist"
            )

    robots = config["robots"]["policy"]
    if robots not in ROBOTS_POLICIES:
        raise ConfigError(f"robots.policy must be one of {ROBOTS_POLICIES}, got {robots!r}")
    scope = config["scope"]["internal"]
    if scope not in INTERNAL_SCOPES:
        raise ConfigError(f"scope.internal must be one of {INTERNAL_SCOPES}, got {scope!r}")

    limits = config["limits"]
    if limits["max_urls"] < 1:
        raise ConfigError("limits.max_urls must be at least 1")
    if limits["max_depth"] < 0:
        raise ConfigError("limits.max_depth cannot be negative")
    if config["speed"]["min_delay_seconds"] < 0:
        raise ConfigError("speed.min_delay_seconds cannot be negative")

    # A crawl with no budget at all runs forever on an infinite URL space.
    if not limits["max_urls"] and not limits["max_depth"] and not limits["max_crawl_seconds"]:
        raise ConfigError(
            "a crawl needs at least one budget: max_urls, max_depth or max_crawl_seconds"
        )


def load(path: str | None = None, overrides: dict[str, Any] | None = None) -> dict[str, Any]:
    """Resolve the configuration: defaults, then file, then environment, then arguments.

    The order is fixed and tested. Explicit arguments win because they are the
    most local statement of intent.
    """
    config = copy.deepcopy(DEFAULTS)

    if path:
        try:
            with open(path, encoding="utf-8") as handle:
                from_file = json.load(handle)
        except OSError as exc:
            raise ConfigError(f"cannot read config {path!r}: {exc}") from exc
        except ValueError as exc:
            raise ConfigError(f"config {path!r} is not valid JSON: {exc}") from exc
        if not isinstance(from_file, dict):
            raise ConfigError(f"config {path!r} must contain an object")
        config = _merge(config, from_file)

    for variable, setting in ENV_OVERRIDES.items():
        raw = os.environ.get(variable)
        if raw is not None and raw != "":
            try:
                _set_path(config, setting, _coerce(setting, raw))
            except ValueError as exc:
                raise ConfigError(f"{variable}={raw!r} is not valid for {setting}: {exc}") from exc

    for setting, value in (overrides or {}).items():
        if value is not None:
            _set_path(config, setting, value)

    validate(config)
    return config


def manifest(config: dict[str, Any]) -> dict[str, Any]:
    """The resolved values of every setting that can change what was found.

    Resolved values, not their sources: a report that says "the default was used"
    is not reproducible once the default moves.
    """
    flat = _flatten(config)
    return {path: flat[path] for path in sorted(RESULTS_AFFECTING) if path in flat}


def effective_request_rate(config: dict[str, Any]) -> float:
    """Worst-case requests per second this configuration permits.

    Politeness is a combination, not a single knob, so the number worth printing
    and gating on is this one rather than any individual setting.
    """
    delay = float(config["speed"]["min_delay_seconds"])
    return 1.0 / delay if delay > 0 else float("inf")
