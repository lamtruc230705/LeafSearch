"""Đọc, tách vùng lá, căn giữa vào khung chuẩn 512×512.

Khớp các bước trong báo cáo: HSV -> opening 3x3 -> closing 7x7 ->
contour ngoài lớn nhất -> cạnh dài ~440px. Kết quả mask dùng cho 4 nhóm đặc trưng.
"""

from dataclasses import dataclass

import cv2
import numpy as np


CANVAS = 512
TARGET_LEAF_LENGTH = 440


class ImageProcessingError(ValueError):
    """Ảnh không giải mã được hoặc không phát hiện vùng lá."""


@dataclass
class ProcessedImage:
    """Ảnh BGR đã căn giữa và mask nhị phân tương ứng."""

    image: np.ndarray
    mask: np.ndarray
    mask_ratio: float
    review_required: bool
    warning: str | None


def decode_image(content: bytes, max_pixels: int = 20_000_000) -> np.ndarray:
    """Giải mã PNG/JPG/WEBP; ảnh alpha được ghép nền trắng."""
    raw = np.frombuffer(content, dtype=np.uint8)
    image = cv2.imdecode(raw, cv2.IMREAD_UNCHANGED)
    if image is None or image.ndim not in (2, 3):
        raise ImageProcessingError("Không giải mã được tệp ảnh")
    height, width = image.shape[:2]
    if height * width > max_pixels or min(height, width) < 32:
        raise ImageProcessingError("Kích thước ảnh không hợp lệ (32px tối thiểu, 20MP tối đa)")
    if image.ndim == 2:
        return cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
    if image.shape[2] == 3:
        return image
    if image.shape[2] == 4:
        alpha = image[:, :, 3:4].astype(np.float32) / 255.0
        return np.clip(image[:, :, :3] * alpha + 255 * (1 - alpha), 0, 255).astype(np.uint8)
    raise ImageProcessingError("Ảnh chứa số kênh không được hỗ trợ")


def preprocess(image_bgr: np.ndarray) -> ProcessedImage:
    """Tách lá từ nền sáng, giữ thành phần lớn nhất, chuẩn hóa vị trí và tỉ lệ."""
    if image_bgr.ndim != 3 or image_bgr.shape[2] != 3:
        raise ImageProcessingError("Ảnh đầu vào phải có 3 kênh BGR")

    hsv = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2HSV)
    s, v = hsv[:, :, 1], hsv[:, :, 2]
    mask = np.where(((s > 33) & (v < 252)) | (v < 155), 255, 0).astype(np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((7, 7), np.uint8))
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        raise ImageProcessingError("Không phát hiện được vùng lá; thử ảnh trên nền sáng")
    contour = max(contours, key=cv2.contourArea)
    if cv2.contourArea(contour) < 80:
        raise ImageProcessingError("Vùng lá được phát hiện quá nhỏ để trích xuất")

    main_mask = np.zeros_like(mask)
    cv2.drawContours(main_mask, [contour], -1, color=255, thickness=-1)
    x, y, w, h = cv2.boundingRect(contour)
    scale = TARGET_LEAF_LENGTH / max(w, h)
    out_w, out_h = max(1, round(w * scale)), max(1, round(h * scale))
    resized = cv2.resize(image_bgr[y:y+h, x:x+w], (out_w, out_h), interpolation=cv2.INTER_AREA if scale < 1 else cv2.INTER_LINEAR)
    resized_mask = cv2.resize(main_mask[y:y+h, x:x+w], (out_w, out_h), interpolation=cv2.INTER_NEAREST)

    canvas = np.full((CANVAS, CANVAS, 3), 255, np.uint8)
    canvas_mask = np.zeros((CANVAS, CANVAS), np.uint8)
    ox, oy = (CANVAS-out_w)//2, (CANVAS-out_h)//2
    canvas[oy:oy+out_h, ox:ox+out_w] = resized
    canvas_mask[oy:oy+out_h, ox:ox+out_w] = resized_mask
    canvas[canvas_mask == 0] = 255

    fraction = float(np.count_nonzero(main_mask) / main_mask.size)
    # Chỉ là cờ rà soát, không khẳng định ảnh không hợp lệ.
    review = fraction < .025 or fraction > .90 or min(w, h) / max(w, h) < .09
    message = "Mặt nạ bất thường: cần kiểm tra thủ công" if review else None
    return ProcessedImage(canvas, canvas_mask, fraction, review, message)


def to_png(image: np.ndarray) -> bytes:
    """Mã hóa BGR hoặc mask grayscale thành PNG để hiển thị trên website."""
    ok, encoded = cv2.imencode(".png", image)
    if not ok:
        raise ImageProcessingError("Không thể xuất ảnh PNG")
    return encoded.tobytes()
