"""Các truy vấn SQL chỉ phục vụ nghiệp vụ, tách biệt API và thuật toán."""

import numpy as np
from pathlib import Path

from .db import connect, decode_vector, get_metadata
from .vision.features import DIMENSIONS, ORDER


class DatasetNotReady(RuntimeError):
    """CSDL chưa có gallery/feature_stats đồng nhất phiên bản."""


def dataset_status(db_path: Path, version: str) -> dict:
    """Đọc thống kê thật trong SQLite; không hard-code số 1.685."""
    with connect(db_path) as con:
        total = con.execute("SELECT COUNT(*) FROM images").fetchone()[0]
        categories = con.execute("SELECT COUNT(*) FROM categories").fetchone()[0]
        parts = {r["split"]: r["n"] for r in con.execute(
            "SELECT split,COUNT(*) AS n FROM images GROUP BY split"
        )}
        vector_count = con.execute(
            "SELECT COUNT(*) FROM features WHERE version=?", (version,)
        ).fetchone()[0]
        review_count = con.execute(
            "SELECT COUNT(*) FROM images WHERE quality_status='review'"
        ).fetchone()[0]
        label = get_metadata(con, "dataset_label", "uninitialized")
        stat_count = con.execute(
            "SELECT COUNT(*) FROM feature_stats WHERE version=?", (version,)
        ).fetchone()[0]
        ready = (total > 0 and parts.get("gallery", 0) >= 5
                 and vector_count == 4*total and stat_count == 4)
        return {
            "ready": ready, "dataset_label": label, "total_images": total,
            "categories": categories, "vector_count": vector_count,
            "gallery": parts.get("gallery", 0),
            "validation": parts.get("validation", 0),
            "test": parts.get("test", 0),
            "review_count": review_count,
            "pipeline_version": version,
        }


def categories(db_path: Path) -> list[dict]:
    with connect(db_path) as con:
        rows = con.execute(
            "SELECT c.group_id,c.description,COUNT(i.image_id) AS image_count, "
            "MIN(i.image_id) AS sample_image_id "
            "FROM categories c LEFT JOIN images i ON i.group_id=c.group_id "
            "GROUP BY c.group_id ORDER BY c.group_id"
        ).fetchall()
        return [dict(r) | {"thumbnail_url": f"/api/images/{r['sample_image_id']}/file"
                        if r["sample_image_id"] is not None else None} for r in rows]


def list_images(db_path: Path, group: str | None, split: str | None, name: str,
                page: int, limit: int) -> dict:
    """Truy vấn phân trang (không trả BLOB) và tránh nối chuỗi SQL tùy tiện."""
    conditions, params = [], []
    if group:
        conditions.append("group_id=?")
        params.append(group)
    if split:
        conditions.append("split=?")
        params.append(split)
    if name:
        conditions.append("file_name LIKE ?")
        params.append(f"%{name}%")
    where = " WHERE " + " AND ".join(conditions) if conditions else ""
    with connect(db_path) as con:
        total = con.execute("SELECT COUNT(*) FROM images"+where, params).fetchone()[0]
        rows = con.execute(
            "SELECT image_id,file_name,group_id,split,mask_ratio,quality_status,width,height "
            "FROM images" + where + " ORDER BY group_id,file_name LIMIT ? OFFSET ?",
            (*params, limit, (page-1)*limit),
        ).fetchall()
    items = [dict(r) | {"image_url": f"/api/images/{r['image_id']}/file"} for r in rows]
    return {"items": items, "total": total, "page": page, "page_size": limit}


def image_details(db_path: Path, image_id: int, version: str) -> dict | None:
    with connect(db_path) as con:
        row = con.execute("SELECT * FROM images WHERE image_id=?", (image_id,)).fetchone()
        if not row:
            return None
        groups = con.execute(
            "SELECT feature_group,dimension,version,vector FROM features "
            "WHERE image_id=? AND version=? ORDER BY feature_group", (image_id, version)
        ).fetchall()
    result = {key: row[key] for key in row.keys()}
    result.update(image_url=f"/api/images/{image_id}/file",
                  normalized_url=f"/api/images/{image_id}/processed/normalized",
                  mask_url=f"/api/images/{image_id}/processed/mask",
                  features={r["feature_group"]: {
                      "dimension": r["dimension"], "version": r["version"],
                      "sample_values": decode_vector(r["vector"], r["dimension"])[:12].round(6).tolist(),
                  } for r in groups})
    return result


def image_path(db_path: Path, image_id: int, images_dir: Path) -> Path | None:
    """Dùng đường dẫn tương đối do importer ghi, không dùng đường dẫn từ URL."""
    with connect(db_path) as con:
        row = con.execute("SELECT relative_path FROM images WHERE image_id=?", (image_id,)).fetchone()
    if not row:
        return None
    path = (images_dir / row["relative_path"]).resolve()
    root = images_dir.resolve()
    if not path.is_relative_to(root):
        return None
    return path


def read_vectors(db_path: Path, split: str, version: str) -> list[dict]:
    """Đọc 4 BLOB/ảnh và fail-fast nếu thiếu hoặc khác phiên bản."""
    with connect(db_path) as con:
        rows = con.execute(
            "SELECT i.image_id,i.file_name,i.group_id,f.feature_group,f.dimension,f.vector "
            "FROM images i JOIN features f ON i.image_id=f.image_id "
            "WHERE i.split=? AND f.version=? ORDER BY i.image_id", (split, version)
        ).fetchall()
        expected_count = con.execute(
            "SELECT COUNT(*) FROM images WHERE split=?", (split,)
        ).fetchone()[0]
    indexed: dict[int, dict] = {}
    for row in rows:
        item = indexed.setdefault(row["image_id"], {
            "image_id": row["image_id"], "file_name": row["file_name"],
            "group_id": row["group_id"], "vectors": {},
        })
        group = row["feature_group"]
        if group not in DIMENSIONS or row["dimension"] != DIMENSIONS[group]:
            raise DatasetNotReady("Một vector trong cơ sở dữ liệu sai cấu trúc")
        item["vectors"][group] = decode_vector(row["vector"], row["dimension"])
    if len(indexed) != expected_count or any(set(x["vectors"]) != set(ORDER) for x in indexed.values()):
        raise DatasetNotReady("Thiếu vector hoặc sai phiên bản: hãy xây dựng lại database")
    return list(indexed.values())


def feature_stats(db_path: Path, version: str, gallery_count: int) -> dict:
    """Đọc mean/scale được tính DUY NHẤT từ gallery."""
    with connect(db_path) as con:
        rows = con.execute("SELECT * FROM feature_stats WHERE version=?", (version,)).fetchall()
    if len(rows) != 4:
        raise DatasetNotReady("Thiếu feature_stats: hãy chạy script import")
    stats = {}
    for row in rows:
        group = row["feature_group"]
        if group not in DIMENSIONS or row["dimension"] != DIMENSIONS[group] or row["gallery_count"] != gallery_count:
            raise DatasetNotReady("feature_stats không phù hợp với gallery hoặc phiên bản")
        mu = decode_vector(row["mean_vector"], row["dimension"])
        scale = decode_vector(row["scale_vector"], row["dimension"])
        if np.any(scale <= 0):
            raise DatasetNotReady("Scale chuẩn hóa phải dương")
        stats[group] = {"mean": mu, "scale": scale}
    return stats
