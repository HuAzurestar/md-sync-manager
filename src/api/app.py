"""Minimal FastAPI shell shared by the PIRC-14 workbench features."""

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse

from src.core.capabilities import P0_CAPABILITIES


UI_ROOT = Path(__file__).resolve().parents[1] / "ui"


def success(data: object) -> dict[str, object | None]:
    """Wrap successful API data in the stable P0 response envelope."""

    return {"status": "success", "data": data, "error": None}


def failure(message: str) -> dict[str, object | None]:
    """Wrap a readable error without leaking implementation details."""

    return {"status": "error", "data": None, "error": {"message": message}}


def create_app() -> FastAPI:
    application = FastAPI(
        title="Markdown Focus Workbench",
        version="0.1.0",
        docs_url=None,
        redoc_url=None,
        openapi_url="/api/v1/openapi.json",
    )

    @application.exception_handler(Exception)
    async def unhandled_error(_request: Request, exc: Exception) -> JSONResponse:
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

    return application


app = create_app()
