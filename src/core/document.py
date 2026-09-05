"""Markdown document model, parser, and renderer."""

from dataclasses import dataclass
from pathlib import Path

import yaml

from src.core.remote import RemotePath


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


def parse_text(text: str, path: Path = Path("<memory>")) -> MarkdownDocument:
    if not text.startswith("---"):
        raise ValueError("Markdown requires YAML front matter")
    parts = text.split("---", 2)
    if len(parts) != 3:
        raise ValueError("YAML front matter is not closed")
    metadata = yaml.safe_load(parts[1]) or {}
    if not isinstance(metadata, dict):
        raise ValueError("YAML front matter must be a mapping")
    unknown = set(metadata) - {"title", "parent", "remote"}
    if unknown:
        raise ValueError(f"unsupported metadata fields: {', '.join(sorted(unknown))}")

    title = metadata.get("title")
    if not isinstance(title, str) or not title.strip():
        raise ValueError("title must be a non-empty string")
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
