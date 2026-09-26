from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from fastapi.staticfiles import StaticFiles

from app.api.routes import router
from app.core.config import PROJECT_ROOT
from app.services.etl import ensure_operational_db


def create_app() -> FastAPI:
    ensure_operational_db()
    app = FastAPI(title="Analisis Financiero API", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=r"^https?://.*",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(router)

    frontend_out = PROJECT_ROOT / "app" / "frontend" / "out"
    if frontend_out.exists():
        app.mount("/", StaticFiles(directory=str(frontend_out), html=True), name="static")

    return app


app = create_app()
