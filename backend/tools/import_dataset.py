"""Nhập ZIP/thư mục lá cây -> ảnh thật + SQLite chứa 4 vector/ảnh.

Chạy ví dụ:
    python -m backend.tools.import_dataset --source "Bo_anh_la_1685.zip"

Có thể dùng --allow-nonstandard để kiểm thử bộ ảnh nhỏ. Không dùng cờ này
khi nộp bài chính thức: chế độ mặc định kiểm tra 1.685 ảnh / 32 nhóm.
"""

import argparse
from collections import Counter
from dataclasses import dataclass
from hashlib import sha256
import io
import json
from pathlib import Path
import random
import re
import sqlite3
import shutil
import tempfile
from typing import Iterator
import zipfile

import cv2
import numpy as np
from PIL import Image, UnidentifiedImageError

from ..config import SETTINGS
from ..db import connect, encode_vector, initialize, set_metadata
from ..vision.features import DIMENSIONS, ORDER, extract_features
from ..vision.preprocess import preprocess

NAME_PATTERN = re.compile(r"^(\d{1,2})\.(\d+)\.png$", re.IGNORECASE)
EXPECTED_COUNTS = {
    "01": 6, "02": 60, "03": 56, "04": 77, "05": 62, "06": 61,
    "07": 66, "08": 60, "09": 55, "10": 55, "11": 65, "12": 54,
    "13": 52, "14": 53, "15": 55, "16": 56, "17": 64, "18": 31,
    "19": 18, "20": 69, "21": 56, "22": 65, "23": 50, "24": 15,
    "25": 5, "26": 58, "27": 63, "28": 53, "29": 59, "30": 72,
    "31": 62, "32": 52,
}
assert sum(EXPECTED_COUNTS.values()) == 1685
MAX_FILE_BYTES = 10 * 1024 * 1024


def _database_has_data(path: Path) -> bool:
    """Phân biệt SQLite *chỉ có schema rỗng* với CSDL đã nhập ảnh.

    FastAPI tạo schema khi khởi động lần đầu. Người dùng vẫn phải có thể
    nhập ZIP không cần --replace trong trường hợp DB chưa chứa dữ liệu.
    """
    if not path.exists() or path.stat().st_size == 0:
        return False
    try:
        with sqlite3.connect(str(path)) as con:
            tables = {row[0] for row in con.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            )}
            allowed = {"metadata", "categories", "images", "features", "feature_stats",
                       "search_logs", "evaluation_runs"}
            if not tables.issubset(allowed):
                return True  # Không xóa ngầm bảng do người dùng tự tạo.
            return any(con.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0] > 0
                       for name in tables)
    except sqlite3.DatabaseError:
        return True  # Không ghi đè DB lỗi/chưa rõ định dạng.


@dataclass(frozen=True)
class Record:
    """Thông tin ảnh sau kiểm tra; không giữ toàn bộ ảnh trong RAM."""
    file_name: str
    group_id: str
    relative_path: str
    sha256: str
    pixel_sha256: str
    width: int
    height: int


def _iter_source(source: Path) -> Iterator[tuple[str, bytes]]:
    """Duyệt tên tệp + bytes từ ZIP hoặc thư mục, không giải nén đường dẫn ZIP trực tiếp."""
    if source.is_dir():
        for path in sorted(source.rglob("*.png")):
            if not path.name.startswith("."):
                yield path.name, path.read_bytes()
        return
    if source.is_file() and zipfile.is_zipfile(source):
        with zipfile.ZipFile(source) as archive:
            members = sorted((m for m in archive.infolist() if not m.is_dir()
                              and m.filename.lower().endswith(".png")
                              and not Path(m.filename).name.startswith(".")),
                             key=lambda m: Path(m.filename).name)
            for info in members:
                if info.file_size > MAX_FILE_BYTES:
                    raise ValueError(f"Ảnh vượt {MAX_FILE_BYTES} byte: {info.filename}")
                with archive.open(info) as stream:
                    yield Path(info.filename).name, stream.read(MAX_FILE_BYTES + 1)
        return
    raise FileNotFoundError(f"Không tìm thấy ZIP/thư mục dữ liệu hợp lệ: {source}")


def _read_metadata(name: str, blob: bytes) -> tuple[str, str, int, int, str]:
    """Xác thực tên, PNG RGB, kích thước và tạo hash của pixel RGB."""
    match = NAME_PATTERN.fullmatch(name)
    if not match or not (1 <= int(match.group(1)) <= 32):
        raise ValueError(f"Tên sai mẫu <nhóm>.<số>.png: {name}")
    if not blob or len(blob) > MAX_FILE_BYTES:
        raise ValueError(f"Tệp rỗng hoặc quá 10MB: {name}")
    try:
        with Image.open(io.BytesIO(blob)) as image:
            if image.format != "PNG" or image.mode != "RGB":
                raise ValueError(f"Ảnh phải là PNG chế độ RGB: {name} ({image.format}, {image.mode})")
            width, height = image.size
            if (width, height) != (512, 512):
                raise ValueError(f"Ảnh phải là 512×512 pixel: {name} ({width}×{height})")
            # Chuyển thành bytes thống nhất theo thứ tự RGB, phát hiện trùng pixel.
            pixels_hash = sha256(np.asarray(image).tobytes()).hexdigest()
    except (OSError, UnidentifiedImageError) as exc:
        raise ValueError(f"Không đọc được PNG: {name}") from exc
    group_id = f"{int(match.group(1)):02d}"
    return group_id, sha256(blob).hexdigest(), width, height, pixels_hash


def _allocate(counts: dict[str, int], target: int, already: dict[str, int]) -> dict[str, int]:
    """Phân bổ số mẫu theo tỉ lệ; ưu tiên phần dư lớn, đảm bảo lớp ít ảnh có đại diện."""
    ratios = {g: n * target / sum(counts.values()) for g, n in counts.items()}
    result = {g: max(1 if counts[g] >= 3 else 0, int(ratios[g])) for g in counts}
    for g in counts:
        result[g] = min(result[g], max(counts[g] - 1 - already.get(g, 0), 0))
    while sum(result.values()) < target:
        candidates = [g for g in counts if result[g] + already.get(g, 0) < counts[g] - 1]
        if not candidates:
            raise ValueError("Không đủ ảnh để phân chia tập hợp lệ")
        g = max(candidates, key=lambda x: (ratios[x] - result[x], counts[x], -int(x)))
        result[g] += 1
    while sum(result.values()) > target:
        candidates = [g for g in counts if result[g] > (1 if counts[g] >= 3 else 0)]
        if not candidates:
            raise ValueError("Phân bổ tối thiểu vượt chỉ tiêu")
        g = min(candidates, key=lambda x: (ratios[x] - result[x], -counts[x], int(x)))
        result[g] -= 1
    return result


def make_splits(records: list[Record], seed: int = 2026,
                strict: bool = True) -> dict[str, str]:
    """Chia ngẫu nhiên có thể tái lập; mặc định chính xác 1345/170/170."""
    buckets: dict[str, list[str]] = {}
    for r in records:
        buckets.setdefault(r.group_id, []).append(r.file_name)
    counts = {g: len(v) for g, v in buckets.items()}
    total = len(records)
    # Với dữ liệu kiểm thử nhỏ, bảo đảm mỗi nhóm >=3 ảnh có một mẫu
    # validation và một mẫu test; dữ liệu chính thức vẫn khóa 170/170.
    min_per_split = sum(n >= 3 for n in counts.values())
    target_val = 170 if strict else max(round(total * 0.10), min_per_split)
    target_test = 170 if strict else max(round(total * 0.10), min_per_split)
    allocation_val = _allocate(counts, target_val, {})
    allocation_test = _allocate(counts, target_test, allocation_val)
    splits = {}
    for g, names in sorted(buckets.items()):
        names.sort()
        random.Random(seed + int(g)).shuffle(names)
        for i, name in enumerate(names):
            splits[name] = ("validation" if i < allocation_val[g] else
                            "test" if i < allocation_val[g] + allocation_test[g] else "gallery")
    return splits


def import_dataset(source: Path, output_db: Path = SETTINGS.database,
                   output_images: Path = SETTINGS.images_dir,
                   strict: bool = True, overwrite: bool = False,
                   seed: int = 2026, version: str = SETTINGS.pipeline_version) -> dict:
    """Kiểm kê, trích 560 đặc trưng và chỉ đưa dữ liệu mới vào vận hành khi thành công.

    Không thay thế CSDL hiện hành trước khi xử lý xong toàn bộ ảnh. Nếu
    overwrite, giữ bản trước với đuôi .previous để có thể khôi phục.
    """
    source = Path(source).expanduser().resolve()
    output_db, output_images = Path(output_db).resolve(), Path(output_images).resolve()
    output_db.parent.mkdir(parents=True, exist_ok=True)
    output_images.parent.mkdir(parents=True, exist_ok=True)
    # Không chặn lần nhập đầu nếu người học đã mở website (schema rỗng).
    # Nhưng luôn chặn ghi đè ảnh/DB có dữ liệu thực nếu không có --replace.
    images_have_content = output_images.exists() and any(output_images.iterdir())
    if not overwrite and (images_have_content or _database_has_data(output_db)):
        raise FileExistsError("Đích đã có dữ liệu; dùng --replace để nhập lại có bản sao lưu")
    parent = output_db.parent
    with tempfile.TemporaryDirectory(prefix="leafsearch-build-", dir=parent) as working:
        temp_dir = Path(working)
        stage_images = temp_dir / "images"
        stage_db = temp_dir / "leafsearch.sqlite"
        records: list[Record] = []
        seen_byte: dict[str, Record] = {}
        seen_pixel: dict[str, Record] = {}
        seen_names: set[str] = set()
        duplicated: list[dict] = []
        raw_count = 0
        # Lượt 1: đọc, lọc bản sao chính xác, lưu ảnh và metadata.
        for name, blob in _iter_source(source):
            raw_count += 1
            group, checksum, width, height, pixel_checksum = _read_metadata(name, blob)
            if name in seen_names:
                raise ValueError(f"Tệp tên bị lặp: {name}")
            seen_names.add(name)
            old = seen_byte.get(checksum) or seen_pixel.get(pixel_checksum)
            if old:
                if old.group_id != group:
                    raise ValueError(f"Một ảnh pixel được gán 2 nhóm: {old.file_name}, {name}")
                duplicated.append({"removed": name, "kept": old.file_name})
                continue
            relpath = f"{group}/{name}"
            path = stage_images / relpath
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(blob)
            record = Record(name, group, relpath, checksum, pixel_checksum, width, height)
            records.append(record)
            seen_byte[checksum], seen_pixel[pixel_checksum] = record, record
        counts = dict(Counter(r.group_id for r in records))
        if strict and (len(records) != 1685 or counts != EXPECTED_COUNTS):
            diffs = {g: [counts.get(g, 0), n] for g, n in EXPECTED_COUNTS.items() if counts.get(g, 0) != n}
            raise ValueError(f"Dataset không khớp báo cáo: {len(records)} ảnh, {len(counts)} nhóm; "
                             f"sai lệch số lượng thực tế/chuẩn: {diffs}")
        if len(records) < 7 or len(counts) == 0:
            raise ValueError("Cần tối thiểu 7 ảnh để chia gallery/validation/test và tìm Top 5")
        splits = make_splits(records, seed=seed, strict=strict)
        initialize(stage_db)
        vectors_gallery = {g: [] for g in ORDER}
        with connect(stage_db) as con:
            for g in sorted(counts):
                con.execute("INSERT INTO categories(group_id,description) VALUES (?,?)",
                            (g, f"Nhóm hình thái {g}; chưa xác thực tên loài"))
            # Lượt 2: cùng pipeline cho toàn bộ ảnh, 4 vector x số ảnh.
            for index, r in enumerate(sorted(records, key=lambda x: (x.group_id, x.file_name)), 1):
                file_bytes = (stage_images / r.relative_path).read_bytes()
                image = cv2.imdecode(np.frombuffer(file_bytes, dtype=np.uint8), cv2.IMREAD_COLOR)
                if image is None:
                    raise ValueError(f"Không đọc được ảnh khi trích đặc trưng: {r.file_name}")
                processed = preprocess(image)
                features = extract_features(processed)
                cur = con.execute(
                    "INSERT INTO images(file_name,group_id,relative_path,sha256,pixel_sha256,"
                    "width,height,split,mask_ratio,quality_status) VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (r.file_name, r.group_id, r.relative_path, r.sha256, r.pixel_sha256,
                     r.width, r.height, splits[r.file_name], processed.mask_ratio,
                     "review" if processed.review_required else "ok"),
                )
                image_id = cur.lastrowid
                for g in ORDER:
                    vector = features[g]
                    con.execute(
                        "INSERT INTO features(image_id,feature_group,version,dimension,vector) "
                        "VALUES (?,?,?,?,?)",
                        (image_id, g, version, DIMENSIONS[g], encode_vector(vector)),
                    )
                    if splits[r.file_name] == "gallery":
                        vectors_gallery[g].append(vector)
                if index % 50 == 0 or index == len(records):
                    print(f"Trích xuất: {index}/{len(records)} ảnh", flush=True)
            gallery_size = sum(1 for x in splits.values() if x == "gallery")
            for g in ORDER:
                matrix = np.stack(vectors_gallery[g]).astype(np.float64)
                means = matrix.mean(axis=0).astype(np.float32)
                scales = matrix.std(axis=0).astype(np.float32)
                scales[scales < 1e-8] = 1.0
                con.execute(
                    "INSERT INTO feature_stats(feature_group,version,dimension,gallery_count,mean_vector,scale_vector) "
                    "VALUES (?,?,?,?,?,?)",
                    (g, version, DIMENSIONS[g], gallery_size,
                     encode_vector(means), encode_vector(scales)),
                )
            set_metadata(con, "dataset_label", source.name)
            set_metadata(con, "seed", str(seed))
            set_metadata(con, "source_count", str(raw_count))
            set_metadata(con, "removed_duplicates", str(len(duplicated)))
            set_metadata(con, "pipeline_version", version)
        with connect(stage_db) as con:
            if con.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise RuntimeError("Lỗi SQLite integrity_check")
            if con.execute("PRAGMA foreign_key_check").fetchone():
                raise RuntimeError("Lỗi SQLite foreign_key_check")
        (temp_dir / "removed_duplicates.json").write_text(
            json.dumps(duplicated, ensure_ascii=False, indent=2), encoding="utf-8")
        # Chỉ swap sau khi toàn bộ ảnh/vector/DB đã hợp lệ.
        prior: list[tuple[Path, Path]] = []
        for target in (output_db, output_images):
            if not target.exists():
                continue
            if overwrite:
                backup = target.with_name(target.name + ".previous")
                if backup.exists():
                    raise FileExistsError(f"Đã có bản sao lưu {backup}; hãy lưu/đổi tên trước")
            else:
                # Di chuyển schema/trống vào staging, tự dọn khi thành công;
                # nếu lỗi sẽ được phục hồi, không làm mất nội dung hiện có.
                backup = temp_dir / (target.name + ".empty_schema")
            target.rename(backup)
            prior.append((target, backup))
        try:
            stage_images.rename(output_images)
            stage_db.rename(output_db)
            shutil.copy2(temp_dir / "removed_duplicates.json", parent / "removed_duplicates.json")
        except Exception:
            if output_db.exists():
                output_db.unlink()
            if output_images.exists():
                shutil.rmtree(output_images)
            for target, backup in reversed(prior):
                backup.rename(target)
            raise
    split_counts = Counter(splits.values())
    summary = {"images": len(records), "source_png": raw_count,
               "removed_duplicates": len(duplicated), "groups": len(counts),
               "gallery": split_counts["gallery"], "validation": split_counts["validation"],
               "test": split_counts["test"], "features": len(records) * 4,
               "database": str(output_db), "images_directory": str(output_images),
               "pipeline_version": version}
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Nhập ZIP ảnh lá cây thật vào LeafSearch")
    parser.add_argument("--source", required=True, type=Path, help="Đường dẫn ZIP hoặc thư mục PNG")
    parser.add_argument("--db", type=Path, default=SETTINGS.database)
    parser.add_argument("--images", type=Path, default=SETTINGS.images_dir)
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--replace", action="store_true", help="Sao lưu bản cũ .previous trước khi thay")
    parser.add_argument("--allow-nonstandard", action="store_true", help="Chỉ dành cho thử nghiệm")
    args = parser.parse_args()
    import_dataset(args.source, args.db, args.images,
                   strict=not args.allow_nonstandard, overwrite=args.replace, seed=args.seed)


if __name__ == "__main__":
    main()
