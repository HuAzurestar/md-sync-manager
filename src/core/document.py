"""Markdown document model, parser, and renderer."""

from dataclasses import dataclass
from pathlib import Path

import yaml
from yaml.resolver import BaseResolver

from src.core.remote import RemotePath


STANDARD_DOCUMENT_TYPES = {"pirc.requirement", "pirc.solution"}


class _UniqueKeyLoader(yaml.SafeLoader):
    """Safe YAML loader that rejects ambiguous duplicate mapping keys."""


def _construct_unique_mapping(loader, node, deep=False):
    mapping = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if not isinstance(key, str):
            rendered = key_node.value if key_node.id == "scalar" else key_node.id
            raise yaml.constructor.ConstructorError(
                "while constructing YAML front matter",
                node.start_mark,
                f"metadata field names must be strings: {rendered}",
                key_node.start_mark,
            )
        if key in mapping:
            raise ValueError(f"duplicate metadata field: {key}")
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


_UniqueKeyLoader.add_constructor(
    BaseResolver.DEFAULT_MAPPING_TAG, _construct_unique_mapping
)


@dataclass
class MarkdownDocument:
    path: Path
    metadata: dict[str, object]
    body: str
    remote: RemotePath | None = None

    @property
    def title(self) -> str:
        return str(self.metadata.get("title") or self.path.stem)

    @property
    def parent(self) -> str | None:
        value = self.metadata.get("parent")
        return str(value) if value else None

    @property
    def document_type(self) -> str | None:
        value = self.metadata.get("type")
        return str(value) if value else None


def parse_text(text: str, path: Path = Path("<memory>")) -> MarkdownDocument:
    if not text.startswith("---"):
        raise ValueError("Markdown requires YAML front matter")
    parts = text.split("---", 2)
    if len(parts) != 3:
        raise ValueError("YAML front matter is not closed")
    metadata = yaml.load(parts[1], Loader=_UniqueKeyLoader) or {}
    if not isinstance(metadata, dict):
        raise ValueError("YAML front matter must be a mapping")
    non_string_keys = [key for key in metadata if not isinstance(key, str)]
    if non_string_keys:
        rendered = ", ".join(sorted(repr(key) for key in non_string_keys))
        raise ValueError(f"metadata field names must be strings: {rendered}")
    unknown = set(metadata) - {"title", "type", "parent", "remote"}
    if unknown:
        raise ValueError(f"unsupported metadata fields: {', '.join(sorted(unknown))}")

    title = metadata.get("title")
    if not isinstance(title, str) or not title.strip():
        raise ValueError("title must be a non-empty string")
    document_type = metadata.get("type")
    if document_type is not None and document_type not in STANDARD_DOCUMENT_TYPES:
        allowed = ", ".join(sorted(STANDARD_DOCUMENT_TYPES))
        raise ValueError(f"type must be one of: {allowed}")
    parent = metadata.get("parent")
    if parent is not None and (not isinstance(parent, str) or not parent.strip()):
        raise ValueError("parent must be a non-empty remote path string")
    if parent:
        RemotePath.parse(parent, require="object")
    remote_value = metadata.get("remote")
    if remote_value is not None and (
        not isinstance(remote_value, str) or not remote_value.strip()
    ):
        raise ValueError("remote must be a non-empty remote path string")

    remote = RemotePath.parse(remote_value, require="object") if remote_value else None
    body = parts[2].lstrip("\r\n")
    return MarkdownDocument(path, metadata, body, remote)


def parse_file(path: Path) -> MarkdownDocument:
    return parse_text(path.read_text(encoding="utf-8"), path)


def render_document(document: MarkdownDocument, body: str | None = None) -> str:
    metadata = {"title": document.title}
    if document.document_type:
        metadata["type"] = document.document_type
    if document.parent:
        metadata["parent"] = document.parent
    if document.remote:
        metadata["remote"] = str(document.remote)
    front_matter = yaml.safe_dump(
        metadata, allow_unicode=True, sort_keys=False
    ).rstrip()
    return (
        "---\n" + front_matter + "\n---\n\n" + (document.body if body is None else body)
    )
