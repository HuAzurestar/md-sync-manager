"""Command-line entry point for Markdown remote operations."""

import argparse
import sys
from pathlib import Path

from src.controller.sync_controller import SyncController
from src.core.config import load_config
from src.core.logging import get_logger


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="List, pull, push, or upload Markdown content"
    )
    commands = parser.add_subparsers(dest="command", required=True)

    list_command = commands.add_parser(
        "list", help="list IDs and titles in a remote collection"
    )
    list_command.add_argument(
        "target", help="collection path, for example github/issues/owner/repo"
    )

    pull = commands.add_parser(
        "pull", help="pull a remote object into a local Markdown file"
    )
    pull.add_argument("file", type=Path)
    pull.add_argument("--from", dest="source", help="object path")

    push = commands.add_parser(
        "push", help="update the one remote bound in the Markdown file"
    )
    push.add_argument("file", type=Path)

    upload = commands.add_parser("upload", help="create and bind a new remote object")
    upload.add_argument("file", type=Path)
    upload.add_argument("--target", required=True, help="collection path")
    upload.add_argument("--parent", help="optional parent object path")
    upload.add_argument("--base", help="base branch required for Pull Request upload")
    upload.add_argument("--head", help="head branch required for Pull Request upload")
    return parser


def format_table(items) -> str:
    rows = [(str(item.object_id), item.title) for item in items]
    id_width = max([len("ID"), *(len(row[0]) for row in rows)])
    lines = [f"{'ID':<{id_width}}  TITLE", f"{'-' * id_width}  {'-' * 5}"]
    lines.extend(f"{object_id:<{id_width}}  {title}" for object_id, title in rows)
    return "\n".join(lines)


def configure_console_encoding() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure:
            reconfigure(encoding="utf-8")


def main() -> None:
    configure_console_encoding()
    args = build_parser().parse_args()
    logger = get_logger("python " + " ".join(sys.argv))
    logger.info("cli_start command=%s", args.command)

    def log_uncaught(exc_type, exc_value, exc_traceback):
        if exc_type is KeyboardInterrupt:
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        logger.error(
            "cli_error command=%s",
            args.command,
            exc_info=(exc_type, exc_value, exc_traceback),
        )

    sys.excepthook = log_uncaught
    config = load_config()
    controller = SyncController(config)
    if args.command == "list":
        print(format_table(controller.list(args.target)))
    elif args.command == "pull":
        print(controller.pull(args.file, args.source))
    elif args.command == "push":
        print(controller.push(args.file))
    else:
        print(
            controller.upload(args.file, args.target, args.parent, args.base, args.head)
        )


if __name__ == "__main__":
    main()
