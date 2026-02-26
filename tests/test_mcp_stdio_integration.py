import socket
import unittest

import anyio
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client


def _pick_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


class TestMcpStdioIntegration(unittest.TestCase):
    def test_server_tools_end_to_end(self) -> None:
        anyio.run(self._run_end_to_end)

    async def _run_end_to_end(self) -> None:
        cdp_port = _pick_free_port()
        server = StdioServerParameters(
            command="python3",
            args=["-m", "playwright_cdp_framework.server"],
            cwd="/workspace",
        )

        async with stdio_client(server) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()

                tools = await session.list_tools()
                tool_names = {tool.name for tool in tools.tools}
                self.assertIn("launch_browser", tool_names)
                self.assertIn("wm_branding_theme", tool_names)

                status = await session.call_tool("browser_status", {})
                status_payload = status.structuredContent
                self.assertTrue(status_payload["ok"])
                self.assertFalse(status_payload["data"]["running"])

                launch = await session.call_tool(
                    "launch_browser",
                    {"headless": True, "cdp_port": cdp_port},
                )
                launch_payload = launch.structuredContent
                self.assertTrue(launch_payload["ok"])
                self.assertTrue(launch_payload["data"]["running"])
                self.assertEqual(launch_payload["theme"]["brand"], "WM")

                nav = await session.call_tool(
                    "open_url",
                    {
                        "url": "data:text/html,<title>WM%20Demo</title><h1 id='wm-title'>Ready</h1>",
                        "new_tab": False,
                    },
                )
                nav_payload = nav.structuredContent
                self.assertTrue(nav_payload["ok"])

                js = await session.call_tool(
                    "execute_javascript",
                    {
                        "script": "() => ({title: document.title, heading: document.querySelector('#wm-title')?.textContent})"
                    },
                )
                js_payload = js.structuredContent
                self.assertTrue(js_payload["ok"])
                self.assertEqual(js_payload["data"]["result"]["title"], "WM Demo")
                self.assertEqual(js_payload["data"]["result"]["heading"], "Ready")

                tabs = await session.call_tool("list_tabs", {})
                tabs_payload = tabs.structuredContent
                self.assertTrue(tabs_payload["ok"])
                self.assertGreaterEqual(len(tabs_payload["data"]), 1)

                close = await session.call_tool("close_browser", {})
                close_payload = close.structuredContent
                self.assertTrue(close_payload["ok"])
                self.assertFalse(close_payload["data"]["running"])

    def test_tool_error_payload_without_browser(self) -> None:
        anyio.run(self._run_error_case)

    async def _run_error_case(self) -> None:
        server = StdioServerParameters(
            command="python3",
            args=["-m", "playwright_cdp_framework.server"],
            cwd="/workspace",
        )

        async with stdio_client(server) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                result = await session.call_tool(
                    "execute_javascript",
                    {"script": "() => document.title"},
                )
                payload = result.structuredContent
                self.assertFalse(payload["ok"])
                self.assertEqual(payload["error"]["action"], "execute_javascript")
                self.assertIn("No connected browser", payload["error"]["message"])
