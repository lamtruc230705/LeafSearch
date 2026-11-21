# REST API LeafSearch — hướng dẫn gọi và kiểm tra

Khởi chạy: `python -m uvicorn backend.main:app --reload`. API base URL: `http://127.0.0.1:8000/api`.
Swagger tự động: `http://127.0.0.1:8000/docs`.

| Method | URL | Nhiệm vụ | Kết quả |
| --- | --- | --- | --- |
| GET | `/api/health` | Kiểm tra DB và 4 stats | `ready`, `total_images`, `gallery`, `test` |
| GET | `/api/dashboard` | Thống kê từ DB | như health, dùng cho dashboard |
| GET | `/api/categories` | Nhóm hình thái | `items:[{group_id,image_count,thumbnail_url}]` |
| GET | `/api/quality` | Chỉ số mặt nạ/pHash và ảnh cần xem lại | `review_count`, `cross_split_pairs`, `review_samples` |
| GET | `/api/quality/near-duplicates.csv` | Tải danh sách pHash nghi vấn | CSV / HTTP 404 nếu chưa chạy audit |
| GET | `/api/images?page=1&page_size=24&group_id=01` | Danh sách ảnh theo nhóm | `items`, `total`, `page`, `page_size` |
| GET | `/api/images/{image_id}` | Metadata và 12 số mẫu mỗi vector | `features` theo 4 nhóm, URL ảnh/mask |
| GET | `/api/images/{image_id}/file` | PNG ảnh gốc | `Content-Type: image/png` |
| GET | `/api/images/{image_id}/processed/normalized` | PNG ảnh chuẩn hóa | PNG |
| GET | `/api/images/{image_id}/processed/mask` | PNG mask foreground | PNG |
| POST | `/api/search` | FormData upload + 4 trọng số | `query`, `results` Top 5, runtime |
| POST | `/api/evaluate` | JSON `{split, weights}` | số liệu thật và ví dụ sai |
| GET | `/api/evaluations/latest` | Lần đánh giá gần nhất | Metrics / examples_wrong |
| GET | `/api/evaluations/{id}` | Một lần đánh giá theo id | Metrics / examples_wrong |

## Upload ảnh qua cURL

```bash
curl -X POST http://127.0.0.1:8000/api/search \
  -F "file=@test_leaf.png" \
  -F "color=25" -F "shape=45" -F "ridge=15" -F "texture=15"
```

JSON trả về (chỉ **ví dụ cấu trúc**, không phải số đo thật):

```json
{
  "version": "leaf-v1-web-1.0",
  "gallery_count": 1345,
  "weights": {"color": 0.25, "shape": 0.45, "ridge": 0.15, "texture": 0.15},
  "runtime_ms": 0,
  "query": {"file_name": "test_leaf.png", "mask_ratio": 0, "quality_warning": null,
            "normalized_image": "data:image/png;base64,...", "mask_image": "data:image/png;base64,..."},
  "results": [
    {"rank": 1, "image_id": 101, "file_name": "14.1.png", "group_id": "14",
     "image_url": "/api/images/101/file", "distance_total": 0,
     "distance_by_group": {"color": 0, "shape": 0, "ridge": 0, "texture": 0}}
  ],
  "meaning": "Khoảng cách thấp hơn = gần hơn; không phải xác suất nhận dạng loài."
}
```

Dòng ví dụ trên dùng **0 làm placeholder minh họa cấu trúc**, tuyệt đối không sử dụng để báo cáo kết quả. API thật luôn trả Top 5 từ SQLite sau khi nhập ảnh thành công.

## Đánh giá

```bash
curl -X POST http://127.0.0.1:8000/api/evaluate \
  -H "Content-Type: application/json" \
  -d '{"split":"test", "weights":{"color":0.25,"shape":0.45,"ridge":0.15,"texture":0.15}}'
```

Giá trị `split` chỉ được phép là `test` hoặc `validation`. Nên chạy validation trước khi khóa cấu hình, sau đó mới đánh giá test.

## Lỗi thường gặp

| HTTP | Nguyên nhân | Cách xử lý |
| --- | --- | --- |
| 400 | Tệp ảnh bị lỗi/mask rỗng/trọng số âm/sai split | Kiểm tra input hoặc đưa ảnh lên nền sáng |
| 404 | Không có ảnh theo ID | Duyệt `/api/images` để biết ID |
| 413 | Upload vượt 10 MB | Dùng ảnh nhỏ hơn |
| 415 | Tệp không phải PNG, JPG hoặc WebP | Chọn định dạng hợp lệ |
| 422 | Trường form/JSON sai kiểu | Mở Swagger để xem schema |
| 503 | DB chưa nạp hoặc thiếu feature_stats/gallery | Chạy lại importer và `GET /api/health` |

Mọi endpoint sử dụng `image_id` từ DB để truy vấn ảnh; backend không bao giờ cho client chỉ định đường dẫn file tùy ý.
