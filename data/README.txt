BẢN V1.1 ĐÃ TÍCH HỢP TOÀN BỘ DỮ LIỆU THẬT (21/11/2026)

images/                   1.685 PNG thực tế, phân theo 32 mã nhóm
leafsearch.sqlite         SQLite đã có 6.740 vector, feature_stats, metric test/validation
image_manifest.csv        Tên file, mã nhóm, split, hash byte/pixel
verification.json         Kết quả xác minh hash PNG, SQLite và mean/scale gallery
dataset_release.json      Dữ liệu nguồn, mã SHA-256 và metrics từ thử nghiệm
near_duplicate_review.csv 4.766 cặp nghi vấn pHash, KHÔNG xác nhận trùng
phash_sensitivity.json    Thử nghiệm độ nhạy nếu loại ứng viên pHash khỏi gallery
{test,validation}_group_metrics.csv, *_top1_errors.csv: phân tích từng nhóm/truy vấn sai
removed_duplicates.json  Danh sách 0 ảnh trùng chính xác khi import

CẤM đổi tên/di chuyển ảnh trong images/ vì DB giữ đường dẫn tương đối.
Không coi nhóm 01..32 là loài thực vật đã kiểm chứng.
Tài liệu diễn giải: docs/REAL_DATASET_REPORT.md.
