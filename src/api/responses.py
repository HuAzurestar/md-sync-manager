"""Shared HTTP response envelopes."""


def success(data: object) -> dict[str, object | None]:
    return {"status": "success", "data": data, "error": None}


def failure(message: str) -> dict[str, object | None]:
    return {"status": "error", "data": None, "error": {"message": message}}
