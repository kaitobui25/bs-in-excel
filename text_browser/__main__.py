"""Application coordinator. Excel IO, command parsing and CDP stay separate."""
from __future__ import annotations

import argparse
import logging
import time

import pythoncom
import pywintypes

from .browser import ChromeTextBrowser, Link, PageData
from .config import LOCAL_DATA, POLL_INTERVAL_SECONDS
from .excel_ui import ExcelUI
from .history import HistoryStore
from .navigation import Command, parse_command

logger = logging.getLogger(__name__)


class TextBrowserApp:
    def __init__(self, excel: ExcelUI, browser: ChromeTextBrowser, history: HistoryStore):
        self.excel = excel
        self.browser = browser
        self.history = history
        self.displayed_links: list[Link] = []

    def _show(self, data: PageData) -> None:
        self.displayed_links = self.excel.show_page(data)
        self.history.add(data.url, data.title)

    def execute(self, raw: str) -> None:
        command: Command = parse_command(raw)
        if command.action == "noop":
            return
        if command.action == "invalid":
            self.excel.status(command.value)
            return

        if command.action == "help":
            self.displayed_links = []
            self.excel.show_help()
            return
        if command.action == "history":
            self.displayed_links = [
                Link(item.title, item.url) for item in self.history.entries
            ]
            self.excel.show_history(self.displayed_links)
            return
        if command.action == "open_link":
            index = int(command.value) - 1
            if not 0 <= index < len(self.displayed_links):
                self.excel.status("Số liên kết không hợp lệ. Gõ :history hoặc mở một trang.")
                return
            command = Command("navigate", self.displayed_links[index].url)

        self.excel.status("Đang tải trang...")
        try:
            if command.action == "search":
                result = self.browser.search(command.value)
            elif command.action == "navigate":
                result = self.browser.navigate(command.value)
            elif command.action == "back":
                result = self.browser.back()
            elif command.action == "forward":
                result = self.browser.forward()
            elif command.action == "reload":
                result = self.browser.reload()
            else:
                raise ValueError(f"Unsupported command: {command.action}")
            if result is None:
                self.excel.status("Không có trang trước / sau.")
                return
            self._show(result)
        except Exception as exc:
            logger.exception("Navigation failed")
            self.excel.status(f"Lỗi tải trang: {str(exc)[:220]}")

    def run(self, initial_url: str | None = None) -> None:
        self.excel.status("Đang kết nối Chrome Profile 3... Nếu được hỏi, chọn Allow trong Chrome.")
        try:
            self.browser.connect()
        except Exception:
            logger.exception("Chrome CDP connection not approved or unavailable")
            self.excel.status("Chrome chưa kết nối. Chấp thuận 'Allow remote debugging?' trên Chrome rồi chạy lại start.ps1.")
            return
        self.excel.show_help()
        if initial_url:
            self.execute(initial_url)
        while True:
            try:
                value = self.excel.pop_command()
                if value:
                    logger.info("Executing input command")
                    self.execute(value)
            except pywintypes.com_error:
                # Excel may temporarily reject COM while editing a cell/dialog.
                logger.debug("Excel is temporarily busy", exc_info=True)
            time.sleep(POLL_INTERVAL_SECONDS)


def main() -> None:
    parser = argparse.ArgumentParser(description="Text-only browser inside the currently open Excel workbook")
    parser.add_argument("--url", help="Optional first URL displayed on startup")
    args = parser.parse_args()
    LOCAL_DATA.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        filename=str(LOCAL_DATA / "browser.log"),
        encoding="utf-8",
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    # A file lock prevents two watchers from competing over Excel cell C4.
    with (LOCAL_DATA / "instance.lock").open("a+b") as lock:
        try:
            msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError:
            logger.warning("Excel Text Browser is already running")
            return
        pythoncom.CoInitialize()
        browser = ChromeTextBrowser()
        try:
            app = TextBrowserApp(ExcelUI(), browser, HistoryStore(LOCAL_DATA / "history.json"))
            app.run(initial_url=args.url)
        except KeyboardInterrupt:
            pass
        except Exception:
            logger.exception("Unexpected application error")
            raise
        finally:
            browser.close()
            pythoncom.CoUninitialize()


if __name__ == "__main__":
    main()
