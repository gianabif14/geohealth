from contextlib import asynccontextmanager
import re
from pathlib import Path
from fastapi import FastAPI, Request, Response
from fastapi.staticfiles import StaticFiles
from app.db import close_pools, get_backend_mode
from app.routers import analisis, faskes, hotspot, meta

FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend"
_COORD_QUERY_RE = re.compile(r"(lat|lon|prev_lat|prev_lon)=(-?\d+(?:\.\d+)?)", re.IGNORECASE)


def redact_query_coords(query_string: str) -> str:
    return _COORD_QUERY_RE.sub(r"\1=[REDACTED]", query_string)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    get_backend_mode()
    try:
        yield
    finally:
        close_pools()


def create_app() -> FastAPI:
    app = FastAPI(
        title="GeoHealth GIS API",
        description="Sistem Informasi Geospasial Fasilitas Kesehatan untuk Mitigasi Dampak Karhutla di Sumatera Selatan",
        version="1.0.0",
        lifespan=lifespan,
    )

    @app.middleware("http")
    async def privacy_no_store_middleware(request: Request, call_next) -> Response:
        # Jangan pernah mencatat koordinat mentah pada state request dan matikan caching lokasi pengguna
        if request.url.path.startswith("/api/terdekat") or request.url.path.startswith("/api/hotspot/dekat"):
            request.state.redacted_query = redact_query_coords(request.url.query)
        response: Response = await call_next(request)
        if request.url.path.startswith("/api/terdekat") or request.url.path.startswith("/api/hotspot/dekat"):
            response.headers["Cache-Control"] = "no-store"
            response.headers["X-Privacy-Policy"] = "no-location-retention"
        return response

    app.include_router(meta.router)
    app.include_router(faskes.router)
    app.include_router(hotspot.router)
    app.include_router(analisis.router)

    if FRONTEND_DIR.exists():
        app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")

    return app


app = create_app()
