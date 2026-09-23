"""Request DTOs for the P0 browser synchronization API."""

from typing import Any

from pydantic import BaseModel


class ProviderUpdateRequest(BaseModel):
    providers: dict[str, dict[str, Any]]


class RemoteListRequest(BaseModel):
    target: str


class RemoteOpenRequest(BaseModel):
    remote: str


class DocumentRequest(BaseModel):
    name: str
    content: str


class FocusReadRequest(DocumentRequest):
    selectors: list[str]


class FocusApplyRequest(DocumentRequest):
    selector: str
    expected_source: str
    replacement: str


class PullPreviewRequest(DocumentRequest):
    source: str | None = None


class PullConfirmRequest(DocumentRequest):
    preview_id: str


class PushConfirmRequest(DocumentRequest):
    preview_id: str


class UploadRequest(DocumentRequest):
    target: str
    parent: str | None = None
    base: str | None = None
    head: str | None = None
