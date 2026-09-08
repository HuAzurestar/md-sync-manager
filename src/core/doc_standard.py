"""Facts, validation, extraction, and review for the fixed PIRC Markdown contract."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any, Iterable
import os
import re

import yaml

from src.core.document import MarkdownDocument, parse_text


FORMAT_VERSION = "pirc-doc-guard-v1"
HASH_ALGORITHM = "pirc-md-body-v1"
RELATION_HEADING = "## 文档关系"
RELATION_KEYS = ("Issue", "需求文档", "方案文档")
ISSUE_PATTERN = re.compile(r"\bPIRC-\d+\b", re.IGNORECASE)
ID_PATTERN = re.compile(
    r"\b(?:KR|REQ|NG|AC|SOL|TEST|EXT|NFR|SEC|STATE|MIG|OBS|RES|CAP|LIFE)-\d{3}\b"
)
RECORD_HEADING_PATTERN = re.compile(
    r"^(?P<id>(?:KR|AC|SOL|TEST|EXT|NFR|SEC|STATE|MIG|OBS|RES|CAP|LIFE)-\d{3})\b\s*(?P<title>.*)$"
)
LIST_RECORD_PATTERN = re.compile(
    r"^\s*\d+\.\s+`?(?P<id>(?:REQ|NG)-\d{3})\b`?(?P<title>.*)$"
)
FIELD_PATTERN = re.compile(r"^\s*-\s*([^：:]+)[：:]\s*(.*)$")

SECTION_KEYS = {
    "pirc.requirement": {
        "文档关系": "relation",
        "背景与目标": "background-goals",
        "需求范围": "scope",
        "验收": "acceptance",
        "生产约束": "production-constraints",
        "依赖、风险与补充": "dependencies-risks-supplement",
    },
    "pirc.solution": {
        "文档关系": "relation",
        "执行范围与追溯": "execution-trace",
        "技术设计": "technical-design",
        "实施与验收": "implementation-acceptance",
        "生产保障": "production-assurance",
        "生命周期与补充": "lifecycle-supplement",
    },
}
REQUIRED_SECTIONS = {
    "pirc.requirement": ("文档关系", "背景与目标", "需求范围", "验收"),
    "pirc.solution": ("文档关系", "执行范围与追溯", "技术设计", "实施与验收"),
}
RECORD_PARENT_SECTIONS = {
    "KR": {"背景与目标"},
    "REQ": {"需求范围"},
    "NG": {"需求范围"},
    "AC": {"验收"},
    "SOL": {"技术设计"},
    "TEST": {"实施与验收"},
    "NFR": {"生产约束"},
    "SEC": {"生产约束"},
    "STATE": {"生产约束"},
    "MIG": {"生产保障"},
    "OBS": {"生产保障"},
    "RES": {"生产保障"},
    "CAP": {"生产保障"},
    "LIFE": {"生命周期与补充"},
}
REQUIRED_FIELDS = {
    "KR": (("指标",), ("目标",), ("测量",)),
    "REQ": (("结果",), ("验证",), ("验收",)),
    "NG": (("原因",),),
    "AC": (("需求",), ("Given",), ("When",), ("Then",)),
    "SOL": (("需求",), ("输入",), ("输出",), ("过程",), ("失败",), ("测试",)),
    "TEST": (
        ("需求", "需求/方案"),
        ("方案", "需求/方案"),
        ("前置",),
        ("动作",),
        ("预期",),
    ),
    "EXT": (("父节",), ("用途",), ("触发", "触发条件"), ("结构类型",), ("关联",)),
    "NFR": (
        ("需求",),
        ("指标",),
        ("适用范围",),
        ("基线",),
        ("目标或上限",),
        ("测量与验收",),
    ),
    "SEC": (
        ("需求",),
        ("数据/资产",),
        ("触发因素",),
        ("约束",),
        ("失败表现",),
        ("验收",),
    ),
    "STATE": (
        ("需求",),
        ("实体",),
        ("当前状态",),
        ("事件",),
        ("下一状态",),
        ("非法跃迁结果",),
        ("验收",),
    ),
    "MIG": (
        ("需求/方案", "需求", "方案"),
        ("对象",),
        ("现状",),
        ("目标",),
        ("兼容",),
        ("迁移/废弃",),
        ("回滚",),
        ("测试",),
    ),
    "OBS": (
        ("需求/方案", "需求", "方案"),
        ("阶段或信号",),
        ("机制或指标",),
        ("门槛",),
        ("失败动作",),
        ("测试",),
    ),
    "RES": (
        ("需求/方案", "需求", "方案"),
        ("故障",),
        ("超时/重试",),
        ("限流/熔断",),
        ("降级",),
        ("恢复",),
        ("测试",),
    ),
    "CAP": (
        ("需求/方案", "需求", "方案"),
        ("资源",),
        ("基线",),
        ("预计",),
        ("上限",),
        ("测量",),
        ("超限动作",),
        ("测试",),
    ),
    "LIFE": (
        ("方案",),
        ("状态",),
        ("替代文档",),
        ("As-Built 偏差",),
        ("影响",),
        ("责任",),
        ("回填时间",),
        ("测试",),
    ),
}
ALLOWED_REFERENCES = {
    "KR": {"REQ", "AC"},
    "REQ": {"KR", "AC", "REQ"},
    "NG": {"REQ"},
    "AC": {"REQ", "KR"},
    "SOL": {"REQ", "TEST", "MIG", "OBS", "RES", "CAP", "LIFE"},
    "TEST": {"REQ", "AC", "SOL"},
    "EXT": {"KR", "REQ", "NG", "AC", "SOL", "TEST"},
    "NFR": {"REQ", "AC"},
    "SEC": {"REQ", "AC"},
    "STATE": {"REQ", "AC"},
    "MIG": {"REQ", "SOL", "TEST"},
    "OBS": {"REQ", "SOL", "TEST"},
    "RES": {"REQ", "SOL", "TEST"},
    "CAP": {"REQ", "SOL", "TEST"},
    "LIFE": {"SOL", "TEST"},
}
EXTENSION_STRUCTURES = {"表格", "有序记录列表", "H4 记录块", "图", "代码契约"}
AGENT_STATUSES = {"CLEAR", "WARNING", "NEEDS_CHANGE"}
HUMAN_STATUSES = {"APPROVED", "CHANGES_REQUESTED", "DEFERRED"}
DISPOSITIONS = {"OPEN", "ACCEPTED", "REJECTED", "RESOLVED"}


@dataclass(frozen=True)
class Diagnostic:
    code: str
    path: Path
    line: int
    message: str
    layer: str = "AUTO"
    severity: str = "BLOCKER"
    target: str | None = None


@dataclass(frozen=True)
class DocumentRelation:
    issue: str
    requirement_path: str
    solution_path: str
    lines: dict[str, int] = field(compare=False, repr=False)


@dataclass(frozen=True)
class HeadingFacts:
    level: int
    title: str
    line: int
    end_line: int
    key: str


@dataclass(frozen=True)
class RecordFacts:
    record_id: str
    kind: str
    title: str
    parent_section: str
    parent_group: str
    fields: dict[str, str] = field(compare=False)
    line: int = 1
    end_line: int = 1
    markdown: str = field(default="", compare=False)
    status: str = "TODO"
    priority: str | None = None
    references: tuple[str, ...] = ()


@dataclass(frozen=True)
class TraceEdge:
    source_id: str
    target_id: str
    target_path: str | None
    line: int


@dataclass(frozen=True)
class CoverageMetric:
    covered: int
    total: int
    percent: float | None


@dataclass(frozen=True)
class CatalogEntry:
    key: str
    title: str
    level: int
    entry_type: str
    record_count: int
    byte_count: int
    image_count: int
    table_count: int
    list_count: int
    code_block_count: int
    ids: tuple[str, ...]
    line_start: int
    line_end: int


@dataclass(frozen=True)
class DocumentFacts:
    path: Path
    document: MarkdownDocument
    relation: DocumentRelation | None
    source: str = field(default="", compare=False, repr=False)
    sha256: str = ""
    h1: str | None = None
    headings: tuple[HeadingFacts, ...] = ()
    records: tuple[RecordFacts, ...] = ()
    edges: tuple[TraceEdge, ...] = ()
    catalog: tuple[CatalogEntry, ...] = ()

    @property
    def record_index(self) -> dict[str, RecordFacts]:
        return {record.record_id: record for record in self.records}


@dataclass(frozen=True)
class CheckResult:
    facts: tuple[DocumentFacts, ...]
    diagnostics: tuple[Diagnostic, ...]
    coverage: dict[str, CoverageMetric] = field(default_factory=dict)

    @property
    def status(self) -> str:
        return (
            "BLOCKED"
            if any(item.severity == "BLOCKER" for item in self.diagnostics)
            else "PASS"
        )


def _body_from_source(source: str) -> tuple[str, int]:
    normalized = source.replace("\r\n", "\n").replace("\r", "\n")
    lines = normalized.split("\n")
    if not lines or lines[0].strip() != "---":
        return normalized, 1
    closing = next(
        (i for i, line in enumerate(lines[1:], 1) if line.strip() == "---"), None
    )
    if closing is None:
        return "", 1
    return "\n".join(lines[closing + 1 :]).lstrip("\n"), closing + 2


def source_sha256(source: str) -> str:
    """Hash the normalized body while blanking only declared SHA-256 slots."""
    body, _ = _body_from_source(source)
    output = []
    for line in body.split("\n"):
        stripped = line.strip()
        declared_slot = bool(
            re.match(
                r"(?:[-*]\s*)?(?:SHA-?256|源哈希|source_sha256)\s*[:：=|]",
                stripped,
                re.IGNORECASE,
            )
            or (
                stripped.startswith("|")
                and re.search(
                    r"(?:SHA-?256|源哈希|source_sha256)", stripped, re.IGNORECASE
                )
            )
        )
        if declared_slot:
            line = re.sub(
                r"(?<![0-9a-fA-F])[0-9a-fA-F]{64}(?![0-9a-fA-F])", "<sha256>", line
            )
        output.append(line)
    return sha256("\n".join(output).encode("utf-8")).hexdigest()


def _metadata_line(source: str, message: str) -> int:
    match = re.search(r"(?:field: |fields: )([^,\s]+)", message)
    key = match.group(1) if match else ("type" if message.startswith("type ") else None)
    for number, line in enumerate(source.splitlines(), 1):
        if key and re.match(rf"^\s*{re.escape(key)}\s*:", line):
            return number
    return 1


def _clean_cell(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] == "`":
        return value[1:-1].strip()
    return value


def _code_fence_lines(lines: list[str]) -> set[int]:
    ignored: set[int] = set()
    marker: str | None = None
    marker_length = 0
    for index, line in enumerate(lines):
        match = re.match(r"^\s*(`{3,}|~{3,})", line)
        if marker is None:
            if match:
                token = match.group(1)
                marker, marker_length = token[0], len(token)
                ignored.add(index)
            continue
        ignored.add(index)
        if match:
            token = match.group(1)
            if token[0] == marker and len(token) >= marker_length:
                marker, marker_length = None, 0
    return ignored


def _parse_relation(
    source: str, path: Path
) -> tuple[DocumentRelation | None, list[Diagnostic]]:
    body, first_line = _body_from_source(source)
    lines = body.splitlines()
    ignored = _code_fence_lines(lines)
    indexes = [
        i
        for i, line in enumerate(lines)
        if i not in ignored and line.strip() == RELATION_HEADING
    ]
    if len(indexes) != 1:
        code = "relation.missing" if not indexes else "relation.duplicate"
        line = first_line if not indexes else first_line + indexes[1]
        return None, [Diagnostic(code, path, line, "expected one 文档关系 section")]
    start = indexes[0]
    end = next(
        (
            i
            for i in range(start + 1, len(lines))
            if i not in ignored and lines[i].startswith("## ")
        ),
        len(lines),
    )
    rows: dict[str, list[tuple[str, int]]] = {key: [] for key in RELATION_KEYS}
    for index in range(start + 1, end):
        if index in ignored:
            continue
        line = lines[index].strip()
        if not line.startswith("|") or not line.endswith("|"):
            continue
        cells = [_clean_cell(cell) for cell in line[1:-1].split("|")]
        if len(cells) >= 2 and cells[0] in rows:
            rows[cells[0]].append((cells[1], first_line + index))
    diagnostics: list[Diagnostic] = []
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
    matches = ISSUE_PATTERN.findall(rows["Issue"][0][0])
    if len(matches) != 1:
        return None, [
            Diagnostic(
                "relation.issue_invalid",
                path,
                rows["Issue"][0][1],
                "Issue relation must contain exactly one PIRC issue ID",
            )
        ]
    return DocumentRelation(
        matches[0].upper(),
        rows["需求文档"][0][0],
        rows["方案文档"][0][0],
        {key: rows[key][0][1] for key in RELATION_KEYS},
    ), []


def _slug(title: str) -> str:
    return (
        re.sub(r"[^0-9A-Za-z\u4e00-\u9fff]+", "-", title).strip("-").lower()
        or "section"
    )


def _parse_headings(
    body: str, first_line: int, document_type: str | None, path: Path
) -> tuple[list[HeadingFacts], list[Diagnostic]]:
    lines = body.splitlines()
    ignored = _code_fence_lines(lines)
    raw: list[tuple[int, str, int]] = []
    diagnostics: list[Diagnostic] = []
    for index, line in enumerate(lines):
        if index in ignored:
            continue
        match = re.match(r"^(#{1,})\s+(.+?)\s*$", line)
        if not match:
            continue
        level = len(match.group(1))
        if level > 4:
            diagnostics.append(
                Diagnostic(
                    "structure.heading_too_deep",
                    path,
                    first_line + index,
                    "headings below H4 are not allowed",
                )
            )
            continue
        raw.append((level, match.group(2).strip(), index))
    counts: dict[str, int] = {}
    headings: list[HeadingFacts] = []
    parent_key = ""
    for position, (level, title, index) in enumerate(raw):
        end = len(lines)
        for next_level, _, next_index in raw[position + 1 :]:
            if next_level <= level:
                end = next_index
                break
        if level == 2:
            key = SECTION_KEYS.get(document_type or "", {}).get(title)
            if not key:
                base = _slug(title)
                counts[base] = counts.get(base, 0) + 1
                key = base if counts[base] == 1 else f"{base}~{counts[base]}"
            parent_key = key
        elif level == 3:
            base = f"{parent_key}/{_slug(title)}" if parent_key else _slug(title)
            counts[base] = counts.get(base, 0) + 1
            key = base if counts[base] == 1 else f"{base}~{counts[base]}"
        else:
            key = _slug(title)
        headings.append(
            HeadingFacts(level, title, first_line + index, first_line + end - 1, key)
        )
    return headings, diagnostics


def _parent_titles(headings: list[HeadingFacts], line: int) -> tuple[str, str]:
    section = group = ""
    for heading in headings:
        if heading.line >= line:
            break
        if heading.level == 2:
            section, group = heading.title, ""
        elif heading.level == 3:
            group = heading.title
    return section, group


def _field_map(lines: list[str]) -> dict[str, str]:
    fields: dict[str, str] = {}
    ignored = _code_fence_lines(lines)
    for index, line in enumerate(lines):
        if index in ignored:
            continue
        match = FIELD_PATTERN.match(line)
        if match:
            fields[match.group(1).strip()] = match.group(2).strip()
    return fields


def _references(fields: dict[str, str]) -> tuple[str, ...]:
    found: list[str] = []
    for value in fields.values():
        for record_id in ID_PATTERN.findall(value):
            if record_id not in found:
                found.append(record_id)
    return tuple(found)


def _reference_edges(record: RecordFacts) -> tuple[TraceEdge, ...]:
    edges: list[TraceEdge] = []
    seen: set[tuple[str, str | None]] = set()
    identifier_pattern = ID_PATTERN.pattern[2:-2]
    explicit_pattern = re.compile(
        r"`([^`#]+)#(" + identifier_pattern + r")`"
        r"|([^\s`\uFF0C\u3002\u3001\uFF1B\uFF1A,;]+)#(" + identifier_pattern + r")"
    )
    for value in record.fields.values():
        candidates: list[tuple[int, str, str | None]] = []
        explicit_spans: set[tuple[int, int]] = set()
        for match in explicit_pattern.finditer(value):
            target_group = 2 if match.group(2) else 4
            path_group = 1 if target_group == 2 else 3
            candidates.append(
                (match.start(), match.group(target_group), match.group(path_group))
            )
            explicit_spans.add(match.span(target_group))
        for match in ID_PATTERN.finditer(value):
            if match.span() not in explicit_spans:
                candidates.append((match.start(), match.group(), None))
        for _, target_id, target_path in sorted(candidates):
            item = (target_id, target_path)
            if item not in seen:
                edges.append(
                    TraceEdge(record.record_id, target_id, item[1], record.line)
                )
                seen.add(item)
    return tuple(edges)


def _parse_records(
    body: str, first_line: int, headings: list[HeadingFacts], path: Path
) -> tuple[list[RecordFacts], list[Diagnostic]]:
    lines = body.splitlines()
    ignored = _code_fence_lines(lines)
    starts: list[tuple[int, str, str, str]] = []
    diagnostics: list[Diagnostic] = []
    for index, line in enumerate(lines):
        if index in ignored:
            continue
        heading = re.match(r"^####\s+(.+?)\s*$", line)
        if heading:
            heading_text = heading.group(1).replace("`", "")
            match = RECORD_HEADING_PATTERN.match(heading_text)
            if match:
                starts.append(
                    (index, match.group("id"), match.group("title").strip(), "heading")
                )
                continue
            token = re.match(
                r"^((?:KR|REQ|NG|AC|SOL|TEST|EXT|NFR|SEC|STATE|MIG|OBS|RES|CAP|LIFE)-[^\s]+)",
                heading_text,
            )
            absolute_line = first_line + index
            parent_section, _ = _parent_titles(headings, absolute_line)
            token_kind = token.group(1).split("-", 1)[0] if token else None
            is_record_position = bool(
                token_kind
                and parent_section in RECORD_PARENT_SECTIONS.get(token_kind, set())
            )
            if (
                token
                and is_record_position
                and re.fullmatch(r"(?:REQ|NG)-\d{3}", token.group(1))
            ):
                diagnostics.append(
                    Diagnostic(
                        "record.shape_invalid",
                        path,
                        first_line + index,
                        f"{token.group(1)} must use an ordered record list",
                        target=token.group(1),
                    )
                )
            elif token and is_record_position:
                diagnostics.append(
                    Diagnostic(
                        "record.id_invalid",
                        path,
                        first_line + index,
                        f"invalid record ID: {token.group(1)}",
                    )
                )
        listed = LIST_RECORD_PATTERN.match(line)
        if listed:
            starts.append(
                (index, listed.group("id"), listed.group("title").strip(), "list")
            )
        elif re.match(
            r"^\s*\d+\.\s+`?(?:KR|REQ|NG|AC|SOL|TEST|EXT|NFR|SEC|STATE|MIG|OBS|RES|CAP|LIFE)-",
            line,
        ):
            token = re.match(r"^\s*\d+\.\s+`?([^`\s]+)", line)
            record_id = token.group(1) if token else line.strip()
            absolute_line = first_line + index
            parent_section, _ = _parent_titles(headings, absolute_line)
            token_kind = record_id.split("-", 1)[0]
            if parent_section not in RECORD_PARENT_SECTIONS.get(token_kind, set()):
                continue
            code = (
                "record.shape_invalid"
                if re.fullmatch(ID_PATTERN, record_id)
                else "record.id_invalid"
            )
            message = (
                f"{record_id} must use an H4 record block"
                if code == "record.shape_invalid"
                else f"invalid record ID: {record_id}"
            )
            diagnostics.append(
                Diagnostic(code, path, first_line + index, message, target=record_id)
            )
    records: list[RecordFacts] = []
    seen: set[str] = set()
    for position, (index, record_id, title, shape) in enumerate(starts):
        end = starts[position + 1][0] if position + 1 < len(starts) else len(lines)
        for candidate in range(index + 1, end):
            if candidate in ignored:
                continue
            heading = re.match(r"^(#{1,4})\s+", lines[candidate])
            if heading and len(heading.group(1)) <= (4 if shape == "heading" else 3):
                end = candidate
                break
        absolute = first_line + index
        section, group = _parent_titles(headings, absolute)
        fields = _field_map(lines[index + 1 : end])
        annotations = re.findall(r"\[([A-Z0-9]+)\]", title)
        priorities = [item for item in annotations if re.fullmatch(r"P[0-3]", item)]
        states = [item for item in annotations if item not in priorities]
        kind = record_id.split("-", 1)[0]
        status = states[0] if states else ("REJ" if kind == "NG" else "TODO")
        clean_title = re.sub(r"`?\[[A-Z0-9]+\]`?", "", title).strip()
        record = RecordFacts(
            record_id,
            kind,
            clean_title,
            section,
            group,
            fields,
            absolute,
            first_line + max(index, end - 1),
            "\n".join(lines[index:end]).rstrip() + "\n",
            status,
            priorities[0] if len(priorities) == 1 else None,
            _references(fields),
        )
        if record_id in seen:
            diagnostics.append(
                Diagnostic(
                    "record.duplicate_id",
                    path,
                    absolute,
                    f"duplicate record ID: {record_id}",
                    target=record_id,
                )
            )
        seen.add(record_id)
        records.append(record)
    return records, diagnostics


def _section_slice(body: str, first_line: int, heading: HeadingFacts) -> str:
    lines = body.splitlines()
    start = max(0, heading.line - first_line)
    end = max(start + 1, heading.end_line - first_line + 1)
    return "\n".join(lines[start:end]).rstrip() + "\n"


def _count_tables(lines: list[str]) -> int:
    count = 0
    previous = False
    for line in lines:
        current = line.strip().startswith("|") and line.strip().endswith("|")
        if current and not previous:
            count += 1
        previous = current
    return count


def _content_metrics(text: str) -> tuple[int, int, int, int, int]:
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    ignored = _code_fence_lines(lines)
    visible = [line for index, line in enumerate(lines) if index not in ignored]
    outside = "\n".join(visible)
    fence_starts = 0
    marker: str | None = None
    marker_length = 0
    for line in lines:
        match = re.match(r"^\s*(`{3,}|~{3,})", line)
        if marker is None:
            if match:
                token = match.group(1)
                marker, marker_length = token[0], len(token)
                fence_starts += 1
        elif match:
            token = match.group(1)
            if token[0] == marker and len(token) >= marker_length:
                marker, marker_length = None, 0
    return (
        len(outside.encode("utf-8")),
        len(re.findall(r"!\[[^\]]*\]\([^)]*\)|<img\b", outside, re.IGNORECASE)),
        _count_tables(visible),
        sum(1 for line in visible if re.match(r"^\s*(?:[-+*]|\d+\.)\s+", line)),
        fence_starts,
    )


def _catalog(
    body: str,
    first_line: int,
    headings: list[HeadingFacts],
    records: list[RecordFacts],
    document_type: str | None,
) -> list[CatalogEntry]:
    entries: list[CatalogEntry] = []
    allowed = SECTION_KEYS.get(document_type or "", {})
    for heading in (item for item in headings if item.level in {2, 3}):
        text = _section_slice(body, first_line, heading)
        byte_count, images, tables, lists, fences = _content_metrics(text)
        if heading.level == 2:
            section_records = [
                item for item in records if item.parent_section == heading.title
            ]
        else:
            section_records = [
                item
                for item in records
                if item.parent_group == heading.title
                and heading.line <= item.line <= heading.end_line
            ]
        entries.append(
            CatalogEntry(
                heading.key,
                heading.title,
                heading.level,
                "standard"
                if heading.level == 2 and heading.title in allowed
                else "unknown",
                len(section_records),
                byte_count,
                images,
                tables,
                lists,
                fences,
                tuple(item.record_id for item in section_records),
                heading.line,
                heading.end_line,
            )
        )
    for record in records:
        byte_count, images, tables, lists, fences = _content_metrics(record.markdown)
        entries.append(
            CatalogEntry(
                record.record_id,
                record.title,
                4,
                "extension" if record.kind == "EXT" else "standard",
                1,
                byte_count,
                images,
                tables,
                lists,
                fences,
                (record.record_id,),
                record.line,
                record.end_line,
            )
        )
    entries.sort(key=lambda item: (item.line_start, item.level, item.key))
    return entries


def _validate_structure(facts: DocumentFacts) -> list[Diagnostic]:
    path = facts.path
    diagnostics: list[Diagnostic] = []
    h1s = [item for item in facts.headings if item.level == 1]
    if len(h1s) != 1:
        diagnostics.append(
            Diagnostic(
                "structure.h1",
                path,
                h1s[1].line if len(h1s) > 1 else 1,
                "standard documents require exactly one H1",
            )
        )
    h2s = [item for item in facts.headings if item.level == 2]
    titles = [item.title for item in h2s]
    allowed = SECTION_KEYS.get(facts.document.document_type or "", {})
    for title in REQUIRED_SECTIONS.get(facts.document.document_type or "", ()):
        if title not in titles:
            diagnostics.append(
                Diagnostic(
                    "structure.required_section",
                    path,
                    1,
                    f"missing required H2: {title}",
                    target=allowed.get(title),
                )
            )
    seen: set[str] = set()
    for heading in h2s:
        if heading.title not in allowed:
            diagnostics.append(
                Diagnostic(
                    "structure.unknown_section",
                    path,
                    heading.line,
                    f"unknown H2 for {facts.document.document_type}: {heading.title}",
                    target=heading.key,
                )
            )
        elif heading.title in seen:
            diagnostics.append(
                Diagnostic(
                    "structure.duplicate_section",
                    path,
                    heading.line,
                    f"duplicate H2: {heading.title}",
                    target=allowed[heading.title],
                )
            )
        seen.add(heading.title)
    for heading in facts.headings:
        if heading.level == 3:
            parent = next(
                (
                    item
                    for item in reversed(facts.headings)
                    if item.level == 2 and item.line < heading.line
                ),
                None,
            )
            if parent is None:
                diagnostics.append(
                    Diagnostic(
                        "structure.heading_parent",
                        path,
                        heading.line,
                        "H3 requires a preceding H2",
                    )
                )
            elif parent.title == "文档关系":
                diagnostics.append(
                    Diagnostic(
                        "structure.relation_children",
                        path,
                        heading.line,
                        "文档关系 cannot contain H3 groups",
                        target="relation",
                    )
                )
    for record in facts.records:
        permitted = RECORD_PARENT_SECTIONS.get(record.kind)
        if permitted and record.parent_section not in permitted:
            diagnostics.append(
                Diagnostic(
                    "record.parent_invalid",
                    path,
                    record.line,
                    f"{record.record_id} is not allowed under {record.parent_section}",
                    target=record.record_id,
                )
            )
        if not record.parent_group:
            diagnostics.append(
                Diagnostic(
                    "record.group_missing",
                    path,
                    record.line,
                    f"{record.record_id} must be inside an H3 record group",
                    target=record.record_id,
                )
            )
        required_fields = REQUIRED_FIELDS.get(record.kind, ())
        if record.kind == "REQ" and record.status != "TODO":
            required_fields = ()
        for choices in required_fields:
            if not any(record.fields.get(choice, "").strip() for choice in choices):
                diagnostics.append(
                    Diagnostic(
                        "record.missing_field",
                        path,
                        record.line,
                        f"{record.record_id} missing field: {'/'.join(choices)}",
                        target=record.record_id,
                    )
                )
        if record.kind == "REQ":
            annotations = re.findall(
                r"\[([A-Z0-9]+)\]", record.markdown.splitlines()[0]
            )
            states = [item for item in annotations if not re.fullmatch(r"P[0-3]", item)]
            priorities = [item for item in annotations if re.fullmatch(r"P[0-3]", item)]
            if (
                any(
                    item in {"WIP", "DEF"} or item not in {"BLK", "REJ", "DONE"}
                    for item in states
                )
                or len(states) > 1
            ):
                diagnostics.append(
                    Diagnostic(
                        "status.invalid",
                        path,
                        record.line,
                        f"invalid requirement status: {','.join(states)}",
                        target=record.record_id,
                    )
                )
            if record.status == "TODO" and len(priorities) != 1:
                diagnostics.append(
                    Diagnostic(
                        "priority.invalid",
                        path,
                        record.line,
                        f"TODO requirement requires exactly one P0-P3: {record.record_id}",
                        target=record.record_id,
                    )
                )
            evidence = {
                "BLK": (("占用", "占用者", "Issue"), ("阻塞原因",), ("释放条件",)),
                "REJ": (("原因", "拒绝原因"),),
                "DONE": (("实现路径", "版本", "测试证据"),),
            }
            for choices in evidence.get(record.status, ()):
                if not any(choice in record.fields for choice in choices):
                    diagnostics.append(
                        Diagnostic(
                            "status.evidence_missing",
                            path,
                            record.line,
                            f"{record.record_id} missing status evidence: {'/'.join(choices)}",
                            target=record.record_id,
                        )
                    )
        if record.kind == "EXT":
            if record.fields.get("父节", "") != record.parent_section:
                diagnostics.append(
                    Diagnostic(
                        "extension.parent_mismatch",
                        path,
                        record.line,
                        f"{record.record_id} declares a different parent section",
                        target=record.record_id,
                    )
                )
            if record.fields.get("结构类型") not in EXTENSION_STRUCTURES:
                diagnostics.append(
                    Diagnostic(
                        "extension.structure_invalid",
                        path,
                        record.line,
                        f"unsupported EXT structure: {record.fields.get('结构类型', '')}",
                        target=record.record_id,
                    )
                )
    groups: dict[tuple[str, str], set[str]] = {}
    for record in facts.records:
        if record.parent_group:
            groups.setdefault((record.parent_section, record.parent_group), set()).add(
                record.kind
            )
    for (section, group), kinds in groups.items():
        if len(kinds) > 1 and "EXT" not in kinds:
            record = next(
                item
                for item in facts.records
                if item.parent_section == section and item.parent_group == group
            )
            diagnostics.append(
                Diagnostic(
                    "record.group_mixed",
                    path,
                    record.line,
                    f"record group {group} mixes prefixes: {', '.join(sorted(kinds))}",
                )
            )
        same_group = [
            item
            for item in facts.records
            if item.parent_section == section
            and item.parent_group == group
            and item.kind != "EXT"
        ]
        if len(same_group) > 1:
            expected = set(same_group[0].fields)
            for record in same_group[1:]:
                if set(record.fields) != expected:
                    diagnostics.append(
                        Diagnostic(
                            "record.shape_mismatch",
                            path,
                            record.line,
                            f"{record.record_id} fields differ from sibling {same_group[0].record_id}",
                            target=record.record_id,
                        )
                    )
    return diagnostics


def inspect_document(path: Path) -> tuple[DocumentFacts | None, list[Diagnostic]]:
    path = Path(path)
    try:
        source = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        return None, [Diagnostic("document.read_error", path, 1, str(error))]
    try:
        document = parse_text(source, path)
    except (ValueError, yaml.YAMLError) as error:
        mark = getattr(error, "problem_mark", None)
        line = mark.line + 1 if mark is not None else _metadata_line(source, str(error))
        return None, [Diagnostic("metadata.invalid", path, line, str(error))]
    body, first_line = _body_from_source(source)
    headings, diagnostics = _parse_headings(
        body, first_line, document.document_type, path
    )
    records, record_diagnostics = _parse_records(body, first_line, headings, path)
    diagnostics.extend(record_diagnostics)
    relation = None
    if document.document_type is not None:
        relation, relation_diagnostics = _parse_relation(source, path)
        diagnostics.extend(relation_diagnostics)
    catalog = _catalog(body, first_line, headings, records, document.document_type)
    edges = tuple(edge for record in records for edge in _reference_edges(record))
    facts = DocumentFacts(
        path,
        document,
        relation,
        source,
        source_sha256(source),
        next((h.title for h in headings if h.level == 1), None),
        tuple(headings),
        tuple(records),
        edges,
        tuple(catalog),
    )
    if document.document_type is not None:
        diagnostics.extend(_validate_structure(facts))
    return facts, diagnostics


def _same_path(left: Path, right: Path) -> bool:
    return os.path.normcase(str(left.resolve())) == os.path.normcase(
        str(right.resolve())
    )


def _relation_root(owner: Path, owner_reference: str) -> Path | None:
    reference = Path(owner_reference.replace("/", os.sep))
    if reference.is_absolute():
        return owner.parent if _same_path(reference, owner) else None
    reference_parts = tuple(os.path.normcase(part) for part in reference.parts)
    owner_parts = owner.resolve().parts
    normalized_owner = tuple(os.path.normcase(part) for part in owner_parts)
    if (
        not reference_parts
        or len(reference_parts) > len(normalized_owner)
        or normalized_owner[-len(reference_parts) :] != reference_parts
    ):
        return None
    return Path(*owner_parts[: -len(reference_parts)])


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


def relation_path_matches(
    owner: Path, value: str, target: Path, *, owner_reference: str | None = None
) -> bool:
    return _same_path(
        resolve_relation_path(owner, value, owner_reference=owner_reference), target
    )


def _sorted_diagnostics(items: Iterable[Diagnostic]) -> tuple[Diagnostic, ...]:
    unique = {
        (
            os.path.normcase(str(item.path)),
            item.line,
            item.code,
            item.message,
            item.layer,
            item.severity,
            item.target,
        ): item
        for item in items
    }
    return tuple(
        sorted(
            unique.values(),
            key=lambda item: (
                os.path.normcase(str(item.path)),
                item.line,
                item.code,
                item.message,
            ),
        )
    )


def _local_reference_diagnostics(facts: DocumentFacts) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    index = facts.record_index
    for edge in facts.edges:
        target = index.get(edge.target_id)
        if target is None:
            if edge.target_path is None:
                diagnostics.append(
                    Diagnostic(
                        "reference.unknown",
                        facts.path,
                        edge.line,
                        f"unknown reference: {edge.source_id} -> {edge.target_id}",
                        target=edge.source_id,
                    )
                )
            continue
        source = index.get(edge.source_id)
        if source and target.kind not in ALLOWED_REFERENCES.get(source.kind, set()):
            diagnostics.append(
                Diagnostic(
                    "reference.direction",
                    facts.path,
                    edge.line,
                    f"illegal reference direction: {edge.source_id} -> {edge.target_id}",
                    target=edge.source_id,
                )
            )
    return diagnostics


def check_document(path: Path) -> CheckResult:
    facts, diagnostics = inspect_document(Path(path))
    if facts is None:
        return CheckResult((), _sorted_diagnostics(diagnostics))
    if facts.relation:
        own_reference = (
            facts.relation.requirement_path
            if facts.document.document_type == "pirc.requirement"
            else facts.relation.solution_path
        )
        if not _same_path(resolve_relation_path(facts.path, own_reference), facts.path):
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
    diagnostics.extend(_local_reference_diagnostics(facts))
    return CheckResult((facts,), _sorted_diagnostics(diagnostics))


def _record_diagnostics(
    facts: list[DocumentFacts],
) -> tuple[list[Diagnostic], dict[str, CoverageMetric]]:
    diagnostics: list[Diagnostic] = []
    records = [record for document in facts for record in document.records]
    index: dict[str, RecordFacts] = {}
    owner: dict[str, Path] = {}
    for document in facts:
        for record in document.records:
            if record.record_id in index:
                diagnostics.append(
                    Diagnostic(
                        "record.duplicate_id",
                        document.path,
                        record.line,
                        f"duplicate record ID across pair: {record.record_id}",
                        target=record.record_id,
                    )
                )
            else:
                index[record.record_id], owner[record.record_id] = record, document.path
    for record in records:
        allowed = ALLOWED_REFERENCES.get(record.kind, set())
        for target_id in record.references:
            target = index.get(target_id)
            if target is None:
                diagnostics.append(
                    Diagnostic(
                        "reference.unknown",
                        owner.get(record.record_id, facts[0].path),
                        record.line,
                        f"unknown reference: {record.record_id} -> {target_id}",
                        target=record.record_id,
                    )
                )
            elif target.kind not in allowed:
                diagnostics.append(
                    Diagnostic(
                        "reference.direction",
                        owner[record.record_id],
                        record.line,
                        f"illegal reference direction: {record.record_id} -> {target_id}",
                        target=record.record_id,
                    )
                )
            elif (
                record.kind == "SOL"
                and target.kind == "REQ"
                and (target.status != "TODO" or target.priority != "P0")
            ):
                diagnostics.append(
                    Diagnostic(
                        "scope.non_current_reference",
                        owner[record.record_id],
                        record.line,
                        f"solution references non-current requirement: {record.record_id} -> {target_id}",
                        target=record.record_id,
                    )
                )
    required_targets = {
        "AC": {"REQ"},
        "SOL": {"REQ", "TEST"},
        "TEST": {"REQ", "SOL"},
        "NFR": {"REQ", "AC"},
        "SEC": {"REQ", "AC"},
        "STATE": {"REQ", "AC"},
        "MIG": {"REQ", "SOL", "TEST"},
        "OBS": {"REQ", "SOL", "TEST"},
        "RES": {"REQ", "SOL", "TEST"},
        "CAP": {"REQ", "SOL", "TEST"},
        "LIFE": {"SOL", "TEST"},
    }
    for record in records:
        actual = {index[target].kind for target in record.references if target in index}
        missing = required_targets.get(record.kind, set()) - actual
        if missing:
            diagnostics.append(
                Diagnostic(
                    "reference.required",
                    owner[record.record_id],
                    record.line,
                    f"{record.record_id} requires explicit references to: {', '.join(sorted(missing))}",
                    target=record.record_id,
                )
            )
        if record.kind == "EXT" and not actual.intersection(ALLOWED_REFERENCES["EXT"]):
            diagnostics.append(
                Diagnostic(
                    "reference.required",
                    owner[record.record_id],
                    record.line,
                    f"{record.record_id} requires an explicit related record ID",
                    target=record.record_id,
                )
            )
    backlink_pairs = {("SOL", "TEST"), ("TEST", "SOL")}
    reported_backlinks: set[tuple[str, str]] = set()
    for record in records:
        for target_id in record.references:
            target = index.get(target_id)
            if target is None or (record.kind, target.kind) not in backlink_pairs:
                continue
            pair = tuple(sorted((record.record_id, target_id)))
            if (
                record.record_id not in target.references
                and pair not in reported_backlinks
            ):
                diagnostics.append(
                    Diagnostic(
                        "reference.backlink_missing",
                        owner[record.record_id],
                        record.line,
                        f"missing backlink for {record.record_id} -> {target_id}",
                        target=record.record_id,
                    )
                )
                reported_backlinks.add(pair)
    for document in facts:
        for edge in document.edges:
            target_path = owner.get(edge.target_id)
            if target_path is None:
                continue
            crosses_document = not _same_path(document.path, target_path)
            if crosses_document and not edge.target_path:
                diagnostics.append(
                    Diagnostic(
                        "reference.cross_document_path_missing",
                        document.path,
                        edge.line,
                        f"cross-document reference requires path#ID: {edge.source_id} -> {edge.target_id}",
                        target=edge.source_id,
                    )
                )
            elif edge.target_path:
                resolved = resolve_relation_path(document.path, edge.target_path)
                if not _same_path(resolved, target_path):
                    diagnostics.append(
                        Diagnostic(
                            "reference.path_mismatch",
                            document.path,
                            edge.line,
                            f"reference path does not contain {edge.target_id}: {edge.target_path}",
                            target=edge.source_id,
                        )
                    )
    requirements = [
        record
        for record in records
        if record.kind == "REQ" and record.status == "TODO" and record.priority == "P0"
    ]
    ac_count = sol_count = test_count = 0
    for requirement in requirements:
        req_id = requirement.record_id
        valid_ac = {
            target
            for target in requirement.references
            if target.startswith("AC-")
            and target in index
            and req_id in index[target].references
        }
        if valid_ac:
            ac_count += 1
        else:
            diagnostics.append(
                Diagnostic(
                    "coverage.ac_missing",
                    owner[req_id],
                    requirement.line,
                    f"missing REQ/AC backlink closure for {req_id}",
                    target=req_id,
                )
            )
        solutions = [
            record
            for record in records
            if record.kind == "SOL" and req_id in record.references
        ]
        if solutions:
            sol_count += 1
        else:
            diagnostics.append(
                Diagnostic(
                    "coverage.solution_missing",
                    owner[req_id],
                    requirement.line,
                    f"missing SOL coverage for {req_id}",
                    target=req_id,
                )
            )
        closed = any(
            index.get(target)
            and index[target].kind == "TEST"
            and req_id in index[target].references
            and solution.record_id in index[target].references
            for solution in solutions
            for target in solution.references
        )
        if closed:
            test_count += 1
        else:
            diagnostics.append(
                Diagnostic(
                    "coverage.test_missing",
                    owner[req_id],
                    requirement.line,
                    f"missing SOL/TEST closure for {req_id}",
                    target=req_id,
                )
            )
    total = len(requirements)

    def metric(count: int) -> CoverageMetric:
        return CoverageMetric(
            count, total, None if total == 0 else round(count * 100.0 / total, 2)
        )

    return diagnostics, {
        "ac": metric(ac_count),
        "solution": metric(sol_count),
        "test": metric(test_count),
    }


def check_pair(
    requirement_path: Path, solution_path: Path | None = None
) -> CheckResult:
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
        return CheckResult(tuple(facts), _sorted_diagnostics(diagnostics))
    requirement = facts[0]
    if requirement.relation is None:
        return CheckResult(tuple(facts), _sorted_diagnostics(diagnostics))
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
        return CheckResult(tuple(facts), _sorted_diagnostics(diagnostics))
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
        return CheckResult(tuple(facts), _sorted_diagnostics(diagnostics))
    if solution.relation:
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
    record_diagnostics, coverage = _record_diagnostics(facts)
    diagnostics.extend(record_diagnostics)
    return CheckResult(tuple(facts), _sorted_diagnostics(diagnostics), coverage)


def _json_value(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value.resolve())
    if is_dataclass(value):
        return {key: _json_value(item) for key, item in asdict(value).items()}
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_json_value(item) for item in value]
    return value


def check_result_dict(result: CheckResult) -> dict[str, Any]:
    coverage: dict[str, Any] = {}
    for key, value in result.coverage.items():
        if value.total == 0:
            coverage[key] = {
                "covered": value.covered,
                "total": 0,
                "not_applicable": True,
            }
        else:
            coverage[key] = _json_value(value)
    return {
        "format_version": FORMAT_VERSION,
        "status": result.status,
        "documents": [
            {
                "path": str(item.path.resolve()),
                "type": item.document.document_type,
                "sha256": item.sha256,
            }
            for item in result.facts
        ],
        "coverage": coverage,
        "diagnostics": [_json_value(item) for item in result.diagnostics],
    }


def catalog_document(path: Path) -> dict[str, Any]:
    facts, diagnostics = inspect_document(path)
    if facts is None:
        raise ValueError(diagnostics[0].message)
    return {
        "format_version": FORMAT_VERSION,
        "path": str(facts.path.resolve()),
        "sha256": facts.sha256,
        "document_type": facts.document.document_type,
        "entries": [
            {**_json_value(item), "type": item.entry_type} for item in facts.catalog
        ],
        "diagnostics": [_json_value(item) for item in _sorted_diagnostics(diagnostics)],
    }


def _find_heading(facts: DocumentFacts, key: str) -> HeadingFacts | None:
    return next(
        (item for item in facts.headings if item.level in {2, 3} and item.key == key),
        None,
    )


def extract_document(
    path: Path,
    *,
    section: str | None = None,
    record_id: str | None = None,
    profile: str = "audit",
) -> dict[str, Any]:
    if profile not in {"focus", "audit", "full"}:
        raise ValueError("profile must be focus, audit, or full")
    if (section is None) == (record_id is None):
        raise ValueError("select exactly one section or record ID")
    facts, diagnostics = inspect_document(path)
    if facts is None:
        raise ValueError(diagnostics[0].message)
    body, first_line = _body_from_source(facts.source)
    record = facts.record_index.get(record_id or "")
    heading = _find_heading(facts, section or "")
    if record_id and record is None:
        raise ValueError(f"unknown record ID: {record_id}")
    if section and heading is None:
        raise ValueError(f"unknown section key: {section}")
    selected = record or heading
    assert selected is not None
    markdown = record.markdown if record else _section_slice(body, first_line, heading)
    references = (
        list(record.references)
        if record
        else [
            item.record_id
            for item in facts.records
            if selected.line <= item.line <= selected.end_line
        ]
    )
    section_key = section
    if record:
        section_heading = next(
            (
                item
                for item in facts.headings
                if item.level == 2 and item.title == record.parent_section
            ),
            None,
        )
        section_key = section_heading.key if section_heading else None
    result: dict[str, Any] = {
        "format_version": FORMAT_VERSION,
        "source_path": str(facts.path.resolve()),
        "source_sha256": facts.sha256,
        "selector": record_id or section,
        "section_key": section_key,
        "record_id": record_id,
        "profile": profile,
        "range": {"line_start": selected.line, "line_end": selected.end_line},
        "references": references,
        "markdown": markdown,
    }
    if profile == "focus":
        if record:
            result["markdown"] = (
                f"#### {record.record_id} {record.title}\n"
                + "\n".join(f"- {key}：{value}" for key, value in record.fields.items())
                + "\n"
            )
        return result
    pair_result: CheckResult | None = None
    if profile == "audit" and facts.document.document_type == "pirc.requirement":
        pair_result = check_pair(facts.path)
    elif (
        profile == "audit"
        and facts.document.document_type == "pirc.solution"
        and facts.relation
    ):
        requirement_path = resolve_relation_path(
            facts.path,
            facts.relation.requirement_path,
            owner_reference=facts.relation.solution_path,
        )
        pair_result = check_pair(requirement_path, facts.path)
    available_facts = (
        pair_result.facts if pair_result and pair_result.facts else (facts,)
    )
    available_records = [
        item for document in available_facts for item in document.records
    ]
    record_paths = {
        item.record_id: str(document.path.resolve())
        for document in available_facts
        for item in document.records
    }
    related_ids = set(references)
    if record:
        related_ids.update(
            item.record_id
            for item in available_records
            if record.record_id in item.references
        )
    result.update(
        {
            "related_records": [
                {
                    "id": item.record_id,
                    "kind": item.kind,
                    "path": record_paths[item.record_id],
                    "line": item.line,
                    "references": list(item.references),
                    "markdown": item.markdown,
                }
                for item in available_records
                if item.record_id in related_ids
            ],
            "edges": [
                _json_value(item)
                for document in available_facts
                for item in document.edges
                if item.source_id == record_id or item.target_id == record_id
            ],
            "coverage": check_result_dict(pair_result)["coverage"]
            if pair_result
            else {},
            "diagnostics": [
                _json_value(item)
                for item in (
                    pair_result.diagnostics
                    if pair_result
                    else _sorted_diagnostics(diagnostics)
                )
            ],
        }
    )
    if profile == "full":
        result.update(
            {
                "raw_markdown": markdown,
                "fields": dict(record.fields) if record else {},
                "catalog": [
                    _json_value(item)
                    for item in facts.catalog
                    if selected.line <= item.line_start <= selected.end_line
                ],
            }
        )
    return result


def context_for_requirement(
    requirement_path: Path, solution_path: Path, requirement_id: str
) -> dict[str, Any]:
    result = check_pair(requirement_path, solution_path)
    if result.status != "PASS":
        raise ValueError("cannot build context from a blocked document pair")
    index = {
        record.record_id: record for facts in result.facts for record in facts.records
    }
    requirement = index.get(requirement_id)
    if requirement is None or requirement.kind != "REQ":
        raise ValueError(f"unknown requirement ID: {requirement_id}")
    selected = {requirement_id, *requirement.references}
    selected.update(
        record.record_id
        for record in index.values()
        if requirement_id in record.references
    )
    for solution in (
        record
        for record in index.values()
        if record.kind == "SOL" and requirement_id in record.references
    ):
        selected.add(solution.record_id)
        selected.update(
            target for target in solution.references if target.startswith("TEST-")
        )
    ordered = [
        record
        for facts in result.facts
        for record in facts.records
        if record.record_id in selected
        and (record.kind != "REQ" or record.record_id == requirement_id)
    ]
    return {
        "format_version": FORMAT_VERSION,
        "requirement_id": requirement_id,
        "source_sha256": {
            str(facts.path.resolve()): facts.sha256 for facts in result.facts
        },
        "record_ids": [record.record_id for record in ordered],
        "records": [
            {
                "id": record.record_id,
                "path": str(
                    next(
                        facts.path.resolve()
                        for facts in result.facts
                        if record.record_id in facts.record_index
                    )
                ),
                "line": record.line,
                "markdown": record.markdown,
            }
            for record in ordered
        ],
        "diagnostics": [],
    }


def _validate_external_result(
    data: dict[str, Any], layer: str, hashes: dict[str, str], valid_targets: set[str]
) -> list[dict[str, Any]]:
    statuses = AGENT_STATUSES if layer == "AGENT" else HUMAN_STATUSES
    status = data.get("status")
    if (
        data.get("layer") != layer
        or not isinstance(status, str)
        or status not in statuses
    ):
        raise ValueError(f"{layer} result has an invalid layer or status")
    if not isinstance(data.get("owner"), str) or not data["owner"].strip():
        raise ValueError(f"{layer} result requires owner")
    if data.get("source_sha256") != hashes:
        raise ValueError(f"{layer} result source_sha256 is stale or incomplete")
    findings = data.get("findings", [])
    if not isinstance(findings, list):
        raise ValueError("findings must be a list")
    for finding in findings:
        if not isinstance(finding, dict):
            raise ValueError("each finding must be an object")
        required_strings = {
            "layer",
            "owner",
            "severity",
            "target",
            "reason",
            "evidence",
            "suggestion",
            "disposition",
        }
        missing = sorted(
            key
            for key in required_strings
            if not isinstance(finding.get(key), str) or not finding[key].strip()
        )
        if finding.get("source_sha256") in (None, ""):
            missing.append("source_sha256")
        if missing:
            raise ValueError(f"finding missing fields: {', '.join(missing)}")
        if finding["layer"] != layer:
            raise ValueError(f"finding layer must be {layer}")
        if finding["source_sha256"] != hashes:
            raise ValueError("finding source_sha256 is stale or incomplete")
        disposition = finding["disposition"]
        if disposition not in DISPOSITIONS:
            raise ValueError(f"invalid finding disposition: {disposition}")
        if finding.get("target") not in valid_targets:
            raise ValueError(f"finding target does not exist: {finding.get('target')}")
        if disposition == "REJECTED" and not finding.get("reason"):
            raise ValueError("REJECTED finding requires reason")
        if disposition == "RESOLVED" and (
            not finding.get("result_sha256") or not finding.get("review_result")
        ):
            raise ValueError(
                "RESOLVED finding requires result_sha256 and review_result"
            )
        if disposition == "ACCEPTED" and (
            not finding.get("acceptance_check")
            or not (finding.get("assignee") or finding.get("owner"))
        ):
            raise ValueError("ACCEPTED finding requires acceptance_check and assignee")
    return findings


def review_documents(
    requirement_path: Path,
    *,
    solution_path: Path | None = None,
    scope: str | None = None,
    profile: str = "audit",
    agent_result: dict[str, Any] | None = None,
    human_result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    result = check_pair(requirement_path, solution_path)
    hashes = {str(facts.path.resolve()): facts.sha256 for facts in result.facts}
    report: dict[str, Any] = {
        "format_version": FORMAT_VERSION,
        "auto": check_result_dict(result),
        "source_sha256": hashes,
        "scope": scope,
        "profile": profile,
        "agent_status": None,
        "human_status": None,
        "overall_status": "BLOCKED" if result.status == "BLOCKED" else "PENDING_AGENT",
        "layers": {
            "AUTO": {"required": True, "status": result.status, "owner": "doc_guard"},
            "AGENT": {"required": True, "status": None, "owner": None},
            "HUMAN": {"required": True, "status": None, "owner": None},
        },
        "findings": [],
        "change_items": [],
        "review_package": None,
    }
    if result.status == "BLOCKED":
        return report
    valid_targets = {entry.key for facts in result.facts for entry in facts.catalog} | {
        record.record_id for facts in result.facts for record in facts.records
    }
    if scope and scope not in valid_targets:
        raise ValueError(f"review scope does not exist: {scope}")
    package: dict[str, Any] = {
        "source_sha256": hashes,
        "scope": scope,
        "profile": profile,
        "required_layers": ["AUTO", "AGENT", "HUMAN"],
        "catalog": {
            str(facts.path.resolve()): [_json_value(item) for item in facts.catalog]
            for facts in result.facts
        },
        "extraction": None,
    }
    if scope:
        owner_facts = next(
            facts
            for facts in result.facts
            if scope in facts.record_index
            or any(item.key == scope for item in facts.catalog)
        )
        package["extraction"] = extract_document(
            owner_facts.path,
            record_id=scope if scope in owner_facts.record_index else None,
            section=None if scope in owner_facts.record_index else scope,
            profile=profile,
        )
    report["review_package"] = package
    findings: list[dict[str, Any]] = []
    if agent_result is not None:
        findings.extend(
            _validate_external_result(agent_result, "AGENT", hashes, valid_targets)
        )
        report["agent_status"] = agent_result["status"]
        report["layers"]["AGENT"] = {
            "required": True,
            "status": agent_result["status"],
            "owner": agent_result.get("owner"),
        }
        report["overall_status"] = (
            "NEEDS_CHANGE"
            if agent_result["status"] == "NEEDS_CHANGE"
            else "PENDING_HUMAN"
        )
    if human_result is not None:
        if agent_result is None or agent_result.get("status") == "NEEDS_CHANGE":
            raise ValueError("HUMAN result requires a non-blocking AGENT result")
        findings.extend(
            _validate_external_result(human_result, "HUMAN", hashes, valid_targets)
        )
        report["human_status"], report["overall_status"] = (
            human_result["status"],
            human_result["status"],
        )
        report["layers"]["HUMAN"] = {
            "required": True,
            "status": human_result["status"],
            "owner": human_result.get("owner"),
        }
    report["findings"] = findings
    report["change_items"] = [
        {
            "finding": index,
            "target": finding["target"],
            "reason": finding["reason"],
            "expected_change": finding.get("suggestion", ""),
            "acceptance_check": finding.get("acceptance_check", ""),
            "owner": finding.get("assignee") or finding.get("owner", ""),
        }
        for index, finding in enumerate(findings, 1)
        if finding.get("disposition", "OPEN") == "ACCEPTED"
    ]
    return report
