"""Tổng hợp chất lượng ảnh/kiểm tra rủi ro gần trùng để giải thích metrics.

Không tự đánh giá hai ảnh là một bản sao. pHash chỉ sinh danh sách *ứng viên*
cho người nghiên cứu kiểm tra thủ công, đặc biệt khi khác split.
"""

from __future__ import annotations

import csv
from pathlib import Path

from ..db import connect


def quality_summary(db_path: Path, *, limit: int = 12) -> dict:
    """Đọc ảnh bị flag từ DB, tổng hợp pHash nếu có tệp kiểm kê."""
    with connect(db_path) as con:
        review_count = con.execute(
            "SELECT COUNT(*) FROM images WHERE quality_status='review'"
        ).fetchone()[0]
        rows = con.execute(
            "SELECT image_id,file_name,group_id,mask_ratio,split "
            "FROM images WHERE quality_status='review' "
            "ORDER BY mask_ratio ASC, image_id ASC LIMIT ?", (limit,)
        ).fetchall()
    samples = [{**dict(r), "image_url": f"/api/images/{r['image_id']}/file",
                "mask_url": f"/api/images/{r['image_id']}/processed/mask"} for r in rows]
    csv_file = db_path.parent / "near_duplicate_review.csv"
    if not csv_file.exists():
        return {"review_count": review_count, "review_samples": samples,
                "audit_available": False, "candidate_pairs": None,
                "cross_split_pairs": None, "same_group_cross_split": None,
                "csv_url": None,
                "note": "Chưa chạy pHash audit. Lệnh: python -m backend.tools.audit_near_duplicates"}
    total = cross_split = same_group_cross_split = 0
    with csv_file.open(newline="", encoding="utf-8-sig") as stream:
        for row in csv.DictReader(stream):
            total += 1
            if row["cross_split"] == "True":
                cross_split += 1
                if row["cross_group"] == "False":
                    same_group_cross_split += 1
    return {"review_count": review_count, "review_samples": samples,
            "audit_available": True, "candidate_pairs": total,
            "cross_split_pairs": cross_split,
            "same_group_cross_split": same_group_cross_split,
            "csv_url": "/api/quality/near-duplicates.csv",
            "note": "Các cặp nghi gần trùng theo pHash <= 6, chưa xác nhận trùng thực tế; "
                    "không tự xóa hay điều chỉnh các tập."}
