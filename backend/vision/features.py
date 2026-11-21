"""Trích xuất 4 nhóm đặc trưng (326 + 145 + 41 + 48 = 560 chiều).

Mục đích: chuyển ảnh thành vector so sánh được, KHÔNG phải mô hình phân loại loài.
Các phép thống kê/chuẩn hóa cố định ở đây tạo nên phiên bản leaf-v1-web-1.0.
Không trộn vector từ phiên bản khác trong cùng CSDL.
"""

from __future__ import annotations

import cv2
import numpy as np
from scipy.ndimage import gaussian_filter
from scipy.stats import kurtosis, skew
from skimage.feature import graycomatrix, graycoprops, local_binary_pattern
from skimage.morphology import skeletonize

from .preprocess import ProcessedImage


DIMENSIONS = {"color": 326, "shape": 145, "ridge": 41, "texture": 48}
ORDER = tuple(DIMENSIONS.keys())
DEFAULT_WEIGHTS = {"color": .25, "shape": .45, "ridge": .15, "texture": .15}


def _hist(values: np.ndarray, bins: int, range_: tuple[float, float]) -> np.ndarray:
    """Histogram chuẩn hóa tổng 1, luôn trả đúng số bin."""
    hist, _ = np.histogram(values, bins=bins, range=range_)
    hist = hist.astype(np.float64)
    return hist / max(float(hist.sum()), 1.0)


def _entropy(hist: np.ndarray) -> float:
    p = hist[hist > 0]
    return float(-np.sum(p * np.log2(p)))


def color_features(image: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """326 chiều: HSV256 + Lab48 + RGB12 + Hue2 + Entropy3 + ExG5."""
    is_leaf = mask > 0
    bgr = image[is_leaf]
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)[is_leaf]
    lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)[is_leaf]
    if len(bgr) == 0:
        raise ValueError("Mask không có pixel lá")

    # HSV 3D: H: 16 bin [0,180), S và V: 4 bin [0,256).
    hist_hsv, _ = np.histogramdd(
        hsv.astype(np.float32), bins=(16, 4, 4),
        range=((0, 180), (0, 256), (0, 256)),
    )
    hsv_256 = (hist_hsv / max(float(hist_hsv.sum()), 1.0)).ravel()

    lab_48 = np.concatenate([_hist(lab[:, ch], 16, (0, 256)) for ch in range(3)])
    rgb = bgr[:, ::-1].astype(np.float64) / 255.0
    moments = []
    for ch in range(3):
        samples = rgb[:, ch]
        # Dữ liệu hằng màu có phương sai 0 -> các mômen cấp cao bằng 0.
        asym = float(skew(samples)) if samples.std() > 1e-8 else 0.0
        kurt = float(kurtosis(samples)) if samples.std() > 1e-8 else 0.0
        moments += [float(samples.mean()), float(samples.std()), asym / 10, kurt / 10]

    angles = hsv[:, 0].astype(float) * (2 * np.pi / 180)
    saturation = hsv[:, 1].astype(float) / 255.0
    denom = max(float(saturation.sum()), 1e-10)
    hue_circle = [float((np.sin(angles) * saturation).sum() / denom),
                  float((np.cos(angles) * saturation).sum() / denom)]
    ents = [_entropy(_hist(hsv[:, i], 32, (0, 180) if i == 0 else (0, 256)))
            for i in range(3)]
    exg = 2 * rgb[:, 1] - rgb[:, 0] - rgb[:, 2]
    quantiles = np.percentile(exg, [0, 25, 50, 75, 100])
    return np.concatenate([hsv_256, lab_48, moments, hue_circle, ents, quantiles])


def _resample_contour(contour: np.ndarray, points: int = 512) -> np.ndarray:
    """Nội suy contour thành các điểm cách đều theo độ dài cung (đường kín)."""
    xy = contour[:, 0, :].astype(np.float64)
    xy = np.vstack([xy, xy[0]])
    increments = np.linalg.norm(np.diff(xy, axis=0), axis=1)
    cumulative = np.r_[0, np.cumsum(increments)]
    if cumulative[-1] <= 0:
        raise ValueError("Contour suy biến")
    distances = np.linspace(0, cumulative[-1], points, endpoint=False)
    return np.stack([np.interp(distances, cumulative, xy[:, i]) for i in (0, 1)], axis=1)


def _turn_angles(xy: np.ndarray, smooth_radius: int) -> np.ndarray:
    """Góc đổi hướng có dấu tại mỗi điểm; làm trơn contour theo lân cận."""
    if smooth_radius > 1:
        xy = sum(np.roll(xy, shift, axis=0) for shift in range(-smooth_radius, smooth_radius+1)) / (2*smooth_radius+1)
    a = xy - np.roll(xy, 1, axis=0)
    b = np.roll(xy, -1, axis=0) - xy
    cross = a[:, 0]*b[:, 1] - a[:, 1]*b[:, 0]
    dot = np.einsum("ij,ij->i", a, b)
    return np.arctan2(cross, dot)


def shape_features(mask: np.ndarray) -> np.ndarray:
    """145 chiều: 12 hình học + 54 histogram góc + 15 thống kê + Fourier64."""
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    if not contours:
        raise ValueError("Không tìm thấy đường biên")
    contour = max(contours, key=cv2.contourArea)
    area = max(cv2.contourArea(contour), 1.)
    perimeter = max(cv2.arcLength(contour, True), 1.)
    x, y, w, h = cv2.boundingRect(contour)
    hull = cv2.convexHull(contour)
    hull_area = max(cv2.contourArea(hull), 1.)
    hull_perimeter = max(cv2.arcLength(hull, True), 1.)
    xy = _resample_contour(contour)

    cov = np.cov(xy.T)
    eigenvalues = np.maximum(np.linalg.eigvalsh(cov), 0)
    major, minor = float(eigenvalues[-1]), float(eigenvalues[0])
    eccentricity = np.sqrt(max(0, 1-minor/(major+1e-9)))
    rect_aspect = min(w, h)/max(w, h)
    (cx, cy), enclosing_radius = cv2.minEnclosingCircle(contour)
    compact = area/(np.pi * max(enclosing_radius**2, 1))
    geom = [
        rect_aspect,
        area/(w*h),                   # extent
        4*np.pi*area/(perimeter**2), # circularity
        area/hull_area,              # solidity
        hull_perimeter/perimeter,    # convexity (chu vi)
        area/(mask.shape[0]*mask.shape[1]),
        perimeter/(mask.shape[0]+mask.shape[1]),
        eccentricity,
        np.sqrt(4*area/np.pi)/max(mask.shape),
        w/mask.shape[1],
        h/mask.shape[0],
        compact,
    ]

    angles_54, angles_15 = [], []
    for radius in (1, 5, 15):
        theta = _turn_angles(xy, radius)
        abs_theta = np.abs(theta)
        angles_54.extend(_hist(abs_theta, 18, (0, np.pi)))
        angles_15.extend([
            abs_theta.mean(), abs_theta.std(),
            np.percentile(abs_theta, 90),
            np.mean(abs_theta > np.pi/4), theta.mean(),
        ])
    # FFT đường biên phức: bỏ thành phần DC (tịnh tiến), chuẩn hóa hệ số 1 (tỉ lệ).
    centered = (xy[:, 0]-xy[:, 0].mean()) + 1j*(xy[:, 1]-xy[:, 1].mean())
    spectrum = np.abs(np.fft.fft(centered))[1:65]
    spectrum = spectrum / max(float(spectrum[0]), 1e-8)
    return np.asarray([*geom, *angles_54, *angles_15, *spectrum], dtype=np.float64)


def ridge_features(image: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """41 chiều: Hessian đa thang 24 + skeleton 8 + hướng 8 + coherence 1.

    Đây là đường gờ/vân *ứng viên*, không được diễn giải là gân thực vật học.
    """
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    gray = cv2.resize(gray, (160, 160)).astype(np.float32) / 255.0
    roi = cv2.resize(mask, (160, 160), interpolation=cv2.INTER_NEAREST) > 0
    responses = []
    measures = []
    for sigma in (1., 2., 3.):
        hxx = gaussian_filter(gray, sigma, order=(0, 2))
        hyy = gaussian_filter(gray, sigma, order=(2, 0))
        hxy = gaussian_filter(gray, sigma, order=(1, 1))
        disc = np.sqrt((hxx-hyy)**2 + 4*hxy*hxy)
        # Eigenvalue có trị tuyệt đối lớn: đáp ứng đường tối/sáng.
        eig_a = (hxx+hyy+disc)/2
        eig_b = (hxx+hyy-disc)/2
        dominant = np.where(np.abs(eig_a) > np.abs(eig_b), eig_a, eig_b)
        for polarity in (1, -1):
            response = np.maximum(polarity*dominant, 0)*sigma**2
            values = response[roi]
            if not values.size:
                raise ValueError("Mask rỗng khi xử lý vân")
            threshold = max(float(np.percentile(values, 85)), 0.002)
            measures.extend([values.mean(), values.std(), np.percentile(values, 90),
                             np.mean(values > threshold)])
            responses.append(response)

    maximum = np.max(np.stack(responses, axis=0), axis=0)
    values = maximum[roi]
    threshold = max(float(np.percentile(values, 80)), 0.003)
    skeleton = skeletonize((maximum >= threshold) & roi)
    skel_byte = skeleton.astype(np.uint8)
    neighbors = cv2.filter2D(skel_byte, cv2.CV_16S, np.ones((3, 3), np.uint8)) - skel_byte
    ends = int(np.count_nonzero(skeleton & (neighbors == 1)))
    branches = int(np.count_nonzero(skeleton & (neighbors >= 3)))
    count, labels, component_sizes, _ = cv2.connectedComponentsWithStats(skel_byte, 8)
    sizes = component_sizes[1:, cv2.CC_STAT_AREA] if count > 1 else np.array([])
    s_count = max(int(skeleton.sum()), 1)
    skeleton_8 = [
        float(np.mean(skeleton)), ends/s_count, branches/s_count,
        float(len(sizes)), float(sizes.mean())/25600 if sizes.size else 0.,
        float(sizes.max())/25600 if sizes.size else 0.,
        s_count/max(int(roi.sum()), 1),
        float(np.std(sizes))/25600 if sizes.size else 0.,
    ]
    # Histogram hướng từ gradient, quy về 0–180° để không phụ thuộc chiều.
    gx = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
    theta = (np.arctan2(gy, gx) + np.pi/2) % np.pi
    selected = theta[skeleton]
    orientation_8 = _hist(selected, 8, (0, np.pi)) if selected.size else np.zeros(8)
    coherence = float(np.abs(np.exp(2j*selected).mean())) if selected.size else 0.0
    return np.asarray([*measures, *skeleton_8, *orientation_8, coherence])


def texture_features(image: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """48 chiều: GLCM 6 thuộc tính × 3 khoảng cách + LBP uniform 10 × 3."""
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    gray = cv2.resize(gray, (128, 128), interpolation=cv2.INTER_AREA)
    roi = cv2.resize(mask, (128, 128), interpolation=cv2.INTER_NEAREST) > 0
    if not roi.any():
        raise ValueError("Mask rỗng khi xử lý kết cấu")
    gray = gray.copy()
    gray[~roi] = np.uint8(gray[roi].mean())
    quantized = (gray//16).astype(np.uint8)
    glcm = graycomatrix(
        quantized, distances=(1, 2, 4),
        angles=(0, np.pi/4, np.pi/2, 3*np.pi/4), levels=16,
        symmetric=True, normed=True,
    )
    stats = []
    for prop in ("contrast", "dissimilarity", "homogeneity", "ASM", "energy", "correlation"):
        stats.extend(np.mean(graycoprops(glcm, prop), axis=1))

    lbp_features = []
    for radius in (1, 2, 3):
        local = local_binary_pattern(gray, P=8, R=radius, method="uniform")
        # Chỉ các điểm lá tránh viền bằng erosion.
        eroded = cv2.erode(roi.astype(np.uint8), np.ones((2*radius+1,)*2, np.uint8)) > 0
        pixels = local[eroded] if eroded.any() else local[roi]
        lbp_features.extend(_hist(pixels, 10, (0, 10)))
    return np.asarray([*stats, *lbp_features])


def extract_features(item: ProcessedImage) -> dict[str, np.ndarray]:
    """Trích xuất/kiểm tra toàn bộ 560 số thực; lỗi nếu sai một nhóm."""
    output = {
        "color": color_features(item.image, item.mask),
        "shape": shape_features(item.mask),
        "ridge": ridge_features(item.image, item.mask),
        "texture": texture_features(item.image, item.mask),
    }
    for group, expected in DIMENSIONS.items():
        vector = np.asarray(output[group], dtype=np.float32)
        if vector.shape != (expected,) or not np.isfinite(vector).all():
            raise ValueError(f"Đặc trưng {group} sai kích thước hoặc chứa NaN/inf")
        output[group] = vector
    return output
