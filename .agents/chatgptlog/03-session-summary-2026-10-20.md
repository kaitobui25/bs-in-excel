# 03 — Tổng hợp session: Facebook reader và tối ưu tốc độ Excel Add-in

**Ngày:** 2026-10-20

**Dự án:** `bs-in-excel` / Text Browser in Excel

**Workspace:** `C:\phong\AI\other\bs-in-excel\main`
**Phạm vi:** Các yêu cầu và thay đổi tiếp theo tài liệu `02-session-summary-2026-10-20.md`. Đây là bản bàn giao kỹ thuật, **không phải transcript**.

## 1. Yêu cầu của người dùng

1. **Đưa working tree về trạng thái sạch trước khi sửa lỗi**, lưu riêng các thay đổi giao diện đã có.
2. Sửa lỗi Facebook hiển thị chuỗi chữ vô nghĩa, mỗi ký tự xuống một dòng, trước phần nội dung thật của bài viết.
3. Cải thiện bộ lọc quảng cáo Facebook vì vẫn còn các bài quảng bá **ChatGPT**, **WiFi**, **Vật Vờ Studio** và những lời chào bán khác.
4. Đối với bài Facebook dài, **mặc định chỉ hiện 4 dòng đầu**, có **See more / See less**; bài ngắn không có nút thừa.
5. Tìm nguyên nhân **BrowserOS Neo đã hiện website nhưng Excel chậm 30–45 giây**, cả với các website không phải Facebook. Ban đầu chỉ được nghiên cứu, **không sửa code**.
6. Nghiên cứu và so sánh ba phương án tăng tốc, sau đó triển khai **phương án 2 (asynchronous + progressive rendering) kết hợp nền tảng phương án 1**.
7. Viết tổng hợp session vào **thư mục sẵn có** `.agents/chatgptlog`; không tạo một thư mục `chatgptlog` mới ở vị trí khác.

## 2. Sửa lỗi trích xuất Facebook

### Chuỗi metadata bị làm rối

- Kiểm tra trực tiếp DOM của tab Facebook do add-in quản lý trong BrowserOS Neo xác nhận chuỗi lạ nằm trong **liên kết metadata gần tác giả/timestamp**, không nằm trong nội dung bài viết.
- Các ký tự được Facebook đặt trong nhiều `<span>`, có **U+034F COMBINING GRAPHEME JOINER**; CSS định vị từng span khiến `innerText` của toàn thẻ bài viết tạo ra các dòng rời rạc.
- Nguyên nhân ở reader: dùng `el.innerText` cho cả card, trộn phần header bị obfuscate vào nội dung.
- Sửa `text_browser/hybrid_browser.py`: ưu tiên văn bản từ `[data-ad-preview="message"]`, giữ đường dự phòng cho bố cục Facebook cũ, bỏ liên kết metadata mang nhiều ký tự U+034F nhưng vẫn giữ link bài viết và preview.
- Thêm `tests/test_facebook_dom_extraction.py` để kiểm tra bài thật còn nguyên, chuỗi U+034F bị bỏ và fallback hoạt động.

### Lọc quảng cáo lọt

Các mẫu do người dùng cung cấp đã được biến thành regression tests:

- **ChatGPT (tiếng Nhật):** quảng bá tạo hình ảnh, lời kêu gọi dùng thử miễn phí.
- **Internet JAPAN / WiFi:** giá cước, ưu đãi và liên hệ, viết bằng **Unicode cách điệu**.
- **Vật Vờ Studio:** giveaway Galaxy, yêu cầu follow/like/share/comment để nhận quà.
- **Rao bán bất động sản:** lô đất, mức giá, số điện thoại liên hệ.
- **Quảng bá plugin:** kêu gọi tải qua bình luận.

`text_browser/facebook_ads.py` thêm bước **Unicode NFKC normalization chỉ khi phân loại**, nhận diện CTA dùng thử, chương trình giveaway và một số tín hiệu rao bán khác. Có negative tests cho bài **chỉ thảo luận** ChatGPT/WiFi/thương hiệu/khuyến mãi để giảm lọc nhầm. Đây vẫn là bộ lọc **rule-based, best-effort**, không bảo đảm 100% quảng cáo bị loại.

### Rút gọn bài Facebook

- `addin/app.js` + `addin/style.css`: nội dung mỗi bài giới hạn **4 dòng hiển thị** bằng CSS line clamp.
- Bài dài có **See more** để mở hết và **See less** để thu gọn; bài ngắn không hiện nút.
- Trạng thái mở bài được duy trì khi tải thêm bài bằng **khóa định danh bài viết** do backend trả về.
- Link đính kèm bài viết bị thu gọn sẽ được hiện lại khi mở rộng.
- Bộ trích xuất bỏ chữ **“See less”** còn dính vào cuối văn bản Facebook.
- Không áp dụng quy tắc 4 dòng cho Siemens, trang tin, kết quả tìm kiếm hoặc website thường.

## 3. Phân tích độ trễ Excel so với BrowserOS Neo

**Quan sát:** Neo có thể render website sớm, nhưng phiên bản add-in trước đó chỉ gọi `showPage()` sau khi `fetch('/api/browse')` trả **toàn bộ JSON**. Backend sử dụng `HTTPServer` tuần tự nên một yêu cầu dài có thể chặn yêu cầu sau.

**Các phát hiện được kiểm tra:**

- Trang thường mặc định dùng `requests.get(..., timeout=12)` + BeautifulSoup, **không dùng Neo** (trừ chế độ `BS_EXCEL_BROWSER_MODE=neo`). Tìm kiếm có thể thử Yahoo sau Google.
- Phép đo độc lập trên máy tại thời điểm nghiên cứu: `example.com` ~**536 ms**, `siemens.com` ~**631 ms** để tải, parse và trích xuất HTML. Đây **không phải** thời gian end-to-end bên trong Excel.
- Log Neo có trường hợp **`run exceeded 30000ms`** trong thao tác tải thêm Facebook. Vấn đề Neo là có thật nhưng **không đủ giải thích mọi website chậm**.
- Backend và Excel trước khi sửa dùng giao thức trả dữ liệu theo một lần xử lý đồng bộ; không có kết quả từng phần, không ưu tiên và bỏ qua kết quả của yêu cầu cũ.
- Trong quá trình triển khai còn phát hiện `localhost` trên Windows ưu tiên `::1` trong khi backend cũ chỉ bind `127.0.0.1`: lúc đó đo `127.0.0.1` khoảng **55–89 ms**, còn `localhost` khoảng **2,5–4,4 s** đối với health API. Đây là phép đo kết nối cục bộ, không đại diện tốc độ tải trang.

### Ba phương án đã so sánh

| Phương án | Tư tưởng | Ưu điểm | Hạn chế |
| --- | --- | --- | --- |
| **1 — Tối ưu hiện tại** | Backend concurrency, HTTP fast path, timeout/cache, điều phối Neo | Đơn giản, ít thay đổi | Excel vẫn phải đợi phản hồi đầy đủ |
| **2 — Async + Progressive Rendering** | Tác vụ nền, trả phần nội dung có sớm, cập nhật tiếp | Giảm **thời gian chờ trước khi thấy nội dung** trên mọi trang | Thêm quản lý job, trạng thái và hủy yêu cầu |
| **3 — Event-driven/CDP sâu** | Theo dõi DOM/sự kiện Neo, trích xuất incremental | Tiềm năng tối ưu trang JS nặng | Phức tạp, phụ thuộc API Neo nhiều |

**Quyết định người dùng:** triển khai **phương án 2 + cải tiến nền tảng phương án 1**. Không theo đuổi phương án 3 ở session này.

## 4. Kiến trúc tăng tốc đã triển khai

```text
Excel Content Add-in (addin/app.js)
   ├─ POST /api/jobs → nhận job_id nhanh
   └─ GET /api/jobs/{job_id}?since=N → pending / partial / complete / error
         │
         ▼
Python ThreadingHTTPServer (text_browser/service.py)
         │
         ▼
BrowseJobs (text_browser/jobs.py)
   ├─ HTTP worker pool → HTTP streaming → parse HTML → preview → full page
   └─ Neo worker pool  → serialized tab operations → filtered preview → more posts
```

**Chi tiết chính:**

1. **`text_browser/jobs.py` (mới):** quản lý job theo ID ngẫu nhiên, phát snapshot mới nhất, hạn chế bộ nhớ, tự hết hạn khi chờ quá lâu; job mới thay thế job cũ và ngăn kết quả cũ ghi đè nội dung/history.
2. **`text_browser/service.py`:** thêm `POST /api/jobs`, `GET /api/jobs/<id>?since=<version>`; dùng `ThreadingHTTPServer`. Vẫn giữ `/api/browse` đồng bộ để tương thích. Tiếp tục kiểm tra `Host`, `Origin`, định dạng JSON, ID và phiên bản job.
3. **`text_browser/http_browser.py`:** với job progressive, đọc HTML theo chunk; khi đủ nội dung có thể phát **một preview** trước khi tải xong. Trang nhỏ có thể trả thẳng kết quả cuối. Mỗi worker dùng `requests.Session` riêng; việc hủy HTTP có hiệu lực khi đến lượt đọc chunk tiếp theo.
4. **`text_browser/hybrid_browser.py`:** lượt đầu Facebook đọc các bài sẵn có trước khi cuộn sâu; chỉ phát preview sau khi đã lọc quảng cáo. Sau đó tiếp tục thu thập bài mới; Neo trên một tab vẫn chạy tuần tự.
5. **`addin/app.js`:** polling ~**260 ms**, hiển thị snapshot mới khi nhận, có trạng thái đang tải tiếp; điều hướng mới dùng `AbortController` và request version để bỏ qua phản hồi cũ. Giữ Back/Forward/Reload/History và logic See more.
6. **`localhost` IPv4/IPv6:** server lắng nghe **`127.0.0.1` + `::1`** (chỉ loopback, không mở LAN), tránh chi phí thử IPv6 thất bại.
7. **HTTP/1.1 keep-alive:** tái sử dụng TLS connection cho polling liên tục, tránh handshake trên mỗi lần hỏi trạng thái.
8. **Log:** ghi thời gian từ khi tạo job tới **first content** và **complete** để có thể đo tiếp theo website.

## 5. Kiểm thử và số đo đã ghi nhận

- Sau phần sửa Facebook và lọc quảng cáo: **66 → 71 tests đạt** theo từng lần thay đổi.
- Sau tính năng See more: **72/72 tests đạt**.
- Sau kiến trúc progressive, IPv4/IPv6 và keep-alive: **82/82 tests đạt** khi chạy `python -m unittest discover -s tests -q`.
- `node --check addin/app.js`, `python -m compileall -q text_browser tests` và `git diff --check`: đạt tại các lượt kiểm tra liên quan.
- Kiểm thử mới bao gồm: preview xuất hiện trước nội dung đầy đủ; truy cập trang HTTP khi HTTP khác hoặc Neo đang chờ; hủy kết quả cũ; Back/Forward/Reload/History; job hết hạn; API localhost bảo vệ Origin; IPv4/IPv6 loopback; HTTP keep-alive trên cùng kết nối.
- Backend đã được khởi động lại sau triển khai, lắng nghe ở cả hai loopback; phản hồi health HTTP 200 và các endpoint job đã được kiểm tra. **PID tại thời điểm đó:** `33684`, không phải hằng số.
- Sau khi bật dual-loopback + keep-alive, đo `/api/health`: `localhost` lần đầu ~**70 ms**, các lần kế tiếp ~**1–81 ms**; `127.0.0.1` lần đầu ~**45 ms**, sau đó ~**1–2 ms**. Đây là **thời gian API**, không phải thời gian render end-to-end trong Excel.
- **Chưa xác nhận thực nghiệm thời gian hiển thị từng phần trên giao diện Excel thật** ở build cuối. Người dùng cần tải lại add-in để dùng `app.js` mới.

## 6. Các commit trong session (nhánh `main`)

| Commit | Nội dung |
| --- | --- |
| `69ba3dc` | Commit những thay đổi giao diện có sẵn để working tree sạch trước khi sửa bug |
| `d8cf97e` | Trích xuất phần body Facebook, bỏ metadata header bị làm rối |
| `6ac2d65` | Lọc Unicode cách điệu, CTA tiếng Nhật, giveaway và các bài rao bán |
| `1234889` | Thu gọn 4 dòng, nút See more/See less cho bài Facebook |
| `3dda697` | Jobs bất đồng bộ, progressive preview, xử lý điều hướng đồng thời |
| `ae63d51` | HTTPS localhost qua cả IPv4 và IPv6 loopback |
| `fa25e03` | HTTP/1.1 keep-alive cho polling API |

**HEAD tại thời điểm viết bản tổng hợp này:** `fa25e03`. Các commit trên là commit **cục bộ**, không có bằng chứng trong session rằng đã `git push`.

## 7. Giới hạn và việc cần xác minh tiếp

- **Progressive không đồng nghĩa tải xong nhanh hơn.** Trang HTML nhỏ thường trả ngay kết quả cuối; trang JavaScript nặng hoặc Neo vẫn có thể chờ DOM/navigation mới có nội dung.
- Một lệnh Neo đang chạy **không bị hủy cưỡng bức**; thao tác Neo tiếp theo trên cùng tab có thể phải chờ lệnh hiện tại hoàn thành hoặc timeout. HTTP mới không bị Neo chặn.
- Khi nội dung Facebook thay đổi DOM, các selector hoặc quy tắc lọc quảng cáo có thể cần cập nhật; tiếp tục thu thập case thật để tạo regression tests.
- Đo benchmark **Excel click → first meaningful text → complete** trên ít nhất ba nhóm: HTML tĩnh, website JS nặng, Facebook; so sánh khi backend rảnh và lúc Neo đang tải.
- Kiểm tra UI thực tế: bấm link nhanh liên tiếp, Back/Forward, lỗi tải, load-more, giữ See more và kết quả mới không bị ghi đè.
- Giữ nguyên chính sách chỉ hiển thị tiêu đề lớn cho **Siemens**; không mở ảnh/video và không can thiệp tab cá nhân trong Neo.
- Theo log cũ, chứng chỉ Office localhost có mốc hết hạn **2026-11-04**; cần kiểm tra/gia hạn trước khi hết hạn.
- Kiến trúc và hướng dẫn vận hành hiện tại được mô tả thêm trong `README.md`.

---

*Snapshot của session ngày 2026-10-20. Nội dung nào mới chỉ được xác nhận qua unit/integration tests được ghi tách biệt với thao tác UI Excel thực tế. Mốc thời gian, PID và số đo chỉ đại diện cho lần kiểm tra đã thực hiện.*
