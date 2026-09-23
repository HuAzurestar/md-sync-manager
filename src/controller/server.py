"""Run the local Markdown workbench service."""

import os

import uvicorn


DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8000


def main() -> None:
    host = os.getenv("SMMD_HOST", DEFAULT_HOST)
    port = int(os.getenv("SMMD_PORT", str(DEFAULT_PORT)))
    uvicorn.run("src.api.app:app", host=host, port=port)


if __name__ == "__main__":
    main()
