"""Thử nghiệm độ nhạy: bỏ ứng viên gallery nghi gần trùng pHash với từng query.

Đây KHÔNG phải phép loại trùng xác nhận và KHÔNG thay thế đánh giá Top 5 chuẩn.
Dùng để minh họa rủi ro rò rỉ giữa tập test và gallery theo ngưỡng pHash.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
import csv
import json
from pathlib import Path

from ..config import SETTINGS
from ..services.search import normalize_weights, prepare_index, rank
from ..repository import read_vectors
from ..vision.features import DEFAULT_WEIGHTS


def sensitivity_check(db: Path, audit_csv: Path, split: str = "test") -> dict:
    """Với mỗi query, loại gallery gần theo pHash rồi xếp hạng lại.

    Chú ý pHash có false positive/false negative; không xóa ảnh khỏi SQLite.
    """
    if split not in {"validation", "test"}:
        raise ValueError("split phải là validation/test")
    if not audit_csv.exists():
        raise FileNotFoundError("Chưa chạy audit_near_duplicates")
    excluded_by_query: dict[str, set[str]] = defaultdict(set)
    with audit_csv.open(newline="", encoding="utf-8-sig") as stream:
        for pair in csv.DictReader(stream):
            # Kết quả là cặp vô hướng: cả thứ tự query/gallery đều hợp lệ.
            if pair["split_a"] == split and pair["split_b"] == "gallery":
                excluded_by_query[pair["file_a"]].add(pair["file_b"])
            if pair["split_b"] == split and pair["split_a"] == "gallery":
                excluded_by_query[pair["file_b"]].add(pair["file_a"])
    gallery, stats = prepare_index(db, SETTINGS.pipeline_version)
    queries = read_vectors(db, split, SETTINGS.pipeline_version)
    weights = normalize_weights(DEFAULT_WEIGHTS)
    detailed = []
    for q in queries:
        excludes = excluded_by_query.get(q["file_name"], set())
        clean_gallery = [item for item in gallery if item["file_name"] not in excludes]
        if len(clean_gallery) < 5:
            raise ValueError(f"Gallery còn dưới 5 ảnh cho {q['file_name']}")
        top5 = rank(q["vectors"], clean_gallery, stats, weights)
        correct = [item["group_id"] == q["group_id"] for item in top5]
        first_correct = next((pos + 1 for pos, ok in enumerate(correct) if ok), None)
        detailed.append({
            "file_name": q["file_name"], "group_id": q["group_id"],
            "excluded_gallery_candidates": len(excludes),
            "accuracy_at_1": int(correct[0]),
            "precision_at_5": sum(correct) / 5,
            "reciprocal_rank_at_5": 1 / first_correct if first_correct else 0,
        })
    n = len(detailed)
    return {
        "split": split, "queries": n, "weight_profile": weights,
        "phash_threshold": 6, "warning": (
            "Kết quả stress-test pHash. Cặp nghi vấn KHÔNG phải bản sao đã xác nhận; "
            "loại nhầm mẫu hợp lệ có thể làm metric giảm. Không dùng kết quả để "
            "tối ưu cấu hình từ tập test."
        ),
        "queries_with_exclusions": sum(x["excluded_gallery_candidates"] > 0 for x in detailed),
        "suspected_gallery_exclusions_total": sum(x["excluded_gallery_candidates"] for x in detailed),
        "accuracy_at_1": round(sum(x["accuracy_at_1"] for x in detailed) / n, 6),
        "precision_at_5": round(sum(x["precision_at_5"] for x in detailed) / n, 6),
        "mrr_at_5": round(sum(x["reciprocal_rank_at_5"] for x in detailed) / n, 6),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Thử nghiệm độ nhạy pHash, không thay đổi DB")
    parser.add_argument("--db", type=Path, default=SETTINGS.database)
    parser.add_argument("--audit", type=Path, default=SETTINGS.database.parent / "near_duplicate_review.csv")
    parser.add_argument("--split", choices=["validation", "test"], default="test")
    parser.add_argument("--output", type=Path, default=SETTINGS.database.parent / "phash_sensitivity.json")
    args = parser.parse_args()
    result = sensitivity_check(args.db, args.audit, args.split)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
