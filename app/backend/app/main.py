from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import router
from app.api.luka import router as luka_router
from app.core.config import PROJECT_ROOT
from app.services.etl import ensure_operational_db


class SPAStaticFiles(StaticFiles):
    async def get_response(self, path: str, scope):
        response = await super().get_response(path, scope)
        if response.status_code == 404:
            clean = path.strip("/")
            base = Path(self.directory)
            html_file = base / f"{clean}.html"
            if html_file.is_file():
                return FileResponse(html_file)
            index_file = base / clean / "index.html"
            if index_file.is_file():
                return FileResponse(index_file)
        return response


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
    app.include_router(luka_router)

    frontend_out = PROJECT_ROOT / "app" / "frontend" / "out"
    if frontend_out.exists():
        app.mount("/", SPAStaticFiles(directory=str(frontend_out), html=True), name="static")

    return app


app = create_app()
