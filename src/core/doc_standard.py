"""Minimal facts and checks for the PIRC requirement/solution relationship."""

from dataclasses import dataclass, field
from pathlib import Path
import os
import re

import yaml

from src.core.document import MarkdownDocument, parse_text


RELATION_HEADING = "## 文档关系"
RELATION_KEYS = ("Issue", "需求文档", "方案文档")
ISSUE_PATTERN = re.compile(r"\bPIRC-\d+\b", re.IGNORECASE)


@dataclass(frozen=True)
class Diagnostic:
    code: str
    path: Path
    line: int
    message: str


@dataclass(frozen=True)
class DocumentRelation:
    issue: str
    requirement_path: str
    solution_path: str
    lines: dict[str, int] = field(compare=False, repr=False)


@dataclass(frozen=True)
class DocumentFacts:
    path: Path
    document: MarkdownDocument
    relation: DocumentRelation | None


@dataclass(frozen=True)
class CheckResult:
    facts: tuple[DocumentFacts, ...]
    diagnostics: tuple[Diagnostic, ...]

    @property
    def status(self) -> str:
        return "BLOCKED" if self.diagnostics else "PASS"


def _metadata_line(source: str, message: str) -> int:
    match = re.search(r"(?:field: |fields: )([^,\s]+)", message)
    key = match.group(1) if match else None
    if message.startswith("metadata field names must be strings: "):
        key = message.split(": ", 1)[1].split(",", 1)[0]
    if not key and message.startswith("type "):
        key = "type"
    for number, line in enumerate(source.splitlines(), 1):
        if key and re.match(rf"^\s*{re.escape(key)}\s*:", line):
            return number
    return 1


def _body_lines(source: str) -> tuple[list[str], int]:
    lines = source.splitlines()
    closing = next(
        (index for index, line in enumerate(lines[1:], 1) if line.strip() == "---"),
        None,
    )
    if closing is None:
        return [], 1
    return lines[closing + 1 :], closing + 2


def _clean_cell(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] == "`":
        return value[1:-1].strip()
    return value


def _code_fence_lines(lines: list[str]) -> set[int]:
    ignored = set()
    marker = None
    marker_length = 0
    for index, line in enumerate(lines):
        match = re.match(r"^\s*(`{3,}|~{3,})", line)
        if marker is None:
            if match:
                token = match.group(1)
                marker = token[0]
                marker_length = len(token)
                ignored.add(index)
            continue
        ignored.add(index)
        if match:
            token = match.group(1)
            if token[0] == marker and len(token) >= marker_length:
                marker = None
                marker_length = 0
    return ignored


def _parse_relation(
    source: str, path: Path
) -> tuple[DocumentRelation | None, list[Diagnostic]]:
    body, first_line = _body_lines(source)
    ignored = _code_fence_lines(body)
    heading_indexes = [
        index
        for index, line in enumerate(body)
        if index not in ignored and line.strip() == RELATION_HEADING
    ]
    if len(heading_indexes) != 1:
        code = "relation.missing" if not heading_indexes else "relation.duplicate"
        line = first_line if not heading_indexes else first_line + heading_indexes[1]
        return None, [Diagnostic(code, path, line, "expected one 文档关系 section")]

    start = heading_indexes[0]
    end = next(
        (
            index
            for index in range(start + 1, len(body))
            if index not in ignored and body[index].startswith("## ")
        ),
        len(body),
    )
    rows: dict[str, list[tuple[str, int]]] = {key: [] for key in RELATION_KEYS}
    for index in range(start + 1, end):
        if index in ignored:
            continue
        line = body[index].strip()
        if not line.startswith("|") or not line.endswith("|"):
            continue
        cells = [_clean_cell(cell) for cell in line[1:-1].split("|")]
        if len(cells) >= 2 and cells[0] in rows:
            rows[cells[0]].append((cells[1], first_line + index))

    diagnostics = []
    for key in RELATION_KEYS:
        if not rows[key]:
            diagnostics.append(
                Diagnostic(
                    "relation.row_missing",
                    path,
                    first_line + start,
                    f"missing relation row: {key}",
                )
            )
        elif len(rows[key]) > 1:
            diagnostics.append(
                Diagnostic(
                    "relation.row_duplicate",
                    path,
                    rows[key][1][1],
                    f"duplicate relation row: {key}",
                )
            )
    if diagnostics:
        return None, diagnostics

    issue_matches = ISSUE_PATTERN.findall(rows["Issue"][0][0])
    if len(issue_matches) != 1:
        return None, [
            Diagnostic(
                "relation.issue_invalid",
                path,
                rows["Issue"][0][1],
                "Issue relation must contain exactly one PIRC issue ID",
            )
        ]
    relation = DocumentRelation(
        issue_matches[0].upper(),
        rows["需求文档"][0][0],
        rows["方案文档"][0][0],
        {key: rows[key][0][1] for key in RELATION_KEYS},
    )
    return relation, []


def inspect_document(path: Path) -> tuple[DocumentFacts | None, list[Diagnostic]]:
    path = Path(path)
    try:
        source = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        return None, [Diagnostic("document.read_error", path, 1, str(error))]
    try:
        document = parse_text(source, path)
    except (ValueError, yaml.YAMLError) as error:
        problem_mark = getattr(error, "problem_mark", None)
        line = (
            problem_mark.line + 1
            if problem_mark is not None
            else _metadata_line(source, str(error))
        )
        return None, [
            Diagnostic("metadata.invalid", path, line, str(error))
        ]

    if document.document_type is None:
        return DocumentFacts(path, document, None), []
    relation, diagnostics = _parse_relation(source, path)
    return DocumentFacts(path, document, relation), diagnostics


def _same_path(left: Path, right: Path) -> bool:
    return os.path.normcase(str(left.resolve())) == os.path.normcase(str(right.resolve()))


def _relation_root(owner: Path, owner_reference: str) -> Path | None:
    reference = Path(owner_reference.replace("/", os.sep))
    if reference.is_absolute():
        return owner.parent if _same_path(reference, owner) else None
    reference_parts = tuple(os.path.normcase(part) for part in reference.parts)
    owner_parts = owner.resolve().parts
    normalized_owner = tuple(os.path.normcase(part) for part in owner_parts)
    if (
        len(reference_parts) > len(normalized_owner)
        or normalized_owner[-len(reference_parts) :] != reference_parts
    ):
        return None
    return Path(*owner_parts[: -len(reference_parts)])


def relation_path_matches(
    owner: Path,
    value: str,
    target: Path,
    *,
    owner_reference: str | None = None,
) -> bool:
    return _same_path(
        resolve_relation_path(owner, value, owner_reference=owner_reference), target
    )


def resolve_relation_path(
    owner: Path, value: str, *, owner_reference: str | None = None
) -> Path:
    reference = Path(value.replace("/", os.sep))
    if reference.is_absolute():
        return reference
    if owner_reference is not None:
        root = _relation_root(owner, owner_reference)
        if root is not None:
            return root / reference
    for base in (owner.parent, *owner.parents):
        candidate = base / reference
        if candidate.exists():
            return candidate
    return owner.parent / reference


def check_document(path: Path) -> CheckResult:
    facts, diagnostics = inspect_document(Path(path))
    if facts is None:
        return CheckResult((), tuple(diagnostics))
    if facts.relation:
        own_reference = (
            facts.relation.requirement_path
            if facts.document.document_type == "pirc.requirement"
            else facts.relation.solution_path
        )
        if not _same_path(
            resolve_relation_path(facts.path, own_reference), facts.path
        ):
            key = (
                "需求文档"
                if facts.document.document_type == "pirc.requirement"
                else "方案文档"
            )
            diagnostics.append(
                Diagnostic(
                    "relation.path_mismatch",
                    facts.path,
                    facts.relation.lines[key],
                    f"{key} relation does not point to this document",
                )
            )
    return CheckResult((facts,), tuple(diagnostics))


def check_pair(requirement_path: Path, solution_path: Path | None = None) -> CheckResult:
    requirement_result = check_document(Path(requirement_path))
    diagnostics = list(requirement_result.diagnostics)
    facts = list(requirement_result.facts)
    if not facts or facts[0].document.document_type != "pirc.requirement":
        if facts:
            diagnostics.append(
                Diagnostic(
                    "relation.requirement_type",
                    facts[0].path,
                    1,
                    "pair check requires a pirc.requirement document",
                )
            )
        return CheckResult(tuple(facts), tuple(diagnostics))
    requirement = facts[0]
    if requirement.relation is None:
        return CheckResult(tuple(facts), tuple(diagnostics))

    expected_solution = resolve_relation_path(
        requirement.path,
        requirement.relation.solution_path,
        owner_reference=requirement.relation.requirement_path,
    )
    selected_solution = Path(solution_path) if solution_path else expected_solution
    if not _same_path(selected_solution, expected_solution):
        diagnostics.append(
            Diagnostic(
                "relation.path_mismatch",
                requirement.path,
                requirement.relation.lines["方案文档"],
                "explicit solution does not match the requirement relation",
            )
        )

    solution_result = check_document(selected_solution)
    diagnostics.extend(solution_result.diagnostics)
    facts.extend(solution_result.facts)
    if not solution_result.facts:
        return CheckResult(tuple(facts), tuple(diagnostics))
    solution = solution_result.facts[0]
    if solution.document.document_type != "pirc.solution":
        diagnostics.append(
            Diagnostic(
                "relation.solution_type",
                solution.path,
                1,
                "paired document must have type pirc.solution",
            )
        )
        return CheckResult(tuple(facts), tuple(diagnostics))
    if solution.relation is None:
        return CheckResult(tuple(facts), tuple(diagnostics))

    if solution.relation.issue != requirement.relation.issue:
        diagnostics.append(
            Diagnostic(
                "relation.issue_mismatch",
                solution.path,
                solution.relation.lines["Issue"],
                "requirement and solution must reference the same Issue",
            )
        )
    expected_requirement = resolve_relation_path(
        solution.path,
        solution.relation.requirement_path,
        owner_reference=solution.relation.solution_path,
    )
    if not _same_path(expected_requirement, requirement.path):
        diagnostics.append(
            Diagnostic(
                "relation.path_mismatch",
                solution.path,
                solution.relation.lines["需求文档"],
                "solution requirement relation does not match the input document",
            )
        )
    return CheckResult(tuple(facts), tuple(diagnostics))
