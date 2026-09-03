"""MCP server integration test over real stdio.

Skipped automatically when the optional ``mcp`` SDK isn't installed.
"""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import sys

import pytest

pytest.importorskip("mcp")

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from seohead.servers.mcp_server import build_server

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIXTURES = os.path.join(ROOT, "tests", "fixtures")


def test_all_mcp_tools_have_structured_schemas_and_safety_annotations():
    """Keep MCP clients informed about output shape, side effects, and network use."""
    tools = {tool.name: tool for tool in build_server()._tool_manager.list_tools()}

    assert len(tools) == 48
    assert all(tool.fn_metadata.output_schema for tool in tools.values())
    assert all(tool.annotations is not None for tool in tools.values())

    optimizer = tools["seo_images_optimize"].annotations
    assert optimizer.destructiveHint is True
    assert optimizer.readOnlyHint is False
    assert optimizer.openWorldHint is False

    live_fetch = tools["seo_parse"].annotations
    assert live_fetch.readOnlyHint is True
    assert live_fetch.openWorldHint is True

    paid = tools["seo_google_keywords"].annotations
    assert paid.readOnlyHint is False
    assert paid.openWorldHint is True

    local_report = tools["seo_spend_report"].annotations
    assert local_report.readOnlyHint is True
    assert local_report.openWorldHint is False

    crawl = tools["sf_audit_run"].annotations
    assert crawl.readOnlyHint is False
    assert crawl.destructiveHint is False
    assert crawl.openWorldHint is True


def _payload(r):
    sc = getattr(r, "structuredContent", None)
    if isinstance(sc, dict):
        return sc["result"] if set(sc.keys()) == {"result"} else sc
    return json.loads(r.content[0].text)


async def _drive(exports_dir: str, out_dir: str) -> dict:
    params = StdioServerParameters(
        command=sys.executable, args=["-m", "seohead.servers.mcp_server"], cwd=ROOT
    )
    async with (
        stdio_client(params) as (read, write),
        ClientSession(read, write) as session,
    ):
        await session.initialize()
        tools = {t.name for t in (await session.list_tools()).tools}

        le = _payload(await session.call_tool("sf_list_exports", {"exports_dir": exports_dir}))
        run = _payload(
            await session.call_tool(
                "sf_audit_run",
                {"mode": "parse-exports", "input": exports_dir, "out": out_dir},
            )
        )
        summ = _payload(
            await session.call_tool("sf_audit_summary", {"json_path": run["json_path"]})
        )
        issues = _payload(
            await session.call_tool(
                "sf_audit_issues",
                {"json_path": run["json_path"], "check": "BROKEN_INTERNAL_LINK", "limit": 5},
            )
        )
        backlog = _payload(
            await session.call_tool(
                "sf_audit_tasks",
                {"json_path": run["json_path"], "out": os.path.join(out_dir, "tasks")},
            )
        )
        return {
            "tools": tools,
            "list_exports": le,
            "run": run,
            "summary": summ,
            "issues": issues,
            "tasks": backlog,
        }


def test_mcp_all_tools(tmp_path):
    exports = tmp_path / "exports"
    exports.mkdir()
    for name in os.listdir(FIXTURES):
        shutil.copy(os.path.join(FIXTURES, name), exports / name)
    out = tmp_path / "out"

    res = asyncio.run(_drive(str(exports), str(out)))

    assert {
        "sf_audit_run",
        "sf_audit_summary",
        "sf_audit_issues",
        "sf_list_exports",
        "sf_audit_tasks",
    } <= res["tools"]
    # One connector exposes both crawl-audit and live-analysis tools.
    assert {"seo_parse", "seo_robots_check", "seo_headers_check"} <= res["tools"]
    assert "internal_all" in res["list_exports"]["found"]
    assert os.path.isfile(res["run"]["json_path"])
    assert os.path.isfile(res["run"]["md_path"])
    assert res["summary"]["by_severity"]["critical"] >= 1
    assert res["issues"][0]["check"] == "BROKEN_INTERNAL_LINK"
    assert len(res["issues"][0]["locations"]) == 2
    assert res["tasks"]["summary"]["tasks_total"] >= 1
    assert os.path.isfile(res["tasks"]["tasks_md"])
