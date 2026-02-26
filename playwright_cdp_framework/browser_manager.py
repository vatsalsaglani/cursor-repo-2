from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse
from urllib.request import urlopen

from playwright.async_api import Browser, BrowserContext, Page, Playwright, async_playwright


class BrowserSessionError(RuntimeError):
    """Raised when browser session actions are invalid."""


@dataclass(frozen=True)
class _TabRef:
    context_index: int
    page_index: int
    page: Page


class BrowserSession:
    """Manages one active browser connection for MCP tools."""

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._active_page: Page | None = None
        self._managed_browser = False
        self._cdp_http_url: str | None = None
        self._cdp_ws_url: str | None = None

    async def launch_browser(
        self,
        *,
        headless: bool = True,
        cdp_port: int = 9222,
        channel: str | None = None,
    ) -> dict[str, Any]:
        """Launch a new Chromium browser with remote debugging enabled."""
        async with self._lock:
            await self._close_browser_unlocked()
            playwright = await self._ensure_playwright()

            launch_kwargs: dict[str, Any] = {
                "headless": headless,
                "args": [f"--remote-debugging-port={cdp_port}"],
            }
            if channel:
                launch_kwargs["channel"] = channel

            self._browser = await playwright.chromium.launch(**launch_kwargs)
            self._managed_browser = True
            self._cdp_http_url = f"http://127.0.0.1:{cdp_port}"
            self._cdp_ws_url = await self._wait_for_debug_ws_url(self._cdp_http_url)
            self._active_page = await self._new_page_unlocked()
            return await self._get_status_unlocked()

    async def connect_over_cdp(self, endpoint_url: str, *, timeout_ms: int = 30000) -> dict[str, Any]:
        """Connect to an already running browser via CDP."""
        async with self._lock:
            await self._close_browser_unlocked()
            playwright = await self._ensure_playwright()
            self._browser = await playwright.chromium.connect_over_cdp(endpoint_url, timeout=timeout_ms)
            self._managed_browser = False
            self._cdp_http_url = self._to_http_debug_url(endpoint_url)
            self._cdp_ws_url = await self._detect_ws_url(endpoint_url)

            tabs = self._tab_refs_unlocked()
            if tabs:
                self._active_page = tabs[0].page
            else:
                self._active_page = await self._new_page_unlocked()

            return await self._get_status_unlocked()

    async def open_url(
        self,
        url: str,
        *,
        new_tab: bool = False,
        wait_until: str = "load",
        timeout_ms: int = 30000,
    ) -> dict[str, Any]:
        """Open URL in active tab or a new tab."""
        async with self._lock:
            page = self._active_page
            if new_tab or page is None or page.is_closed():
                page = await self._new_page_unlocked()

            await page.goto(url, wait_until=wait_until, timeout=timeout_ms)
            self._active_page = page
            tab = await self._tab_info_for_page_unlocked(page)
            if tab is None:
                raise BrowserSessionError("Failed to resolve active tab after navigation.")
            return tab

    async def list_tabs(self) -> list[dict[str, Any]]:
        """Return all tabs across browser contexts."""
        async with self._lock:
            self._require_browser_unlocked()
            tabs: list[dict[str, Any]] = []
            for tab_index, ref in enumerate(self._tab_refs_unlocked()):
                tabs.append(await self._tab_info(ref, tab_index=tab_index))
            return tabs

    async def switch_tab(self, tab_index: int) -> dict[str, Any]:
        """Switch active page to a tab index from list_tabs."""
        async with self._lock:
            refs = self._tab_refs_unlocked()
            if tab_index < 0 or tab_index >= len(refs):
                raise BrowserSessionError(
                    f"tab_index out of range: {tab_index}. Available tabs: {len(refs)}."
                )

            page = refs[tab_index].page
            await page.bring_to_front()
            self._active_page = page
            return await self._tab_info(refs[tab_index], tab_index=tab_index)

    async def execute_javascript(self, script: str, *, arg: Any = None) -> dict[str, Any]:
        """Evaluate JavaScript in the active tab."""
        async with self._lock:
            page = await self._require_active_page_unlocked()
            result = await page.evaluate(script, arg)
            tab = await self._tab_info_for_page_unlocked(page)
            return {"result": self._make_json_safe(result), "tab": tab}

    async def close_tab(self, tab_index: int | None = None) -> dict[str, Any]:
        """Close a specific tab or the active tab."""
        async with self._lock:
            refs = self._tab_refs_unlocked()
            if not refs:
                raise BrowserSessionError("No tabs available to close.")

            page_to_close: Page
            if tab_index is None:
                page_to_close = await self._require_active_page_unlocked()
            else:
                if tab_index < 0 or tab_index >= len(refs):
                    raise BrowserSessionError(
                        f"tab_index out of range: {tab_index}. Available tabs: {len(refs)}."
                    )
                page_to_close = refs[tab_index].page

            was_active = page_to_close is self._active_page
            await page_to_close.close()
            remaining = self._tab_refs_unlocked()
            self._active_page = remaining[0].page if remaining else None

            return {
                "closed_active_tab": was_active,
                "remaining_tabs": [
                    await self._tab_info(ref, tab_index=i) for i, ref in enumerate(remaining)
                ],
            }

    async def close_browser(self) -> dict[str, Any]:
        """Close active browser connection."""
        async with self._lock:
            await self._close_browser_unlocked()
            return {"running": False}

    async def get_status(self) -> dict[str, Any]:
        """Return current browser/session state."""
        async with self._lock:
            return await self._get_status_unlocked()

    async def shutdown(self) -> None:
        """Close browser and stop Playwright runtime."""
        async with self._lock:
            await self._close_browser_unlocked()
            if self._playwright is not None:
                await self._playwright.stop()
                self._playwright = None

    async def _close_browser_unlocked(self) -> None:
        if self._browser is not None:
            try:
                await self._browser.close()
            except Exception:
                pass

        self._browser = None
        self._active_page = None
        self._managed_browser = False
        self._cdp_http_url = None
        self._cdp_ws_url = None

    async def _get_status_unlocked(self) -> dict[str, Any]:
        running = self._browser is not None and self._browser.is_connected()
        tab_count = len(self._tab_refs_unlocked()) if running else 0
        active = await self._tab_info_for_page_unlocked(self._active_page) if running else None
        return {
            "running": running,
            "managed_browser": self._managed_browser,
            "cdp_http_url": self._cdp_http_url,
            "cdp_ws_url": self._cdp_ws_url,
            "tab_count": tab_count,
            "active_tab": active,
        }

    async def _ensure_playwright(self) -> Playwright:
        if self._playwright is None:
            self._playwright = await async_playwright().start()
        return self._playwright

    def _require_browser_unlocked(self) -> Browser:
        browser = self._browser
        if browser is None or not browser.is_connected():
            raise BrowserSessionError(
                "No connected browser. Call launch_browser or connect_over_cdp first."
            )
        return browser

    async def _require_active_page_unlocked(self) -> Page:
        browser = self._require_browser_unlocked()
        page = self._active_page
        if page is not None and not page.is_closed():
            return page

        refs = self._tab_refs_unlocked()
        if refs:
            self._active_page = refs[0].page
            return self._active_page

        context = await self._default_context_unlocked(browser)
        page = await context.new_page()
        self._active_page = page
        return page

    async def _new_page_unlocked(self) -> Page:
        browser = self._require_browser_unlocked()
        context = await self._default_context_unlocked(browser)
        page = await context.new_page()
        self._active_page = page
        return page

    async def _default_context_unlocked(self, browser: Browser) -> BrowserContext:
        if browser.contexts:
            return browser.contexts[0]
        return await browser.new_context()

    def _tab_refs_unlocked(self) -> list[_TabRef]:
        browser = self._browser
        if browser is None or not browser.is_connected():
            return []

        refs: list[_TabRef] = []
        for context_index, context in enumerate(browser.contexts):
            for page_index, page in enumerate(context.pages):
                refs.append(_TabRef(context_index=context_index, page_index=page_index, page=page))
        return refs

    async def _tab_info_for_page_unlocked(self, page: Page | None) -> dict[str, Any] | None:
        if page is None or page.is_closed():
            return None

        refs = self._tab_refs_unlocked()
        for tab_index, ref in enumerate(refs):
            if ref.page is page:
                return await self._tab_info(ref, tab_index=tab_index)
        return None

    async def _tab_info(self, ref: _TabRef, *, tab_index: int) -> dict[str, Any]:
        page = ref.page
        return {
            "tab_index": tab_index,
            "tab_id": f"{ref.context_index}:{ref.page_index}",
            "context_index": ref.context_index,
            "page_index": ref.page_index,
            "url": page.url,
            "title": await self._safe_title(page),
            "is_active": page is self._active_page,
        }

    @staticmethod
    async def _safe_title(page: Page) -> str:
        try:
            return await page.title()
        except Exception:
            return ""

    @staticmethod
    def _make_json_safe(value: Any) -> Any:
        try:
            json.dumps(value)
        except TypeError:
            return repr(value)
        return value

    @staticmethod
    def _to_http_debug_url(endpoint_url: str) -> str | None:
        parsed = urlparse(endpoint_url)
        if parsed.scheme in {"http", "https"}:
            return f"{parsed.scheme}://{parsed.netloc}".rstrip("/")
        if parsed.scheme in {"ws", "wss"} and parsed.hostname and parsed.port:
            return f"http://{parsed.hostname}:{parsed.port}"
        return None

    async def _detect_ws_url(self, endpoint_url: str) -> str | None:
        parsed = urlparse(endpoint_url)
        if parsed.scheme in {"ws", "wss"}:
            return endpoint_url
        debug_url = self._to_http_debug_url(endpoint_url)
        if debug_url is None:
            return None
        return await self._fetch_debug_ws_url(debug_url)

    async def _wait_for_debug_ws_url(
        self,
        cdp_http_url: str,
        *,
        attempts: int = 60,
        delay_seconds: float = 0.25,
    ) -> str:
        for _ in range(attempts):
            ws_url = await self._fetch_debug_ws_url(cdp_http_url)
            if ws_url:
                return ws_url
            await asyncio.sleep(delay_seconds)
        raise BrowserSessionError(
            f"Could not resolve CDP websocket URL from {cdp_http_url}/json/version."
        )

    async def _fetch_debug_ws_url(self, cdp_http_url: str) -> str | None:
        return await asyncio.to_thread(self._fetch_debug_ws_url_blocking, cdp_http_url)

    @staticmethod
    def _fetch_debug_ws_url_blocking(cdp_http_url: str) -> str | None:
        try:
            with urlopen(f"{cdp_http_url.rstrip('/')}/json/version", timeout=1.5) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except Exception:
            return None
        return payload.get("webSocketDebuggerUrl")
