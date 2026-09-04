"""Every interface tool must be able to reach the handler it forwards to.

CI already asserts that each CLI command and MCP tool *registers*. Registration
only proves the decorator ran; it says nothing about whether the body can call
what it calls. seo_crawl_site forwarded a keyword its handler never accepted and
raised TypeError on every invocation for as long as it existed, invisibly,
because nothing ever called it.
"""

from __future__ import annotations

import ast
import inspect
import pathlib

import pytest

from seohead.servers import handlers

ROOT = pathlib.Path(__file__).resolve().parents[1]
MCP_SERVER = ROOT / "seohead" / "servers" / "mcp_server.py"


def _forwarding_calls() -> list[tuple[str, str, set[str]]]:
    """Each (tool, handler, forwarded keywords) triple found in the MCP server.

    Attributed to the innermost enclosing function: the tools are nested inside
    build_server, so walking every function would report each call twice, once
    under the tool and once under its enclosing scope.
    """
    out: list[tuple[str, str, set[str]]] = []

    def visit(node: ast.AST, owner: str) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef):
                visit(child, child.name)
                continue
            if isinstance(child, ast.Call):
                func = child.func
                if (
                    isinstance(func, ast.Attribute)
                    and isinstance(func.value, ast.Name)
                    and func.value.id == "handlers"
                ):
                    out.append((owner, func.attr, {kw.arg for kw in child.keywords if kw.arg}))
            visit(child, owner)

    visit(ast.parse(MCP_SERVER.read_text(encoding="utf-8")), "<module>")
    return out


FORWARDS = _forwarding_calls()


def test_the_scan_found_the_tools():
    # A refactor that moves the calls must fail loudly here rather than make
    # every assertion below vacuously true.
    assert len(FORWARDS) > 30


@pytest.mark.parametrize(
    ("tool", "handler_name", "forwarded"), FORWARDS, ids=[f[0] for f in FORWARDS]
)
def test_forwarded_keywords_exist_on_the_handler(tool, handler_name, forwarded):
    handler = getattr(handlers, handler_name, None)
    assert handler is not None, f"{tool} forwards to handlers.{handler_name}, which does not exist"
    accepted = set(inspect.signature(handler).parameters)
    unexpected = forwarded - accepted
    assert not unexpected, (
        f"{tool} passes {sorted(unexpected)} to handlers.{handler_name}, "
        f"which accepts {sorted(accepted)}"
    )


def test_crawl_site_accepts_every_robots_policy():
    # The boolean this tool used to take could not express report_only, which is
    # why the handler takes a policy instead.
    from seohead.crawl.settings import ROBOTS_POLICIES

    accepted = inspect.signature(handlers.crawl_site).parameters
    assert "robots" in accepted
    assert set(ROBOTS_POLICIES) == {"respect", "report_only", "ignore"}
