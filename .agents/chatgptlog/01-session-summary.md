# 01 — Tổng hợp session: BS in Excel / Text Browser

**Ngày:** 2026-10-19  
**Dự án:** bs-in-excel  
**Repository:** https://github.com/kaitobui25/bs-in-excel  
**Workspace:** C:\phong\AI\other\bs-in-excel\main  
**Loại tài liệu:** Tóm tắt kỹ thuật của session, không phải bản chép nguyên văn.

## 1. Mục tiêu đã thống nhất

Xây dựng **trình duyệt web thuần text ngay trong Excel Desktop** trên máy Windows hiện tại:

- Duyệt URL, tìm kiếm, bấm liên kết, Back / Forward / Reload / History ngay trên giao diện add-in.
- Người dùng không cần nhập lệnh vào ô tính hoặc chạy PowerShell mỗi lần sử dụng.
- Thanh địa chỉ và các nút giữ vị trí cố định; nội dung cuộn riêng.
- Không hiển thị ảnh/video. Vị trí ảnh trong nội dung được thay bằng một khung nhỏ trống, không có text.
- Link phải mở đúng URL đích, bao gồm các liên kết tới anchor (#mục) khi có thể.
- Clean code, dễ bảo trì, nâng cấp, ưu tiên hiệu năng và ít phụ thuộc.
- Facebook phải mở bằng **phiên đã đăng nhập của Chrome Profile 3 đang chạy**, không phải Chrome profile độc lập.
- Không làm thay đổi workbook công việc của người dùng khi thử nghiệm.
- Không dùng Java/VBA; Office Add-in dùng JavaScript nhẹ để vận hành UI, chỉ hiển thị nội dung web dạng text.

## 2. Diễn biến phát triển

### Giai đoạn A — MVP bằng ô C4 (đã bỏ)

Phiên bản đầu tiên dùng Python + Excel COM (pywin32) + Chrome CDP. Tạo sheet Text Browser, nhập URL hoặc từ khóa ở C4 và dùng lệnh dạng :back, :open N, :history. Có ghi nhiều ô bằng một lệnh COM để giảm overhead.

Kiểm thử kỹ thuật đạt nhưng **UX không đạt**: phải mở PowerShell và nhớ cú pháp lệnh. Người dùng yêu cầu học theo add-in tham khảo và thao tác trực tiếp bên trong Excel. Vì vậy đã bỏ thiết kế polling ô tính.

### Giai đoạn B — Nghiên cứu reference và đổi sang Office Content Add-in

Reference từ C:\phong\AI\other\bs-in-excel\ref dẫn tới dự án LamLongChart, ví dụ examples\excel-content-addin. Kiến trúc được thay bằng:

    Excel Content Add-in (HTML / CSS / JavaScript)
        → HTTPS localhost API (Python)
        → Web reader
        → Nội dung text và link

Các thành phần chính: manifest.xml, add-in nhúng trong workbook, thanh URL, nút điều hướng, vùng nội dung cuộn.

### Giai đoạn C — Đưa add-in vào Excel thực tế

- Excel trên PC không có nút “Upload My Add-in” như hướng dẫn chung. Đã đăng ký Trusted Add-in Catalog theo cách FileSystem.
- Workbook do công cụ sideload tạo ban đầu tham chiếu Registry/developer, báo “only available during debugging”. Đã sửa web-extension reference sang FileSystem catalog.
- Tạo workbook Text Browser.xlsx; xác nhận HTML/CSS/JS và API localhost được tải từ Excel thật.
- Tạo shortcut Desktop **Text Browser Excel**, launcher VBS và backend Python chạy ẩn; hỗ trợ tự khởi động cùng Windows.
- Launcher được sửa để kích hoạt workbook đã mở, tránh mở thêm bản Read-Only.
- Bảo toàn các workbook công việc khác.

### Giai đoạn D — Reader text, link và ảnh đã lọc

- Các website HTML công khai, ví dụ Siemens TIA Portal, dùng requests/BeautifulSoup để giảm chi phí tải.
- Google đôi khi trả trang chuyển hướng khi truy vấn tự động. Công cụ có thể dùng **Yahoo! Japan làm kết quả dự phòng**; UI bỏ tiêu đề kỹ thuật dài theo yêu cầu. URL nguồn được giữ lại để không hiểu nhầm kết quả Yahoo là Google.
- Bộ chuyển HTML sang danh sách các block có thứ tự (heading, đoạn, link, anchor, image-placeholder), giữ tương đối đúng vị trí các thành phần trong nội dung.
- Link nằm ngay trong đoạn text bấm được; đã bấm kết quả Siemens trong add-in và xác nhận chuyển đến đúng URL Siemens.
- Ảnh không tải; UI hiển thị khung hình nhỏ không có nhãn chữ.
- Các nút và thanh địa chỉ giữ vị trí, chỉ vùng trang cuộn.

### Giai đoạn E — Facebook ban đầu và yêu cầu đăng nhập

- Truy cập HTTP trực tiếp vào Facebook bị từ chối hoặc trả nội dung không dùng được.
- Đã thử Chrome thật với profile riêng: xem được trang công khai, nhưng trang chủ xuất hiện login wall. Cách này **không đáp ứng** yêu cầu dùng Facebook đã đăng nhập.
- Tạo hybrid browser: HTTP cho trang thường, Chrome cho Facebook.

### Giai đoạn F — Facebook sử dụng chính Chrome Profile 3 (phiên bản hiện tại)

- Kiểm tra Chrome hiện có với --profile-directory="Profile 3"; Remote Debugging đang chạy trên localhost. Endpoint lấy từ file DevToolsActivePort, **không hard-code port**.
- Playwright CDP đã kết nối đúng instance Chrome Profile 3, tạo **một tab mới riêng do add-in quản lý**.
- Thử trực tiếp trong Profile 3: Facebook HTTP 200, không xuất hiện biểu mẫu password, nhiều link hiển thị. Không sao chép cookie, token hay file profile.
- Thay luồng Facebook từ launch_persistent_context (Chrome mới/profile riêng) sang connect_over_cdp và dùng browser context hiện hữu.
- Hộp thoại “Allow remote debugging?” có thể xuất hiện lần đầu hoặc khi kết nối lại; phải chấp thuận cho ứng dụng local tin cậy. Một số lần trước timeout vì Chrome đang chờ hộp thoại.
- Sau khi kết nối được backend Excel: Facebook hiển thị **1.839 ký tự text, 18 link** ở một lượt thử; các lượt tiếp theo mở trang Facebook/Siemens, Back/Forward và Siemens bình thường đều thành công, không cần cấp quyền lại trong cùng kết nối.
- Chỉ đóng **tab do add-in tạo**, không đóng browser/profile hoặc tab có sẵn. Chặn tải ảnh, video và font **trong tab add-in**, không áp dụng cho tab khác.
- Thêm thông báo dễ hiểu nếu Chrome chưa cấp quyền kết nối.

## 3. Kiến trúc mã hiện tại

    Text Browser.xlsx
       └─ addin/index.html + app.js + style.css
          └─ HTTPS https://localhost:3010
             └─ text_browser/service.py
                └─ HybridTextBrowser
                   ├─ Website thông thường: HttpTextBrowser (HTTP + HTML parser)
                   └─ Facebook: FacebookChrome (CDP → Chrome Profile 3 đang mở)
                      └─ tab mới riêng + phiên đăng nhập đã có

**Các file chính (tính từ thư mục main):**

| File/thư mục | Chức năng |
| --- | --- |
| Text Browser.xlsx | Workbook Excel chứa add-in |
| addin/manifest.xml | Cấu hình Office Content Add-in |
| addin/index.html, app.js, style.css | UI text-only, điều hướng, link và placeholder ảnh |
| text_browser/service.py | HTTPS API chạy cục bộ |
| text_browser/hybrid_browser.py | Chọn HTTP hoặc Facebook qua Chrome Profile 3 |
| text_browser/browser.py | CDP, đọc DevToolsActivePort |
| text_browser/http_browser.py | HTTP reader và tìm kiếm |
| text_browser/html_content.py | Trích xuất block text/link/placeholder ảnh |
| text_browser/history.py | Lịch sử cục bộ |
| Open Text Browser.vbs, run_addin.pyw | Mở workbook/backend ẩn |
| install_once.ps1, Install Text Browser.cmd | Cài đặt lần đầu |
| tests/ | Unit và HTTP contract tests |

**Runtime:** backend HTTPS cục bộ tại 127.0.0.1:3010; lịch sử và log lưu dưới %LOCALAPPDATA%\bs-in-excel. Chứng chỉ Office localhost đã được ghi nhận hết hạn **2026-11-04**, cần gia hạn trước khi dùng tiếp sau ngày đó.

## 4. Các kiểm thử đã thực hiện

| Tính năng | Kết quả đã xác nhận |
| --- | --- |
| Add-in xuất hiện và tải UI trong Excel | Đạt |
| Mở Siemens TIA Portal bằng Excel | Đạt |
| Click link trong nội dung tới URL đích | Đạt |
| Giữ vị trí các nút, cuộn nội dung riêng | Đạt qua kiểm tra UI |
| Khung giữ vị trí ảnh đã lọc | Đạt |
| Tìm kiếm qua nguồn dự phòng Yahoo | Đạt; không phải Google Search trực tiếp |
| Facebook công khai bằng Chrome thật | Đạt |
| Kết nối Facebook bằng session Chrome Profile 3 | Đạt qua CDP và backend |
| Facebook Back/Forward qua backend | Đạt |
| Tự động kiểm thử sau thay đổi cuối | **20/20 test đạt**, Python/JS syntax đạt |
| Click Facebook trực tiếp trong Excel ở build cuối | **Chưa xác nhận**: Windows đang ở màn hình khóa khi thử lại |

Không nên nói toàn bộ Facebook trong UI Excel đã kiểm thử đầu-cuối sau build mới nhất: phần **API backend** đã kiểm thử bằng Profile 3, nhưng bước click UI cuối cùng chưa hoàn tất vì Windows bị khóa.

## 5. Các commit chính (nhánh main, đã push GitHub)

| Commit | Nội dung |
| --- | --- |
| 3590fed | Bản đầu: Excel COM + Chrome CDP |
| 695ec67 | Đổi thành Content Add-in thay polling C4 |
| 5019916 | Launcher một lần bấm, HTTP-first reader |
| 4fabc6d | Link theo thứ tự nội dung và vị trí ảnh lọc |
| 20215b7 | Facebook với Chrome profile riêng (giai đoạn trung gian) |
| a0a9874 | Facebook dùng **Chrome Profile 3 đã đăng nhập** |

**HEAD trước khi ghi tài liệu này:** a0a9874; repo nhánh main sạch, origin trỏ tới https://github.com/kaitobui25/bs-in-excel.git.

## 6. Cách sử dụng hiện tại

1. Chrome **Profile 3** phải đang mở, Remote Debugging được bật nếu cần Facebook.
2. Nhấp đúp shortcut Desktop **Text Browser Excel** hoặc chạy Open Text Browser.vbs.
3. Nhập URL trong thanh địa chỉ add-in, ví dụ https://www.facebook.com/ hoặc https://www.facebook.com/Siemens/.
4. Bấm link ngay trong text; dùng Back/Forward/Reload/History.
5. Nếu Chrome yêu cầu **Allow remote debugging?**, chỉ cho phép công cụ local tin cậy. Kết nối đã cấp phép có thể được giữ cho các thao tác tiếp theo.

Không quay lại UI dùng ô C4. Không cần đóng, sao chép hoặc đăng xuất Profile 3.

## 7. Cần lưu ý cho session tiếp theo

1. **Ưu tiên** kiểm tra bấm Facebook thực tế trong Excel UI sau khi mở khóa Windows, sử dụng đúng phiên Profile 3 đã đăng nhập.
2. Kiểm tra reconnect nếu Chrome đóng/mở lại, CDP port đổi, hoặc tab thuộc add-in bị đóng; không can thiệp các tab cá nhân.
3. Kiểm tra thời gian tải Facebook, giới hạn text/block/placeholder để UI luôn phản hồi nhanh.
4. Nếu muốn Google Search trực tiếp, phải thiết kế thêm; hiện nay Yahoo là giải pháp dự phòng, không được thể hiện như Google thật.
5. Kiểm tra/gia hạn certificate localhost trước 2026-11-04.
6. Mọi thay đổi tiếp tục theo tiêu chí: tối giản, clean code, không phá workbook người dùng.

---

*Tài liệu là snapshot kiến thức của session. Trạng thái Chrome/CDP/Excel và phiên đăng nhập phải được xác minh lại khi bắt đầu session mới.*

