"""Non-blocking navigation jobs with small, latest-only progress snapshots.

HTTP documents are fetched independently so a slow Neo tab cannot block a
new regular website. Neo operations remain serialized on their shared tab.
Only the newest job may publish or change browser history.
"""
from __future__ import annotations

import logging
import threading
import time
import uuid
from concurrent.futures import CancelledError, ThreadPoolExecutor
from dataclasses import dataclass, field

from .browser import PageData
from .http_browser import HttpTextBrowser
from .hybrid_browser import HybridTextBrowser, FacebookNeo, is_facebook_url
from .service import BrowserService


LOG = logging.getLogger(__name__)
JOB_TTL = 120  # seconds after completion
JOB_DEADLINE = 120  # bound user-visible waiting even if a browser stalls
MAX_JOBS = 12


@dataclass
class BrowseJob:
    id: str
    action: str
    value: str
    created: float = field(default_factory=time.monotonic)
    version: int = 0
    status: str = "pending"
    result: dict | None = None
    error: str = ""
    committed: bool = False
    finished: float = 0
    first_published: float = 0


class BrowseJobs:
    """Manage one active navigation without blocking the local HTTPS server."""

    def __init__(self, service: BrowserService):
        self.service = service
        self._lock = threading.RLock()
        self._neo_lock = threading.Lock()
        self._http_workers = ThreadPoolExecutor(max_workers=4, thread_name_prefix="excel-http")
        self._neo_workers = ThreadPoolExecutor(max_workers=2, thread_name_prefix="excel-neo")
        self._jobs: dict[str, BrowseJob] = {}
        self._active: str | None = None

    def _prune(self) -> None:
        now = time.monotonic()
        for key, job in list(self._jobs.items()):
            if job.finished and now - job.finished > JOB_TTL:
                del self._jobs[key]
        if len(self._jobs) > MAX_JOBS:
            for key, job in list(self._jobs.items()):
                if len(self._jobs) <= MAX_JOBS:
                    break
                if key != self._active and job.status != "pending":
                    del self._jobs[key]

    def start(self, action: str, value: str = "") -> dict:
        problem = self.service.validate(action, value)
        if problem:
            return {"ok": False, "error": problem}
        job = BrowseJob(uuid.uuid4().hex, action, value)
        with self._lock:
            if self._active in self._jobs:
                previous = self._jobs[self._active]
                if previous.status in {"pending", "partial"}:
                    previous.status = "cancelled"
                    previous.finished = time.monotonic()
                    previous.version += 1
            self._jobs[job.id] = job
            self._active = job.id
            self._prune()
        worker = self._neo_workers if self._needs_neo(action, value) else self._http_workers
        worker.submit(self._run, job)
        return {"ok": True, "job_id": job.id}

    def _needs_neo(self, action: str, value: str) -> bool:
        browser = self.service.browser
        if not isinstance(browser, HybridTextBrowser):
            return True
        if action == "more":
            return True
        if action in {"search", "history"}:
            return False
        if action == "navigate":
            return is_facebook_url(value)
        with self.service.lock:
            position = browser.position
            if action == "back":
                position -= 1
            elif action == "forward":
                position += 1
            if 0 <= position < len(browser.urls):
                return is_facebook_url(browser.urls[position])
        return False

    def snapshot(self, job_id: str, since: int = 0) -> dict | None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return None
            if job.status in {"pending", "partial"} and time.monotonic() - job.created > JOB_DEADLINE:
                job.status = "error"
                job.error = "Quá thời gian tải trang; hãy thử tải lại."
                job.finished = time.monotonic()
                job.version += 1
                if self._active == job.id:
                    self._active = None
            changed = job.version > since
            return {"ok": True, "version": job.version, "status": job.status,
                    "result": job.result if changed else None,
                    "error": job.error if changed else ""}

    def _is_active(self, job: BrowseJob) -> bool:
        with self._lock:
            return self._active == job.id and job.status in {"pending", "partial"}

    def _position(self, job: BrowseJob) -> tuple[str, int | None]:
        with self.service.lock:
            browser = self.service.browser
            urls, position = browser.urls, browser.position
            if job.action == "navigate":
                return job.value.strip(), None
            if job.action == "search":
                return "", None
            if position < 0:
                raise ValueError("Chưa có trang để tải lại.")
            if job.action == "back":
                if position <= 0:
                    raise ValueError("Không có trang trước.")
                return urls[position - 1], position - 1
            if job.action == "forward":
                if position + 1 >= len(urls):
                    raise ValueError("Không có trang sau.")
                return urls[position + 1], position + 1
            return urls[position], position

    def _publish(self, job: BrowseJob, page: PageData, target_position: int | None,
                 *, final: bool = False) -> None:
        with self._lock:
            if self._active != job.id or job.status not in {"pending", "partial"}:
                return
            with self.service.lock:
                browser = self.service.browser
                if not job.committed and job.action in {"navigate", "search"}:
                    browser.urls = browser.urls[:browser.position + 1] + [page.url]
                    browser.position += 1
                elif not job.committed and job.action in {"back", "forward"}:
                    browser.position = target_position
                if not self.service.connected:
                    browser.connect()
                    self.service.connected = True
                result = self.service.publish_page(page, record_history=not job.committed)
            if not job.first_published:
                job.first_published = time.monotonic()
                LOG.info("Browse %s %s: first content %.0f ms", job.id[:8], job.action,
                         (job.first_published - job.created) * 1000)
            job.committed = True
            job.result = result
            job.status = "complete" if final else "partial"
            job.version += 1
            if final:
                job.finished = time.monotonic()
                LOG.info("Browse %s %s: complete %.0f ms", job.id[:8], job.action,
                         (job.finished - job.created) * 1000)

    def _run_hybrid(self, job: BrowseJob) -> None:
        url, position = self._position(job)
        def emit(page: PageData) -> None:
            self._publish(job, page, position)

        if job.action == "more":
            with self._neo_lock:
                if not self._is_active(job):
                    return
                browser = self.service.browser
                if not is_facebook_url(url) or browser._facebook is None:
                    raise ValueError("Tải thêm chỉ áp dụng cho trang Facebook đang mở.")
                page = browser._facebook.load_more(on_progress=emit)
        elif job.action == "search" or not is_facebook_url(url):
            # A fresh session per HTTP worker prevents concurrent requests from
            # sharing requests.Session or mutating Neo navigation state.
            local = HttpTextBrowser()
            try:
                if job.action == "search":
                    page = local.search(job.value.strip())
                else:
                    page = local._fetch(url, on_progress=emit,
                                        is_cancelled=lambda: not self._is_active(job))
            finally:
                local.close()
        else:
            with self._neo_lock:
                if not self._is_active(job):
                    return
                browser = self.service.browser
                if browser._facebook is None:
                    browser._facebook = FacebookNeo()
                page = browser._facebook.navigate(url, on_progress=emit)
        self._publish(job, page, position, final=True)

    def _run(self, job: BrowseJob) -> None:
        try:
            if not self._is_active(job):
                return
            if job.action == "history":
                with self.service.lock:
                    result = self.service.open("history")
                with self._lock:
                    if self._active == job.id:
                        job.result = result
                        job.status = "complete"
                        job.version += 1
                        job.finished = time.monotonic()
            elif isinstance(self.service.browser, HybridTextBrowser):
                self._run_hybrid(job)
            else:
                # Explicit all-Neo mode preserves its original navigation API.
                with self._neo_lock:
                    if not self._is_active(job):
                        return
                    with self.service.lock:
                        result = self.service.open(job.action, job.value)
                    with self._lock:
                        if self._active == job.id:
                            job.result = result
                            job.status = "complete" if result.get("ok") else "error"
                            job.error = result.get("error", "")
                            job.version += 1
                            job.finished = time.monotonic()
        except CancelledError:
            pass
        except Exception as exc:
            if isinstance(exc, ValueError):
                LOG.info("Invalid navigation (%s): %s", job.action, exc)
            else:
                LOG.exception("Navigation job failed (%s)", job.action)
            with self._lock:
                if self._active == job.id and job.status in {"pending", "partial"}:
                    job.status = "error"
                    job.error = f"Không thể tải trang: {str(exc)[:220]}"
                    job.version += 1
                    job.finished = time.monotonic()

    def close(self) -> None:
        with self._lock:
            self._active = None
        self._http_workers.shutdown(wait=False, cancel_futures=True)
        self._neo_workers.shutdown(wait=False, cancel_futures=True)
