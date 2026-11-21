"""Kiểm chứng độc lập dữ liệu ảnh THẬT và 4 vector đã lưu trong SQLite.

Chạy: python -m backend.tools.verify_dataset
Không xây lại vector; dùng kiểm tra trước khi trình diễn/nộp bài.
"""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path

import numpy as np
from PIL import Image

from ..config import SETTINGS
from ..db import connect, decode_vector
from ..vision.features import DIMENSIONS, ORDER
from .import_dataset import EXPECTED_COUNTS


def verify_dataset(db_path: Path, images_dir: Path, *, strict: bool = True,
                   check_hashes: bool = True) -> dict:
    """Đối chiếu DB và file PNG, kiểm tra toàn vẹn vector và mean/scale gallery.

    strict=True kiểm tra số lượng chính thức trong báo cáo PTIT (1685/32 nhóm).
    Hàm trả báo cáo JSON nhỏ; dữ liệu không đúng thì ném ValueError.
    """
    if not db_path.is_file() or not images_dir.is_dir():
        raise FileNotFoundError("Chưa có SQLite hoặc thư mục ảnh; hãy nhập ZIP trước")
    with connect(db_path) as con:
        integrity = con.execute("PRAGMA integrity_check").fetchone()[0]
        fk = con.execute("PRAGMA foreign_key_check").fetchall()
        rows = con.execute("SELECT image_id,file_name,group_id,relative_path,sha256,"
                           "pixel_sha256,width,height,split FROM images ORDER BY image_id").fetchall()
        features = con.execute("SELECT image_id,feature_group,version,dimension,vector FROM features").fetchall()
        feature_stats = con.execute("SELECT * FROM feature_stats").fetchall()
    if integrity != "ok" or fk:
        raise ValueError("SQLite không toàn vẹn")
    if not rows:
        raise ValueError("SQLite không có ảnh")
    ids = {r["image_id"] for r in rows}
    groups = Counter(r["group_id"] for r in rows)
    splits = Counter(r["split"] for r in rows)
    if strict:
        if len(rows) != 1685 or dict(groups) != EXPECTED_COUNTS:
            raise ValueError("Số lượng/mã nhóm ảnh không khớp báo cáo PTIT")
        if splits != {"gallery": 1345, "validation": 170, "test": 170}:
            raise ValueError("Phân tập không khớp 1345/170/170")
    root = images_dir.resolve()
    bytes_verified = 0
    for row in rows:
        path = (root / row["relative_path"]).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise ValueError(f"Thiếu hoặc đường dẫn ảnh không hợp lệ: {row['file_name']}")
        if row["file_name"] != path.name or not row["relative_path"].startswith(row["group_id"] + "/"):
            raise ValueError(f"Sai định danh ảnh: {row['file_name']}")
        if strict and (row["width"], row["height"]) != (512, 512):
            raise ValueError(f"Sai kích thước ảnh: {row['file_name']}")
        if check_hashes:
            blob = path.read_bytes()
            bytes_verified += len(blob)
            if sha256(blob).hexdigest() != row["sha256"]:
                raise ValueError(f"Byte ảnh đã bị thay đổi: {row['file_name']}")
            with Image.open(path) as img:
                if img.format != "PNG" or img.mode != "RGB" or img.size != (row["width"], row["height"]):
                    raise ValueError(f"Ảnh hỏng/khác metadata: {row['file_name']}")
                if sha256(np.asarray(img).tobytes()).hexdigest() != row["pixel_sha256"]:
                    raise ValueError(f"Pixel ảnh bị thay đổi: {row['file_name']}")
    actual_files = {p.resolve() for p in images_dir.rglob("*.png")}
    if len(actual_files) != len(rows):
        raise ValueError(f"Số ảnh trên đĩa ({len(actual_files)}) khác DB ({len(rows)})")

    vector_versions = Counter(x["version"] for x in features)
    if len(vector_versions) != 1:
        raise ValueError("Có nhiều phiên bản vector lẫn trong DB")
    version = next(iter(vector_versions))
    vectors_by_group = {name: {} for name in ORDER}
    vector_pairs = set()
    for f in features:
        g = f["feature_group"]
        if f["image_id"] not in ids or g not in DIMENSIONS or f["dimension"] != DIMENSIONS[g]:
            raise ValueError("Đặc trưng không hợp lệ hoặc tham chiếu ảnh không tồn tại")
        key = (f["image_id"], g)
        if key in vector_pairs:
            raise ValueError("Trùng vector của một ảnh")
        vector_pairs.add(key)
        vectors_by_group[g][f["image_id"]] = decode_vector(f["vector"], DIMENSIONS[g])
    if len(vector_pairs) != len(rows) * len(ORDER):
        raise ValueError("Thiếu vector, không đủ 4 nhóm/ảnh")
    if len(feature_stats) != len(ORDER):
        raise ValueError("Thiếu thống kê chuẩn hóa gallery")
    gallery_ids = {r["image_id"] for r in rows if r["split"] == "gallery"}
    for stats in feature_stats:
        group = stats["feature_group"]
        if group not in ORDER or stats["version"] != version or stats["gallery_count"] != len(gallery_ids):
            raise ValueError("feature_stats khác phiên bản hoặc sai gallery_count")
        scale = decode_vector(stats["scale_vector"], DIMENSIONS[group])
        mean = decode_vector(stats["mean_vector"], DIMENSIONS[group])
        gallery_array = np.stack([vectors_by_group[group][i] for i in sorted(gallery_ids)])
        if np.any(scale <= 0) or not np.allclose(mean, gallery_array.mean(axis=0), atol=1e-4, rtol=1e-4):
            raise ValueError(f"Thống kê chuẩn hóa lỗi ở nhóm {group}")
        expected_scale = gallery_array.std(axis=0)
        expected_scale[expected_scale < 1e-8] = 1.0
        if not np.allclose(scale, expected_scale, atol=1e-4, rtol=1e-4):
            raise ValueError(f"Scale gallery không chính xác ở nhóm {group}")
    return {
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "passed": True, "sqlite_integrity": integrity, "sqlite_foreign_key_errors": len(fk),
        "images": len(rows), "groups": len(groups), "images_by_group": dict(sorted(groups.items())),
        "splits": dict(splits), "feature_vectors": len(features),
        "feature_dimensions": DIMENSIONS, "pipeline_version": version,
        "image_bytes_verified": bytes_verified, "byte_sha256_and_pixel_sha256_checked": check_hashes,
        "gallery_mean_and_scale_recomputed": True,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Xác minh ảnh PNG, SQLite và 4 vector/ảnh")
    parser.add_argument("--db", type=Path, default=SETTINGS.database)
    parser.add_argument("--images", type=Path, default=SETTINGS.images_dir)
    parser.add_argument("--output", type=Path, default=SETTINGS.database.parent / "verification.json")
    parser.add_argument("--allow-nonstandard", action="store_true", help="Cho bộ dữ liệu thử nhỏ")
    parser.add_argument("--no-hash", action="store_true", help="Không kiểm tra SHA-256 (nhanh hơn)")
    args = parser.parse_args()
    result = verify_dataset(args.db, args.images, strict=not args.allow_nonstandard,
                            check_hashes=not args.no_hash)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
