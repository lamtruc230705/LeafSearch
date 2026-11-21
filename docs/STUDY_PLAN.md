# Lộ trình 10 bài: hiểu toàn bộ dự án và tự bảo vệ trước giảng viên

Đây là tài liệu hướng dẫn đọc code và thao tác cụ thể. Mỗi bài đọc đúng một tầng, tự trả lời câu hỏi cuối bài.

| Bài | Tệp cần đọc | Việc tự làm để hiểu thật |
| --- | --- | --- |
| 1 | `README.md`, `frontend/index.html` | Vẽ lại sitemap 6 trang; tìm ID `searchBtn`, `libraryGrid` |
| 2 | `frontend/styles.css` | Đổi màu theme, kiểm tra responsive trên điện thoại |
| 3 | `frontend/app.js` | Đặt breakpoint ở `doSearch()` để xem FormData ảnh/trọng số |
| 4 | `backend/main.py`, `backend/api.py` | Mở `/docs`, tìm route `POST /api/search` |
| 5 | `backend/config.py`, `backend/db.py`, `backend/schema.sql` | Mở SQLite DB Browser, chạy `SELECT COUNT(*) FROM features;` |
| 6 | `backend/tools/import_dataset.py` | Tự giải thích mã nhóm `14.1.png -> 14`; in thống kê split |
| 7 | `backend/vision/preprocess.py` | So sánh ảnh gốc, normalized và mask của một ảnh thật |
| 8 | `backend/vision/features.py` | Tính tổng 326+145+41+48 và chỉ ra tác dụng từng nhóm |
| 9 | `backend/services/search.py`, `backend/repository.py` | Với 1 ảnh test, kiểm tra Top 5 luôn thuộc gallery |
| 10 | `backend/services/evaluation.py`, `tests/test_pipeline.py` | Chạy test, đọc các metric và phân tích trường hợp sai |

## 10 câu hỏi giảng viên thường hỏi và cách trả lời

1. **Website tìm theo tên cây hay ảnh?** Theo nội dung ảnh (CBIR): ảnh mới -> vector đặc trưng -> so với gallery; tên nhóm chỉ dùng để đánh giá.
2. **Vì sao 560 chiều?** Bốn nhóm số 326 màu, 145 hình dạng, 41 đường gờ ứng viên, 48 kết cấu, cộng thành 560.
3. **Vì sao tiền xử lý?** Để giảm ảnh hưởng nền, vị trí và tỉ lệ phóng; lấy đặc trưng trên lá thay vì nền trắng.
4. **Vì sao dùng SQLite?** Số ảnh 1.685 và 6.740 BLOB thuộc bài tập vừa phải; SQLite thuận tiện, có ràng buộc và query.
5. **Có phải học máy phân loại không?** Không. Đây là CBIR dựa trên khoảng cách đặc trưng và xếp hạng Top 5.
6. **Vì sao chỉ lấy gallery?** Validation/test phục vụ đánh giá; đưa chúng vào ứng viên sẽ làm sai quy trình kiểm thử.
7. **Vì sao chuẩn hóa RMS?** Số chiều và thang đo mỗi nhóm khác nhau; RMS và scale bảo đảm kết hợp trọng số có ý nghĩa hơn.
8. **Top 5 được chọn ra sao?** Tính D của query với từng vector gallery, sắp D tăng và lấy 5 ảnh đầu.
9. **P@5 có luôn phản ánh tốt thuật toán không?** Không. Nhóm có ít hơn 5 ảnh gallery thì trần P@5 nhỏ hơn 100%.
10. **Độ chính xác ước lượng như thế nào?** Chạy test thật, đo Accuracy@1, P@5, MRR@5, rà soát ảnh gần trùng, không bịa tỷ lệ thành công.

## Checklist trước khi nộp

- [ ] `GET /api/health` có `ready=true` và 1.685 ảnh thật.
- [ ] Kiểm tra 32 nhãn nhóm theo tên tệp, không tự chuyển thành loài.
- [ ] Xem được ảnh gốc + normalized + mask của 4 nhóm đặc biệt.
- [ ] Tải một ảnh chưa nằm trong gallery rồi tìm được Top 5 ảnh thật, có D.
- [ ] Kiểm tra ít nhất một kết quả tìm kiếm sai.
- [ ] Chạy audit pHash, xem và xử lý trường hợp rò rỉ nếu có.
- [ ] Chạy validation để chọn cấu hình, khóa trọng số rồi mới đo test.
- [ ] Ghi metric thật vào báo cáo Phần IV, ghi đúng số query và runtime.
- [ ] `python -m pytest -q` xanh, không có lỗi integrity_check.
- [ ] Hiểu nhiệm vụ của từng file trong `docs/FILE_GUIDE.md`.

## Bài 11 — Rà soát dữ liệu và chất lượng mô hình tìm kiếm

1. Đọc `backend/tools/verify_dataset.py`, hiểu vì sao kiểm ảnh gốc và vector là hai việc khác nhau.
2. Mở `data/verification.json` và `data/image_manifest.csv`, so sánh với `backend/schema.sql`.
3. Đọc `backend/services/quality.py` và quan sát tab Đánh giá — phần rà soát ảnh/mask.
4. Mở `data/near_duplicate_review.csv`, hiểu vì sao pHash không chứng minh tuyệt đối hai ảnh trùng nhau.
5. Đọc `backend/tools/evaluate_sensitivity.py` và `docs/REAL_DATASET_REPORT.md`; phân biệt thực nghiệm trên tập hiện có với khả năng khái quát hóa sang ảnh độc lập.
