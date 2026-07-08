"""End-to-end MCP tests: drive the real server over stdio with the MCP client.

Unlike test_mcp_server.py (which calls ``_impl_*`` pure functions directly),
these tests spawn the actual ``promoagent-mcp`` server subprocess and speak
the MCP protocol — verifying tool registration, the initialize handshake, and
cross-call state persistence on disk (analyze caches ``result`` under
``source_id``, a follow-up image_brief call recovers it).

No AI calls are made: only the no-AI tools (s2l_analyze, s2l_list_platforms,
s2l_image_brief) are exercised, so no API key or mock HTTP server is needed.
The staged AI tools (research/blueprint/produce) are covered by the _impl_*
unit tests with mocked dispatch_chat.
"""
import json
import os
import sys
import unittest
from pathlib import Path
from typing import Any, Awaitable, Callable

from mcp.client.session import ClientSession
from mcp.client.stdio import stdio_client, StdioServerParameters

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests_py" / "fixtures"


def _server_params() -> StdioServerParameters:
    """Launch promoagent-mcp as a subprocess, isolated from the host env."""
    env = {
        "PATH": os.environ.get("PATH", ""),
        "PROMOAGENT_LOG_LEVEL": "WARNING",
        # Keep AI keys out so no accidental network calls happen during E2E.
    }
    return StdioServerParameters(
        command=sys.executable,
        args=["-m", "promoagent.mcp_server"],
        env=env,
    )


class TestMcpEndToEnd(unittest.IsolatedAsyncioTestCase):

    async def _run_session(self, fn: Callable[[ClientSession], Awaitable[Any]]) -> Any:
        """Spawn the server, open a client session, run fn(session), then tear down."""
        async with stdio_client(_server_params()) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                return await fn(session)

    async def test_initialize_handshake(self):
        """The server responds to initialize with its serverInfo."""
        async with stdio_client(_server_params()) as (read, write):
            async with ClientSession(read, write) as session:
                result = await session.initialize()
        self.assertEqual(result.serverInfo.name, "promoagent")
        self.assertTrue(result.protocolVersion)

    async def test_tools_list_exposes_all_nine(self):
        async def call(session):
            return await session.list_tools()

        tools = await self._run_session(call)
        names = sorted(t.name for t in tools.tools)
        self.assertEqual(names, [
            "s2l_analyze", "s2l_blueprint", "s2l_build_image_prompt", "s2l_draft",
            "s2l_edit_blueprint", "s2l_image_brief", "s2l_list_platforms",
            "s2l_produce", "s2l_research",
        ])
        # Every tool must carry a description (the AI tool shows these to users).
        for tool in tools.tools:
            self.assertTrue(tool.description, f"{tool.name} missing description")

    async def test_list_platforms_via_protocol(self):
        async def call(session):
            return await session.call_tool("s2l_list_platforms", {})

        result = await self._run_session(call)
        # Must be a single TextContent holding one JSON object, not one-per-platform.
        self.assertEqual(len(result.content), 1, "list_platforms must return one content item, not one per platform")
        payload = json.loads(result.content[0].text)
        plats = payload["platforms"]
        keys = [p["key"] for p in plats]
        self.assertIn("xiaohongshu", keys)
        self.assertIn("twitter", keys)
        self.assertFalse(result.isError)

    async def test_analyze_then_image_brief_shares_state(self):
        """Cross-call state: analyze caches result under source_id, image_brief recovers it.

        This is the one behavior the _impl_* unit tests can't verify end-to-end
        (they mock PipelineState to a temp dir). Here the real server writes to
        ~/.cache and a second tool call reads it back over a fresh request.
        """
        target = str(FIXTURES / "healthy-repo")

        async def run(session):
            # 1. analyze → source_id
            a = await session.call_tool("s2l_analyze", {"target": target})
            analysis = json.loads(a.content[0].text)
            self.assertTrue(analysis["ok"], analysis)
            self.assertEqual(analysis["project"]["name"], "repo-pulse")
            source_id = analysis["source_id"]
            self.assertTrue(source_id)

            # 2. image_brief with that source_id — recovers the cached result
            b = await session.call_tool("s2l_image_brief", {
                "source_id": source_id, "title": "E2E 标题", "cta": "立即了解",
            })
            return json.loads(b.content[0].text)

        brief_result = await self._run_session(run)
        self.assertTrue(brief_result["ok"], brief_result)
        self.assertEqual(brief_result["brief"]["title"], "E2E 标题")
        self.assertEqual(brief_result["brief"]["cta"], "立即了解")

    async def test_analyze_returns_valid_json(self):
        """analyze returns well-formed {ok, source_id, project, ...} content."""
        async def call(session):
            return await session.call_tool("s2l_analyze", {"target": "/nonexistent/xyz/abc"})

        result = await self._run_session(call)
        payload = json.loads(result.content[0].text)
        self.assertIn("ok", payload)
        self.assertFalse(result.isError)


if __name__ == "__main__":
    unittest.main()

