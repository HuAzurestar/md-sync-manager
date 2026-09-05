"""GitHub clients and single-object-type providers."""

import json
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from src.core.remote import RemoteContent, RemoteItem, RemotePath
from src.core.logging import get_logger
from src.providers.base import RemoteProvider


class GitHubClient:
    def __init__(self, config: dict):
        self.url = config.get("api_url", "https://api.github.com").rstrip("/")
        self.token = config.get("token", "")
        self.logger = get_logger()

    def request(self, method: str, path: str, payload=None):
        self.logger.info("api_request provider=github method=%s path=%s", method, path)
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        data = (
            json.dumps(payload, ensure_ascii=False).encode("utf-8")
            if payload is not None
            else None
        )
        if data is not None:
            headers["Content-Type"] = "application/json"
        request = Request(self.url + path, data=data, headers=headers, method=method)
        try:
            with urlopen(request, timeout=30) as response:
                raw = response.read().decode("utf-8")
                return json.loads(raw) if raw else {}
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:500]
            raise RuntimeError(
                f"GitHub API {exc.code} for {method} {path}: {detail}"
            ) from exc


class GitHubIssueProvider(RemoteProvider):
    source = "github"
    resource_type = "issues"
    supports_parent = True

    def __init__(self, client: GitHubClient):
        self.client = client

    def list(self, collection: RemotePath) -> list[RemoteItem]:
        self.validate(collection, require="collection")
        owner, repository = collection.scope
        data = self.client.request(
            "GET", f"/repos/{owner}/{repository}/issues?state=all&per_page=100"
        )
        return [
            RemoteItem(str(item["number"]), item.get("title") or "")
            for item in data
            if "pull_request" not in item
        ]

    def pull(self, remote: RemotePath) -> RemoteContent:
        self.validate(remote, require="object")
        owner, repository = remote.scope
        data = self.client.request(
            "GET", f"/repos/{owner}/{repository}/issues/{remote.object_id}"
        )
        return RemoteContent(data.get("title") or "", data.get("body") or "")

    def push(self, remote: RemotePath, content: RemoteContent) -> None:
        self.validate(remote, require="object")
        owner, repository = remote.scope
        self.client.request(
            "PATCH",
            f"/repos/{owner}/{repository}/issues/{remote.object_id}",
            {"title": content.title, "body": content.body},
        )

    def upload(
        self, collection, content, *, parent=None, base=None, head=None
    ) -> RemotePath:
        self.validate(collection, require="collection")
        if base or head:
            raise ValueError("--base and --head are only valid for Pull Request upload")
        if parent:
            self.validate_parent(collection, parent)
        owner, repository = collection.scope
        data = self.client.request(
            "POST",
            f"/repos/{owner}/{repository}/issues",
            {"title": content.title, "body": content.body},
        )
        return collection.with_id(data["number"])

    def set_parent(self, remote: RemotePath, parent: RemotePath) -> None:
        collection = RemotePath(remote.source, remote.resource_type, remote.scope)
        self.validate_parent(collection, parent)
        owner, repository = remote.scope
        child = self.client.request(
            "GET", f"/repos/{owner}/{repository}/issues/{remote.object_id}"
        )
        self.client.request(
            "POST",
            f"/repos/{owner}/{repository}/issues/{parent.object_id}/sub_issues",
            {"sub_issue_id": child["id"]},
        )


class GitHubPullProvider(RemoteProvider):
    source = "github"
    resource_type = "pulls"

    def __init__(self, client: GitHubClient):
        self.client = client

    def list(self, collection: RemotePath) -> list[RemoteItem]:
        self.validate(collection, require="collection")
        owner, repository = collection.scope
        data = self.client.request(
            "GET", f"/repos/{owner}/{repository}/pulls?state=all&per_page=100"
        )
        return [
            RemoteItem(str(item["number"]), item.get("title") or "") for item in data
        ]

    def pull(self, remote: RemotePath) -> RemoteContent:
        self.validate(remote, require="object")
        owner, repository = remote.scope
        data = self.client.request(
            "GET", f"/repos/{owner}/{repository}/pulls/{remote.object_id}"
        )
        return RemoteContent(data.get("title") or "", data.get("body") or "")

    def push(self, remote: RemotePath, content: RemoteContent) -> None:
        self.validate(remote, require="object")
        owner, repository = remote.scope
        self.client.request(
            "PATCH",
            f"/repos/{owner}/{repository}/pulls/{remote.object_id}",
            {"title": content.title, "body": content.body},
        )

    def upload(
        self, collection, content, *, parent=None, base=None, head=None
    ) -> RemotePath:
        self.validate(collection, require="collection")
        if parent:
            self.validate_parent(collection, parent)
        if not base or not head:
            raise ValueError("GitHub Pull Request upload requires --base and --head")
        owner, repository = collection.scope
        data = self.client.request(
            "POST",
            f"/repos/{owner}/{repository}/pulls",
            {"title": content.title, "body": content.body, "base": base, "head": head},
        )
        return collection.with_id(data["number"])
