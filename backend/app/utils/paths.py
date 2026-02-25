from __future__ import annotations

from pathlib import Path

from app.core.errors import AppError


ALLOWED_SUFFIXES = {".txt", ".md"}


def validate_relative_file_path(path_str: str) -> Path:
    path = Path(path_str)
    if path.is_absolute() or ".." in path.parts:
        raise AppError("INVALID_FILE_PATH", "File path must be relative and must not contain traversal segments.", status_code=400)

    if path.suffix.lower() not in ALLOWED_SUFFIXES:
        raise AppError("INVALID_FILE_PATH", "Only .txt and .md files are allowed.", status_code=400)

    if not path.parts:
        raise AppError("INVALID_FILE_PATH", "Path cannot be empty.", status_code=400)

    return path


def safe_join(root: Path, relative: Path) -> Path:
    target = (root / relative).resolve()
    root_resolved = root.resolve()
    if not str(target).startswith(str(root_resolved)):
        raise AppError("INVALID_FILE_PATH", "Resolved path escapes node merged directory.", status_code=400)
    return target
