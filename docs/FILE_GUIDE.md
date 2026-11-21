# Hướng dẫn đọc hiểu chức năng từng file — LeafSearch PTIT

Mục tiêu: người mới đọc code có thể lần từ nút trên website đến dòng Python và bảng SQLite tương ứng. **Một file đảm nhận một trách nhiệm chính**, không gom thuật toán vào API.

## 1. `frontend/index.html` — kết cấu 6 màn hình

- **Đầu vào:** các thẻ `<section id="page-...">`, `id` của nút, form, vùng kết quả.
- **Đầu ra:** cấu trúc DOM để `app.js` gắn sự kiện.
- **Không chứa:** thuật toán tìm kiếm hay dữ liệu kết quả giả.
- `page-overview`: 4 chỉ số dữ liệu + thống kê phân tập.
- `page-search`: thẻ `fileInput`, `searchBtn`, 4 thanh `weight-*`, `resultGrid`.
- `page-library`: `libraryGrid` hiển thị 32 nhóm, `libraryResults` chứa danh sách ảnh.
- `page-features`: sơ đồ giải thích 4 nhóm vector.
- `page-evaluation`: `runEvaluation`, `metricAccuracy`, `metricPrecision`, `metricMrr`.
- `page-system`: kiến trúc API/DB cho phần bảo vệ bài tập lớn.

**Thử nghiệm:** mở `http://127.0.0.1:8000/` và nhấp menu bên trái. Trang không có API sẽ báo rõ lỗi kết nối.

## 2. `frontend/styles.css` — hệ thống phong cách giao diện

- Màu xanh đậm cho sidebar; nền trắng/xám nhạt cho nội dung.
- CSS `grid` cho thống kê, thư viện, kết quả Top 5.
- `.screen.active` kiểm soát trang nào đang hiển thị.
- `.status-banner`, `.modal`, `.result-card` là phần bổ sung khi kết nối API.
- Responsive bằng media query cho điện thoại; không cần CSS framework.

**Thay đổi màu:** sửa biến `--forest`, `--green`, `--paper` ở đầu file.

## 3. `frontend/app.js` — điều phối frontend

| Hàm | Làm gì? | API liên quan |
| --- | --- | --- |
| `api(path, options)` | Gọi `fetch`, ném lỗi có thông điệp HTTP | Tất cả API |
| `showPage(page)` | Ẩn/hiện màn hình và cập nhật URL hash | Không |
| `loadDashboard()` | Thay số mẫu tĩnh bằng số thật từ SQLite | GET `/dashboard` |
| `loadGroups()` | Lấy 32 nhóm và ảnh đại diện thật | GET `/categories` |
| `renderGroups()` | Lọc/sắp xếp nhóm, tạo thẻ ảnh | Không |
| `loadGroupImages()` | Phân trang 16 ảnh và gắn nút chi tiết | GET `/images` |
| `chooseFile(file)` | Kiểm định frontend và preview upload | Không |
| `readWeights()` | Nhận trọng số slider của người dùng | Không |
| `doSearch()` | Upload ảnh bằng `FormData`, kết quả Top 5 | POST `/search` |
| `showImageDetail(id)` | Modal hiển thị ảnh gốc/mask và 12 giá trị mẫu | GET `/images/{id}` |
| `runEvaluation(split)` | Gửi yêu cầu đánh giá và render metric thực | POST `/evaluate` |
| `loadLatestEvaluation()` | Tải lần đánh giá được lưu gần nhất | GET `/evaluations/latest` |
| `safe(text)` | Escape chuỗi HTML để tránh injection | Không |

**Quan trọng:** FE **không tính vector**. Browser gửi bytes ảnh, mọi công thức xử lý nằm ở backend.

## 4. `backend/main.py` — điểm vào chương trình

- `app = create_app()` khởi tạo FastAPI.
- `initialize()` tạo **schema rỗng**, không tự tạo dữ liệu mẫu.
- `app.include_router(router)` nối các đường dẫn `/api/...` trong `api.py`.
- `app.mount('/assets', StaticFiles(...))` phục vụ HTML/CSS/JS.
- Lệnh chạy: `python -m uvicorn backend.main:app --reload`.

## 5. `backend/config.py` — thiết lập dự án

| Cấu hình | Ý nghĩa |
| --- | --- |
| `ROOT` | Đường dẫn thư mục gốc, tính theo file Python |
| `database` | Mặc định `data/leafsearch.sqlite`, đổi được qua `LEAFSEARCH_DB` |
| `images_dir` | Mặc định `data/images`, đổi được qua `LEAFSEARCH_IMAGES` |
| `frontend_dir` | Nơi lưu HTML/CSS/JS |
| `max_upload_bytes` | Giới hạn file upload 10 MB |
| `max_image_pixels` | Ngăn ảnh truy vấn quá 20 triệu pixel |
| `pipeline_version` | ID bắt buộc thống nhất giữa vector và stats |

## 6. `backend/schema.sql` — bảng dữ liệu và quan hệ

| Bảng | Một dòng tương đương | Liên hệ |
| --- | --- | --- |
| `categories` | Một mã nhóm `01`–`32` | Một nhóm có nhiều ảnh |
| `images` | Một ảnh PNG + tên, hash, split, cờ kiểm tra | Khóa chính `image_id`, khóa ngoại `group_id` |
| `features` | Một vector thuộc một trong 4 nhóm của một ảnh | Khóa ghép `(image_id,feature_group,version)` |
| `feature_stats` | Mean và scale từng chiều của gallery | Một bản theo `(group,version)` |
| `search_logs` | Một lần người dùng tìm kiếm | JSON trọng số, Top 5 và runtime |
| `evaluation_runs` | Một lượt kiểm thử test/validation | JSON metric + ví dụ sai |
| `metadata` | Cấu hình nguồn nhập | seed, nhãn ZIP, số bản loại trùng, phiên bản |

**Tại sao lưu vector BLOB?** Một vector `float32` 560 chiều chỉ 2.240 bytes/ảnh (chưa tính DB overhead); SQLite có thể quản lý khóa và đọc dữ liệu không cần tạo file NPY riêng cho từng ảnh.

## 7. `backend/db.py` — cổng vào SQLite

- `connect(db_path)` tự đóng kết nối, bật `PRAGMA foreign_keys=ON`, commit/rollback đúng ngữ cảnh.
- `initialize(db_path)` thực thi `schema.sql`.
- `encode_vector(vector)` -> bytes float32 little-endian; kiểm tra NaN/Inf.
- `decode_vector(blob, dimension)` -> NumPy float64, kiểm tra đúng số chiều.
- `set_metadata()` / `get_metadata()` lưu/đọc thông tin nguồn import.

**Tại sao không lưu trực tiếp mảng Python?** SQLite chỉ lưu `NULL/INTEGER/REAL/TEXT/BLOB`; vector dùng BLOB để giảm dung lượng và đọc lại nhất quán.

## 8. `backend/repository.py` — truy vấn dữ liệu sạch

- `dataset_status()`: số ảnh/nhóm/vector/size split, trạng thái `ready`.
- `categories()`: các nhóm + ảnh đại diện lấy `MIN(image_id)`.
- `list_images()`: lọc ảnh theo nhóm/split/tên, phân trang (không đọc BLOB nặng).
- `image_details()`: metadata + 12 số đầu mỗi vector cho mục đích minh họa.
- `image_path()`: chỉ cho phép đường dẫn bên trong `data/images`; không dùng đường dẫn người dùng đưa vào.
- `read_vectors()`: đọc đủ 4 nhóm/ảnh thuộc split, kiểm tra version và số chiều.
- `feature_stats()`: lấy mean/scale và đối chiếu số ảnh gallery.

## 9. `backend/vision/preprocess.py` — xử lý ảnh bước 1

- `decode_image(content)` chuyển bytes PNG/JPG/WEBP thành BGR, ghép alpha lên nền trắng.
- `preprocess(image_bgr)` tính mask nhị phân từ HSV, mở/đóng, lấy contour chính, chuẩn hóa ảnh về 512×512.
- `ProcessedImage` giữ `image`, `mask`, `mask_ratio`, `review_required`, `warning`.
- `to_png()` mã hóa ảnh/mask để backend trả lên trình duyệt.

**Tại sao mask phải đồng nhất với ảnh?** Vì color histogram, contour, ridge và texture đều cần loại nền trước khi tính số thực.

## 10. `backend/vision/features.py` — xử lý ảnh bước 2

- `DIMENSIONS`/`ORDER`: bảng cấu hình 4 nhóm, thứ tự nhất quán với SQLite.
- `color_features(image,mask)` -> **326 số**: HSV256 + Lab48 + RGB12 + Hue2 + entropy3 + ExG5.
- `shape_features(mask)` -> **145 số**: hình học12 + góc histogram54 + góc statistics15 + Fourier64.
- `ridge_features(image,mask)` -> **41 số**: Hessian24 + skeleton8 + hướng8 + coherence1.
- `texture_features(image,mask)` -> **48 số**: GLCM18 + LBP30.
- `extract_features(item)` gọi cả bốn và báo lỗi nếu thiếu chiều/NaN/Inf.

**Không đổi thứ tự vector mà không đổi `pipeline_version`**: số đo sẽ mất nhất quán với những ảnh cũ.

## 11. `backend/tools/import_dataset.py` — bước xây dữ liệu offline

`_iter_source()` → `_read_metadata()` → `make_splits()` → `preprocess()` → `extract_features()` → `INSERT` → `mean/std gallery` → `integrity_check` → đưa DB/ảnh vào vận hành.

- `_iter_source`: đọc ZIP hoặc thư mục; không giải nén theo đường dẫn nội bộ ZIP, hạn chế nguy cơ path traversal.
- `_read_metadata`: kiểm tra tên dạng `14.1.png`, RGB, PNG, 512×512, SHA256 bytes/pixel.
- `make_splits`: seed 2026, đúng tỉ lệ; dữ liệu chính thức được khóa 1345/170/170.
- `import_dataset`: xây staging, chỉ thay CSDL chính sau khi hoàn thành; có tùy chọn backup `--replace`.
- `EXPECTED_COUNTS`: 32 số lượng sau lọc từ báo cáo; chế độ strict bắt buộc khớp toàn bộ để tránh nhập nhầm ZIP.

**Ví dụ lỗi thường gặp:** nếu thư mục chứa nhiều ảnh `14.1.png` cùng tên ở hai thư mục khác nhau, importer chặn thay vì ghi đè âm thầm.

## 12. `backend/services/search.py` — tìm tương đồng

- `normalize_weights`: kiểm tra 4 trọng số, âm/NaN/0 đều không hợp lệ.
- `prepare_index`: đọc gallery và `feature_stats` đúng phiên bản.
- `rank`: tính `D_color,D_shape,D_ridge,D_texture` và tổng, sắp tăng dần rồi chọn Top 5.
- `search_image`: chạy 1 ảnh truy vấn, ghi log và tạo hình chuẩn hóa/mask dạng data URL.

**Hiểu công thức:** `mu` của cùng từng chiều bị triệt tiêu khi trừ hai giá trị z-score; vì vậy `(q-i)/scale` tương đương `z(q)-z(i)`, không làm thay đổi thứ tự kết quả.

## 13. `backend/services/evaluation.py` — đo chất lượng

- `evaluate(split,weights)`: chỉ nhận `validation` hoặc `test`, so sánh với gallery.
- `Accuracy@1`: tỷ lệ query có kết quả #1 cùng mã nhóm.
- `P@5`: số ảnh cùng nhóm trong 5 kết quả chia 5, lấy trung bình qua query.
- `MRR@5`: trung bình `1/rank` của ảnh đúng nhóm đầu tiên trong Top 5; nếu không có đúng = 0.
- `get_evaluation()`: đọc và trả JSON số đo đã lưu (không tự tạo metric giả).

**Chú ý nhóm ít ảnh:** một query thuộc nhóm có ít hơn 5 ảnh gallery sẽ có `P@5` bị giới hạn ngay cả khi thuật toán xếp hạng lý tưởng.

## 14. `backend/api.py` — REST HTTP giao tiếp FE/BE

- `GET /api/health`, `/dashboard`, `/categories`, `/images` và `/images/{id}` dùng repository.
- `GET /api/images/{id}/file`, `/processed/{kind}` trả PNG trực tiếp.
- `POST /api/search`: nhận upload và 4 trường trọng số `Form`, gọi `search_image()`.
- `POST /api/evaluate`: nhận JSON `{split,weights}`, gọi `evaluate()`.
- `GET /api/evaluations/latest`: xem lần đánh giá cuối.

**Chức năng không nằm ở đây:** tính đặc trưng, SQL phức tạp. API chỉ điều phối, giúp dễ hiểu và test.

## 15. `backend/tools/audit_near_duplicates.py` — kiểm soát rò rỉ

- `perceptual_hash()` tính pHash 64 bit từ ảnh xám 32×32 bằng DCT.
- `audit_near_duplicates()` so từng cặp ảnh có Hamming distance thấp và đánh dấu `cross_split`, `cross_group`.
- Kết quả CSV chỉ đưa ra ứng viên để duyệt, **không tự loại ảnh**.

## 16. `tests/*` — kiểm chứng máy thay vì chỉ nhìn giao diện

- `conftest.py`: tạo 15 ảnh thử tự vẽ trong thư mục tạm, **không phải** dữ liệu gốc.
- `test_pipeline.py`: kiểm đủ 4 vector × số ảnh, gallery split, thống kê chỉ gallery, API upload, Top5, đánh giá, integrity SQLite và pHash audit.

**Cách học:** đọc `tests/test_pipeline.py` để biết hành vi mong đợi, sau đó đọc hàm tương ứng trong backend. Đây là cách dễ hiểu nhất để đọc dự án từ đầu đến cuối.

## 17. `database/schema_template.sqlite` — CSDL khung để học

Đã tạo 7 bảng từ `backend/schema.sql` nhưng **chưa chứa ảnh hoặc vector thật**. Có thể mở bằng DB Browser for SQLite để quan sát khóa chính, chỉ mục và quan hệ. Khi nhập ZIP, ứng dụng tạo CSDL hoạt động riêng trong `data/leafsearch.sqlite`.


## 18. `backend/services/quality.py` — bảng kiểm soát chất lượng

- `quality_summary(db_path)`: lấy số ảnh `quality_status='review'`, ảnh cần xem lại và đếm cặp nghi gần trùng trong CSV có sẵn.
- Nếu chưa chạy audit, các trường `candidate_pairs`, `cross_split_pairs` phải là `null`, không tự suy đoán.
- Frontend tải thông tin này vào phần cuối màn hình **Đánh giá**, cho phép xem ảnh thực, mask và tải CSV.

## 19. `backend/tools/verify_dataset.py` — nghiệm thu dữ liệu thật

- `verify_dataset()`: đối chiếu 1.685 ảnh trong `data/images/` với toàn bộ bản ghi SQLite.
- Kiểm byte SHA-256 và pixel SHA-256, mã nhóm, tên file, `PRAGMA integrity_check`, khóa ngoại, chiều và tính hữu hạn của 6.740 vector.
- Tính lại mean/std chỉ từ 1.345 ảnh gallery, so với `feature_stats` đã lưu.
- Lệnh: `python -m backend.tools.verify_dataset`. Báo cáo xuất `data/verification.json`.

## 20. `backend/tools/evaluate_sensitivity.py` — phép thử độ nhạy

- **Không** sửa SQLite/split, chỉ giả lập bỏ các ảnh gallery có pHash gần truy vấn test.
- Tính lại Top 5 để xem độ nhạy với ứng viên gần trùng (pHash vẫn có false positives/negatives).
- Lệnh: `python -m backend.tools.evaluate_sensitivity --split test`.
- Kết quả chỉ dùng như kiểm tra độ nhạy, không thay thế đánh giá test thông thường hoặc phép rà soát thủ công.

## 21. Các file dữ liệu thật bên trong `data/`

| File | Công dụng |
|---|---|
| `images/<nhóm>/<ảnh>.png` | Toàn bộ **1.685 ảnh gốc** đã nhập vào dự án |
| `leafsearch.sqlite` | Metadata, 4 vector/ảnh, mean/scale gallery, log và metrics test/validation |
| `image_manifest.csv` | 1.685 dòng đối chiếu mã nhóm, split, hash byte và pixel |
| `verification.json` | Kết quả kiểm độc lập byte/pixel/vector/gallery |
| `dataset_release.json` | Provenance ZIP, SHA-256, kết quả đo thực tế |
| `near_duplicate_review.csv` | Danh sách các cặp **nghi vấn**, KHÔNG phải danh sách ảnh trùng chắc chắn |
| `phash_sensitivity.json` | Phép thử độ nhạy với việc loại ứng viên pHash |
| `test_group_metrics.csv`, `validation_group_metrics.csv` | Chỉ số đánh giá theo mã nhóm |
| `test_top1_errors.csv`, `validation_top1_errors.csv` | Các ảnh truy vấn sai Top 1 để thảo luận |

## 22. Scripts Windows mới

- `scripts/INSTALL_AND_RUN_WINDOWS.bat`: khởi tạo môi trường Python, cài thư viện và chạy website; không nhập ảnh lại.
- `scripts/VERIFY_WINDOWS.bat`: chạy pytest và kiểm chứng toàn bộ SHA-256/vector/SQLite.
- Nếu muốn chạy từng bước và hiểu vì sao: đọc `README.md`, không nên chỉ dùng file BAT rồi bỏ qua các module.
