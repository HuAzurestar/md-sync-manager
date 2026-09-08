"""Command-line entry point for PIRC Markdown generation and checking."""

import argparse
import os
from pathlib import Path
import re
import sys

from src.core.doc_standard import (
    CheckResult,
    check_document,
    check_pair,
    relation_path_matches,
)


TEMPLATE_ROOT = Path(__file__).resolve().parents[2] / "templates" / "docs"
ISSUE_PATTERN = re.compile(r"\b(PIRC-\d+)\b", re.IGNORECASE)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate or check PIRC Markdown")
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
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as target:
        target.write(content)


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
        raise ValueError("requirement must pass its single-document relation check")
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
    lines = [result.status]
    lines.extend(
        f"{diagnostic.code} {diagnostic.path.name}:{diagnostic.line} {diagnostic.message}"
        for diagnostic in result.diagnostics
    )
    return "\n".join(lines)


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

    if args.document and args.requirement:
        raise ValueError("use either positional document or --requirement")
    requirement = args.requirement or args.document
    if requirement is None:
        raise ValueError("check requires a requirement document")
    result = check_pair(requirement, args.solution)
    print(format_result(result))
    return 0 if result.status == "PASS" else 1


def main() -> None:
    configure_console_encoding()
    try:
        raise SystemExit(run())
    except (OSError, UnicodeError, ValueError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(2) from error


if __name__ == "__main__":
    main()
