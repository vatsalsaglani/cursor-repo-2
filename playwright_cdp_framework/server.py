from __future__ import annotations

import asyncio
import atexit
from typing import Any, Literal

from mcp.server.fastmcp import FastMCP

from playwright_cdp_framework.browser_manager import BrowserSession, BrowserSessionError

mcp = FastMCP("playwright-cdp-browser")
session = BrowserSession()
WM_THEME = {
    "brand": "WM",
    "primary": "#006B3F",
    "secondary": "#8DC63F",
    "accent": "#FFC72C",
    "background": "#F5F8F5",
    "text": "#1F2933",
}


def _success(data: Any) -> dict[str, Any]:
    return {"ok": True, "data": data, "theme": WM_THEME}


def _error(action: str, exc: Exception) -> dict[str, Any]:
    return {
        "ok": False,
        "error": {
            "action": action,
            "type": exc.__class__.__name__,
            "message": str(exc),
        },
        "theme": WM_THEME,
    }


@mcp.tool()
async def launch_browser(
    headless: bool = True,
    cdp_port: int = 9222,
    channel: str | None = None,
) -> dict[str, Any]:
    """
    Launch a Chromium browser and expose its CDP endpoint.

    Args:
        headless: Launch without UI when True.
        cdp_port: Port used for Chromium remote debugging endpoint.
        channel: Optional browser channel (for example: "chrome", "msedge").
    """
    try:
        return _success(
            await session.launch_browser(headless=headless, cdp_port=cdp_port, channel=channel)
        )
    except (BrowserSessionError, Exception) as exc:
        return _error("launch_browser", exc)


@mcp.tool()
async def connect_over_cdp(endpoint_url: str, timeout_ms: int = 30000) -> dict[str, Any]:
    """
    Connect Playwright to an existing Chromium instance over CDP.

    Args:
        endpoint_url: CDP endpoint URL (http(s)://host:port or ws(s)://...).
        timeout_ms: Connection timeout in milliseconds.
    """
    try:
        return _success(await session.connect_over_cdp(endpoint_url, timeout_ms=timeout_ms))
    except (BrowserSessionError, Exception) as exc:
        return _error("connect_over_cdp", exc)


@mcp.tool()
async def open_url(
    url: str,
    new_tab: bool = False,
    wait_until: Literal["commit", "domcontentloaded", "load", "networkidle"] = "load",
    timeout_ms: int = 30000,
) -> dict[str, Any]:
    """
    Navigate to URL in active tab or a new tab.

    Args:
        url: URL to open.
        new_tab: Open in a new tab if True.
        wait_until: Playwright load state to wait for.
        timeout_ms: Navigation timeout in milliseconds.
    """
    try:
        return _success(
            await session.open_url(url, new_tab=new_tab, wait_until=wait_until, timeout_ms=timeout_ms)
        )
    except (BrowserSessionError, Exception) as exc:
        return _error("open_url", exc)


@mcp.tool()
async def list_tabs() -> dict[str, Any]:
    """List tabs and return stable tab indices for switch_tab."""
    try:
        return _success(await session.list_tabs())
    except (BrowserSessionError, Exception) as exc:
        return _error("list_tabs", exc)


@mcp.tool()
async def switch_tab(tab_index: int) -> dict[str, Any]:
    """Set the active tab by tab index from list_tabs."""
    try:
        return _success(await session.switch_tab(tab_index))
    except (BrowserSessionError, Exception) as exc:
        return _error("switch_tab", exc)


@mcp.tool()
async def execute_javascript(script: str, arg: Any = None) -> dict[str, Any]:
    """
    Execute JavaScript in the active tab.

    Args:
        script: JS expression/function body accepted by page.evaluate().
        arg: Optional serializable argument passed to script.
    """
    try:
        return _success(await session.execute_javascript(script, arg=arg))
    except (BrowserSessionError, Exception) as exc:
        return _error("execute_javascript", exc)


@mcp.tool()
async def close_tab(tab_index: int | None = None) -> dict[str, Any]:
    """Close a tab by index, or close active tab when index is omitted."""
    try:
        return _success(await session.close_tab(tab_index=tab_index))
    except (BrowserSessionError, Exception) as exc:
        return _error("close_tab", exc)


@mcp.tool()
async def close_browser() -> dict[str, Any]:
    """Close the current browser connection."""
    try:
        return _success(await session.close_browser())
    except (BrowserSessionError, Exception) as exc:
        return _error("close_browser", exc)


@mcp.tool()
async def browser_status() -> dict[str, Any]:
    """Return browser runtime status including CDP URLs and active tab."""
    try:
        return _success(await session.get_status())
    except (BrowserSessionError, Exception) as exc:
        return _error("browser_status", exc)


@mcp.tool()
def wm_branding_theme() -> dict[str, Any]:
    """Return WM branding theme colors for MCP clients/UI wrappers."""
    return _success(WM_THEME)


def main() -> None:
    mcp.run()


def _shutdown_session() -> None:
    try:
        asyncio.run(session.shutdown())
    except Exception:
        pass


atexit.register(_shutdown_session)


if __name__ == "__main__":
    main()
