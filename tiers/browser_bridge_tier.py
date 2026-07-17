"""Browser bridge tier — controls Chrome/Chromium via CDP (DevTools Protocol).

Requires Chrome/Chromium started with:
  google-chrome --remote-debugging-port=9222 --user-data-dir=/tmp/chrome_vorlix

Or auto-launches with xdg-open if no debug port is found.
"""
import asyncio
import json
import os
import urllib.request
import urllib.error
from typing import Optional

from core.tier_base import AgenticAutomationTier, TierRequest, TierResponse, TierResult

CDP_PORT = 9222
NAVIGATION_TIMEOUT_S = 10
ELEMENT_TIMEOUT_S = 5


class BrowserBridgeTier(AgenticAutomationTier):
    """Controls browser via Chrome DevTools Protocol — no Selenium required."""

    def __init__(self):
        super().__init__("BrowserBridgeTier")
        self._ws: Optional = None
        self._target_id: Optional[str] = None
        self._cmd_id = 0
        self._connected = False
        self._lock = asyncio.Lock()

    # ------------------------------------------------------------------
    # CDP connection management
    # ------------------------------------------------------------------

    async def _ensure_connected(self) -> bool:
        """Open a CDP connection if not already connected. Returns True on success."""
        if self._connected and self._ws:
            return True
        return await self._connect()

    async def _connect(self) -> bool:
        """Discover Chrome debug endpoint and open a CDP WebSocket."""
        # Try to find an existing Chrome with remote debugging
        debug_url = None
        try:
            req = urllib.request.Request(
                f"http://127.0.0.1:{CDP_PORT}/json/version",
                headers={"Accept": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=2) as resp:
                info = json.loads(resp.read())
                debug_url = info.get("webSocketDebuggerUrl", "")
        except (urllib.error.URLError, json.JSONDecodeError, OSError):
            pass

        if not debug_url:
            return False

        try:
            import websockets
            self._ws = await websockets.connect(debug_url, max_size=2**20)
        except Exception:
            return False

        # Get the browser's target list and pick/create a page target
        targets = await self._list_targets()
        for t in targets:
            if t.get("type") == "page":
                self._target_id = t["id"]
                break

        if not self._target_id:
            return False

        # Enable Page and DOM domains
        await self._send("Page.enable")
        await self._send("DOM.enable")
        self._connected = True
        return True

    async def _list_targets(self) -> list:
        """Get all available CDP targets."""
        try:
            req = urllib.request.Request(
                f"http://127.0.0.1:{CDP_PORT}/json",
                headers={"Accept": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=2) as resp:
                return json.loads(resp.read())
        except Exception:
            return []

    async def _send(self, method: str, params: dict = None) -> dict:
        """Send a CDP command and return the result."""
        async with self._lock:
            self._cmd_id += 1
            cmd = {"id": self._cmd_id, "method": method, "params": params or {}}
            await self._ws.send(json.dumps(cmd))

            # Read until we get the matching response
            while True:
                raw = await self._ws.recv()
                msg = json.loads(raw)
                if msg.get("id") == self._cmd_id:
                    if "error" in msg:
                        raise RuntimeError(msg["error"].get("message", str(msg["error"])))
                    return msg.get("result", {})
                # Handle events (notifications without id)
                continue

    async def _send_to_target(self, method: str, params: dict = None) -> dict:
        """Send a CDP command scoped to the current page target."""
        return await self._send("Target.sendMessageToTarget", {
            "targetId": self._target_id,
            "message": json.dumps({"id": self._cmd_id + 1, "method": method, "params": params or {}}),
        })

    async def _evaluate(self, js: str) -> dict:
        """Evaluate JavaScript in the page context."""
        result = await self._send("Runtime.evaluate", {
            "expression": js,
            "returnByValue": True,
        })
        return result

    async def _disconnect(self):
        """Close the CDP connection."""
        self._connected = False
        if self._ws:
            try:
                await self._ws.close()
            except Exception:
                pass
            self._ws = None

    # ------------------------------------------------------------------
    # Guardrails
    # ------------------------------------------------------------------

    def is_within_guardrails(self, request: TierRequest) -> bool:
        return True

    # ------------------------------------------------------------------
    # Execute
    # ------------------------------------------------------------------

    def _validate_args(self, tool: str, args: dict) -> Optional[str]:
        """Check required args before attempting connection. Returns error message or None."""
        if tool == "browser_bridge.navigate":
            if not args.get("url", "").strip():
                return "Missing url argument."
        elif tool == "browser_bridge.click_by_text":
            if not args.get("text", "").strip():
                return "Missing text argument."
        elif tool == "browser_bridge.fill_field":
            if not args.get("selector", "").strip():
                return "Missing selector argument."
        return None

    async def execute(self, request: TierRequest) -> TierResponse:
        tool = request.tool
        args = request.arguments

        if not tool.startswith("browser_bridge."):
            return TierResponse(
                result=TierResult.BLOCKED,
                message=f"Unknown tool: {tool}",
            )

        # Validate arguments before attempting connection
        err = self._validate_args(tool, args)
        if err:
            return TierResponse(result=TierResult.BLOCKED, message=err)

        connected = await self._ensure_connected()
        if not connected:
            return TierResponse(
                result=TierResult.BLOCKED,
                message="No Chrome/Chromium found with --remote-debugging-port=9222. "
                        "Start Chrome with: google-chrome --remote-debugging-port=9222",
            )

        try:
            if tool == "browser_bridge.navigate":
                return await self._navigate(args)
            elif tool == "browser_bridge.click_by_text":
                return await self._click_by_text(args)
            elif tool == "browser_bridge.fill_field":
                return await self._fill_field(args)
            elif tool == "browser_bridge.get_text":
                return await self._get_text(args)
            elif tool == "browser_bridge.screenshot":
                return await self._screenshot(args)
            else:
                return TierResponse(
                    result=TierResult.BLOCKED,
                    message=f"Unknown tool: {tool}",
                )
        except RuntimeError as e:
            return TierResponse(
                result=TierResult.BLOCKED,
                message=str(e),
            )
        except Exception as e:
            return TierResponse(
                result=TierResult.FAILED,
                message=str(e),
            )

    # ------------------------------------------------------------------
    # Tool implementations
    # ------------------------------------------------------------------

    async def _navigate(self, args: dict) -> TierResponse:
        url = args.get("url", "").strip()
        if not url:
            return TierResponse(
                result=TierResult.BLOCKED,
                message="Missing url argument.",
            )

        result = await self._send("Page.navigate", {"url": url})

        # Wait for page to finish loading
        try:
            await asyncio.wait_for(
                self._wait_for_load(), timeout=NAVIGATION_TIMEOUT_S
            )
        except asyncio.TimeoutError:
            pass  # Page may still render — not always a failure

        frame_id = result.get("frameId", "")
        return TierResponse(
            result=TierResult.SUCCESS,
            data={"url": url, "frame_id": frame_id},
            message=f"Navigated to {url}",
        )

    async def _wait_for_load(self):
        """Wait for the Page.loadEventFired event."""
        while True:
            raw = await self._ws.recv()
            msg = json.loads(raw)
            if msg.get("method") == "Page.loadEventFired":
                return

    async def _click_by_text(self, args: dict) -> TierResponse:
        text = args.get("text", "").strip()
        if not text:
            return TierResponse(
                result=TierResult.BLOCKED,
                message="Missing text argument.",
            )

        escaped = text.replace("'", "\\'")
        js = f"""
        (() => {{
            const elements = document.querySelectorAll('a, button, input[type="submit"], [role="button"], [onclick]');
            for (const el of elements) {{
                if (el.textContent.trim().includes('{escaped}')) {{
                    el.click();
                    return 'clicked';
                }}
            }}
            // Try XPath as fallback
            const xpathResult = document.evaluate(
                "//*[contains(text(), '{escaped}')]",
                document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null
            );
            if (xpathResult.singleNodeValue) {{
                xpathResult.singleNodeValue.click();
                return 'clicked_xpath';
            }}
            return 'not_found';
        }})()
        """
        result = await self._evaluate(js)
        status = (result.get("result", {}) or {}).get("value", "not_found")

        if status == "not_found":
            return TierResponse(
                result=TierResult.BLOCKED,
                message=f"No element found with text: {text}",
                data={"text": text},
            )

        return TierResponse(
            result=TierResult.SUCCESS,
            data={"text": text, "method": status},
            message=f"Clicked element with text: {text}",
        )

    async def _fill_field(self, args: dict) -> TierResponse:
        selector = args.get("selector", "").strip()
        value = args.get("value", "").strip()
        if not selector:
            return TierResponse(
                result=TierResult.BLOCKED,
                message="Missing selector argument.",
            )

        escaped_value = value.replace("'", "\\'")
        escaped_selector = selector.replace("'", "\\'")
        js = f"""
        (() => {{
            const el = document.querySelector('{escaped_selector}');
            if (!el) return 'not_found';
            const tag = el.tagName.toLowerCase();
            const type = (el.type || '').toLowerCase();
            if (tag === 'input' || tag === 'textarea' || tag === 'select') {{
                el.value = '{escaped_value}';
                el.dispatchEvent(new Event('input', {{ bubbles: true }}));
                el.dispatchEvent(new Event('change', {{ bubbles: true }}));
                return 'filled';
            }}
            if (el.isContentEditable) {{
                el.textContent = '{escaped_value}';
                el.dispatchEvent(new Event('input', {{ bubbles: true }}));
                return 'filled_editable';
            }}
            return 'not_interactive';
        }})()
        """
        result = await self._evaluate(js)
        status = (result.get("result", {}) or {}).get("value", "not_found")

        if status == "not_found":
            return TierResponse(
                result=TierResult.BLOCKED,
                message=f"Element not found: {selector}",
                data={"selector": selector},
            )
        if status == "not_interactive":
            return TierResponse(
                result=TierResult.BLOCKED,
                message=f"Element is not an input field: {selector}",
                data={"selector": selector},
            )

        return TierResponse(
            result=TierResult.SUCCESS,
            data={"selector": selector, "value": value},
            message=f"Field '{selector}' set to '{value}'",
        )

    async def _get_text(self, args: dict) -> TierResponse:
        result = await self._evaluate("document.body.innerText")
        text = (result.get("result", {}) or {}).get("value", "")
        return TierResponse(
            result=TierResult.SUCCESS,
            data={"length": len(text), "text_preview": text[:500]},
            message=f"Got {len(text)} characters of page text",
        )

    async def _screenshot(self, args: dict) -> TierResponse:
        result = await self._send("Page.captureScreenshot", {
            "format": "png",
            "fromSurface": True,
        })
        data = result.get("data", "")
        out_path = args.get("output_path", "")
        if out_path and data:
            import base64
            with open(out_path, "wb") as f:
                f.write(base64.b64decode(data))
            return TierResponse(
                result=TierResult.SUCCESS,
                data={"path": out_path, "size": len(data)},
                message=f"Screenshot saved to {out_path}",
            )
        return TierResponse(
            result=TierResult.SUCCESS,
            data={"screenshot_base64_length": len(data)},
            message="Screenshot captured",
        )
