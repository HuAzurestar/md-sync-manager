"""Platform-neutral remote resource values."""

from dataclasses import dataclass


ROUTES = {
    ("github", "issues"): 2,
    ("github", "pulls"): 2,
    ("gitee", "issues"): 2,
    ("gitee", "pulls"): 2,
    ("youtrack", "issues"): 1,
    ("youtrack", "articles"): 1,
}


@dataclass(frozen=True)
class RemotePath:
    source: str
    resource_type: str
    scope: tuple[str, ...]
    object_id: str | None = None

    @property
    def route(self) -> tuple[str, str]:
        return self.source, self.resource_type

    @property
    def is_collection(self) -> bool:
        return self.object_id is None

    def with_id(self, object_id: str | int) -> "RemotePath":
        if not self.is_collection:
            raise ValueError(f"remote path already identifies an object: {self}")
        if object_id is None or not str(object_id).strip():
            raise ValueError("remote object ID must be non-empty")
        value = str(object_id).strip()
        if self.source == "youtrack" and (not value.isascii() or not value.isdigit()):
            raise ValueError("YouTrack object IDs must be numeric")
        return RemotePath(self.source, self.resource_type, self.scope, value)

    def __str__(self) -> str:
        parts = [self.source, self.resource_type, *self.scope]
        if self.object_id is not None:
            parts.append(self.object_id)
        return "/".join(parts)

    @classmethod
    def parse(cls, value: str, *, require: str | None = None) -> "RemotePath":
        if not isinstance(value, str) or not value.strip():
            raise ValueError("remote path must be a non-empty string")
        parts = value.strip().strip("/").split("/")
        if len(parts) < 2:
            raise ValueError(f"invalid remote path: {value}")
        route = (parts[0].lower(), parts[1].lower())
        scope_size = ROUTES.get(route)
        if scope_size is None:
            raise ValueError(f"unsupported remote route: {'/'.join(route)}")
        tail = parts[2:]
        if len(tail) not in (scope_size, scope_size + 1) or any(
            not part for part in tail
        ):
            raise ValueError(f"invalid remote path: {value}")
        scope = tuple(tail[:scope_size])
        object_id = tail[scope_size] if len(tail) == scope_size + 1 else None
        if route[0] == "youtrack" and object_id is not None:
            if not object_id.isascii() or not object_id.isdigit():
                raise ValueError(f"YouTrack object paths require a numeric ID: {value}")
        result = cls(route[0], route[1], scope, object_id)
        if require == "collection" and not result.is_collection:
            raise ValueError(f"expected a collection path without an ID: {value}")
        if require == "object" and result.is_collection:
            raise ValueError(f"expected an object path with an ID: {value}")
        return result


@dataclass(frozen=True)
class RemoteContent:
    title: str
    body: str


@dataclass(frozen=True)
class RemoteItem:
    object_id: str
    title: str
