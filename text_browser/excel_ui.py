"""Excel's worksheet is the entire UI: no VBA, add-in, or embedded web view."""
from __future__ import annotations

import textwrap
from collections.abc import Sequence

import win32com.client

from .browser import Link, PageData
from .config import MAX_BODY_LINES, MAX_LINKS, SHEET_NAME

FIRST_ROW = 12
LAST_ROW = 239
ROW_CAPACITY = LAST_ROW - FIRST_ROW + 1


def _rgb(red: int, green: int, blue: int) -> int:
    return red | (green << 8) | (blue << 16)


def page_rows(data: PageData) -> tuple[list[tuple[str, str, str]], list[Link]]:
    """Prepare one dense, bulk Excel write. Return only links visible on screen."""
    rows: list[tuple[str, str, str]] = []
    text_lines: list[str] = []
    for paragraph in data.text.splitlines():
        content = paragraph.strip()
        if not content:
            continue
        text_lines.extend(textwrap.wrap(content, width=105, break_long_words=True))
        if len(text_lines) >= MAX_BODY_LINES:
            break

    rows.append(("", "NỘI DUNG TEXT", ""))
    rows.extend(("", line[:32000], "") for line in text_lines[:MAX_BODY_LINES])
    rows.append(("", "", ""))
    rows.append(("", "LIÊN KẾT — gõ :open N vào C4 để mở", ""))
    visible = data.links[:MAX_LINKS]
    rows.extend((str(i), link.title, link.url) for i, link in enumerate(visible, 1))
    return rows[:ROW_CAPACITY], visible


def history_rows(items: Sequence[Link]) -> list[tuple[str, str, str]]:
    rows = [("", "LỊCH SỬ — gõ :open N vào C4 để mở lại", "")]
    rows.extend((str(i), item.title, item.url) for i, item in enumerate(items, 1))
    return rows[:ROW_CAPACITY]


class ExcelUI:
    def __init__(self):
        self.excel = win32com.client.GetActiveObject("Excel.Application")
        self.workbook = self.excel.ActiveWorkbook
        if self.workbook is None or self.workbook.Name.upper() == "PERSONAL.XLSB":
            raise RuntimeError("Mở một workbook thông thường trong Excel trước khi chạy.")
        try:
            self.sheet = self.workbook.Worksheets(SHEET_NAME)
        except Exception:
            self.sheet = self.workbook.Worksheets.Add(
                After=self.workbook.Worksheets(self.workbook.Worksheets.Count)
            )
            self.sheet.Name = SHEET_NAME
        self._format_sheet()

    def _format_sheet(self) -> None:
        sh = self.sheet
        sh.Columns("A:A").ColumnWidth = 3
        sh.Columns("B:B").ColumnWidth = 10
        sh.Columns("C:C").ColumnWidth = 94
        sh.Columns("D:D").ColumnWidth = 70
        sh.Rows("1:1").RowHeight = 31
        sh.Range("C1").Value2 = "TEXT BROWSER  /  EXCEL + CHROME"
        sh.Range("B1:D1").Interior.Color = _rgb(32, 45, 63)
        sh.Range("B1:D1").Font.Color = _rgb(255, 255, 255)
        sh.Range("B1:D1").Font.Bold = True
        sh.Range("B1:D1").Font.Size = 15
        sh.Range("B2").Value2 = "Nhập URL / từ khóa Google:"
        sh.Range("C4").Interior.Color = _rgb(235, 244, 255)
        sh.Range("C4").Font.Size = 13
        sh.Range("C4").NumberFormat = "@"
        sh.Rows("4:4").RowHeight = 28
        sh.Range("B4").Value2 = "GO / SEARCH"
        sh.Range("B5").Value2 = "COMMANDS"
        sh.Range("C5").Value2 = ":back     :forward     :reload     :history     :open N     :help"
        sh.Range("B6").Value2 = "STATUS"
        sh.Range("B8").Value2 = "TITLE"
        sh.Range("B9").Value2 = "URL"
        sh.Range("B11:D11").Value2 = (("NO.", "TEXT CONTENT / LINK TITLE", "LINK URL"),)
        sh.Range("B11:D11").Font.Bold = True
        sh.Range("B11:D11").Interior.Color = _rgb(220, 231, 242)
        sh.Range("C8:C9").NumberFormat = "@"
        sh.Range("B12:D239").NumberFormat = "@"
        sh.Range("B12:D239").Font.Name = "Aptos"
        sh.Range("B12:D239").Font.Size = 10
        sh.Range("B12:D239").VerticalAlignment = -4108  # xlCenter
        sh.Range("D12:D239").Font.Color = _rgb(62, 104, 152)
        sh.Activate()
        sh.Range("C4").Select()

    def pop_command(self) -> str:
        raw = self.sheet.Range("C4").Value2
        if not isinstance(raw, str) or not raw.strip():
            return ""
        # A command is sent by typing in C4 and pressing Enter.
        self.sheet.Range("C4").ClearContents()
        return raw.strip()

    def status(self, message: str) -> None:
        self.sheet.Range("C6").Value2 = message[:300]

    def _write_rows(self, rows: Sequence[tuple[str, str, str]]) -> None:
        padded = list(rows[:ROW_CAPACITY])
        padded.extend([("", "", "")] * (ROW_CAPACITY - len(padded)))
        self.sheet.Range(f"B{FIRST_ROW}:D{LAST_ROW}").Value2 = tuple(padded)

    def show_page(self, data: PageData) -> list[Link]:
        self.sheet.Range("C8").Value2 = data.title[:32000]
        self.sheet.Range("C9").Value2 = data.url[:32000]
        rows, links = page_rows(data)
        self._write_rows(rows)
        self.status(f"Đã tải. {len(data.text):,} ký tự / {len(links)} liên kết. Nhập vào C4 để tiếp tục.")
        return links

    def show_history(self, items: Sequence[Link]) -> None:
        self._write_rows(history_rows(items))
        self.status(f"Lịch sử: {len(items)} trang. Nhập :open N để mở lại.")

    def show_help(self) -> None:
        self._write_rows([
            ("", "Nhập URL: https://www.siemens.com/ja-jp/products/tia-portal/", ""),
            ("", "Tìm Google: siemens tia portal", ""),
            ("", ":back / :forward — điều hướng", ""),
            ("", ":reload — tải lại trang", ""),
            ("", ":history — hiển thị lịch sử", ""),
            ("", ":open 1 — mở liên kết số 1 của danh sách hiện tại", ""),
            ("", ":help — hướng dẫn này", ""),
        ])
        self.status("Sẵn sàng. Không yêu cầu VBA / macro.")
