"""ATX heading catalog for one Markdown source."""

from dataclasses import asdict, dataclass
from pathlib import Path
import re


ATX_HEADING = re.compile(r"^( {0,3})(#{1,6})(?:[ \t]+(.*?)|[ \t]*)$")
FENCE_OPEN = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")
FENCE_CLOSE = re.compile(r"^ {0,3}(`{3,}|~{3,})[ \t]*$")


@dataclass(frozen=True)
class CatalogEntry:
    heading: str
    level: int
    text: str
    line: int

    def as_dict(self) -> dict[str, str | int]:
        return asdict(self)


@dataclass(frozen=True)
class DocumentCatalog:
    path: str
    entries: tuple[CatalogEntry, ...]
    line_count: int
    character_count: int

    def as_dict(self) -> dict[str, object]:
        return {
            "path": self.path,
            "entries": [entry.as_dict() for entry in self.entries],
            "metrics": {
                "lines": self.line_count,
                "characters": self.character_count,
                "headings": len(self.entries),
            },
        }


def catalog_text(text: str, *, path: str = "<memory>") -> DocumentCatalog:
    entries: list[CatalogEntry] = []
    fence_char: str | None = None
    fence_length = 0
    lines = text.splitlines(keepends=True)
    front_matter_end = _front_matter_end(lines)

    for line_number, line_with_ending in enumerate(lines, start=1):
        if line_number <= front_matter_end:
            continue
        line = line_with_ending.rstrip("\r\n")
        if fence_char is not None:
            closing = FENCE_CLOSE.match(line)
            if closing:
                marker = closing.group(1)
                if marker[0] == fence_char and len(marker) >= fence_length:
                    fence_char = None
                    fence_length = 0
            continue

        opening = FENCE_OPEN.match(line)
        if opening:
            marker = opening.group(1)
            if marker[0] == "`" and "`" in opening.group(2):
                continue
            fence_char = marker[0]
            fence_length = len(marker)
            continue

        match = ATX_HEADING.match(line)
        if not match:
            continue
        hashes = match.group(2)
        raw_text = (match.group(3) or "").strip()
        display_text = re.sub(r"[ \t]+#+[ \t]*$", "", raw_text).strip()
        entries.append(
            CatalogEntry(
                heading=line,
                level=len(hashes),
                text=display_text,
                line=line_number,
            )
        )

    return DocumentCatalog(
        path=path,
        entries=tuple(entries),
        line_count=len(lines),
        character_count=len(text),
    )


def _front_matter_end(lines: list[str]) -> int:
    if not lines or lines[0].rstrip("\r\n") != "---":
        return 0
    for line_number, line in enumerate(lines[1:], start=2):
        if line.rstrip("\r\n") in {"---", "..."}:
            return line_number
    return 0


def catalog_file(path: Path) -> DocumentCatalog:
    if not path.exists():
        raise FileNotFoundError(f"Markdown file not found: {path}")
    if not path.is_file():
        raise ValueError(f"Markdown path is not a file: {path}")
    if path.suffix.casefold() != ".md":
        raise ValueError(f"only .md files are supported: {path}")
    with path.open("r", encoding="utf-8", newline="") as stream:
        return catalog_text(stream.read(), path=str(path))


def format_catalog(catalog: DocumentCatalog) -> str:
    return "\n".join(
        f"{index}. {entry.heading}"
        for index, entry in enumerate(catalog.entries, start=1)
    )
