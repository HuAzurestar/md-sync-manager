"""Exact heading-range reads and compare-and-swap updates."""

from dataclasses import asdict, dataclass
import os
from pathlib import Path
import tempfile

from src.core.catalog import DocumentCatalog, catalog_text


class FocusSelectionError(ValueError):
    """A selector did not identify exactly one catalog entry."""


class FocusConflictError(RuntimeError):
    """The retained source no longer matches the current heading range."""


@dataclass(frozen=True)
class FocusSection:
    selector: str
    start_line: int
    end_line: int
    source: str

    def as_dict(self) -> dict[str, str | int]:
        return asdict(self)


def _selected_indices(catalog: DocumentCatalog, selectors: list[str]) -> list[int]:
    if not selectors:
        raise FocusSelectionError("at least one heading selector is required")
    selected: set[int] = set()
    for selector in selectors:
        matches = [
            index
            for index, entry in enumerate(catalog.entries)
            if entry.heading == selector
        ]
        if not matches:
            raise FocusSelectionError(f"heading selector not found: {selector}")
        if len(matches) > 1:
            raise FocusSelectionError(f"heading selector is ambiguous: {selector}")
        selected.add(matches[0])
    return sorted(selected)


def _section(text: str, catalog: DocumentCatalog, index: int) -> FocusSection:
    entry = catalog.entries[index]
    lines = text.splitlines(keepends=True)
    end_line = len(lines)
    for following in catalog.entries[index + 1 :]:
        if following.level <= entry.level:
            end_line = following.line - 1
            break
    source = "".join(lines[entry.line - 1 : end_line])
    return FocusSection(entry.heading, entry.line, end_line, source)


def focus_read_text(text: str, selectors: list[str]) -> tuple[FocusSection, ...]:
    catalog = catalog_text(text)
    return tuple(_section(text, catalog, index) for index in _selected_indices(catalog, selectors))


def focus_apply_text(
    text: str, *, selector: str, expected_source: str, replacement: str
) -> tuple[str, FocusSection]:
    section = focus_read_text(text, [selector])[0]
    if section.source != expected_source:
        raise FocusConflictError(
            "current heading range no longer matches the retained source"
        )
    replacement_lines = replacement.splitlines()
    if not replacement_lines or replacement_lines[0] != selector:
        raise ValueError("replacement must retain the exact selected heading")
    lines = text.splitlines(keepends=True)
    if section.end_line < len(lines) and not replacement.endswith(("\n", "\r")):
        raise ValueError("replacement must end with a newline before the next section")
    updated = (
        "".join(lines[: section.start_line - 1])
        + replacement
        + "".join(lines[section.end_line :])
    )
    return updated, section


def focus_read_file(path: Path, selectors: list[str]) -> tuple[FocusSection, ...]:
    _validate_markdown_file(path)
    return focus_read_text(read_text_exact(path), selectors)


def focus_apply_file(
    path: Path, *, selector: str, expected_source: str, replacement: str
) -> FocusSection:
    _validate_markdown_file(path)
    original = read_text_exact(path)
    updated, previous = focus_apply_text(
        original,
        selector=selector,
        expected_source=expected_source,
        replacement=replacement,
    )
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as stream:
            stream.write(updated)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, path.stat().st_mode)
        os.replace(temporary, path)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise
    return previous


def read_text_exact(path: Path) -> str:
    with path.open("r", encoding="utf-8", newline="") as stream:
        return stream.read()


def _validate_markdown_file(path: Path) -> None:
    if not path.exists():
        raise FileNotFoundError(f"Markdown file not found: {path}")
    if not path.is_file():
        raise ValueError(f"Markdown path is not a file: {path}")
    if path.suffix.casefold() != ".md":
        raise ValueError(f"only .md files are supported: {path}")
