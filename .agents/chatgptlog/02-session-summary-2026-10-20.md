# ChatGPT Log — bs-in-excel

Ngày tổng hợp: 2026-10-20. Tài liệu bàn giao tiến độ và các quyết định kỹ thuật đã thực hiện trong dự án.

## Mục tiêu

Xây dựng trình duyệt **chỉ hiển thị văn bản** bên trong Excel Content Add-in: nhập URL, tìm kiếm, điều hướng Back/Forward/Reload, lịch sử, liên kết có thể bấm và đọc Bảng tin Facebook mà không hiển thị hình ảnh/video. Ưu tiên code dễ bảo trì, hiệu năng, và không tạo tab Facebook trùng trong BrowserOS Neo.

## Kiến trúc hiện tại

- **Excel UI:** `addin/index.html`, `addin/app.js`, `addin/style.css`.
- **Backend HTTPS:** `text_browser/service.py`, phục vụ tại `https://127.0.0.1:3010`.
- **Trang thông thường:** tải HTTP và chuyển HTML thành văn bản qua `text_browser/http_browser.py`, `text_browser/html_content.py`.
- **Facebook:** `text_browser/hybrid_browser.py` trích xuất bài viết từ DOM qua `text_browser/neo_mcp.py` và BrowserOS Neo MCP tại `http://127.0.0.1:9010/mcp`.
- **Bộ lọc quảng bá Facebook:** `text_browser/facebook_ads.py`; **bộ lọc tiêu đề:** `text_browser/title_filter.py`.
- **Khởi động/cài đặt:** `run_addin.pyw`, `Open Text Browser.vbs`, `install_once.ps1`, `Install Text Browser.cmd`.

## Công việc đã hoàn thành

1. **Chuyển Facebook từ Chrome/Playwright sang BrowserOS Neo MCP:** dùng JSON-RPC HTTP, duy trì phiên, trích xuất bài viết thành văn bản, xử lý phiên MCP hết hạn và giữ giao diện/API Excel ổn định.
2. **Lọc tiêu đề theo domain:** chỉ hiện tiêu đề trang lớn cho `siemens.com` và subdomain; các trang Facebook, mạng xã hội, báo và web khác không hiện tiêu đề lớn. Có thể mở rộng danh sách `TITLE_HOSTS`.
3. **Tái sử dụng tab Facebook:** lưu `tabId` và `groupId` trong `%LOCALAPPDATA%\bs-in-excel\neo-facebook-tab.json`, nhận lại tab do add-in quản lý qua các phiên MCP/backend, tránh chiếm tab cá nhân và không tự đóng tab khi backend dừng.
4. **Lọc quảng cáo Facebook:** loại bài có nhãn tài trợ và nhiều bài quảng bá không có nhãn bằng tín hiệu kết hợp: CTA (inbox, liên hệ, đặt hàng, nút Send message), khuyến mãi, giá, dịch vụ/sản phẩm, trang doanh nghiệp, link ngoài, tuyển sinh và bài giới thiệu thương hiệu bằng tiếng Việt/Nhật/Trung. Ghi nhớ khóa bài đã loại để không tính chúng vào số bài cần tải thêm.
5. **Cải thiện giao diện:** khi mở trang/tải lại, xóa nội dung cũ dưới trạng thái “Đang tải”; thao tác “Tải thêm” vẫn giữ nội dung đang đọc.
6. **Bổ sung kiểm thử:** các mẫu quảng cáo từ ảnh thực tế gồm J-Connect, Travel’s One, HACHI, Mobi JP, Global Bridge Japan, Mtrend, cửa hàng lặn, nha khoa và nhãn nệm Nhật; đồng thời kiểm tra tránh lọc nhầm bài cá nhân.

## Xác minh gần nhất

- Bộ kiểm thử: **64/64 đạt** (`python -m unittest discover -s tests -q`).
- Kiểm tra cú pháp Python, `node --check addin/app.js`, và `git diff --check`: đạt.
- Thử trực tiếp qua API Excel trên Facebook: số bài trả về ở các lượt mở trang/tải thêm là **1 → 6 → 11**; không xuất hiện các tên quảng cáo đã đối chiếu trong kết quả đó.
- Số tab Facebook trước/sau thử nghiệm: **2 → 2**, tiếp tục sử dụng tab Excel đã quản lý.
- Backend cuối cùng đã khởi động lại và trả health HTTP 200; PID tại thời điểm xác minh: `34084` (PID có thể thay đổi).
- Đây là kết quả kiểm thử tại thời điểm thực hiện, **không phải cam kết lọc hết quảng cáo trên mọi Bảng tin**.

## Giới hạn và lưu ý vận hành

- Bộ lọc quảng cáo là **rule-based, best-effort**: có thể còn quảng cáo lọt hoặc loại nhầm bài thương mại mang tính thảo luận. Facebook có thể đổi DOM hoặc cách hiển thị nội dung.
- Cần mở BrowserOS Neo và đăng nhập Facebook trong profile Neo; không tự vượt CAPTCHA/đăng nhập.
- Các tab trùng tạo từ phiên bản cũ không được tự động đóng để tránh ảnh hưởng tab của người dùng.
- Chế độ mặc định ưu tiên HTTP cho website thông thường; `BS_EXCEL_BROWSER_MODE=neo` dùng Neo cho các trang khác nếu cần.
- Chứng chỉ phát triển Office localhost từng được ghi nhận hết hạn ngày **2026-11-04**; cần kiểm tra và gia hạn trước khi sử dụng sau thời điểm đó.
- Dữ liệu đăng nhập, cookie, lịch sử cá nhân và file nhận diện tab được giữ cục bộ, không đưa vào Git.

## Mốc Git liên quan

| Commit | Nội dung |
| --- | --- |
| `bae9b35` | Chuyển backend sang BrowserOS Neo MCP |
| `65027a3` | Lọc bài tài trợ Facebook, khôi phục session Neo hết hạn |
| `5d6d726` | Chỉ hiển thị tiêu đề lớn cho domain Siemens |
| `bb50db9` | Tái sử dụng tab Facebook giữa các phiên MCP |
| `0aefb54` | Nâng cấp lọc bài quảng bá Facebook đa ngôn ngữ |

## Hướng tiếp theo

- Tiếp tục thu thập **mẫu bài quảng cáo lọt và bài bị lọc nhầm** làm regression tests; cân nhắc chuyển các quy tắc nhận diện sang cấu hình có thể bảo trì thay vì thêm regex không kiểm soát.
- Theo dõi thay đổi DOM Facebook và thời gian tải bài, tránh cuộn vô hạn khi số bài bị loại cao.
- Kiểm tra chứng chỉ localhost, thời gian phản hồi và quyền truy cập endpoint Neo trước khi triển khai lâu dài.

Tham khảo hướng dẫn chạy/cài đặt và chi tiết kỹ thuật trong [`README.md`](README.md).
