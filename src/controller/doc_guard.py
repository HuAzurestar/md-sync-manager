"""Command-line entry point for the PIRC Markdown document standard."""

import argparse
import json
import os
from pathlib import Path
import re
import sys
import tempfile
from typing import Any

from src.core.doc_standard import (
    CheckResult,
    FORMAT_VERSION,
    catalog_document,
    check_document,
    check_pair,
    check_result_dict,
    context_for_requirement,
    extract_document,
    relation_path_matches,
    review_documents,
)
from src.core.document import parse_file


TEMPLATE_ROOT = Path(__file__).resolve().parents[2] / "templates" / "docs"
ISSUE_PATTERN = re.compile(r"\b(PIRC-\d+)\b", re.IGNORECASE)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate, inspect, or review PIRC Markdown"
    )
    commands = parser.add_subparsers(dest="command", required=True)

    init = commands.add_parser("init", help="create a standard document skeleton")
    document_types = init.add_subparsers(dest="document_type", required=True)
    requirement = document_types.add_parser("requirement")
    requirement.add_argument("output", type=Path)
    solution = document_types.add_parser("solution")
    solution.add_argument("output", type=Path)
    solution.add_argument("--requirement", required=True, type=Path)

    check = commands.add_parser("check", help="check a requirement or document pair")
    check.add_argument("document", nargs="?", type=Path)
    check.add_argument("--requirement", type=Path)
    check.add_argument("--solution", type=Path)
    check.add_argument("--format", choices=("text", "json"), default="text")

    context = commands.add_parser(
        "context", help="build the minimum trace context for a requirement"
    )
    context.add_argument("--requirement", required=True, type=Path)
    context.add_argument("--solution", required=True, type=Path)
    context.add_argument("--requirement-id", required=True)
    context.add_argument("--format", choices=("markdown", "json"), default="markdown")

    catalog = commands.add_parser(
        "catalog", help="list addressable sections and records"
    )
    catalog.add_argument("document", type=Path)
    catalog.add_argument("--format", choices=("text", "json"), default="text")

    extract = commands.add_parser("extract", help="extract one section or record")
    extract.add_argument("document", type=Path)
    selector = extract.add_mutually_exclusive_group(required=True)
    selector.add_argument("--section")
    selector.add_argument("--id", dest="record_id")
    extract.add_argument(
        "--profile", choices=("focus", "audit", "full"), default="audit"
    )
    extract.add_argument("--format", choices=("markdown", "json"), default="markdown")

    review = commands.add_parser(
        "review", help="orchestrate AUTO, AGENT, and HUMAN review results"
    )
    review.add_argument("requirement", type=Path)
    review.add_argument("--scope")
    review.add_argument(
        "--profile", choices=("focus", "audit", "full"), default="audit"
    )
    review.add_argument("--agent-result", type=Path)
    review.add_argument("--human-result", type=Path)
    review.add_argument("--format", choices=("text", "json"), default="text")
    return parser


def _relative_path(target: Path, owner: Path) -> str:
    return Path(os.path.relpath(target, owner.parent)).as_posix()


def _issue_from_path(path: Path) -> str:
    match = ISSUE_PATTERN.search(path.stem)
    if not match:
        raise ValueError("output filename must contain a PIRC issue ID")
    return match.group(1).upper()


def _solution_path_for(requirement: Path) -> Path:
    if "需求分析" in requirement.stem:
        return requirement.with_name(requirement.name.replace("需求分析", "方案设计"))
    return requirement.with_name(f"{requirement.stem} 方案设计.md")


def _render_template(name: str, values: dict[str, str]) -> str:
    template = (TEMPLATE_ROOT / name).read_text(encoding="utf-8")
    for key, value in values.items():
        template = template.replace("{{" + key + "}}", value)
    return template


def _create(path: Path, content: str) -> None:
    """Validate and atomically publish a newly generated document."""

    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise FileExistsError(path)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary = Path(temporary_name)
    try:
        stream = os.fdopen(descriptor, "w", encoding="utf-8", newline="\n")
    except BaseException:
        try:
            os.close(descriptor)
        except OSError:
            pass
        temporary.unlink(missing_ok=True)
        raise
    try:
        with stream as target:
            target.write(content)
            target.flush()
            os.fsync(target.fileno())
        parse_file(temporary)
        os.link(temporary, path)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise
    try:
        temporary.unlink()
    except OSError:
        temporary.unlink(missing_ok=True)


def init_requirement(output: Path) -> None:
    output = Path(output)
    solution = _solution_path_for(output)
    content = _render_template(
        "requirement-analysis.md",
        {
            "TITLE": output.stem,
            "ISSUE_ID": _issue_from_path(output),
            "REQUIREMENT_PATH": output.name,
            "SOLUTION_PATH": _relative_path(solution, output),
        },
    )
    _create(output, content)


def init_solution(output: Path, requirement_path: Path) -> None:
    output = Path(output)
    requirement_path = Path(requirement_path)
    result = check_document(requirement_path)
    if result.status != "PASS" or not result.facts or not result.facts[0].relation:
        raise ValueError("requirement must pass its single-document check")
    requirement = result.facts[0]
    if not relation_path_matches(
        requirement.path,
        requirement.relation.solution_path,
        output,
        owner_reference=requirement.relation.requirement_path,
    ):
        raise ValueError("solution output does not match the requirement relation")
    content = _render_template(
        "solution-design.md",
        {
            "TITLE": output.stem,
            "ISSUE_ID": requirement.relation.issue,
            "REQUIREMENT_PATH": _relative_path(requirement.path, output),
            "SOLUTION_PATH": output.name,
        },
    )
    _create(output, content)


def format_result(result: CheckResult) -> str:
    lines = [result.status, f"format_version {FORMAT_VERSION}"]
    lines.extend(
        f"document {facts.path.resolve()} {facts.document.document_type} sha256={facts.sha256}"
        for facts in result.facts
    )
    lines.extend(
        f"{diagnostic.code} {diagnostic.path.name}:{diagnostic.line} {diagnostic.message}"
        for diagnostic in result.diagnostics
    )
    for name, metric in result.coverage.items():
        percent = "N/A" if metric.percent is None else f"{metric.percent:.1f}%"
        lines.append(f"coverage.{name} {metric.covered}/{metric.total} ({percent})")
    return "\n".join(lines)


def _json_output(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2)


def _markdown_bundle(value: dict[str, Any]) -> str:
    identity_keys = (
        "source_path",
        "source_sha256",
        "selector",
        "section_key",
        "record_id",
        "requirement_id",
        "profile",
        "range",
    )
    identity = [
        f"{key}: {json.dumps(value[key], ensure_ascii=False, sort_keys=True)}"
        for key in identity_keys
        if key in value
    ]
    header = "<!--\n" + "\n".join(identity) + "\n-->"
    if "markdown" in value:
        return f"{header}\n\n{str(value['markdown']).rstrip()}"
    records = value.get("records", [])
    return "\n\n".join([header, *(str(item["markdown"]).rstrip() for item in records)])


def _load_result(path: Path | None) -> dict[str, Any] | None:
    if path is None:
        return None
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"review result must be a JSON object: {path}")
    return value


def configure_console_encoding() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure:
            reconfigure(encoding="utf-8")


def run(arguments: list[str] | None = None) -> int:
    args = build_parser().parse_args(arguments)
    if args.command == "init":
        if args.document_type == "requirement":
            init_requirement(args.output)
        else:
            init_solution(args.output, args.requirement)
        print(args.output)
        return 0

    if args.command == "check":
        if args.document and args.requirement:
            raise ValueError("use either positional document or --requirement")
        requirement = args.requirement or args.document
        if requirement is None:
            raise ValueError("check requires a requirement document")
        result = check_pair(requirement, args.solution)
        print(
            _json_output(check_result_dict(result))
            if args.format == "json"
            else format_result(result)
        )
        return 0 if result.status == "PASS" else 1

    if args.command == "catalog":
        result = catalog_document(args.document)
        if args.format == "json":
            print(_json_output(result))
        else:
            lines = [
                f"format_version {result['format_version']}",
                f"document {result['path']} sha256={result['sha256']}",
            ]
            lines.extend(
                f"{item['key']}\t{item['type']}\t{item['line_start']}-{item['line_end']}\t{item['byte_count']} bytes"
                for item in result["entries"]
            )
            print("\n".join(lines))
        return 0

    if args.command == "extract":
        result = extract_document(
            args.document,
            section=args.section,
            record_id=args.record_id,
            profile=args.profile,
        )
        print(
            _json_output(result) if args.format == "json" else _markdown_bundle(result)
        )
        return 0

    if args.command == "context":
        result = context_for_requirement(
            args.requirement, args.solution, args.requirement_id
        )
        print(
            _json_output(result) if args.format == "json" else _markdown_bundle(result)
        )
        return 0

    result = review_documents(
        args.requirement,
        scope=args.scope,
        profile=args.profile,
        agent_result=_load_result(args.agent_result),
        human_result=_load_result(args.human_result),
    )
    if args.format == "json":
        print(_json_output(result))
    else:
        lines = [
            result["overall_status"],
            f"AUTO {result['auto']['status']}",
            f"AGENT {result['agent_status'] or 'PENDING'}",
            f"HUMAN {result['human_status'] or 'PENDING'}",
        ]
        lines.extend(
            f"source {path} sha256={digest}"
            for path, digest in result["source_sha256"].items()
        )
        lines.extend(
            f"finding {item['layer']} {item['severity']} {item['target']} {item['disposition']}"
            for item in result["findings"]
        )
        print("\n".join(lines))
    return 1 if result["overall_status"] == "BLOCKED" else 0


def main() -> None:
    configure_console_encoding()
    try:
        raise SystemExit(run())
    except (OSError, UnicodeError, ValueError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(2) from error


if __name__ == "__main__":
    main()
