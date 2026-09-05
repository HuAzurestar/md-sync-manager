"""Route list, pull, push, and upload to polymorphic providers."""

from pathlib import Path

from src.core.document import MarkdownDocument, parse_file, render_document
from src.core.remote import RemoteContent, RemotePath
from src.providers.gitee import GiteeClient, GiteeIssueProvider, GiteePullProvider
from src.providers.github import GitHubClient, GitHubIssueProvider, GitHubPullProvider
from src.providers.youtrack import (
    YouTrackArticleProvider,
    YouTrackClient,
    YouTrackIssueProvider,
)


class SyncController:
    def __init__(self, config: dict):
        self.providers = {}
        settings = config.get("providers", {})
        github = settings.get("github", {})
        if github.get("enabled") and github.get("token"):
            client = GitHubClient(github)
            self.register(GitHubIssueProvider(client))
            self.register(GitHubPullProvider(client))
        gitee = settings.get("gitee", {})
        if gitee.get("enabled") and gitee.get("token"):
            client = GiteeClient(gitee)
            self.register(GiteeIssueProvider(client))
            self.register(GiteePullProvider(client))
        youtrack = settings.get("youtrack", {})
        if youtrack.get("enabled") and youtrack.get("token"):
            client = YouTrackClient(youtrack)
            self.register(YouTrackIssueProvider(client))
            self.register(YouTrackArticleProvider(client))

    def register(self, provider) -> None:
        self.providers[provider.route] = provider

    def list(self, target: str):
        collection = RemotePath.parse(target, require="collection")
        return self._provider(collection).list(collection)

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

        content = self._provider(remote).pull(remote)
        if not content.body or not content.body.strip():
            raise ValueError(
                f"remote object has no Markdown content; refusing to write {file}"
            )
        if not content.title.strip():
            raise ValueError(f"remote object has no title; refusing to write {file}")

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
            raise RuntimeError(
                f"created {remote}, but could not save it to {file}; record this remote before retrying upload"
            ) from exc

        if parent_path and not provider.parent_during_upload:
            provider.set_parent(remote, parent_path)
        return {"status": "SUCCESS", "operation": "upload", "remote": str(remote)}

    def _provider(self, path: RemotePath):
        provider = self.providers.get(path.route)
        if not provider:
            raise ValueError(
                f"provider not configured: {path.source}/{path.resource_type}"
            )
        return provider

    @staticmethod
    def _require_markdown_path(file: Path) -> None:
        if file.suffix.lower() != ".md":
            raise ValueError(f"only .md files are supported: {file}")
