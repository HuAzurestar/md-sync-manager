"""File-oriented Markdown synchronization independent of HTTP and browser state."""

from collections.abc import Iterable
from pathlib import Path

from src.core.document import MarkdownDocument, parse_file, render_document
from src.core.remote import RemoteAccessPolicy, RemoteContent, RemotePath


class PartialSyncError(RuntimeError):
    """A remote was created but a later best-effort step failed."""

    def __init__(self, message: str, *, operation: str, remote: RemotePath):
        super().__init__(message)
        self.operation = operation
        self.remote = remote

    def as_result(self) -> dict[str, str]:
        return {
            "status": "PARTIAL",
            "operation": self.operation,
            "remote": str(self.remote),
            "message": str(self),
        }


class ProviderNotConfiguredError(ValueError):
    """A supported provider has no active credentials for a remote route."""

    def __init__(self, source: str):
        self.source = source
        super().__init__(f"provider not configured: {source}")


class SyncService:
    def __init__(
        self,
        providers: Iterable[object] = (),
        access_policy: RemoteAccessPolicy | None = None,
    ):
        self.providers: dict[tuple[str, str], object] = {}
        self.access_policy = access_policy or RemoteAccessPolicy()
        for provider in providers:
            self.register(provider)

    def register(self, provider: object) -> None:
        self.providers[provider.route] = provider

    def list(self, target: str):
        collection = RemotePath.parse(target, require="collection")
        return self._provider(collection).list(collection)

    def download(self, source: str) -> tuple[RemotePath, RemoteContent]:
        remote = RemotePath.parse(source, require="object")
        content = self._provider(remote).pull(remote)
        if not content.body or not content.body.strip():
            raise ValueError(f"remote object has no Markdown content: {remote}")
        if not content.title.strip():
            raise ValueError(f"remote object has no title: {remote}")
        return remote, content

    def pull(self, file: Path, source: str | None = None):
        self._require_markdown_path(file)
        if source:
            remote = RemotePath.parse(source, require="object")
            document = (
                parse_file(file)
                if file.exists()
                else MarkdownDocument(file, {"title": file.stem}, "")
            )
        else:
            if not file.exists():
                raise FileNotFoundError(
                    f"local file does not exist; use --from <remote-path>: {file}"
                )
            document = parse_file(file)
            if not document.remote:
                raise ValueError("pull requires --from or a remote path in YAML")
            remote = document.remote

        _, content = self.download(str(remote))

        existing_parent = document.parent
        document.metadata = {"title": content.title}
        if existing_parent:
            document.metadata["parent"] = existing_parent
        document.remote = remote
        document.body = content.body
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(render_document(document), encoding="utf-8", newline="")
        return {
            "status": "SUCCESS",
            "operation": "pull",
            "remote": str(remote),
            "local_file": str(file),
        }

    def push(self, file: Path):
        self._require_markdown_path(file)
        if not file.exists():
            raise FileNotFoundError(file)
        document = parse_file(file)
        if not document.remote:
            raise ValueError(
                "push requires an existing remote; use upload to create one"
            )
        content = RemoteContent(document.title, document.body)
        self._provider(document.remote).push(document.remote, content)
        return {
            "status": "SUCCESS",
            "operation": "push",
            "remote": str(document.remote),
        }

    def upload(
        self,
        file: Path,
        target: str,
        parent: str | None = None,
        base: str | None = None,
        head: str | None = None,
    ):
        self._require_markdown_path(file)
        if not file.exists():
            raise FileNotFoundError(file)
        document = parse_file(file)
        if document.remote:
            raise ValueError(
                "upload requires an unbound document; use push to update its remote"
            )

        collection = RemotePath.parse(target, require="collection")
        provider = self._provider(collection)
        parent_value = parent if parent is not None else document.parent
        parent_path = (
            RemotePath.parse(parent_value, require="object") if parent_value else None
        )
        if parent_path:
            self.access_policy.require(parent_path)
            provider.validate_parent(collection, parent_path)
            document.metadata["parent"] = str(parent_path)

        content = RemoteContent(document.title, document.body)
        remote = provider.upload(
            collection, content, parent=parent_path, base=base, head=head
        )
        document.remote = remote
        try:
            file.write_text(render_document(document), encoding="utf-8", newline="")
        except OSError as exc:
            raise PartialSyncError(
                f"created {remote}, but could not save it to {file}: {exc}",
                operation="upload",
                remote=remote,
            ) from exc

        if parent_path and not provider.parent_during_upload:
            try:
                provider.set_parent(remote, parent_path)
            except Exception as exc:
                raise PartialSyncError(
                    str(exc), operation="upload", remote=remote
                ) from exc
        return {"status": "SUCCESS", "operation": "upload", "remote": str(remote)}

    def _provider(self, path: RemotePath):
        self.access_policy.require(path)
        provider = self.providers.get(path.route)
        if not provider:
            raise ProviderNotConfiguredError(path.source)
        return provider

    @staticmethod
    def _require_markdown_path(file: Path) -> None:
        if file.suffix.lower() != ".md":
            raise ValueError(f"only .md files are supported: {file}")
