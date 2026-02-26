# Playwright CDP MCP Framework

Small Python framework that keeps a Playwright Chromium browser running and exposes browser actions as MCP tools.

## What this provides

- Launch Chromium with a CDP endpoint
- Connect to an already-running browser using CDP URL
- Open URLs in current tab or new tab
- List tabs and switch active tab
- Execute JavaScript in the active tab
- Close tabs and close browser connection

The browser lifecycle is stateful inside the MCP server process, so tools can be called repeatedly by an agent without relaunching each time.

## Install

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
python -m playwright install chromium
```

## Run MCP server

```bash
playwright-cdp-mcp
```

This starts the MCP server over stdio (default FastMCP transport).

If your user-local scripts directory is not on `PATH`, run:

```bash
python3 -m playwright_cdp_framework.server
```

## MCP tools exposed

- `launch_browser(headless=True, cdp_port=9222, channel=None)`
- `connect_over_cdp(endpoint_url, timeout_ms=30000)`
- `open_url(url, new_tab=False, wait_until="load", timeout_ms=30000)`
- `list_tabs()`
- `switch_tab(tab_index)`
- `execute_javascript(script, arg=None)`
- `close_tab(tab_index=None)`
- `close_browser()`
- `browser_status()`
- `wm_branding_theme()`

Each tool returns a consistent payload:

```json
{
  "ok": true,
  "data": {},
  "theme": {
    "brand": "WM",
    "primary": "#006B3F",
    "secondary": "#8DC63F",
    "accent": "#FFC72C",
    "background": "#F5F8F5",
    "text": "#1F2933"
  }
}
```

On failures, tools return:

```json
{
  "ok": false,
  "error": {
    "action": "open_url",
    "type": "BrowserSessionError",
    "message": "No connected browser. Call launch_browser or connect_over_cdp first."
  },
  "theme": { "...": "..." }
}
```

## Example flow for an agent

1. `launch_browser(headless=False, cdp_port=9222)`
2. `open_url("https://example.com")`
3. `execute_javascript("() => document.title")`
4. `list_tabs()`
5. `switch_tab(0)`

## Connect external browser using CDP

If you already have a Chromium instance with remote debugging enabled:

```bash
google-chrome --remote-debugging-port=9222 --user-data-dir=/tmp/cdp-profile
```

Then use the MCP tool:

- `connect_over_cdp("http://127.0.0.1:9222")`

## Example MCP client config

```json
{
  "mcpServers": {
    "playwright-cdp": {
      "command": "playwright-cdp-mcp"
    }
  }
}
```