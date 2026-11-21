"""Kết nối SQLite, khởi tạo schema và chuyển vector số <-> BLOB."""

from contextlib import contextmanager
from pathlib import Path
import sqlite3
from typing import Iterator

import numpy as np


SCHEMA = Path(__file__).with_name("schema.sql")


@contextmanager
def connect(db_path: Path) -> Iterator[sqlite3.Connection]:
    """Mở kết nối có Row, bật foreign key; commit hoặc rollback tự động."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(db_path), timeout=30)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    con.execute("PRAGMA busy_timeout = 30000")
    try:
        yield con
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


def initialize(db_path: Path) -> None:
    """Tạo bảng trống nếu cần; KHÔNG tự tạo số liệu mẫu."""
    with connect(db_path) as con:
        con.executescript(SCHEMA.read_text(encoding="utf-8"))


def encode_vector(vector: np.ndarray) -> bytes:
    """Lưu vector float32 little-endian để không phụ thuộc nền tảng."""
    values = np.asarray(vector, dtype="<f4")
    if values.ndim != 1 or not np.isfinite(values).all():
        raise ValueError("Vector phải là mảng 1D chỉ chứa số hữu hạn")
    return values.tobytes()


def decode_vector(blob: bytes, dimension: int) -> np.ndarray:
    """Đọc vector từ SQLite và kiểm tra đúng kích thước, không NaN/inf."""
    arr = np.frombuffer(blob, dtype="<f4")
    if arr.size != dimension or not np.isfinite(arr).all():
        raise ValueError(f"Vector lỗi: chờ {dimension} chiều, nhận {arr.size}")
    return arr.astype(np.float64, copy=False)


def set_metadata(con: sqlite3.Connection, key: str, value: str) -> None:
    con.execute(
        "INSERT INTO metadata(key,value) VALUES (?,?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (key, value),
    )


def get_metadata(con: sqlite3.Connection, key: str, default: str = "") -> str:
    row = con.execute("SELECT value FROM metadata WHERE key=?", (key,)).fetchone()
    return row["value"] if row else default
