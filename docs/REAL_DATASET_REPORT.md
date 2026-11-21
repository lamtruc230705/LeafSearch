# Báo cáo nghiệm thu trên bộ ảnh thật — LeafSearch PTIT v1.1

**Ngày kiểm thử:** 21/11/2026 (môi trường thử nghiệm).  
**Nguồn:** `Bộ dữ liệu thu thập.zip` người dùng cung cấp.  
**SHA-256 nguồn ZIP:** `d51c414ec5f0b2766cb2fb671450dcf5487d1a13b6007554bd19d724eaae5d95`.

## 1. Kiểm kê nguồn và cơ sở dữ liệu

| Chỉ tiêu | Kết quả đã kiểm tra |
|---|---:|
| Tệp PNG trong ZIP | **1.685** |
| Ảnh đã nhập `data/images/` | **1.685** |
| Số mã nhóm hình thái | **32** |
| Trùng chính xác byte/pixel khi nhập | **0** |
| Kích thước ảnh | **512 × 512, PNG RGB** |
| Gallery | **1.345** |
| Validation | **170** |
| Test | **170** |
| Vector lưu SQLite | **6.740** |
| Nhóm vector mỗi ảnh | **4** |
| Chiều mỗi ảnh | **326 + 145 + 41 + 48 = 560** |
| Ảnh đánh dấu cần duyệt mask | **78** (nhóm 04: 77 ảnh; nhóm 08: 1 ảnh) |
| `PRAGMA integrity_check` | **ok** |
| `PRAGMA foreign_key_check` | **0 lỗi** |

Chương trình `python -m backend.tools.verify_dataset` đối chiếu **SHA-256 của byte tệp và SHA-256 của pixel RGB** với metadata, kiểm đủ kích thước BLOB/chiều, xác minh tất cả vector hữu hạn và tính lại mean/scale từ **gallery duy nhất**. Lượt kiểm chứng trên nguồn thực hoàn tất không có lỗi. Chi tiết JSON ở `data/verification.json`, danh sách 1.685 ảnh và nhãn split ở `data/image_manifest.csv`.

## 2. Quy trình xử lý thực tế

1. Đọc ZIP và kiểm tra tên dạng `g.s.png`; `g` là mã nhóm, không coi là tên loài.
2. Giải mã PNG RGB 512×512, băm SHA-256 byte và pixel, phát hiện trùng chính xác.
3. Chia tập có seed 2026, riêng cho từng nhóm; không lấy dữ liệu test để tính thống kê chuẩn hóa.
4. Tiền xử lý `HSV → mask → opening 3×3 → closing 7×7 → crop → canvas 512×512`.
5. Trích 4 vector 326/145/41/48 chiều; mã pipeline **`leaf-v1-web-1.0`**.
6. Ghi `images`, `features`, `feature_stats` vào `data/leafsearch.sqlite`.
7. Truy vấn API upload ảnh thật, trả năm ảnh gallery gần nhất theo khoảng cách tăng dần.

*Lưu ý phiên bản*: code hiện thực lại từ thông số báo cáo, không xác nhận trùng từng bit với code Python trước đó nếu chưa đối chiếu file mã nguồn gốc.

## 3. Đo Top 5 trên dữ liệu thật

Trọng số **được cố định trước phép đo test**: màu 0,25 / hình 0,45 / gờ 0,15 / kết cấu 0,15. Mỗi query chỉ so sánh với **1.345 ảnh gallery**.

| Chỉ số | Validation (170 query) | Test (170 query) |
|---|---:|---:|
| Accuracy@1 | **97,06%** (165/170) | **97,65%** (166/170) |
| Precision@5 | **94,35%** (802/850) | **93,06%** (791/850) |
| MRR@5 | **97,99%** | **98,73%** |
| Sai Top 1 | 5 | 4 |

Các giá trị này **được tính từ SQLite chứa 1.685 ảnh thật**; truy vết chi tiết trong `evaluation_runs`, `data/test_group_metrics.csv`, `data/validation_group_metrics.csv`, `data/test_top1_errors.csv` và `data/validation_top1_errors.csv`. Khi mở website, trang Đánh giá sẽ nạp kết quả đã được lưu.

**Ví dụ sai Top 1 trên test** (để giải thích khi bảo vệ):

| Ảnh truy vấn | Nhóm thật | Kết quả đứng đầu | Nhóm trả về |
|---|---|---|---|
| `6.39.png` | 06 | `29.57.png` | 29 |
| `14.40.png` | 14 | `17.11.png` | 17 |
| `16.37.png` | 16 | `24.8.png` | 24 |
| `28.42.png` | 28 | `31.12.png` | 31 |

## 4. Cảnh báo bắt buộc: gần trùng và rò rỉ tiềm năng

- SHA-256 không phát hiện được cắt, xoay, đổi sáng/tối và biến đổi nhỏ.
- Công cụ **pHash 64 bit, Hamming ≤6** tạo ra **4.766 cặp nghi vấn**, trong đó **1.784 cặp khác split**, gồm **610 cặp khác split nhưng cùng mã nhóm**.
- Đây **không phải** 4.766 ảnh trùng đã được xác nhận: pHash có thể ghép nhầm các lá cùng dáng/nền sáng (false positives), đồng thời vẫn bỏ sót một số ảnh gần trùng (false negatives).
- Danh sách đầy đủ là `data/near_duplicate_review.csv`. Chỉ duyệt thủ công, **không xóa tự động**, cũng không thay nhãn test khi đang xem kết quả.
- Cần bổ sung ảnh mới từ mẫu cây/phiên chụp độc lập hoặc gộp ảnh cùng phiên chụp theo nhóm trước khi chia split nếu muốn khẳng định khả năng tổng quát hóa ngoài bộ dữ liệu này.

**Stress-test bổ sung**: thử bỏ ứng viên gallery có pHash gần từng query test (không sửa DB) cho Accuracy@1 = **97,65%**, Precision@5 = **92,82%**, MRR@5 = **98,73%**; **108/170** query bị loại ít nhất một ứng viên, tổng **829** lượt loại. Đây chỉ là **phân tích độ nhạy**, không xác nhận dữ liệu hết rò rỉ hoặc nâng hạng kết quả lên thực nghiệm độc lập. Xem `data/phash_sensitivity.json`.

## 5. Tiêu chuẩn nghiệm thu đã vượt qua

- `GET /api/health`: `ready=true`; số ảnh, nhóm, vector và split đúng toàn bộ.
- `POST /api/search` bằng ảnh **test thật** trả Top 5, chỉ từ gallery, điểm D tăng dần.
- `POST /api/evaluate`: tính/ghi dữ liệu **validation và test thật** vào SQLite.
- `GET /api/quality`: số ảnh mask cần rà soát và thống kê pHash thực tế.
- `python -m pytest -q`: **14 passed** (bao gồm test trên cơ sở dữ liệu thật).
- `python -m backend.tools.verify_dataset`: **passed**, kiểm SHA-256 và scale gallery.

**Giới hạn nghiệm thu**: chưa có nhãn loài được chuyên gia xác nhận và chưa duyệt thủ công từng cặp pHash; vì thế metrics thể hiện độ nhất quán của truy vấn theo mã nhóm hiện có, **không phải** tỉ lệ nhận dạng đúng loài hay đo kiểm hoàn toàn độc lập.
