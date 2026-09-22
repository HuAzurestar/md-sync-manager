"""Content adapter between one browser document and file-oriented sync."""

from __future__ import annotations

from dataclasses import dataclass
from difflib import unified_diff
from pathlib import Path
import re
import secrets
import tempfile
import time

from src.core.document import MarkdownDocument, parse_text, render_document
from src.core.catalog import catalog_text
from src.core.focus import focus_apply_text, focus_read_text
from src.core.remote import RemotePath
from src.service.sync_service import PartialSyncError, SyncService


@dataclass(frozen=True)
class PullPreview:
    preview_id: str
    name: str
    original_content: str
    updated_content: str
    remote: str
    expires_at: float


@dataclass(frozen=True)
class PushPreview:
    preview_id: str
    name: str
    original_content: str
    remote_content: str
    remote: str
    expires_at: float


class WorkbenchSyncService:
    def __init__(self, sync_service: SyncService, *, preview_ttl: float = 600.0):
        self.sync_service = sync_service
        self.preview_ttl = preview_ttl
        self._previews: dict[str, PullPreview | PushPreview] = {}

    def status(self) -> dict[str, object]:
        return {
            "state": "ready",
            "configured_routes": sorted(
                "/".join(route) for route in self.sync_service.providers
            ),
        }

    def list(self, target: str) -> dict[str, object]:
        items = self.sync_service.list(target)
        return {
            "target": target,
            "items": [
                {"id": str(item.object_id), "title": item.title} for item in items
            ],
        }

    def open(self, remote: str) -> dict[str, object]:
        parsed, remote_content = self.sync_service.download(remote)
        filename = self._filename(f"{parsed.object_id}.md")
        document = MarkdownDocument(
            Path(filename), {"title": remote_content.title}, remote_content.body
        )
        document.remote = parsed
        content = render_document(document)
        return {
            "name": filename,
            "content": content,
            "document": self.inspect(filename, content),
            "result": {
                "status": "SUCCESS",
                "operation": "open",
                "remote": str(parsed),
            },
        }

    def inspect(self, name: str, content: str) -> dict[str, object]:
        filename = self._filename(name)
        try:
            document = parse_text(content, Path(filename))
        except ValueError as exc:
            if str(exc) != "Markdown requires YAML front matter":
                raise
            return {
                "name": filename,
                "title": self._plain_title(filename, content),
                "parent": None,
                "remote": None,
                "bound": False,
                "plain": True,
            }
        return {
            "name": filename,
            "title": document.title,
            "parent": document.parent,
            "remote": str(document.remote) if document.remote else None,
            "bound": document.remote is not None,
            "plain": False,
        }

    def catalog(self, name: str, content: str) -> dict[str, object]:
        filename = self._filename(name)
        return catalog_text(content, path=filename).as_dict()

    def focus_read(
        self, name: str, content: str, selectors: list[str]
    ) -> dict[str, object]:
        filename = self._filename(name)
        sections = focus_read_text(content, selectors)
        return {
            "name": filename,
            "sections": [section.as_dict() for section in sections],
        }

    def focus_apply(
        self,
        name: str,
        content: str,
        *,
        selector: str,
        expected_source: str,
        replacement: str,
    ) -> dict[str, object]:
        filename = self._filename(name)
        updated, previous = focus_apply_text(
            content,
            selector=selector,
            expected_source=expected_source,
            replacement=replacement,
        )
        refreshed = focus_read_text(updated, [replacement.splitlines()[0]])[0]
        return {
            "name": filename,
            "content": updated,
            "previous": previous.as_dict(),
            "section": refreshed.as_dict(),
        }

    def preview_pull(
        self, *, name: str, content: str, source: str | None = None
    ) -> dict[str, object]:
        filename = self._filename(name)
        remote = self._resolve_remote(filename, content, source)
        parsed, remote_content = self.sync_service.download(remote)
        updated_content = self._remote_document(
            filename, content, parsed, remote_content.title, remote_content.body
        )
        preview_id = secrets.token_urlsafe(18)
        preview = PullPreview(
            preview_id,
            filename,
            content,
            updated_content,
            str(parsed),
            time.monotonic() + self.preview_ttl,
        )
        self._previews[preview_id] = preview
        return {
            "preview_id": preview_id,
            "direction": "pull",
            "remote": str(parsed),
            "changed": content != updated_content,
            "diff": "".join(
                unified_diff(
                    content.splitlines(keepends=True),
                    updated_content.splitlines(keepends=True),
                    fromfile="local",
                    tofile="remote",
                )
            ),
        }

    def confirm_pull(
        self, *, preview_id: str, name: str, content: str
    ) -> dict[str, object]:
        self._expire_previews()
        preview = self._previews.get(preview_id)
        if not isinstance(preview, PullPreview):
            raise ValueError("pull preview is unknown or expired")
        if preview.name != self._filename(name) or preview.original_content != content:
            raise ValueError("current document no longer matches the pull preview")
        del self._previews[preview_id]
        return {
            "content": preview.updated_content,
            "document": self.inspect(preview.name, preview.updated_content),
            "result": {
                "status": "SUCCESS",
                "operation": "pull",
                "direction": "pull",
                "remote": preview.remote,
            },
        }

    def preview_push(self, *, name: str, content: str) -> dict[str, object]:
        filename = self._filename(name)
        remote = self._resolve_remote(filename, content, None, operation="push")
        parsed, remote_content = self.sync_service.download(remote)
        current_remote_content = self._remote_document(
            filename, content, parsed, remote_content.title, remote_content.body
        )
        preview_id = secrets.token_urlsafe(18)
        preview = PushPreview(
            preview_id,
            filename,
            content,
            current_remote_content,
            str(parsed),
            time.monotonic() + self.preview_ttl,
        )
        self._previews[preview_id] = preview
        return {
            "preview_id": preview_id,
            "direction": "push",
            "remote": str(parsed),
            "changed": current_remote_content != content,
            "diff": "".join(
                unified_diff(
                    current_remote_content.splitlines(keepends=True),
                    content.splitlines(keepends=True),
                    fromfile="remote",
                    tofile="local",
                )
            ),
        }

    def confirm_push(
        self, *, preview_id: str, name: str, content: str
    ) -> dict[str, object]:
        self._expire_previews()
        preview = self._previews.get(preview_id)
        if not isinstance(preview, PushPreview):
            raise ValueError("push preview is unknown or expired")
        filename = self._filename(name)
        if preview.name != filename or preview.original_content != content:
            raise ValueError("current document no longer matches the push preview")
        parsed, remote_content = self.sync_service.download(preview.remote)
        current_remote_content = self._remote_document(
            filename, content, parsed, remote_content.title, remote_content.body
        )
        if preview.remote_content != current_remote_content:
            raise ValueError("remote document no longer matches the push preview")
        result = self.push(name=filename, content=content)
        del self._previews[preview_id]
        return result

    def push(self, *, name: str, content: str) -> dict[str, object]:
        filename = self._filename(name)
        with tempfile.TemporaryDirectory(prefix="md-sync-workbench-") as directory:
            path = Path(directory) / filename
            path.write_text(content, encoding="utf-8", newline="")
            result = self.sync_service.push(path)
        return {
            "content": content,
            "document": self.inspect(filename, content),
            "result": {**result, "direction": "push"},
        }

    def upload(
        self,
        *,
        name: str,
        content: str,
        target: str,
        parent: str | None = None,
        base: str | None = None,
        head: str | None = None,
    ) -> dict[str, object]:
        filename = self._filename(name)
        prepared = self._prepare_content(filename, content)
        with tempfile.TemporaryDirectory(prefix="md-sync-workbench-") as directory:
            path = Path(directory) / filename
            path.write_text(prepared, encoding="utf-8", newline="")
            try:
                result = self.sync_service.upload(path, target, parent, base, head)
            except PartialSyncError as exc:
                result = exc.as_result()
            updated = path.read_text(encoding="utf-8")
        return {
            "content": updated,
            "document": self.inspect(filename, updated),
            "result": {**result, "direction": "upload"},
        }

    def _resolve_remote(
        self, filename: str, content: str, source: str | None, *, operation: str = "pull"
    ) -> str:
        if source:
            return str(RemotePath.parse(source, require="object"))
        document = parse_text(content, Path(filename))
        if not document.remote:
            raise ValueError(f"{operation} requires an existing remote binding")
        return str(document.remote)

    @staticmethod
    def _remote_document(filename, current, remote, title, body) -> str:
        try:
            current_document = parse_text(current, Path(filename))
            parent = current_document.parent
        except ValueError as exc:
            if str(exc) != "Markdown requires YAML front matter":
                raise
            parent = None
        metadata = {"title": title}
        if parent:
            metadata["parent"] = parent
        document = MarkdownDocument(Path(filename), metadata, body)
        document.remote = remote
        return render_document(document)

    @classmethod
    def _prepare_content(cls, filename: str, content: str) -> str:
        try:
            parse_text(content, Path(filename))
            return content
        except ValueError as exc:
            if str(exc) != "Markdown requires YAML front matter":
                raise
        return render_document(
            MarkdownDocument(
                Path(filename),
                {"title": cls._plain_title(filename, content)},
                content,
            )
        )

    def _expire_previews(self) -> None:
        now = time.monotonic()
        expired = [key for key, value in self._previews.items() if value.expires_at < now]
        for key in expired:
            del self._previews[key]

    @staticmethod
    def _filename(name: str) -> str:
        if not isinstance(name, str) or not name.strip():
            raise ValueError("document name is required")
        filename = Path(name.strip()).name
        if filename in {"", ".", ".."} or Path(filename).suffix.casefold() != ".md":
            raise ValueError("only .md files are supported")
        return filename

    @staticmethod
    def _plain_title(filename: str, content: str) -> str:
        heading = re.search(r"^#[ \t]+(.+?)\s*$", content, re.MULTILINE)
        return heading.group(1).strip() if heading else Path(filename).stem
