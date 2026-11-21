"""Tìm Top 5 ảnh theo khoảng cách RMS sau khi chuẩn hóa bằng gallery."""

import base64
import json
from pathlib import Path
from time import perf_counter

import numpy as np

from ..db import connect
from ..repository import DatasetNotReady, feature_stats, read_vectors
from ..vision.features import DIMENSIONS, ORDER, extract_features
from ..vision.preprocess import ProcessedImage, to_png


def normalize_weights(raw: dict[str, float]) -> dict[str, float]:
    """Nhận 4 số >=0, chuẩn hóa tổng thành 1; từ chối NaN/inf/toàn số 0."""
    values = np.asarray([raw[k] for k in ORDER], dtype=float)
    if not np.isfinite(values).all() or np.any(values < 0) or values.sum() == 0:
        raise ValueError("Trọng số phải hữu hạn, không âm và có tổng lớn hơn 0")
    values /= values.sum()
    return dict(zip(ORDER, values.tolist()))


def prepare_index(db_path: Path, version: str) -> tuple[list[dict], dict]:
    """Đọc vector gallery và statistics; không lẫn validation/test vào ứng viên."""
    gallery = read_vectors(db_path, "gallery", version)
    if len(gallery) < 5:
        raise DatasetNotReady("Gallery cần ít nhất 5 ảnh để tìm Top 5")
    stats = feature_stats(db_path, version, len(gallery))
    return gallery, stats


def rank(
    query: dict[str, np.ndarray], gallery: list[dict], stats: dict,
    weights: dict[str, float], k: int = 5,
) -> list[dict]:
    """Tính từng D_g, D tổng; trả kết quả sắp tăng theo khoảng cách."""
    scores = np.zeros(len(gallery), dtype=np.float64)
    components = {}
    for group in ORDER:
        if query[group].shape != (DIMENSIONS[group],):
            raise ValueError(f"Query {group} không đủ chiều")
        scale = stats[group]["scale"]
        # Do z(Q)-z(I)=(Q-I)/scale, mean hủy nhau ở phép trừ.
        candidates = np.stack([row["vectors"][group] for row in gallery])
        distances = np.sqrt(np.mean(((candidates - query[group]) / scale) ** 2, axis=1))
        components[group] = distances
        scores += weights[group] * distances
    # Merge-sort đảm bảo thứ tự ổn định với trường hợp hòa khoảng cách.
    selected = np.argsort(scores, kind="stable")[:k]
    return [{
        "rank": i+1, "image_id": gallery[int(j)]["image_id"],
        "file_name": gallery[int(j)]["file_name"],
        "group_id": gallery[int(j)]["group_id"],
        "image_url": f"/api/images/{gallery[int(j)]['image_id']}/file",
        "distance_total": round(float(scores[j]), 6),
        "distance_by_group": {g: round(float(components[g][j]), 6) for g in ORDER},
    } for i, j in enumerate(selected)]


def _png_data_url(array: np.ndarray) -> str:
    """Chỉ ảnh sau xử lý của truy vấn được trả base64, không lưu file upload."""
    return "data:image/png;base64," + base64.b64encode(to_png(array)).decode("ascii")


def search_image(
    db_path: Path, version: str, query_item: ProcessedImage,
    file_name: str, raw_weights: dict[str, float], save_log: bool = True,
) -> dict:
    """Trích xuất 1 ảnh truy vấn và xếp hạng so với gallery đã lập CSDL."""
    started = perf_counter()
    weights = normalize_weights(raw_weights)
    vectors = extract_features(query_item)
    gallery, stats = prepare_index(db_path, version)
    results = rank(vectors, gallery, stats, weights)
    elapsed_ms = round((perf_counter()-started)*1000, 1)
    response = {
        "version": version, "gallery_count": len(gallery),
        "weights": weights, "runtime_ms": elapsed_ms,
        "query": {
            "file_name": file_name,
            "mask_ratio": round(query_item.mask_ratio, 6),
            "quality_warning": query_item.warning,
            "normalized_image": _png_data_url(query_item.image),
            "mask_image": _png_data_url(query_item.mask),
        },
        "results": results,
        "meaning": "Khoảng cách thấp hơn = gần hơn; không phải xác suất nhận dạng loài.",
    }
    if save_log:
        with connect(db_path) as con:
            con.execute(
                "INSERT INTO search_logs(query_file_name,version,weights_json,results_json,runtime_ms) "
                "VALUES (?,?,?,?,?)",
                (file_name[:256], version, json.dumps(weights), json.dumps(results), elapsed_ms),
            )
    return response
