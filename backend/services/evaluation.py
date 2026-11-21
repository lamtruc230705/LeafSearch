"""Đánh giá CBIR trên validation/test, không sử dụng ảnh query trong gallery."""

import json
from pathlib import Path
from time import perf_counter

from ..db import connect
from ..repository import read_vectors
from .search import normalize_weights, prepare_index, rank


def evaluate(db_path: Path, version: str, split: str, weights_raw: dict[str, float]) -> dict:
    """Tính Accuracy@1, Precision@5, MRR@5 trên dữ liệu THỰC có trong SQLite."""
    if split not in {"test", "validation"}:
        raise ValueError("Chỉ hỗ trợ test hoặc validation")
    weights = normalize_weights(weights_raw)
    gallery, stats = prepare_index(db_path, version)
    queries = read_vectors(db_path, split, version)
    if not queries:
        raise ValueError(f"Không có ảnh thuộc tập {split}")
    started = perf_counter()
    detail = []
    for query in queries:
        top = rank(query["vectors"], gallery, stats, weights)
        correct = [r["group_id"] == query["group_id"] for r in top]
        first_correct = next((i + 1 for i, yes in enumerate(correct) if yes), None)
        detail.append({
            "image_id": query["image_id"], "file_name": query["file_name"],
            "group_id": query["group_id"], "correct_at_1": bool(correct[0]),
            "correct_in_top5": sum(correct),
            "precision_at_5": sum(correct)/5,
            "reciprocal_rank": 1/first_correct if first_correct else 0.0,
            "top5": top,
        })
    count = len(detail)
    metrics = {
        "queries": count, "gallery_count": len(gallery),
        "accuracy_at_1": round(sum(x["correct_at_1"] for x in detail)/count, 6),
        "precision_at_5": round(sum(x["precision_at_5"] for x in detail)/count, 6),
        "mrr_at_5": round(sum(x["reciprocal_rank"] for x in detail)/count, 6),
        "runtime_ms": round((perf_counter()-started)*1000, 1),
    }
    with connect(db_path) as con:
        cur = con.execute(
            "INSERT INTO evaluation_runs(split,version,weights_json,metrics_json,details_json) "
            "VALUES (?,?,?,?,?)",
            (split, version, json.dumps(weights), json.dumps(metrics), json.dumps(detail)),
        )
        evaluation_id = cur.lastrowid
    return {
        "evaluation_id": evaluation_id, "split": split, "version": version,
        "weights": weights, "metrics": metrics,
        "examples_wrong": [d for d in detail if not d["correct_at_1"]][:8],
        "note": "Metric dùng mã nhóm hình thái, không xác nhận tên loài. "
                "Cần kiểm tra rò rỉ near-duplicate trước khi công bố kết quả.",
    }


def get_evaluation(db_path: Path, evaluation_id: int | None = None) -> dict | None:
    with connect(db_path) as con:
        if evaluation_id is None:
            row = con.execute("SELECT * FROM evaluation_runs ORDER BY evaluation_id DESC LIMIT 1").fetchone()
        else:
            row = con.execute("SELECT * FROM evaluation_runs WHERE evaluation_id=?", (evaluation_id,)).fetchone()
    if not row:
        return None
    details = json.loads(row["details_json"])
    return {
        "evaluation_id": row["evaluation_id"],
        "split": row["split"], "version": row["version"],
        "created_at": row["created_at"], "weights": json.loads(row["weights_json"]),
        "metrics": json.loads(row["metrics_json"]),
        "examples_wrong": [d for d in details if not d["correct_at_1"]][:8],
        "query_count": len(details),
    }
