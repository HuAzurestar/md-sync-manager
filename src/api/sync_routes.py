"""Versioned provider and single-document synchronization routes."""

from fastapi import APIRouter, Request

from src.api.models import (
    DocumentRequest,
    FocusApplyRequest,
    FocusReadRequest,
    ProviderUpdateRequest,
    PullConfirmRequest,
    PullPreviewRequest,
    PushConfirmRequest,
    RemoteListRequest,
    RemoteOpenRequest,
    UploadRequest,
)
from src.api.markdown_renderer import render_markdown
from src.api.responses import success
from src.controller.sync_controller import SyncController
from src.service.workbench_sync_service import WorkbenchSyncService


router = APIRouter(prefix="/api/v1")


def _sync(request: Request) -> WorkbenchSyncService:
    return request.app.state.workbench_sync


@router.get("/providers")
async def provider_config(request: Request):
    return success(request.app.state.config_store.public())


@router.put("/providers")
async def update_provider_config(payload: ProviderUpdateRequest, request: Request):
    public = request.app.state.config_store.update(payload.providers)
    service = SyncController(request.app.state.config_store.load())
    request.app.state.workbench_sync = WorkbenchSyncService(service)
    return success(public)


@router.get("/sync/status")
async def sync_status(request: Request):
    return success(_sync(request).status())


@router.post("/sync/list")
async def list_remote(payload: RemoteListRequest, request: Request):
    return success(_sync(request).list(payload.target))


@router.post("/sync/open")
async def open_remote(payload: RemoteOpenRequest, request: Request):
    return success(_sync(request).open(payload.remote))


@router.post("/sync/pull/preview")
async def preview_pull(payload: PullPreviewRequest, request: Request):
    return success(
        _sync(request).preview_pull(
            name=payload.name, content=payload.content, source=payload.source
        )
    )


@router.post("/sync/pull/confirm")
async def confirm_pull(payload: PullConfirmRequest, request: Request):
    return success(
        _sync(request).confirm_pull(
            preview_id=payload.preview_id,
            name=payload.name,
            content=payload.content,
        )
    )


@router.post("/sync/push")
async def push(payload: DocumentRequest, request: Request):
    return success(_sync(request).push(name=payload.name, content=payload.content))


@router.post("/sync/push/preview")
async def preview_push(payload: DocumentRequest, request: Request):
    return success(_sync(request).preview_push(name=payload.name, content=payload.content))


@router.post("/sync/push/confirm")
async def confirm_push(payload: PushConfirmRequest, request: Request):
    return success(
        _sync(request).confirm_push(
            preview_id=payload.preview_id,
            name=payload.name,
            content=payload.content,
        )
    )


@router.post("/sync/upload")
async def upload(payload: UploadRequest, request: Request):
    return success(
        _sync(request).upload(
            name=payload.name,
            content=payload.content,
            target=payload.target,
            parent=payload.parent,
            base=payload.base,
            head=payload.head,
        )
    )


@router.post("/document/inspect")
async def inspect_document(payload: DocumentRequest, request: Request):
    return success(_sync(request).inspect(payload.name, payload.content))


@router.post("/document/render")
async def render_document(payload: DocumentRequest):
    return success({"html": render_markdown(payload.content)})


@router.post("/document/catalog")
async def catalog_document(payload: DocumentRequest, request: Request):
    return success(_sync(request).catalog(payload.name, payload.content))


@router.post("/document/focus/read")
async def read_focus(payload: FocusReadRequest, request: Request):
    return success(
        _sync(request).focus_read(payload.name, payload.content, payload.selectors)
    )


@router.post("/document/focus/apply")
async def apply_focus(payload: FocusApplyRequest, request: Request):
    return success(
        _sync(request).focus_apply(
            payload.name,
            payload.content,
            selector=payload.selector,
            expected_source=payload.expected_source,
            replacement=payload.replacement,
        )
    )
