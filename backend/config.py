"""Cấu hình đường dẫn và giới hạn cho ứng dụng LeafSearch.

Có thể thay đổi vị trí CSDL/ảnh qua biến môi trường để dễ kiểm thử.
"""

from dataclasses import dataclass
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Settings:
    """Các thông số triển khai được các module backend sử dụng."""

    database: Path = Path(os.getenv("LEAFSEARCH_DB", ROOT / "data" / "leafsearch.sqlite"))
    images_dir: Path = Path(os.getenv("LEAFSEARCH_IMAGES", ROOT / "data" / "images"))
    frontend_dir: Path = ROOT / "frontend"
    max_upload_bytes: int = 10 * 1024 * 1024
    max_image_pixels: int = 20_000_000
    pipeline_version: str = "leaf-v1-web-1.0"


SETTINGS = Settings()
