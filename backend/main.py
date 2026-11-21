"""Điểm khởi chạy dự án: uvicorn backend.main:app --reload."""

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .api import router
from .config import SETTINGS, Settings
from .db import initialize


def create_app(settings: Settings = SETTINGS) -> FastAPI:
    """App factory: tiện thay CSDL tạm khi viết test."""
    initialize(settings.database)
    app = FastAPI(
        title="LeafSearch PTIT API", version="1.0.0",
        description="Tìm ảnh lá cây theo 560 đặc trưng thị giác; Swagger tại /docs",
    )
    app.state.settings = settings
    app.include_router(router)
    app.mount("/assets", StaticFiles(directory=settings.frontend_dir), name="assets")

    @app.get("/", include_in_schema=False)
    def index():
        return FileResponse(settings.frontend_dir / "index.html")

    return app


app = create_app()
