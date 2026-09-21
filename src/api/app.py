"""Minimal FastAPI shell shared by the PIRC-14 workbench features."""

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse

from src.api.responses import failure, success
from src.api.sync_routes import router as sync_router
from src.controller.sync_controller import SyncController
from src.core.config import ConfigStore
from src.core.capabilities import P0_CAPABILITIES
from src.service.sync_service import SyncService
from src.service.workbench_sync_service import WorkbenchSyncService


UI_ROOT = Path(__file__).resolve().parents[1] / "ui"


def create_app(
    *,
    config_store: ConfigStore | None = None,
    sync_service: SyncService | None = None,
) -> FastAPI:
    application = FastAPI(
        title="Markdown Focus Workbench",
        version="0.1.0",
        docs_url=None,
        redoc_url=None,
        openapi_url="/api/v1/openapi.json",
    )
    store = config_store or ConfigStore()
    service = sync_service or SyncController(store.load())
    application.state.config_store = store
    application.state.workbench_sync = WorkbenchSyncService(service)

    @application.exception_handler(Exception)
    async def unhandled_error(_request: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(status_code=500, content=failure(str(exc)))

    @application.exception_handler(RequestValidationError)
    async def invalid_request(
        _request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return JSONResponse(status_code=500, content=failure(str(exc)))

    @application.get("/api/v1/health")
    async def health() -> dict[str, object | None]:
        return success(
            {
                "service": "md-sync-manager",
                "state": "ready",
                "capabilities": list(P0_CAPABILITIES),
            }
        )

    @application.get("/", include_in_schema=False)
    async def workbench() -> FileResponse:
        return FileResponse(UI_ROOT / "index.html", media_type="text/html")

    application.include_router(sync_router)
    return application


app = create_app()
