# Báo cáo kiểm thử phần mềm — LeafSearch PTIT v1.1 (21/11/2026)

## 1. Môi trường thực thi

- Python **3.13.5**.
- FastAPI **0.128.2**, Uvicorn **0.48.0**.
- NumPy **2.3.5**, OpenCV **4.13.0**, SciPy **1.17.0**, scikit-image **0.26.0**.
- SQLite (Python `sqlite3`), Pillow, pytest và httpx.

## 2. Kết quả kiểm thử tự động

Chạy tại thư mục gốc:

```bash
python -m pytest -q
```

**Kết quả thực tế: `14 passed`**.

| Nhóm kiểm tra | Nội dung |
|---|---|
| Importer/SQLite | Nhập ảnh, toàn vẹn DB, đủ 4 vector/ảnh và mean/scale từ gallery |
| FastAPI | Health, dashboard, danh mục, phân trang, ảnh gốc/mask/normalized |
| Upload/search | Ảnh test -> 560 chiều -> 5 ảnh gallery xếp theo khoảng cách tăng |
| Evaluation | Validation/test, API lưu/đọc metrics, chặn split không hợp lệ |
| Kiểm tra dữ liệu | Tên file, RGB 512×512, loại bản sao chính xác |
| Chia tập | 1.345/170/170 từ phân bố thật 32 nhóm và seed 2026 |
| pHash | Ghi CSV cặp nghi vấn; không tự xóa |
| Trạng thái lần nhập đầu | Website tạo SQLite schema rỗng trước vẫn import lần đầu được |
| Chất lượng UI/API | Endpoint quality trả dữ liệu thật hoặc null khi chưa audit |
| **Smoke test dataset thật** | Kiểm đủ 1.685 ảnh/6.740 vector, test upload ảnh thật chỉ trả gallery |

## 3. Kiểm chứng toàn bộ dữ liệu ảnh thật

```bash
python -m backend.tools.verify_dataset
```

**Kết quả: `passed=true`, `sqlite_integrity=ok`, `sqlite_foreign_key_errors=0`.**

- **1.685/1.685** file PNG kiểm SHA-256 byte và pixel RGB với database.
- **6.740/6.740** vector đúng các chiều 326/145/41/48, không NaN/Inf.
- Mean/std từ **gallery 1.345 ảnh** được tính lại và đối chiếu với `feature_stats`.
- Tên, group, split, đường dẫn tương đối trong `data/images` khớp hoàn toàn.
- Kết quả JSON: `data/verification.json`.

## 4. Kiểm thử API thật

- `GET /`: **200** (trả giao diện HTML).
- `GET /api/health`: **200**, `ready=true`, 1.685 ảnh, 32 nhóm, 6.740 vector.
- `GET /api/quality`: **200**, 78 ảnh cần xem lại mask, 4.766 cặp nghi pHash.
- `POST /api/search`: **200** trên ảnh test thật; trả đủ Top 5 từ gallery.
- `POST /api/evaluate`: **200** cho validation và test, tạo 2 bản ghi metrics thật trong SQLite.
- `GET /api/evaluations/latest`: **200**, trả kết quả test được lưu.
- JavaScript: `node --check frontend/app.js` không báo lỗi cú pháp.

**Giới hạn kiểm thử giao diện:** đã kiểm HTML/JS/API và đường dẫn tĩnh từ máy chủ; kiểm thử tương tác hiển thị/khả năng responsive bằng trình duyệt thật trên Windows của người dùng chưa được thực hiện trong môi trường này. Không khẳng định đã có kiểm thử trình duyệt đầu-cuối thành công.

## 5. Số liệu thực nghiệm (tham khảo nội bộ, có rủi ro near-duplicate)

| Dataset | Top 1 | P@5 | MRR@5 |
|---|---:|---:|---:|
| Validation — 170 ảnh | 97,06% | 94,35% | 97,99% |
| Test — 170 ảnh | 97,65% | 93,06% | 98,73% |

**Không gọi đây là độ chính xác nhận diện loài độc lập.** pHash đánh dấu 1.784 cặp ứng viên khác split; xem `docs/REAL_DATASET_REPORT.md` và rà soát thủ công trước khi tuyên bố khả năng tổng quát hóa ngoài tập ảnh này.

## 6. Kiểm tra khi giao bài / trình bày

1. Giải nén full ZIP, xác minh có `data/images/` và `data/leafsearch.sqlite`.
2. Nhấp `scripts/INSTALL_AND_RUN_WINDOWS.bat` hoặc chạy theo README.
3. Mở `/`, chọn **Tìm kiếm**, upload ảnh lá test rồi xem Top 5.
4. Vào **Thư viện**, mở mã nhóm, xem ảnh gốc/normalized/mask.
5. Vào **Đánh giá**, xem Accuracy/Precision/MRR cùng mục **Kiểm soát chất lượng**.
6. Mở `/docs` để xem Swagger API và thử endpoint.
7. Chạy `scripts/VERIFY_WINDOWS.bat` nếu cần kiểm chứng lại toàn bộ ảnh/DB.
