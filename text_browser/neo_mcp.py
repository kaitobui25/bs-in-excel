"""Small synchronous BrowserOS Neo MCP client for the local Excel backend.

All page operations use one `run` call. The server owns the Chromium process;
this client owns only the tabs it creates, never user or other-agent tabs.
"""
from __future__ import annotations

import json
import os

import requests


MCP_URL = os.environ.get("BS_EXCEL_NEO_MCP_URL", "http://127.0.0.1:9010/mcp")
HEADERS = {"Accept": "application/json, text/event-stream"}


class NeoMcpError(RuntimeError):
    """BrowserOS Neo is unavailable or rejected a browser operation."""


def _decode_response(response: requests.Response) -> dict:
    """Read a JSON-RPC response, including Streamable HTTP SSE framing."""
    body = response.content.decode("utf-8-sig")
    if body.lstrip().startswith("{"):
        return json.loads(body)
    # A response can contain heartbeats and several SSE events; use the last
    # actual JSON-RPC event, not the heartbeat or a streaming progress event.
    events = [line[5:].strip() for line in body.splitlines() if line.startswith("data:")]
    messages = [json.loads(value) for value in events if value.startswith("{")]
    if not messages:
        raise NeoMcpError("BrowserOS Neo không trả về phản hồi JSON-RPC hợp lệ.")
    return messages[-1]


class NeoMcpClient:
    def __init__(self, url: str = MCP_URL) -> None:
        self.url = url
        self.http = requests.Session()
        self.session_id: str | None = None
        self._request_id = 0

    def _post(self, method: str, params: dict, timeout: int = 40) -> tuple[dict | None, requests.Response]:
        self._request_id += 1
        headers = {**HEADERS, "Content-Type": "application/json"}
        if self.session_id:
            headers["mcp-session-id"] = self.session_id
        payload = {"jsonrpc": "2.0", "id": self._request_id, "method": method, "params": params}
        try:
            response = self.http.post(self.url, json=payload, headers=headers, timeout=(3, timeout))
            response.raise_for_status()
            message = _decode_response(response)
        except requests.HTTPError as exc:
            # Reset only on a confirmed expired session. A timeout or temporary
            # network failure may leave an owned tab open and still closable.
            if response.status_code in {404, 410} and "Session not found" in response.text:
                self.session_id = None
            raise NeoMcpError(f"BrowserOS Neo từ chối yêu cầu: {exc}") from exc
        except (requests.RequestException, ValueError) as exc:
            raise NeoMcpError(f"Không liên lạc được BrowserOS Neo tại {self.url}: {exc}") from exc
        if "error" in message:
            raise NeoMcpError(f"BrowserOS Neo: {message['error'].get('message', 'Lỗi JSON-RPC')}")
        return message.get("result"), response

    def connect(self) -> None:
        if self.session_id:
            return
        result, response = self._post("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "bs-in-excel", "version": "1.0"},
        }, timeout=8)
        session_id = response.headers.get("mcp-session-id")
        if result is None or not session_id:
            raise NeoMcpError("BrowserOS Neo không cấp MCP session.")
        self.session_id = session_id
        headers = {**HEADERS, "Content-Type": "application/json", "mcp-session-id": session_id}
        try:
            response = self.http.post(self.url, json={
                "jsonrpc": "2.0", "method": "notifications/initialized", "params": {},
            }, headers=headers, timeout=(3, 8))
            response.raise_for_status()
        except requests.RequestException as exc:
            self.session_id = None
            raise NeoMcpError("Không hoàn thành kết nối BrowserOS Neo.") from exc

    def run(self, code: str) -> object:
        self.connect()
        result, _ = self._post("tools/call", {
            "name": "run", "arguments": {"code": code, "timeout": 30_000},
        })
        if not isinstance(result, dict):
            raise NeoMcpError("BrowserOS Neo không trả về kết quả của lệnh run.")
        data = result.get("structuredContent")
        if result.get("isError") or not isinstance(data, dict) or data.get("ok") is not True:
            detail = "\n".join(str(item.get("text", "")) for item in result.get("content", [])
                               if isinstance(item, dict))
            raise NeoMcpError(f"BrowserOS Neo không thực hiện được lệnh: {detail[:250]}")
        return data.get("value")

    def close(self) -> None:
        self.session_id = None
        self.http.close()


class NeoPage:
    """A single background tab created by this Excel backend session."""

    def __init__(self, client: NeoMcpClient | None = None, *, block_media: bool = False) -> None:
        self.client = client or NeoMcpClient()
        self.page_id: int | None = None
        self.block_media = block_media

    def _open(self) -> None:
        script = "const page = await browser.open('about:blank');\n"
        if self.block_media:
            # URL patterns are page-scoped: do not alter the user's browser.
            # Facebook still loads images/fonts needed for lazy rendering.
            script += """
try {
  await page.cdp('Network.enable', '{}');
  await page.cdp('Network.setBlockedURLs', JSON.stringify({
    urls: ['*.mp4*', '*.webm*', '*.m3u8*', '*.mpd*', '*.mov*']
  }));
} catch (error) { /* Some Neo versions do not expose page CDP. */ }
"""
        page_id = self.client.run(script + "return page.id;")
        if not isinstance(page_id, int):
            raise NeoMcpError("BrowserOS Neo không cấp page id.")
        self.page_id = page_id

    def run(self, body: str, *, url: str | None = None, _retry: bool = True) -> object:
        if self.client.session_id is None:
            # A terminated MCP session no longer owns the previous page.
            self.page_id = None
        try:
            if self.page_id is None:
                if url is None:
                    raise NeoMcpError("Chưa mở trang trên BrowserOS Neo.")
                self._open()
            prefix = f"""
const owned = (await browser.pages.list()).some(
  tab => tab.pageId === {self.page_id} && tab.ownership === 'mine'
);
if (!owned) throw new Error('NEO_TAB_UNAVAILABLE');
const page = browser.page({self.page_id});
"""
            operation = (f"await page.goto({json.dumps(url, ensure_ascii=False)});\n"
                         if url is not None else "")
            operation += f"const data = await (async () => {{\n{body}\n}})();\nreturn {{pageId: page.id, data}};"
            script = f"{prefix}\n{operation}"
            output = self.client.run(script)
        except NeoMcpError as exc:
            lost_page = self.client.session_id is None or "NEO_TAB_UNAVAILABLE" in str(exc)
            if lost_page:
                self.page_id = None
                # Opening a URL is repeatable. A lost MCP session cannot own
                # the old tab, so create a new one on a fresh session once.
                # Do not retry load_more/scroll or arbitrary page scripts.
                if url is not None and _retry:
                    return self.run(body, url=url, _retry=False)
            raise
        if not isinstance(output, dict) or not isinstance(output.get("pageId"), int):
            raise NeoMcpError("BrowserOS Neo trả về page id không hợp lệ.")
        self.page_id = output["pageId"]
        return output.get("data")

    def close(self) -> None:
        page_id, self.page_id = self.page_id, None
        try:
            if page_id is not None and self.client.session_id:
                try:
                    self.client.run(f"""
const tab = (await browser.pages.list()).find(item => item.pageId === {page_id});
if (tab?.ownership === 'mine') await browser.page({page_id}).close();
return true;
""")
                except NeoMcpError:
                    pass  # Best-effort cleanup; never close any other tab.
        finally:
            self.client.close()
