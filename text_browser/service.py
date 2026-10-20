"""HTTPS loopback service for the Excel Content Add-in.

The HTTPServer thread owns the synchronous Neo MCP client. A browser
tab is created lazily on the first Neo navigation and reused. Nothing is written
directly into Excel.
"""
from __future__ import annotations

import json
import logging
import os
import re
import socket
import ssl
import threading
from contextlib import nullcontext
from dataclasses import asdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .browser import Link, PageData
from .hybrid_browser import HybridTextBrowser
from .config import LOCAL_DATA, MAX_LINKS, MAX_TEXT
from .history import HistoryStore
from .title_filter import visible_title

LOG = logging.getLogger(__name__)
HOST = "127.0.0.1"
IPV6_HOST = "::1"
PORT = 3010
BASE_URL = f"https://localhost:{PORT}"
WEB_ROOT = Path(__file__).resolve().parent.parent / "addin"
CERT_ROOT = Path.home() / ".office-addin-dev-certs"
MAX_REQUEST_SIZE = 8 * 1024


class IPv6LoopbackServer(ThreadingHTTPServer):
    """Accept localhost's IPv6 address without exposing the add-in to LAN."""

    address_family = socket.AF_INET6

    def server_bind(self) -> None:
        self.socket.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 1)
        super().server_bind()


def create_loopback_servers(handler: type[AddinHandler], port: int) -> list[ThreadingHTTPServer]:
    """Bind IPv4 and IPv6 loopback on the same port; tolerate missing IPv6."""
    ipv4 = ThreadingHTTPServer((HOST, port), handler)
    servers = [ipv4]
    try:
        servers.append(IPv6LoopbackServer((IPV6_HOST, ipv4.server_port), handler))
    except OSError:
        LOG.warning("IPv6 localhost is unavailable; continuing with IPv4")
    return servers


class BrowserService:
    def __init__(self, browser=None, history: HistoryStore | None = None):
        if browser is not None:
            self.browser = browser
        elif os.environ.get("BS_EXCEL_BROWSER_MODE", "http").lower() in {"neo", "cdp"}:
            from .browser import NeoTextBrowser
            self.browser = NeoTextBrowser()
        else:
            self.browser = HybridTextBrowser()
        self.history = history or HistoryStore(LOCAL_DATA / "history.json")
        self.links: list[Link] = []
        self.current: PageData | None = None
        self.connected = False
        self.lock = threading.RLock()

    @staticmethod
    def validate(action: str, value: str = "") -> str:
        if action not in {"navigate", "search", "back", "forward", "reload", "more", "history"}:
            return "Lệnh không hỗ trợ."
        if action == "navigate":
            parsed = urlparse(value.strip())
            if parsed.scheme not in ("http", "https") or not parsed.netloc or parsed.username or parsed.password:
                return "Địa chỉ phải bắt đầu bằng http:// hoặc https://"
        if action == "search" and not value.strip():
            return "Nhập từ khóa tìm kiếm."
        return ""

    def publish_page(self, page: PageData, *, record_history: bool = True) -> dict:
        """One trusted serializer for synchronous and progressive responses."""
        old_url = self.current.url if self.current else None
        self.current = page
        self.links = page.links[:MAX_LINKS]
        if record_history or old_url != page.url:
            self.history.add(page.url, page.title)
        return {"ok": True, "page": {
            "title": visible_title(page.url, page.title),
            "url": page.url,
            "text": page.text[:MAX_TEXT],
            "links": [asdict(link) for link in self.links],
            "blocks": page.blocks,
            "notice": page.notice,
            "has_more": page.has_more,
        }}

    def open(self, action: str, value: str = "") -> dict:
        if action == "history":
            return {"ok": True, "history": [
                {**asdict(e), "title": visible_title(e.url, e.title)}
                for e in self.history.entries
            ], "page": None}
        invalid = self.validate(action, value)
        if invalid:
            return {"ok": False, "error": invalid}
        if action == "navigate":
            url = value.strip()
            operation = lambda: self.browser.navigate(url)
        elif action == "search":
            if not value.strip():
                return {"ok": False, "error": "Nhập từ khóa tìm kiếm."}
            operation = lambda: self.browser.search(value.strip())
        elif action == "back":
            operation = self.browser.back
        elif action == "forward":
            operation = self.browser.forward
        elif action == "more":
            if not hasattr(self.browser, "load_more"):
                return {"ok": False, "error": "Trang này không hỗ trợ tải thêm."}
            operation = self.browser.load_more
        else:
            operation = self.browser.reload
        if not self.connected:
            self.browser.connect()
            self.connected = True
        page = operation()
        if page is None:
            return {"ok": False, "error": "Không có trang trước / sau."}
        return self.publish_page(page)

    def close(self) -> None:
        if self.connected:
            self.browser.close()
            self.connected = False


class AddinHandler(BaseHTTPRequestHandler):
    service: BrowserService
    jobs = None  # Set by run(); legacy HTTP tests can use the handler alone.
    # Polling reuses one HTTPS connection instead of a new TLS handshake for
    # every progress update. All responses have explicit Content-Length.
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt: str, *args: object) -> None:
        LOG.info("%s %s", self.address_string(), fmt % args)

    def _headers(self, status: int, content_type: str, length: int) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(length))
        self.send_header("Cache-Control", "public, max-age=86400" if content_type == "image/png" else "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()

    def _send(self, status: int, payload: bytes, mime: str) -> None:
        self._headers(status, mime, len(payload))
        self.wfile.write(payload)

    def _json(self, status: int, obj: dict) -> None:
        self._send(status, json.dumps(obj, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")

    def _trusted_host(self) -> bool:
        return self.headers.get("Host", "").lower() in {f"localhost:{PORT}", f"127.0.0.1:{PORT}"}

    def do_GET(self) -> None:
        if not self._trusted_host():
            self._json(403, {"ok": False, "error": "Invalid host"})
            return
        if self.headers.get("Origin") not in (None, BASE_URL):
            self._json(403, {"ok": False, "error": "Invalid origin"})
            return
        path = self.path.split("?", 1)[0]
        if path.startswith("/api/jobs/"):
            job_id = path.removeprefix("/api/jobs/")
            if (self.jobs is None or not re.fullmatch(r"[0-9a-f]{32}", job_id)):
                self._json(404, {"ok": False, "error": "Unknown job"})
                return
            try:
                since = max(0, int(parse_qs(urlparse(self.path).query).get("since", ["0"])[0]))
            except ValueError:
                self._json(400, {"ok": False, "error": "Invalid version"})
                return
            snapshot = self.jobs.snapshot(job_id, since)
            self._json(200 if snapshot else 404, snapshot or {"ok": False, "error": "Unknown job"})
            return
        if path == "/api/health":
            self._json(200, {"ok": True, "connected": self.service.connected})
            return
        asset = {
            "/": ("index.html", "text/html; charset=utf-8"),
            "/index.html": ("index.html", "text/html; charset=utf-8"),
            "/app.js": ("app.js", "application/javascript; charset=utf-8"),
            "/style.css": ("style.css", "text/css; charset=utf-8"),
            "/icon.png": ("icon.png", "image/png"),
        }.get(path)
        if asset is None:
            self._json(404, {"ok": False, "error": "Not found"})
            return
        name, mime = asset
        try:
            self._send(200, (WEB_ROOT / name).read_bytes(), mime)
        except FileNotFoundError:
            self._json(404, {"ok": False, "error": "Asset missing"})

    def do_POST(self) -> None:
        if not self._trusted_host() or self.headers.get("Origin") != BASE_URL:
            self._json(403, {"ok": False, "error": "Invalid origin"})
            return
        if self.path not in {"/api/browse", "/api/jobs"} or self.headers.get("Content-Type", "").split(";")[0].strip().lower() != "application/json":
            self._json(404, {"ok": False, "error": "Endpoint not found"})
            return
        try:
            size = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            size = 0
        if not 0 < size <= MAX_REQUEST_SIZE:
            self._json(413, {"ok": False, "error": "Request too large"})
            return
        try:
            request = json.loads(self.rfile.read(size))
            action, value = str(request.get("action", "")), str(request.get("value", ""))
            if self.path == "/api/jobs":
                if self.jobs is None:
                    self._json(503, {"ok": False, "error": "Jobs unavailable"})
                    return
                result = self.jobs.start(action, value)
                self._json(202 if result["ok"] else 400, result)
            else:
                with getattr(self.service, "lock", nullcontext()):
                    result = self.service.open(action, value)
                self._json(200, result)
        except Exception as exc:
            LOG.exception("Browser command failed")
            self._json(500, {"ok": False, "error": f"Không thể tải trang: {str(exc)[:220]}"})


def run() -> None:
    LOCAL_DATA.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        filename=str(LOCAL_DATA / "addin.log"),
        encoding="utf-8", level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    cert = CERT_ROOT / "localhost.crt"
    key = CERT_ROOT / "localhost.key"
    if not cert.is_file() or not key.is_file():
        raise RuntimeError("Chưa có Office localhost certificate. Xem README để cài chứng chỉ một lần.")
    service = BrowserService()
    from .jobs import BrowseJobs
    jobs = BrowseJobs(service)
    handler = type("LocalHandler", (AddinHandler,), {"service": service, "jobs": jobs})
    servers = create_loopback_servers(handler, PORT)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(str(cert), str(key))
    for server in servers:
        server.socket = context.wrap_socket(server.socket, server_side=True)
    ipv6_thread = None
    if len(servers) > 1:
        ipv6_thread = threading.Thread(target=servers[1].serve_forever,
                                       name="excel-ipv6-loopback", daemon=True)
        ipv6_thread.start()
    LOG.info("Excel Text Browser add-in server ready on %s (%d loopback listeners)",
             BASE_URL, len(servers))
    try:
        servers[0].serve_forever(poll_interval=0.35)
    finally:
        if ipv6_thread:
            servers[1].shutdown()
            ipv6_thread.join(timeout=2)
        for server in servers:
            server.server_close()
        jobs.close()
        service.close()


if __name__ == "__main__":
    run()
