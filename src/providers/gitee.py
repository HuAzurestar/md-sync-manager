"""Gitee clients and single-object-type providers (API v5)."""

import json
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from src.core.logging import get_logger
from src.core.remote import RemoteContent, RemoteItem, RemotePath
from src.providers.base import RemoteProvider


class GiteeClient:
    def __init__(self, config: dict):
        self.url = config.get("api_url", "https://gitee.com/api/v5").rstrip("/")
        self.token = config.get("token", "")
        self.logger = get_logger()

    def request(self, method: str, path: str, payload=None):
        self.logger.info("api_request provider=gitee method=%s path=%s", method, path)
        separator = "&" if "?" in path else "?"
        data = (
            json.dumps(payload, ensure_ascii=False).encode("utf-8")
            if payload is not None
            else None
        )
        request = Request(
            self.url + path + separator + "access_token=" + self.token,
            data=data,
            headers={"Accept": "application/json", "Content-Type": "application/json"},
            method=method,
        )
        try:
            with urlopen(request, timeout=30) as response:
                raw = response.read().decode("utf-8")
                return json.loads(raw) if raw else {}
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:500]
            raise RuntimeError(
                f"Gitee API {exc.code} for {method} {path}: {detail}"
            ) from exc


class GiteeIssueProvider(RemoteProvider):
    source = "gitee"
    resource_type = "issues"
    supports_parent = True
    parent_during_upload = True

    def __init__(self, client: GiteeClient):
        self.client = client

    def list(self, collection: RemotePath) -> list[RemoteItem]:
        self.validate(collection, require="collection")
        owner, repository = collection.scope
        data = self.client.request(
            "GET", f"/repos/{owner}/{repository}/issues?state=all&page=1&per_page=100"
        )
        return [
            RemoteItem(
                str(item.get("number") or item.get("ident")), item.get("title") or ""
            )
            for item in data
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
            f"/repos/{owner}/issues/{remote.object_id}?repo={repository}",
            {"title": content.title, "body": content.body},
        )

    def upload(
        self, collection, content, *, parent=None, base=None, head=None
    ) -> RemotePath:
        self.validate(collection, require="collection")
        if base or head:
            raise ValueError("--base and --head are only valid for Pull Request upload")
        owner, repository = collection.scope
        payload = {"title": content.title, "body": content.body}
        if parent:
            self.validate_parent(collection, parent)
            parent_data = self.client.request(
                "GET", f"/repos/{owner}/{repository}/issues/{parent.object_id}"
            )
            if not parent_data.get("id"):
                raise RuntimeError(f"Gitee parent issue has no numeric ID: {parent}")
            payload["parent_id"] = parent_data["id"]
        data = self.client.request(
            "POST", f"/repos/{owner}/issues?repo={repository}", payload
        )
        return collection.with_id(data.get("number") or data["ident"])


class GiteePullProvider(RemoteProvider):
    source = "gitee"
    resource_type = "pulls"

    def __init__(self, client: GiteeClient):
        self.client = client

    def list(self, collection: RemotePath) -> list[RemoteItem]:
        self.validate(collection, require="collection")
        owner, repository = collection.scope
        data = self.client.request(
            "GET", f"/repos/{owner}/{repository}/pulls?state=all&page=1&per_page=100"
        )
        return [
            RemoteItem(str(item["number"]), item.get("title") or item.get("name") or "")
            for item in data
        ]

    def pull(self, remote: RemotePath) -> RemoteContent:
        self.validate(remote, require="object")
        owner, repository = remote.scope
        data = self.client.request(
            "GET", f"/repos/{owner}/{repository}/pulls/{remote.object_id}"
        )
        return RemoteContent(
            data.get("title") or data.get("name") or "", data.get("body") or ""
        )

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
            raise ValueError("Gitee Pull Request upload requires --base and --head")
        owner, repository = collection.scope
        data = self.client.request(
            "POST",
            f"/repos/{owner}/{repository}/pulls",
            {"title": content.title, "body": content.body, "base": base, "head": head},
        )
        return collection.with_id(data["number"])
