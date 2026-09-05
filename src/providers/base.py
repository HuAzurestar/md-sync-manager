"""Polymorphic contract implemented by one provider per remote object type."""

from abc import ABC, abstractmethod

from src.core.remote import RemoteContent, RemoteItem, RemotePath


class RemoteProvider(ABC):
    source: str
    resource_type: str
    supports_parent = False
    parent_during_upload = False

    @property
    def route(self) -> tuple[str, str]:
        return self.source, self.resource_type

    def validate(self, path: RemotePath, *, require: str | None = None) -> None:
        if path.route != self.route:
            raise ValueError(
                f"provider {self.source}/{self.resource_type} cannot handle {path}"
            )
        if require == "collection" and not path.is_collection:
            raise ValueError(f"expected collection path: {path}")
        if require == "object" and path.is_collection:
            raise ValueError(f"expected object path: {path}")

    def validate_parent(self, collection: RemotePath, parent: RemotePath) -> None:
        if not self.supports_parent:
            raise ValueError(
                f"{self.source}/{self.resource_type} does not support parent objects"
            )
        self.validate(collection, require="collection")
        self.validate(parent, require="object")
        collection_scope = tuple(part.casefold() for part in collection.scope)
        parent_scope = tuple(part.casefold() for part in parent.scope)
        if collection_scope != parent_scope:
            raise ValueError(
                "parent and target must belong to the same project or repository"
            )

    @abstractmethod
    def list(self, collection: RemotePath) -> list[RemoteItem]: ...

    @abstractmethod
    def pull(self, remote: RemotePath) -> RemoteContent: ...

    @abstractmethod
    def push(self, remote: RemotePath, content: RemoteContent) -> None: ...

    @abstractmethod
    def upload(
        self,
        collection: RemotePath,
        content: RemoteContent,
        *,
        parent: RemotePath | None = None,
        base: str | None = None,
        head: str | None = None,
    ) -> RemotePath: ...

    def set_parent(self, remote: RemotePath, parent: RemotePath) -> None:
        raise ValueError(
            f"{self.source}/{self.resource_type} does not support parent objects"
        )
