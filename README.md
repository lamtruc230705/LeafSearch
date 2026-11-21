# LeafSearch PTIT v1.1 — Website tìm kiếm ảnh lá cây theo nội dung

**Dự án full-stack phục vụ bài tập lớn Cơ sở dữ liệu đa phương tiện tại PTIT.**

Website cho phép duyệt ảnh lá theo **mã nhóm hình thái**, tải ảnh mới lên, tiền xử lý, trích xuất **560 đặc trưng**, tìm **Top 5 ảnh gần nhất** trong gallery và đo **Accuracy@1 / Precision@5 / MRR@5** trên validation/test.

> **Bản v1.1 đã tích hợp dữ liệu thật:** gói Fullstack có **1.685 ảnh PNG** trong `data/images/` và CSDL **`data/leafsearch.sqlite`** chứa **6.740 vector**. Không cần tải ZIP ảnh thêm hoặc nhập lại để sử dụng website. `data/verification.json` xác nhận SHA-256 byte/pixel và thống kê gallery. Báo cáo chi tiết ở **`docs/REAL_DATASET_REPORT.md`**.
>
> Bộ ZIP chính thức được mô tả trong báo cáo: **1.685 ảnh PNG RGB 512×512, 32 mã nhóm**, sau khi loại 100 bản trùng từ 1.785 ảnh. Không được tự đổi mã nhóm thành tên loài chưa kiểm chứng.

## 1. Công nghệ

| Tầng | Công nghệ | Vai trò |
| --- | --- | --- |
| Frontend | HTML5, CSS3, JavaScript thuần | 6 trang, tải ảnh, gọi API, hiển thị dữ liệu thật |
| API | Python, FastAPI, Uvicorn | REST JSON + upload ảnh, phục vụ web |
| Xử lý ảnh | OpenCV, NumPy, SciPy, scikit-image | Mask, hình dạng, đường gờ ứng viên, màu và kết cấu |
| Lưu trữ | SQLite | metadata ảnh, BLOB 560 chiều, mean/scale, log/metrics |
| Kiểm thử | pytest + TestClient + httpx | Test importer, 4 vector, API, Top 5, đánh giá |

## 2. Chạy dự án trên Windows (từ đầu, không cần frontend build)

Mở **PowerShell hoặc CMD** trong thư mục `LeafSearch_PTIT_Fullstack`. Bản ZIP này đã tích hợp dữ liệu 1.685 ảnh và không yêu cầu nhập lại.

```powershell
py -3.11 -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
```

Nếu máy không có Python 3.11 nhưng có 3.12/3.13, thay dòng đầu bằng `py -3.12 -m venv .venv` hoặc `py -3.13 -m venv .venv`.

**Bản này đã có sẵn SQLite và 1.685 ảnh**, vì vậy **bỏ qua bước nhập ZIP**. Chạy server ngay sau khi cài xong thư viện:

```powershell
python -m uvicorn backend.main:app --reload
```

Mở **http://127.0.0.1:8000** (website) hoặc **http://127.0.0.1:8000/docs** (Swagger API).

> Nếu nhập lại ảnh sau khi đã tạo CSDL, thêm `--replace`. Importer chỉ thay file khi xử lý mới thành công và giữ bản cũ với đuôi `.previous`; khi đã có `.previous`, hãy chủ động sao lưu/đổi tên trước một lần nhập tiếp theo.

### Cách dễ nhất trên Windows (không phải gõ lệnh)

Nhấp đúp `scripts/INSTALL_AND_RUN_WINDOWS.bat`; tệp sẽ tạo `.venv`, cài dependencies và mở server. Sau đó truy cập **http://127.0.0.1:8000** trên trình duyệt.

**Khi nào mới cần nhập lại ảnh?** Chỉ khi muốn xây lại database với bộ ZIP mới hoặc thay đổi thuật toán. Dùng `python -m backend.tools.import_dataset --source "DUONG_DAN_ZIP" --replace` sau khi sao lưu toàn bộ `data/`. Không cần dùng lệnh này cho bản tải về.

### Chạy trên macOS/Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m uvicorn backend.main:app --reload
```

### Kiểm tra trước khi nộp bài

```bash
python -m pytest -q
python -m backend.tools.verify_dataset
python -m backend.tools.audit_near_duplicates --threshold 6
```

Bản này đã có sẵn kết quả audit ở `data/near_duplicate_review.csv` và báo cáo số liệu thực tế trong `docs/REAL_DATASET_REPORT.md`. Khi chạy lại, lệnh audit cập nhật CSV. **Chỉ dùng để rà soát**: pHash không chứng minh tuyệt đối ảnh có trùng nhau; không tự xóa và không tự điều chỉnh tập kiểm thử.

## 3. Sơ đồ thư mục

```text
LeafSearch_PTIT_Fullstack/
├── README_START_HERE.txt           # Hướng dẫn ngắn cho Windows
├── README.md                       # Bắt đầu từ đây; cài đặt, chạy và nghiệm thu
├── requirements.txt                # Khai báo dependencies Python
├── pytest.ini                      # Cấu hình chạy pytest
├── .gitignore                      # Tránh commit ảnh gốc/SQLite/dữ liệu nhạy cảm
├── database/
│   ├── schema_template.sqlite      # CSDL khung rỗng, mở bằng DB Browser
│   └── README.txt                  # Phân biệt DB khung và DB có dữ liệu thật
├── frontend/
│   ├── index.html                  # 6 màn hình website (kết cấu giao diện)
│   ├── styles.css                  # Toàn bộ style: sidebar, card, grid, responsive
│   └── app.js                      # Điều hướng + fetch API + render kết quả thật
├── backend/
│   ├── __init__.py                 # Đánh dấu package backend
│   ├── main.py                     # App factory FastAPI, phục vụ frontend
│   ├── api.py                      # Các HTTP route: upload/search/evaluate/images
│   ├── config.py                   # Cấu hình đường dẫn, giới hạn và phiên bản
│   ├── db.py                       # SQLite connection, vector float32 <-> BLOB
│   ├── schema.sql                  # Thiết kế 7 bảng dữ liệu có ràng buộc
│   ├── repository.py               # Tầng truy vấn database (không đặt ở API)
│   ├── vision/
│   │   ├── __init__.py
│   │   ├── preprocess.py           # HSV -> mask -> crop/resize -> ảnh chuẩn
│   │   └── features.py             # 4 nhóm đặc trưng: 326+145+41+48=560
│   ├── services/
│   │   ├── __init__.py
│   │   ├── search.py               # Chuẩn hóa trọng số, RMS, Top 5, log
│   │   ├── evaluation.py           # Accuracy@1, P@5, MRR@5 theo mã nhóm
│   └── quality.py              # Kiểm soát mặt nạ và pHash
│   └── tools/
│       ├── __init__.py
│       ├── import_dataset.py       # Đọc ZIP -> xác thực -> split -> build DB
│       ├── audit_near_duplicates.py # pHash rà soát ảnh gần trùng
│       ├── verify_dataset.py       # Kiểm toàn bộ ảnh/SQLite/560 chiều
│       └── evaluate_sensitivity.py # Kiểm độ nhạy khi bỏ ứng viên pHash
├── tests/
│   ├── conftest.py                 # Sinh ảnh LÁ GIẢ cho test máy; không phải ảnh thật
│   ├── test_pipeline.py            # Kiểm thử nghiệp vụ và tính toàn vẹn DB
│   └── test_real_dataset.py       # Smoke test trên 1.685 ảnh thật
├── docs/
│   ├── FILE_GUIDE.md               # Đọc hiểu từng file và dòng chảy dữ liệu
│   ├── ARCHITECTURE.md             # Kiến trúc, thuật toán và giải thích công thức
│   ├── API.md                      # Hướng dẫn dùng các endpoint, JSON mẫu
│   ├── STUDY_PLAN.md               # Lộ trình tự học code theo 10 bài
│   ├── TEST_REPORT.md              # Kết quả kiểm thử được xác nhận
│   └── REAL_DATASET_REPORT.md      # Thực nghiệm và giới hạn trên 1.685 ảnh
├── scripts/
│   ├── IMPORT_WINDOWS.bat          # Kéo thả ZIP lên BAT để nhập dữ liệu
│   ├── START_WINDOWS.bat           # Chạy server Windows nếu đã cài thư viện
│   ├── INSTALL_AND_RUN_WINDOWS.bat # Một nhấp để cài và chạy
│   ├── VERIFY_WINDOWS.bat          # Chạy test và kiểm chứng dữ liệu
│   └── START_LINUX_MAC.sh          # Chạy server macOS/Linux
└── data/
    ├── README.txt                  # Chỉ dẫn thư mục dữ liệu
    ├── images/                     # ĐÃ CÓ 1.685 PNG của người dùng
    │   └── 01/1.1.png, ...
    ├── leafsearch.sqlite           # ĐÃ CÓ 6.740 vector + các lượt đánh giá
    ├── removed_duplicates.json    # Danh sách bản sao đã bỏ qua
    ├── near_duplicate_review.csv  # 4.766 cặp nghi gần trùng (cần duyệt)
    ├── verification.json          # Kiểm toàn vẹn byte/pixel và mean/scale
    ├── image_manifest.csv         # Danh sách, split và checksum 1.685 ảnh
    ├── dataset_release.json       # Provenance và số liệu đánh giá thực tế
    ├── phash_sensitivity.json     # Kết quả stress-test pHash
    └── *_group_metrics.csv        # Chỉ số theo mã nhóm và lỗi Top 1
```

**Phiên bản v1.1 đã đóng gói đủ `images` và SQLite chứa dữ liệu thật**; `database/schema_template.sqlite` chỉ là CSDL khung rỗng tham khảo, còn `data/leafsearch.sqlite` mới là CSDL đang vận hành. Không cần dựng Node.js/Vite/React: FastAPI phục vụ trang tĩnh cùng origin, tránh lỗi CORS khi học và trình diễn.

## 4. Quy trình nghiệp vụ

1. **Offline, làm một lần cho mỗi bộ ZIP:** importer đọc từng PNG -> kiểm tra 512×512 RGB/tên nhóm -> loại ảnh trùng pixel/chính xác -> chia gallery/validation/test (seed=2026) -> tiền xử lý -> tính 4 vector -> lưu SQLite -> tính mean, scale chỉ từ gallery.
2. **Online, mỗi lượt tìm kiếm:** frontend upload ảnh -> FastAPI giới hạn định dạng/dung lượng -> tiền xử lý cùng một pipeline -> vector 560 chiều -> tải gallery từ SQLite -> tính khoảng cách RMS từng nhóm theo scale gallery -> gộp trọng số -> sắp xếp và trả 5 ảnh.
3. **Đánh giá:** validation để điều chỉnh trọng số; test để báo cáo cuối. Mọi truy vấn chỉ tìm trong gallery; không tính `mean/scale` từ test.
4. **Rà soát:** công cụ pHash đánh dấu các cặp gần trùng (đặc biệt cặp khác tập); người làm bài quyết định thủ công liệu có rò rỉ dữ liệu.

**Công thức khoảng cách:**

\[
D_g(Q,I)=\sqrt{\frac{1}{d_g}\sum_{j=1}^{d_g}\left(\frac{q_j-i_j}{\sigma_{g,j}}\right)^2}\,,\quad
D=0.25D_{màu}+0.45D_{hình}+0.15D_{gờ}+0.15D_{kết\ cấu}.
\]

Giá trị `σ=0` dùng scale=1 để tránh chia cho 0. Trọng số người dùng chỉnh được và luôn được chuẩn hóa về tổng 1. Khoảng cách **không phải xác suất nhận dạng loài**.

## 5. Các yêu cầu nghiệm thu chính

- Mở `GET /api/health`: bản tích hợp thực tế trả `ready=true`, ảnh 1685, 32 nhóm, 6740 vector, gallery 1345, validation 170, test 170.
- `GET /api/images` hiển thị ảnh PNG thật từ thư mục `data/images`.
- `POST /api/search` trả đúng 5 ảnh gallery với `distance_total` tăng dần và các khoảng cách màu/hình/gờ/kết cấu.
- `POST /api/evaluate` ghi số liệu thực nghiệm vào `evaluation_runs` và hiển thị lại qua `GET /api/evaluations/latest`.
- `python -m pytest -q` hiện có **14 test passing**, gồm kiểm thử với ảnh thử nhân tạo **và** smoke test trên bộ ảnh thật.
- `python -m backend.tools.verify_dataset` kiểm chứng SHA-256 file/pixel của 1.685 ảnh, vector, SQLite và thống kê gallery.
- Kết quả đánh giá đã chạy trên 170 ảnh validation và 170 ảnh test thật: xem `docs/REAL_DATASET_REPORT.md`.
- Có **1.784 cặp nghi gần trùng khác tập** theo pHash, vì vậy metric thực nghiệm **không** chứng minh hiệu quả độc lập khỏi bộ ảnh hiện có; cần rà soát thủ công trước khi tuyên bố tổng quát hóa.

## 6. Lưu ý trung thực học thuật

- Báo cáo gốc xác nhận đặc tả 326/145/41/48 chiều. **Mã nguồn ở đây được hiện thực lại từ thông số và công thức trong báo cáo**, có phiên bản `leaf-v1-web-1.0`; **không khẳng định bitwise trùng mã nguồn cũ khi chưa có file Python gốc để đối chiếu**.
- Một số pixel cùng lá dù khác góc xoay/ánh sáng có thể gần trùng sau SHA-256; không nên tuyên bố đã loại hết gần trùng khi chưa kiểm chứng thủ công.
- 32 mã nhóm là nhóm ảnh hình thái, **chưa xác nhận là 32 loài**.
- Các metric trên test chỉ nên công bố sau khi đã rà soát việc rò rỉ giữa các tập và giữ nguyên cấu hình đã chọn từ validation.

**Tài liệu nên đọc theo thứ tự:** `README_START_HERE.txt` → `README.md` → `docs/FILE_GUIDE.md` → `docs/ARCHITECTURE.md` → `docs/REAL_DATASET_REPORT.md` → `docs/API.md` → `docs/STUDY_PLAN.md` → code → `tests/test_pipeline.py`.
