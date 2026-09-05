"""Safely fast-forward this skill package from a configured GitHub remote."""

import argparse
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse


class UpdateError(RuntimeError):
    pass


def is_github_remote(url: str) -> bool:
    value = url.strip()
    if value.casefold().startswith("git@github.com:"):
        return True
    return (urlparse(value).hostname or "").casefold() == "github.com"


def run_git(root: Path, *arguments: str) -> str:
    try:
        result = subprocess.run(
            ["git", *arguments],
            cwd=root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
    except OSError as exc:
        raise UpdateError("git executable is not available") from exc
    if result.returncode:
        command = " ".join(arguments[:2])
        raise UpdateError(f"git {command} failed")
    return result.stdout.strip()


def update(skill_path: Path, remote: str, branch: str | None, check_only: bool) -> str:
    root = skill_path.resolve()
    if not (root / "SKILL.md").is_file() or not (root / ".git").exists():
        raise UpdateError(f"not a Git-backed skill directory: {root}")

    repository_root = Path(run_git(root, "rev-parse", "--show-toplevel")).resolve()
    if repository_root != root:
        raise UpdateError("skill directory must be the root of its Git repository")
    if not is_github_remote(run_git(root, "remote", "get-url", remote)):
        raise UpdateError(f"remote {remote!r} is not hosted on github.com")
    if run_git(root, "status", "--porcelain"):
        raise UpdateError(
            "working tree is not clean; commit or stash changes before updating"
        )

    selected_branch = branch or run_git(root, "branch", "--show-current")
    if not selected_branch:
        raise UpdateError("detached HEAD requires an explicit --branch")

    run_git(root, "fetch", "--quiet", remote, selected_branch)
    local_commit = run_git(root, "rev-parse", "HEAD")
    fetched_commit = run_git(root, "rev-parse", "FETCH_HEAD")
    if local_commit == fetched_commit:
        return f"already up to date: {selected_branch}"
    if run_git(root, "merge-base", local_commit, fetched_commit) != local_commit:
        raise UpdateError("GitHub update is not a fast-forward; update manually")
    if check_only:
        return f"update available: {selected_branch} {local_commit[:8]} -> {fetched_commit[:8]}"

    run_git(root, "merge", "--ff-only", "FETCH_HEAD")
    return f"updated: {selected_branch} {local_commit[:8]} -> {fetched_commit[:8]}"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Safely update md-sync-manager from GitHub"
    )
    parser.add_argument(
        "--skill-path",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="Git-backed skill directory; defaults to this script's parent package",
    )
    parser.add_argument(
        "--remote", default="origin", help="configured GitHub remote name"
    )
    parser.add_argument(
        "--branch", help="branch to fetch; defaults to the current branch"
    )
    parser.add_argument(
        "--check", action="store_true", help="fetch and report without updating files"
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        print(update(args.skill_path, args.remote, args.branch, args.check))
        return 0
    except UpdateError as exc:
        print(f"update refused: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
