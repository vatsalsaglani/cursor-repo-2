from __future__ import annotations

import atexit
from typing import Any, Literal

from mcp.server.fastmcp import FastMCP

from playwright_cdp_framework.browser_manager import BrowserSession

mcp = FastMCP("playwright-cdp-browser")
session = BrowserSession()


@mcp.tool()
def launch_browser(
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
    return session.launch_browser(headless=headless, cdp_port=cdp_port, channel=channel)


@mcp.tool()
def connect_over_cdp(endpoint_url: str, timeout_ms: int = 30000) -> dict[str, Any]:
    """
    Connect Playwright to an existing Chromium instance over CDP.

    Args:
        endpoint_url: CDP endpoint URL (http(s)://host:port or ws(s)://...).
        timeout_ms: Connection timeout in milliseconds.
    """
    return session.connect_over_cdp(endpoint_url, timeout_ms=timeout_ms)


@mcp.tool()
def open_url(
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
    return session.open_url(url, new_tab=new_tab, wait_until=wait_until, timeout_ms=timeout_ms)


@mcp.tool()
def list_tabs() -> list[dict[str, Any]]:
    """List tabs and return stable tab indices for switch_tab."""
    return session.list_tabs()


@mcp.tool()
def switch_tab(tab_index: int) -> dict[str, Any]:
    """Set the active tab by tab index from list_tabs."""
    return session.switch_tab(tab_index)


@mcp.tool()
def execute_javascript(script: str, arg: Any = None) -> dict[str, Any]:
    """
    Execute JavaScript in the active tab.

    Args:
        script: JS expression/function body accepted by page.evaluate().
        arg: Optional serializable argument passed to script.
    """
    return session.execute_javascript(script, arg=arg)


@mcp.tool()
def close_tab(tab_index: int | None = None) -> dict[str, Any]:
    """Close a tab by index, or close active tab when index is omitted."""
    return session.close_tab(tab_index=tab_index)


@mcp.tool()
def close_browser() -> dict[str, Any]:
    """Close the current browser connection."""
    return session.close_browser()


@mcp.tool()
def browser_status() -> dict[str, Any]:
    """Return browser runtime status including CDP URLs and active tab."""
    return session.get_status()


def main() -> None:
    mcp.run()


atexit.register(session.shutdown)


if __name__ == "__main__":
    main()
