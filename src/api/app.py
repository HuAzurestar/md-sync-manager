"""Minimal FastAPI shell shared by the PIRC-14 workbench features."""

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from src.api.responses import failure, success
from src.api.sync_routes import router as sync_router
from src.controller.sync_controller import SyncController
from src.core.config import ConfigStore
from src.core.capabilities import P0_CAPABILITIES
from src.core.focus import FocusConflictError, FocusSelectionError
from src.service.sync_service import ProviderNotConfiguredError, SyncService
from src.service.workbench_sync_service import WorkbenchSyncService


UI_ROOT = Path(__file__).resolve().parents[1] / "ui"
SAFE_VALUE_ERRORS = frozenset({
    "Markdown requires YAML front matter",
    "YAML front matter is not closed",
    "YAML front matter must be a mapping",
    "title must be a non-empty string",
    "parent must be a non-empty remote path string",
    "remote must be a non-empty remote path string",
    "pull preview is unknown or expired",
    "push preview is unknown or expired",
    "current document no longer matches the pull preview",
    "current document no longer matches the push preview",
    "remote document no longer matches the push preview",
    "upload requires an unbound document; use push to update its remote",
})


def _public_error(exc: Exception) -> str:
    if isinstance(exc, ProviderNotConfiguredError):
        provider = {
            "github": "GitHub", "gitee": "Gitee", "youtrack": "YouTrack"
        }[exc.source]
        return f"Set up {provider} in Provider configuration."
    if isinstance(exc, FocusConflictError):
        return "current heading range no longer matches the retained source"
    if isinstance(exc, FocusSelectionError):
        return "heading selector is missing or ambiguous; refresh the catalog"
    if type(exc) is ValueError:
        message = str(exc)
        if message in SAFE_VALUE_ERRORS:
            return message
        return "Invalid document or operation; check the file format and target."
    return "Operation failed; check provider settings or retry."


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
    application.mount("/static", StaticFiles(directory=UI_ROOT), name="static")

    @application.exception_handler(Exception)
    async def unhandled_error(_request: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(status_code=500, content=failure(_public_error(exc)))

    @application.exception_handler(RequestValidationError)
    async def invalid_request(
        _request: Request, _exc: RequestValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=500,
            content=failure("Invalid request; check required fields and data types."),
        )

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
