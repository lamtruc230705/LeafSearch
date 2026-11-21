"""Các REST API cung cấp dữ liệu thật cho 6 màn hình của frontend."""

from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field

from .repository import (
    DatasetNotReady, categories, dataset_status, image_details, image_path, list_images,
)
from .services.evaluation import evaluate, get_evaluation
from .services.quality import quality_summary
from .services.search import search_image
from .vision.preprocess import ImageProcessingError, decode_image, preprocess, to_png

router = APIRouter(prefix="/api")


def _settings(request: Request):
    return request.app.state.settings


def _map_error(exc: Exception) -> HTTPException:
    if isinstance(exc, DatasetNotReady):
        return HTTPException(status_code=503, detail=str(exc))
    return HTTPException(status_code=400, detail=str(exc))


@router.get("/health")
def health(request: Request):
    """Cho biết CSDL đã nhập ảnh và đủ vector để tìm kiếm hay chưa."""
    s = _settings(request)
    stats = dataset_status(s.database, s.pipeline_version)
    return {"status": "ready" if stats["ready"] else "dataset_not_loaded", **stats}


@router.get("/dashboard")
def dashboard(request: Request):
    return dataset_status(_settings(request).database, _settings(request).pipeline_version)


@router.get("/categories")
def list_categories(request: Request):
    return {"items": categories(_settings(request).database)}


@router.get("/quality")
def quality(request: Request):
    """Ảnh cần xem lại và số cặp nghi gần trùng theo pHash (không phải nhãn thật)."""
    return quality_summary(_settings(request).database)


@router.get("/quality/near-duplicates.csv")
def near_duplicates_csv(request: Request):
    """Tải danh sách cặp cần rà soát để mở bằng Excel/LibreOffice."""
    csv_path = _settings(request).database.parent / "near_duplicate_review.csv"
    if not csv_path.is_file():
        raise HTTPException(404, "Chưa chạy rà soát pHash trên bộ dữ liệu")
    return FileResponse(csv_path, media_type="text/csv", filename="near_duplicate_review.csv")


@router.get("/images")
def images(request: Request, group_id: str | None = None,
           split: str | None = None, q: str = "", page: int = Query(1, ge=1),
           page_size: int = Query(24, ge=1, le=100)):
    if split and split not in ("gallery", "validation", "test"):
        raise HTTPException(422, "split phải là gallery / validation / test")
    return list_images(_settings(request).database, group_id, split, q, page, page_size)


@router.get("/images/{image_id}")
def image_detail(image_id: int, request: Request):
    s = _settings(request)
    data = image_details(s.database, image_id, s.pipeline_version)
    if not data:
        raise HTTPException(404, "Không tìm thấy ảnh")
    return data


@router.get("/images/{image_id}/file")
def original_image(image_id: int, request: Request):
    s = _settings(request)
    path = image_path(s.database, image_id, s.images_dir)
    if path is None or not path.is_file():
        raise HTTPException(404, "Không tìm thấy tệp ảnh")
    return FileResponse(path, media_type="image/png")


@router.get("/images/{image_id}/processed/{kind}")
def processed_image(image_id: int, kind: str, request: Request):
    """Sinh lại ảnh chuẩn hóa/mask từ ảnh gốc; không lưu ảnh thừa."""
    if kind not in ("normalized", "mask"):
        raise HTTPException(404, "Chỉ hỗ trợ normalized hoặc mask")
    s = _settings(request)
    path = image_path(s.database, image_id, s.images_dir)
    if path is None or not path.is_file():
        raise HTTPException(404, "Không tìm thấy tệp ảnh")
    item = preprocess(decode_image(path.read_bytes(), s.max_image_pixels))
    return Response(to_png(item.image if kind == "normalized" else item.mask), media_type="image/png")


@router.post("/search")
async def search(request: Request, file: UploadFile = File(...),
                 color: float = Form(.25), shape: float = Form(.45),
                 ridge: float = Form(.15), texture: float = Form(.15)):
    """Upload ảnh mới -> trích 560 chiều -> so với gallery -> Top 5 thật."""
    s = _settings(request)
    if file.content_type not in ("image/png", "image/jpeg", "image/webp"):
        raise HTTPException(415, "Chỉ chấp nhận PNG, JPG/JPEG hoặc WEBP")
    content = await file.read(s.max_upload_bytes + 1)
    await file.close()
    if len(content) > s.max_upload_bytes:
        raise HTTPException(413, "Tệp ảnh vượt 10MB")
    try:
        item = preprocess(decode_image(content, s.max_image_pixels))
        return search_image(s.database, s.pipeline_version, item,
                            Path(file.filename or "query.png").name,
                            {"color": color, "shape": shape,
                             "ridge": ridge, "texture": texture})
    except (DatasetNotReady, ValueError, ImageProcessingError) as exc:
        raise _map_error(exc) from exc


class EvaluationRequest(BaseModel):
    """Khóa mặc định là test; thử nghiệm validation chỉ dùng để chọn cấu hình."""
    split: str = "test"
    weights: dict[str, float] = Field(default_factory=lambda: {
        "color": .25, "shape": .45, "ridge": .15, "texture": .15,
    })


@router.post("/evaluate")
def evaluate_endpoint(request: Request, payload: EvaluationRequest):
    s = _settings(request)
    try:
        return evaluate(s.database, s.pipeline_version, payload.split, payload.weights)
    except (DatasetNotReady, ValueError, KeyError) as exc:
        raise _map_error(exc) from exc


@router.get("/evaluations/latest")
def latest_evaluation(request: Request):
    data = get_evaluation(_settings(request).database)
    if not data:
        raise HTTPException(404, "Chưa có kết quả đánh giá thực tế")
    return data


@router.get("/evaluations/{evaluation_id}")
def evaluation_detail(evaluation_id: int, request: Request):
    data = get_evaluation(_settings(request).database, evaluation_id)
    if not data:
        raise HTTPException(404, "Không tìm thấy lượt đánh giá")
    return data
