"""YouTrack clients and single-object-type providers."""

import json
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from src.core.logging import get_logger
from src.core.remote import RemoteContent, RemoteItem, RemotePath
from src.providers.base import RemoteProvider


class YouTrackClient:
    def __init__(self, config: dict):
        self.url = config["url"].rstrip("/")
        self.token = config.get("token", "")
        self.logger = get_logger()

    @property
    def headers(self):
        return {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/json",
            "Content-Type": "application/json; charset=utf-8",
        }

    def get(self, path: str):
        return self.request("GET", path)

    def post(self, path: str, payload):
        return self.request("POST", path, payload)

    def request(self, method: str, path: str, payload=None):
        self.logger.info(
            "api_request provider=youtrack method=%s path=%s", method, path
        )
        data = (
            json.dumps(payload, ensure_ascii=False).encode("utf-8")
            if payload is not None
            else None
        )
        request = Request(
            self.url + path, data=data, headers=self.headers, method=method
        )
        try:
            with urlopen(request, timeout=30) as response:
                raw = response.read().decode("utf-8")
                return json.loads(raw) if raw else {}
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:500]
            raise RuntimeError(
                f"YouTrack API {exc.code} for {method} {path}: {detail}"
            ) from exc


class YouTrackIssueProvider(RemoteProvider):
    source = "youtrack"
    resource_type = "issues"
    supports_parent = True

    def __init__(self, client: YouTrackClient):
        self.client = client

    @staticmethod
    def _readable_id(remote: RemotePath) -> str:
        return f"{remote.scope[0]}-{remote.object_id}"

    @staticmethod
    def _numeric_id(collection: RemotePath, readable_id: str) -> str:
        prefix = f"{collection.scope[0]}-"
        if not isinstance(readable_id, str) or not readable_id.casefold().startswith(
            prefix.casefold()
        ):
            raise RuntimeError(
                f"unexpected YouTrack ID for {collection}: {readable_id!r}"
            )
        number = readable_id[len(prefix) :]
        if not number.isascii() or not number.isdigit():
            raise RuntimeError(
                f"unexpected YouTrack ID for {collection}: {readable_id!r}"
            )
        return number

    def list(self, collection: RemotePath) -> list[RemoteItem]:
        self.validate(collection, require="collection")
        query = urlencode({"fields": "idReadable,summary", "$top": 100})
        data = self.client.get(
            f"/api/admin/projects/{collection.scope[0]}/issues?{query}"
        )
        return [
            RemoteItem(
                self._numeric_id(collection, item.get("idReadable")),
                item.get("summary") or "",
            )
            for item in data
        ]

    def pull(self, remote: RemotePath) -> RemoteContent:
        self.validate(remote, require="object")
        issue_id = self._readable_id(remote)
        data = self.client.get(
            f"/api/issues/{issue_id}?fields=idReadable,summary,description"
        )
        return RemoteContent(data.get("summary") or "", data.get("description") or "")

    def push(self, remote: RemotePath, content: RemoteContent) -> None:
        self.validate(remote, require="object")
        issue_id = self._readable_id(remote)
        payload = {"summary": content.title, "description": content.body}
        self.client.post(f"/api/issues/{issue_id}", payload)
        verified = self.client.get(
            f"/api/issues/{issue_id}?fields=idReadable,summary,description"
        )
        if (
            verified.get("summary") != content.title
            or (verified.get("description") or "") != content.body
        ):
            raise RuntimeError("YouTrack Issue update verification failed")

    def upload(
        self, collection, content, *, parent=None, base=None, head=None
    ) -> RemotePath:
        self.validate(collection, require="collection")
        if base or head:
            raise ValueError("--base and --head are not valid for YouTrack upload")
        if parent:
            self.validate_parent(collection, parent)
        payload = {
            "summary": content.title,
            "description": content.body,
            "project": {"shortName": collection.scope[0]},
        }
        data = self.client.post("/api/issues?fields=idReadable,id", payload)
        return collection.with_id(self._numeric_id(collection, data.get("idReadable")))

    def set_parent(self, remote: RemotePath, parent: RemotePath) -> None:
        collection = RemotePath(remote.source, remote.resource_type, remote.scope)
        self.validate_parent(collection, parent)
        issue = self.client.get(f"/api/issues/{self._readable_id(remote)}?fields=id")
        parent_issue = self.client.get(
            f"/api/issues/{self._readable_id(parent)}?fields=id"
        )
        link_types = self.client.get("/api/issueLinkTypes?fields=id,name")
        link_type = next(
            (item for item in link_types if item.get("name") == "Subtask"), None
        )
        if not link_type:
            raise RuntimeError("YouTrack link type not found: Subtask")
        self.client.post(
            f"/api/issues/{issue['id']}/links/{link_type['id']}t/issues",
            {"id": parent_issue["id"]},
        )


class YouTrackArticleProvider(RemoteProvider):
    source = "youtrack"
    resource_type = "articles"
    supports_parent = True

    def __init__(self, client: YouTrackClient):
        self.client = client

    @staticmethod
    def _readable_id(remote: RemotePath) -> str:
        return f"{remote.scope[0]}-A-{remote.object_id}"

    @staticmethod
    def _numeric_id(collection: RemotePath, readable_id: str) -> str:
        prefix = f"{collection.scope[0]}-A-"
        if not isinstance(readable_id, str) or not readable_id.casefold().startswith(
            prefix.casefold()
        ):
            raise RuntimeError(
                f"unexpected YouTrack ID for {collection}: {readable_id!r}"
            )
        number = readable_id[len(prefix) :]
        if not number.isascii() or not number.isdigit():
            raise RuntimeError(
                f"unexpected YouTrack ID for {collection}: {readable_id!r}"
            )
        return number

    def list(self, collection: RemotePath) -> list[RemoteItem]:
        self.validate(collection, require="collection")
        query = urlencode({"fields": "id,idReadable,summary", "$top": 100})
        data = self.client.get(
            f"/api/admin/projects/{collection.scope[0]}/articles?{query}"
        )
        return [
            RemoteItem(
                self._numeric_id(collection, item.get("idReadable")),
                item.get("summary") or "",
            )
            for item in data
        ]

    def pull(self, remote: RemotePath) -> RemoteContent:
        self.validate(remote, require="object")
        article_id = self._readable_id(remote)
        data = self.client.get(
            f"/api/articles/{article_id}?fields=id,idReadable,summary,content"
        )
        return RemoteContent(data.get("summary") or "", data.get("content") or "")

    def push(self, remote: RemotePath, content: RemoteContent) -> None:
        self.validate(remote, require="object")
        article_id = self._readable_id(remote)
        payload = {"summary": content.title, "content": content.body}
        self.client.post(f"/api/articles/{article_id}", payload)
        verified = self.client.get(
            f"/api/articles/{article_id}?fields=id,summary,content"
        )
        if (
            verified.get("summary") != content.title
            or (verified.get("content") or "") != content.body
        ):
            raise RuntimeError("YouTrack Article update verification failed")

    def upload(
        self, collection, content, *, parent=None, base=None, head=None
    ) -> RemotePath:
        self.validate(collection, require="collection")
        if base or head:
            raise ValueError("--base and --head are not valid for YouTrack upload")
        if parent:
            self.validate_parent(collection, parent)
        payload = {
            "summary": content.title,
            "content": content.body,
            "project": {"shortName": collection.scope[0]},
        }
        data = self.client.post("/api/articles?fields=idReadable,id", payload)
        return collection.with_id(self._numeric_id(collection, data.get("idReadable")))

    def set_parent(self, remote: RemotePath, parent: RemotePath) -> None:
        collection = RemotePath(remote.source, remote.resource_type, remote.scope)
        self.validate_parent(collection, parent)
        parent_article = self.client.get(
            f"/api/articles/{self._readable_id(parent)}?fields=id"
        )
        child_article = self.client.get(
            f"/api/articles/{self._readable_id(remote)}?fields=id"
        )
        self.client.post(
            f"/api/articles/{parent_article['id']}/childArticles",
            {"id": child_article["id"], "$type": "Article"},
        )
